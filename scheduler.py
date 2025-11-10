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
import sqlite3
import re

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor

from send_message import send_message
from gcal import find_next_event, get_event_time


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ScheduleValidationError(Exception):
    """Raised when schedule configuration is invalid"""
    pass


def send_calendar_message(db_path, event_id, message_config_id, event_start_time_iso, **kwargs):
    """
    Module-level function to send calendar-anchored message and mark as sent.
    Must be module-level to allow APScheduler to serialize it.

    Args:
        db_path: Path to scheduler database
        event_id: Google Calendar event ID
        message_config_id: Message configuration ID
        event_start_time_iso: Event start time as ISO string (for serialization)
        **kwargs: Message data to pass to send_message (channel, content, id, etc.)
    """
    from replacements import get_event_replacements

    # Parse the event start time from ISO string
    event_start_time = datetime.fromisoformat(event_start_time_iso)

    # Generate event-based replacements
    event_replacements = get_event_replacements(event_start_time)

    # Merge with existing replacements (event-based values take priority over defaults)
    # User-provided replacements will still override event-based ones
    existing_replacements = kwargs.get('replacements', {})

    # Priority: user replacements > event replacements > default replacements
    # The replace_recursive function in send_message will handle merging with defaults
    # We just need to inject our event-based replacements here
    kwargs['replacements'] = {**event_replacements, **existing_replacements}

    logger.info(f"Using event time for replacements: {event_start_time.strftime('%Y-%m-%d %I:%M %p')}")

    # Send the message (kwargs contains channel, content, id, google_doc, etc.)
    send_message(**kwargs)

    # Mark as sent in tracker
    tracker = CalendarEventTracker(db_path=db_path)
    tracker.mark_as_sent(message_config_id, event_id)
    logger.info(f"Marked calendar event {event_id} as sent")


class CalendarEventTracker:
    """Tracks calendar events to prevent duplicate message sends"""

    def __init__(self, db_path: str = 'scheduler.db'):
        """Initialize calendar event tracker with SQLite database"""
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Create the calendar events tracking table if it doesn't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS calendar_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_config_id TEXT NOT NULL,
                event_id TEXT NOT NULL,
                event_start_time TEXT NOT NULL,
                scheduled_send_time TEXT NOT NULL,
                job_id TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(message_config_id, event_id)
            )
        ''')

        conn.commit()
        conn.close()

    def is_event_scheduled(self, message_config_id: str, event_id: str) -> bool:
        """Check if a message for this event has already been scheduled/sent"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT status FROM calendar_events
            WHERE message_config_id = ? AND event_id = ?
        ''', (message_config_id, event_id))

        result = cursor.fetchone()
        conn.close()

        return result is not None and result[0] in ('scheduled', 'sent')

    def add_scheduled_event(
        self,
        message_config_id: str,
        event_id: str,
        event_start_time: datetime,
        scheduled_send_time: datetime,
        job_id: str
    ):
        """Record that a message has been scheduled for a calendar event"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        now = datetime.now().isoformat()

        cursor.execute('''
            INSERT OR REPLACE INTO calendar_events
            (message_config_id, event_id, event_start_time, scheduled_send_time,
             job_id, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'scheduled', ?, ?)
        ''', (
            message_config_id,
            event_id,
            event_start_time.isoformat(),
            scheduled_send_time.isoformat(),
            job_id,
            now,
            now
        ))

        conn.commit()
        conn.close()

    def mark_as_sent(self, message_config_id: str, event_id: str):
        """Mark a calendar event message as sent"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE calendar_events
            SET status = 'sent', updated_at = ?
            WHERE message_config_id = ? AND event_id = ?
        ''', (datetime.now().isoformat(), message_config_id, event_id))

        conn.commit()
        conn.close()

    def get_all_scheduled_calendar_messages(self) -> List[Dict[str, Any]]:
        """Get all messages that are scheduled based on calendar events"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM calendar_events
            WHERE status = 'scheduled'
        ''')

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return results


