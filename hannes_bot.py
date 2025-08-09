#!/usr/bin/env python3
"""
HannesBot - Config-driven Slack automation for AI Safety Research Management
Reads message definitions from messages.yaml and sends appropriate messages
"""

import yaml
import requests
import os
import sys
from datetime import datetime, timedelta
import argparse

class HannesBot:
    def __init__(self):
        # Get token from environment variable (more secure for GitHub Actions)
        self.token = os.getenv('SLACK_BOT_TOKEN')
        if not self.token:
            raise ValueError("SLACK_BOT_TOKEN environment variable not set")
            
        self.base_url = "https://slack.com/api"
        
    def load_config(self, config_path="messages.yaml"):
        """Load message configuration from YAML file"""
        try:
            with open(config_path, 'r') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            raise FileNotFoundError(f"Config file {config_path} not found")
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in config file: {e}")
    
    def send_message(self, channel, content):
        """Send a message to Slack based on content configuration"""
        url = f"{self.base_url}/chat.postMessage"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        payload = {"channel": channel}
        
        # Handle different content types
        if content.get("type") == "blocks":
            payload["blocks"] = content["blocks"]
            payload["text"] = "Message from HannesBot"  # Fallback text
        else:
            payload["text"] = content.get("text", "Message from HannesBot")
            
        try:
            response = requests.post(url, headers=headers, json=payload)
            result = response.json()
            
            if result.get("ok"):
                print(f"✅ Message sent to {channel}")
                return True
            else:
                print(f"❌ Error sending to {channel}: {result.get('error')}")
                return False
                
        except Exception as e:
            print(f"❌ Exception sending message: {e}")
            return False
    
    def should_send_message(self, message_config, current_time=None):
        """Determine if a message should be sent based on schedule"""
        if current_time is None:
            current_time = datetime.now()
            
        schedule = message_config.get("schedule", {})
        
        # Check day of week
        current_day = current_time.strftime("%A").lower()
        
        # Handle multiple days (e.g., daily standup)
        if "days" in schedule:
            if current_day not in [day.lower() for day in schedule["days"]]:
                return False
        # Handle single day
        elif "day" in schedule:
            target_day = schedule["day"].lower()
            
            # Special day handling
            if target_day == "first_monday":
                if current_day != "monday" or current_time.day > 7:
                    return False
            elif target_day == "last_friday":
                # Check if it's the last Friday of the month
                next_week = current_time + timedelta(days=7)
                if current_day != "friday" or next_week.month == current_time.month:
                    return False
            else:
                if current_day != target_day:
                    return False
        
        # Check frequency
        frequency = schedule.get("frequency", "weekly")
        if frequency == "biweekly":
            # Simple biweekly check - you might want to store state for this
            week_number = current_time.isocalendar()[1]
            if week_number % 2 != 0:
                return False
        elif frequency == "monthly":
            # Only send on the first occurrence of the day in the month
            if current_time.day > 7:
                return False
        elif frequency == "quarterly":
            # Only send in first month of quarter
            if current_time.month % 3 != 1 or current_time.day > 7:
                return False
                
        return True
    
    def send_scheduled_messages(self, config_path="messages.yaml", dry_run=False):
        """Send messages that are scheduled for the current time"""
        config = self.load_config(config_path)
        current_time = datetime.now()
        
        print(f"🕐 Current time: {current_time.strftime('%A, %B %d, %Y at %I:%M %p')}")
        
        messages_sent = 0
        default_channel = config.get("default_settings", {}).get("channel", "#general")
        
        for message_config in config.get("messages", []):
            message_name = message_config.get("name", "unnamed_message")
            
            if self.should_send_message(message_config, current_time):
                channel = message_config.get("channel", default_channel)
                content = message_config.get("content", {})
                
                print(f"📤 Sending '{message_name}' to {channel}")
                
                if not dry_run:
                    if self.send_message(channel, content):
                        messages_sent += 1
                else:
                    print(f"   (DRY RUN - would send to {channel})")
                    messages_sent += 1
            else:
                print(f"⏭️  Skipping '{message_name}' (not scheduled for now)")
        
        if messages_sent == 0:
            print("📭 No messages scheduled for this time")
        else:
            action = "Would send" if dry_run else "Sent"
            print(f"✅ {action} {messages_sent} message(s)")
            
        return messages_sent

    def list_messages(self, config_path="messages.yaml"):
        """List all configured messages and their schedules"""
        config = self.load_config(config_path)
        
        print("📋 Configured Messages:")
        print("=" * 50)
        
        for message_config in config.get("messages", []):
            name = message_config.get("name", "unnamed")
            schedule = message_config.get("schedule", {})
            channel = message_config.get("channel", config.get("default_settings", {}).get("channel", "#general"))
            
            # Format schedule description
            schedule_desc = []
            if "days" in schedule:
                schedule_desc.append(f"Days: {', '.join(schedule['days'])}")
            elif "day" in schedule:
                schedule_desc.append(f"Day: {schedule['day']}")
            
            if "time" in schedule:
                schedule_desc.append(f"Time: {schedule['time']}")
                
            frequency = schedule.get("frequency", "weekly")
            if frequency != "weekly":
                schedule_desc.append(f"Frequency: {frequency}")
            
            print(f"🤖 {name}")
            print(f"   Channel: {channel}")
            print(f"   Schedule: {' | '.join(schedule_desc)}")
            print()

def main():
    parser = argparse.ArgumentParser(description="HannesBot - Config-driven Slack automation")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be sent without actually sending")
    parser.add_argument("--list", action="store_true", help="List all configured messages")
    parser.add_argument("--config", default="messages.yaml", help="Path to config file")
    
    args = parser.parse_args()
    
    try:
        bot = HannesBot()
        
        if args.list:
            bot.list_messages(args.config)
        else:
            bot.send_scheduled_messages(args.config, dry_run=args.dry_run)
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()