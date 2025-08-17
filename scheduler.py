#!/usr/bin/env python3
"""
Message Scheduler using APScheduler

Loads YAML files containing message schedules and manages them with APScheduler.
Validates schedule configurations and prevents redundant key usage.
"""

from ntpath import isdir
import yaml
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
import os

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor

from replacements import replace_recursive
from send_message import send_message


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ScheduleValidationError(Exception):
    """Raised when schedule configuration is invalid"""
    pass


class MessageScheduler:
    def __init__(self, db_url: str = 'sqlite:///scheduler.db'):
        """
        Initialize the message scheduler with persistent storage.
        
        Args:
            db_url: Database URL for job persistence
        """
        # Configure job stores and executors
        jobstores = {
            'default': SQLAlchemyJobStore(url=db_url)
        }
        executors = {
            'default': ThreadPoolExecutor(max_workers=10)
        }
        job_defaults = {
            'coalesce': True,  # Combine missed jobs
            'max_instances': 1,  # Prevent overlapping jobs
            'misfire_grace_time': 30  # Grace period for missed jobs
        }
        
        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='Europe/London'
        )
        
    def start(self):
        """Start the scheduler"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started")
    
    def stop(self):
        """Stop the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")
    
    def clear_all_jobs(self):
        """Remove all existing scheduled jobs"""
        job_count = len(self.scheduler.get_jobs())
        self.scheduler.remove_all_jobs()
        logger.info(f"Cleared {job_count} existing jobs")
    
    def load_yaml_file(self, yaml_path: str) -> Dict[str, Any]:
        """
        Load and parse YAML file.
        
        Args:
            yaml_path: Path to YAML file
            
        Returns:
            Parsed YAML data
        """
        try:
            with open(yaml_path, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
                logger.info(f"Loaded YAML file: {yaml_path}")
                return data
        except FileNotFoundError:
            raise FileNotFoundError(f"YAML file not found: {yaml_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML format: {e}")
    
    def validate_schedule(self, schedule: Dict[str, Any], message_index: int):
        """
        Validate schedule configuration and check for redundant keys.
        
        Args:
            schedule: Schedule configuration
            message_index: Index of message for error reporting
        """
        frequency = schedule.get('frequency', 'once')
        
        # Define allowed keys for each frequency
        base_keys = {'start_date', 'time', 'timezone', 'frequency', 'interval'}
        frequency_specific_keys = {
            'once': set(),
            'daily': {'end_conditions'},
            'weekly': {'days_of_week', 'end_conditions'},
            'monthly': {'day_of_month', 'week_of_month', 'day_of_week', 'end_conditions'}
        }
        
        if frequency not in frequency_specific_keys:
            raise ScheduleValidationError(
                f"Message {message_index}: Invalid frequency '{frequency}'. "
                f"Must be one of: {list(frequency_specific_keys.keys())}"
            )
        
        allowed_keys = base_keys | frequency_specific_keys[frequency]
        provided_keys = set(schedule.keys())
        redundant_keys = provided_keys - allowed_keys
        
        if redundant_keys:
            raise ScheduleValidationError(
                f"Message {message_index}: Redundant keys for frequency '{frequency}': "
                f"{sorted(redundant_keys)}. Allowed keys: {sorted(allowed_keys)}"
            )
        
        # Additional validation rules
        if frequency == 'once':
            if 'end_conditions' in schedule:
                raise ScheduleValidationError(
                    f"Message {message_index}: 'end_conditions' not allowed for 'once' frequency"
                )
            if 'interval' in schedule and schedule['interval'] != 1:
                raise ScheduleValidationError(
                    f"Message {message_index}: 'interval' not meaningful for 'once' frequency"
                )
        
        if frequency == 'weekly' and 'days_of_week' not in schedule:
            raise ScheduleValidationError(
                f"Message {message_index}: 'days_of_week' required for weekly frequency"
            )
        
        if frequency == 'monthly':
            has_day_of_month = 'day_of_month' in schedule
            has_relative_date = 'week_of_month' in schedule and 'day_of_week' in schedule
            
            if not (has_day_of_month or has_relative_date):
                raise ScheduleValidationError(
                    f"Message {message_index}: Monthly frequency requires either 'day_of_month' "
                    f"or both 'week_of_month' and 'day_of_week'"
                )
            
            if has_day_of_month and has_relative_date:
                raise ScheduleValidationError(
                    f"Message {message_index}: Cannot specify both 'day_of_month' and "
                    f"'week_of_month'+'day_of_week' for monthly frequency"
                )
        
        # Validate time format
        time_str = schedule.get('time')
        if time_str:
            try:
                datetime.strptime(time_str, '%H:%M')
            except ValueError:
                raise ScheduleValidationError(
                    f"Message {message_index}: Invalid time format '{time_str}'. Use HH:MM format"
                )
        
        # Validate date format
        start_date = schedule.get('start_date')
        if start_date:
            try:
                datetime.strptime(start_date, '%Y-%m-%d')
            except ValueError:
                raise ScheduleValidationError(
                    f"Message {message_index}: Invalid start_date format '{start_date}'. "
                    f"Use YYYY-MM-DD format"
                )
    
    def parse_end_conditions(self, end_conditions: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse end conditions into APScheduler-compatible parameters.
        
        Args:
            end_conditions: End conditions configuration
            
        Returns:
            Dictionary with end_date and max_instances for APScheduler
        """
        result = {}
        
        if 'end_date' in end_conditions:
            result['end_date'] = end_conditions['end_date']
        
        if 'max_occurrences' in end_conditions:
            # APScheduler doesn't have direct max_occurrences support
            # This would need to be handled in the job function
            result['max_instances'] = end_conditions['max_occurrences']
        
        if 'end_after_duration' in end_conditions:
            duration_str = end_conditions['end_after_duration']
            # Parse duration like "90d", "12w", "6m"
            if duration_str.endswith('d'):
                days = int(duration_str[:-1])
                end_date = date.today() + timedelta(days=days)
                result['end_date'] = end_date.isoformat()
            elif duration_str.endswith('w'):
                weeks = int(duration_str[:-1])
                end_date = date.today() + timedelta(weeks=weeks)
                result['end_date'] = end_date.isoformat()
            elif duration_str.endswith('m'):
                months = int(duration_str[:-1])
                # Approximate months as 30 days
                end_date = date.today() + timedelta(days=months * 30)
                result['end_date'] = end_date.isoformat()
        
        return result
    
    def create_trigger(self, schedule: Dict[str, Any]):
        """
        Create appropriate APScheduler trigger from schedule configuration.
        
        Args:
            schedule: Schedule configuration
            
        Returns:
            APScheduler trigger object
        """
        frequency = schedule.get('frequency', 'once')
        timezone = schedule.get('timezone', 'Europe/London')
        time_str = schedule.get('time', '00:00')
        start_date = schedule.get('start_date')
        
        # Parse time
        hour, minute = map(int, time_str.split(':'))
        
        # Handle end conditions
        end_conditions = schedule.get('end_conditions', {})
        end_params = self.parse_end_conditions(end_conditions)
        
        if frequency == 'once':
            # For one-time jobs, combine start_date and time
            if not start_date:
                raise ScheduleValidationError("'start_date' is required for 'once' frequency")
            
            run_datetime = datetime.strptime(f"{start_date} {time_str}", '%Y-%m-%d %H:%M')
            return DateTrigger(run_date=run_datetime, timezone=timezone)
        
        elif frequency == 'daily':
            trigger_kwargs = {
                'hour': hour,
                'minute': minute,
                'timezone': timezone
            }
            if start_date:
                trigger_kwargs['start_date'] = start_date
            if 'end_date' in end_params:
                trigger_kwargs['end_date'] = end_params['end_date']
            
            interval = schedule.get('interval', 1)
            if interval == 1:
                return CronTrigger(**trigger_kwargs)
            else:
                # For daily intervals > 1, we need a more complex solution
                # This is a simplified approach
                trigger_kwargs['day'] = f'*/{interval}'
                return CronTrigger(**trigger_kwargs)
        
        elif frequency == 'weekly':
            days_of_week = schedule.get('days_of_week', [])
            # Convert day names to APScheduler format
            day_mapping = {
                'monday': 'mon', 'tuesday': 'tue', 'wednesday': 'wed',
                'thursday': 'thu', 'friday': 'fri', 'saturday': 'sat', 'sunday': 'sun'
            }
            
            cron_days = ','.join([day_mapping.get(day.lower(), day) for day in days_of_week])
            
            trigger_kwargs = {
                'day_of_week': cron_days,
                'hour': hour,
                'minute': minute,
                'timezone': timezone
            }
            if start_date:
                trigger_kwargs['start_date'] = start_date
            if 'end_date' in end_params:
                trigger_kwargs['end_date'] = end_params['end_date']
            
            return CronTrigger(**trigger_kwargs)
        
        elif frequency == 'monthly':
            trigger_kwargs = {
                'hour': hour,
                'minute': minute,
                'timezone': timezone
            }
            
            if 'day_of_month' in schedule:
                trigger_kwargs['day'] = schedule['day_of_month']
            else:
                # Handle relative dates like "2nd Tuesday"
                week_of_month = schedule.get('week_of_month')
                day_of_week = schedule.get('day_of_week')
                day_mapping = {
                    'monday': 'mon', 'tuesday': 'tue', 'wednesday': 'wed',
                    'thursday': 'thu', 'friday': 'fri', 'saturday': 'sat', 'sunday': 'sun'
                }
                
                cron_day = day_mapping.get(day_of_week.lower(), day_of_week)
                trigger_kwargs['day_of_week'] = cron_day
                trigger_kwargs['day'] = f'{week_of_month}-7'  # APScheduler nth occurrence syntax
            
            if start_date:
                trigger_kwargs['start_date'] = start_date
            if 'end_date' in end_params:
                trigger_kwargs['end_date'] = end_params['end_date']
            
            return CronTrigger(**trigger_kwargs)

    
    def schedule_messages_from_yaml(self, yaml_path: str):
        """
        Load YAML file and schedule all messages.
        
        Args:
            yaml_path: Path to YAML file
        """
        # Clear existing jobs
        self.clear_all_jobs()
        

        if os.path.isdir(yaml_path):
            messages = []
            for file in os.listdir(yaml_path):
                if file.endswith('.yaml') or file.endswith('.yml'):
                    data = self.load_yaml_file(os.path.join(yaml_path, file))
                    messages = messages + data.get('messages', [])
            
        else:
            # Load and validate YAML
            data = self.load_yaml_file(yaml_path)
            messages = data.get('messages', [])
        
        if not messages:
            logger.warning("No messages found in YAML file")
            return
        
        scheduled_count = 0
        
        for i, message_data in enumerate(messages):
            try:
                schedule = message_data.pop('schedule', {})
                enabled = message_data.pop('enabled', True)
                
                # Apply defaults
                if 'frequency' not in schedule:
                    schedule['frequency'] = 'once'
                if 'timezone' not in schedule:
                    schedule['timezone'] = 'Europe/London'
                
                # Validate schedule
                self.validate_schedule(schedule, i + 1)
                
                # Create trigger
                trigger = self.create_trigger(schedule)
                
                # Schedule the job
                id = message_data.get('id', 'No_ID')
                job_id = f"message_{i + 1}_{id}_{hash(str(message_data))}"
                self.scheduler.add_job(
                    func=send_message,
                    trigger=trigger,
                    kwargs=message_data,
                    id=job_id,
                    replace_existing=True
                )
                
                scheduled_count += 1
                logger.info(f"Scheduled message {i + 1}: {id}...")
                
            except Exception as e:
                logger.error(f"Failed to schedule message {i + 1}: {e}")
                raise
        
        logger.info(f"Successfully scheduled {scheduled_count} messages")
    
    def list_jobs(self):
        """List all currently scheduled jobs"""
        jobs = self.scheduler.get_jobs()
        if not jobs:
            logger.info("No jobs currently scheduled")
            return
        
        logger.info(f"Currently scheduled jobs ({len(jobs)}):")
        for job in jobs:
            logger.info(f"  {job.id}: next run at {job.next_run_time}")


def main():
    """Example usage of the MessageScheduler"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Schedule messages from YAML file')
    parser.add_argument('--yaml_file', help='Path to YAML file containing messages, or folder of such files', default='messages/')
    parser.add_argument('--db-url', default='sqlite:///scheduler.db', 
                       help='Database URL for job persistence')
    parser.add_argument('--list-jobs', action='store_true',
                       help='List scheduled jobs and exit')
    
    args = parser.parse_args()
    
    scheduler = MessageScheduler(db_url=args.db_url)
    
    try:
        scheduler.start()

        logger.info(f"Current time {datetime.now(scheduler.scheduler.timezone)}")
        
        if args.list_jobs:
            scheduler.list_jobs()
        else:
            scheduler.schedule_messages_from_yaml(args.yaml_file)
            scheduler.list_jobs()
            
            # Keep the script running
            logger.info("Scheduler is running. Press Ctrl+C to stop.")
            import time
            while True:
                time.sleep(1)
                
    except KeyboardInterrupt:
        logger.info("Stopping scheduler...")
    except Exception as e:
        logger.error(f"Error: {e}")
        raise
    finally:
        scheduler.stop()


if __name__ == '__main__':
    main()