class MessageScheduler:
    def __init__(self, db_url: str = 'sqlite:///scheduler.db'):
        """
        Initialize the message scheduler with persistent storage.

        Args:
            db_url: Database URL for job persistence
        """
        # Configure job stores and executors
        # Use in-memory store for recurring system jobs (like reconciliation)
        # Use SQLite for message jobs (so they persist across restarts)
        from apscheduler.jobstores.memory import MemoryJobStore

        jobstores = {
            'default': SQLAlchemyJobStore(url=db_url),
            'memory': MemoryJobStore()  # For non-persisted jobs
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

        # Extract database path from db_url
        self.db_path = db_url.replace('sqlite:///', '')
        self.db_url = db_url
        self.calendar_tracker = CalendarEventTracker(db_path=self.db_path)

        # Store calendar-anchored message configs for reconciliation
        self.calendar_anchored_configs = []
        
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

    def parse_offset(self, offset_str: str) -> timedelta:
        """
        Parse offset string like '-2h', '-30m', '-1d' into timedelta.

        Args:
            offset_str: String like '-2h', '-30m', '-1d', '-2w'

        Returns:
            timedelta object representing the offset
        """
        # Match pattern like -2h, -30m, -1d
        match = re.match(r'^([+-]?\d+)([mhdw])$', offset_str.lower())

        if not match:
            raise ValueError(
                f"Invalid offset format: '{offset_str}'. "
                f"Use format like: -2h, -30m, -1d, -2w"
            )

        value = int(match.group(1))
        unit = match.group(2)

        if unit == 'm':
            return timedelta(minutes=value)
        elif unit == 'h':
            return timedelta(hours=value)
        elif unit == 'd':
            return timedelta(days=value)
        elif unit == 'w':
            return timedelta(weeks=value)

    def schedule_calendar_anchored_message(
        self,
        message_config_id: str,
        message_data: Dict[str, Any],
        calendar_anchor: Dict[str, Any]
    ) -> bool:
        """
        Schedule a message based on a calendar event.

        Args:
            message_config_id: Unique ID for this message configuration
            message_data: Message data to send
            calendar_anchor: Calendar anchor configuration

        Returns:
            True if scheduled successfully, False otherwise
        """
        event_name = calendar_anchor.get('event_name')
        calendar_id = calendar_anchor.get('calendar_id', 'primary')
        offset_str = calendar_anchor.get('offset', '0m')
        search_window_days = calendar_anchor.get('search_window_days', 30)

        # Find the next occurrence of the event
        event = find_next_event(
            event_name=event_name,
            calendar_id=calendar_id,
            days_ahead=search_window_days
        )

        if not event:
            logger.warning(
                f"Calendar event '{event_name}' not found in next {search_window_days} days"
            )
            return False

        event_id = event['id']

        # Check if we've already scheduled for this event
        if self.calendar_tracker.is_event_scheduled(message_config_id, event_id):
            logger.info(
                f"Message '{message_config_id}' already scheduled for event '{event_id}'"
            )
            return False

        # Get event start time and calculate send time
        event_start_time = get_event_time(event)
        offset = self.parse_offset(offset_str)
        scheduled_send_time = event_start_time + offset

        # Get current time (with timezone awareness if needed)
        now = datetime.now(scheduled_send_time.tzinfo) if scheduled_send_time.tzinfo else datetime.now()

        # Check if the event itself has already passed
        if event_start_time < now:
            logger.warning(
                f"Event '{event.get('summary')}' at {event_start_time} has already passed, skipping"
            )
            return False

        # Check if we're too late to send (based on latest_send_offset)
        latest_send_offset_str = calendar_anchor.get('latest_send_offset')
        if latest_send_offset_str:
            latest_send_offset = self.parse_offset(latest_send_offset_str)
            latest_send_time = event_start_time + latest_send_offset

            if now > latest_send_time:
                logger.warning(
                    f"Current time {now} is past the latest send time {latest_send_time}, skipping. "
                    f"(Event is at {event_start_time}, latest_send_offset: {latest_send_offset_str})"
                )
                return False

        # If scheduled send time is in the past but we're still within the send window, send immediately
        if scheduled_send_time < now:
            logger.warning(
                f"Scheduled send time {scheduled_send_time} is in the past. Sending immediately."
            )
            scheduled_send_time = now + timedelta(seconds=5)  # Send in 5 seconds

        # Create the job
        job_id = f"calendar_{message_config_id}_{event_id}"

        # Prepare kwargs for the module-level send_calendar_message function
        job_kwargs = {
            'db_path': self.db_path,
            'event_id': event_id,
            'message_config_id': message_config_id,
            'event_start_time_iso': event_start_time.isoformat(),  # Pass event time for replacements
            **message_data  # All the message data (channel, content, etc.)
        }

        self.scheduler.add_job(
            func=send_calendar_message,  # Module-level function
            trigger=DateTrigger(run_date=scheduled_send_time),
            kwargs=job_kwargs,
            id=job_id,
            replace_existing=True
        )

        # Track the scheduled event
        self.calendar_tracker.add_scheduled_event(
            message_config_id=message_config_id,
            event_id=event_id,
            event_start_time=event_start_time,
            scheduled_send_time=scheduled_send_time,
            job_id=job_id
        )

        logger.info(
            f"Scheduled '{message_config_id}' for {scheduled_send_time.strftime('%Y-%m-%d %H:%M')} "
            f"(event: {event.get('summary')} at {event_start_time.strftime('%Y-%m-%d %H:%M')})"
        )

        return True

    def reconcile_calendar_messages(self):
        """
        Reconcile calendar-anchored messages - runs every 30 minutes.
        Checks for new/updated calendar events and schedules messages accordingly.
        """
        logger.info("Running calendar message reconciliation...")

        scheduled_count = 0

        for config in self.calendar_anchored_configs:
            try:
                message_config_id = config['id']
                message_data = config['message_data']
                calendar_anchor = config['calendar_anchor']

                # Try to schedule (will skip if already scheduled)
                if self.schedule_calendar_anchored_message(
                    message_config_id,
                    message_data,
                    calendar_anchor
                ):
                    scheduled_count += 1

            except Exception as e:
                logger.error(f"Error reconciling calendar message '{config.get('id')}': {e}")

        if scheduled_count > 0:
            logger.info(f"Reconciliation complete: scheduled {scheduled_count} new messages")
        else:
            logger.info("Reconciliation complete: no new messages to schedule")

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
        # Clear existing jobs and calendar configs
        self.clear_all_jobs()
        self.calendar_anchored_configs = []


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
        calendar_count = 0

        for i, message_data in enumerate(messages):
            try:
                # Check if this is a calendar-anchored message
                calendar_anchor = message_data.pop('calendar_anchor', None)
                enabled = message_data.pop('enabled', True)

                if not enabled:
                    logger.info(f"Message {i + 1} disabled, skipping")
                    continue

                id = message_data.get('id', f'message_{i + 1}')

                if calendar_anchor:
                    # Calendar-anchored message
                    logger.info(f"Registering calendar-anchored message: {id}")

                    # Store config for reconciliation
                    self.calendar_anchored_configs.append({
                        'id': id,
                        'message_data': message_data.copy(),
                        'calendar_anchor': calendar_anchor
                    })

                    # Try to schedule immediately
                    if self.schedule_calendar_anchored_message(id, message_data, calendar_anchor):
                        calendar_count += 1

                else:
                    # Regular time-based message
                    schedule = message_data.pop('schedule', {})

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
                    job_id = f"message_{i + 1}_{id}_{hash(str(message_data))}"
                    self.scheduler.add_job(
                        func=send_message,
                        trigger=trigger,
                        kwargs=message_data,
                        id=job_id,
                        replace_existing=True
                    )

                    scheduled_count += 1
                    logger.info(f"Scheduled time-based message {i + 1}: {id}")

            except Exception as e:
                logger.error(f"Failed to schedule message {i + 1}: {e}")
                raise

        # Add the calendar reconciliation job (runs every 30 minutes)
        # Use memory jobstore so it doesn't need to be serialized
        if self.calendar_anchored_configs:
            self.scheduler.add_job(
                func=self.reconcile_calendar_messages,
                trigger=CronTrigger(minute='*/30'),
                id='calendar_reconciliation',
                jobstore='memory',  # Don't persist - will be re-added on startup
                replace_existing=True
            )
            logger.info("Added 30-minute calendar reconciliation job")

        logger.info(
            f"Successfully scheduled {scheduled_count} time-based messages "
            f"and {calendar_count} calendar-anchored messages"
        )
    
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