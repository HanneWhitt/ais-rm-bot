#!/usr/bin/env python3
"""
Generate GitHub Actions workflow from messages.yaml
Run this script whenever you update your message schedules
"""

import yaml
import os
from collections import defaultdict
from datetime import datetime

class WorkflowGenerator:
    def __init__(self):
        self.day_mapping = {
            'monday': 1, 'tuesday': 2, 'wednesday': 3, 'thursday': 4,
            'friday': 5, 'saturday': 6, 'sunday': 0
        }
        
    def load_messages_config(self, config_path="messages.yaml"):
        """Load the messages configuration"""
        with open(config_path, 'r') as file:
            return yaml.safe_load(file)
    
    def parse_schedule(self, schedule):
        """Parse a message schedule into cron components"""
        cron_entries = []
        
        # Get time
        time_str = schedule.get("time", "09:00")
        hour, minute = map(int, time_str.split(":"))
        
        # Handle different day specifications
        if "days" in schedule:
            # Multiple days (e.g., daily standup Monday-Friday)
            days = [self.day_mapping[day.lower()] for day in schedule["days"]]
            day_of_week = ",".join(map(str, sorted(days)))
        elif "day" in schedule:
            day = schedule["day"].lower()
            if day in self.day_mapping:
                day_of_week = str(self.day_mapping[day])
            elif day == "first_monday":
                # First Monday of month - we'll use a special case
                day_of_week = "1"  # Monday, but we'll add day-of-month constraint
            else:
                day_of_week = "*"
        else:
            day_of_week = "*"
        
        # Handle frequency
        frequency = schedule.get("frequency", "weekly")
        
        if frequency == "weekly" or frequency not in ["biweekly", "monthly", "quarterly"]:
            # Standard weekly schedule
            cron_entries.append({
                "minute": minute,
                "hour": hour,
                "day_of_month": "*",
                "month": "*",
                "day_of_week": day_of_week,
                "comment": f"Weekly - {schedule.get('day', 'multiple days')} at {time_str}"
            })
        elif frequency == "biweekly":
            # For biweekly, we'll create two entries offset by a week
            # This is a simplification - true biweekly needs state tracking
            cron_entries.append({
                "minute": minute,
                "hour": hour,
                "day_of_month": "1-7,15-21",  # First and third week of month
                "month": "*",
                "day_of_week": day_of_week,
                "comment": f"Biweekly (approx) - {schedule.get('day')} at {time_str}"
            })
        elif frequency == "monthly":
            if schedule.get("day") == "first_monday":
                cron_entries.append({
                    "minute": minute,
                    "hour": hour,
                    "day_of_month": "1-7",
                    "month": "*",
                    "day_of_week": "1",
                    "comment": f"Monthly - First Monday at {time_str}"
                })
            else:
                cron_entries.append({
                    "minute": minute,
                    "hour": hour,
                    "day_of_month": "1-7",  # First week of month
                    "month": "*",
                    "day_of_week": day_of_week,
                    "comment": f"Monthly - First {schedule.get('day')} at {time_str}"
                })
        elif frequency == "quarterly":
            cron_entries.append({
                "minute": minute,
                "hour": hour,
                "day_of_month": "1-7",
                "month": "1,4,7,10",  # January, April, July, October
                "day_of_week": day_of_week,
                "comment": f"Quarterly - {schedule.get('day')} at {time_str}"
            })
        
        return cron_entries
    
    def adjust_for_uk_timezone(self, cron_entries):
        """Adjust times for UK timezone (both GMT and BST)"""
        adjusted_entries = []
        
        for entry in cron_entries:
            # Create entries for both GMT (UTC+0) and BST (UTC+1)
            # We'll run slightly more often but the script will handle timezone correctly
            
            # GMT time (October-March): No adjustment needed for UK local time
            gmt_entry = entry.copy()
            gmt_entry["comment"] += " (GMT period)"
            adjusted_entries.append(gmt_entry)
            
            # BST time (March-October): Subtract 1 hour for UTC
            bst_hour = (entry["hour"] - 1) % 24
            bst_entry = entry.copy()
            bst_entry["hour"] = bst_hour
            bst_entry["comment"] += " (BST period)"
            adjusted_entries.append(bst_entry)
        
        return adjusted_entries
    
    def format_cron_line(self, entry):
        """Format a cron entry as a YAML line"""
        cron_str = f"{entry['minute']} {entry['hour']} {entry['day_of_month']} {entry['month']} {entry['day_of_week']}"
        return f"    - cron: '{cron_str}'  # {entry['comment']}"
    
    def generate_workflow_yaml(self, config):
        """Generate the complete workflow YAML"""
        
        # Collect all schedule entries
        all_cron_entries = []
        
        for message in config.get("messages", []):
            if "schedule" in message:
                message_name = message.get("name", "unnamed")
                cron_entries = self.parse_schedule(message["schedule"])
                
                # Add message name to comments
                for entry in cron_entries:
                    entry["comment"] = f"{message_name} - {entry['comment']}"
                
                all_cron_entries.extend(cron_entries)
        
        # Adjust for UK timezone
        adjusted_entries = self.adjust_for_uk_timezone(all_cron_entries)
        
        # Remove duplicates and sort
        unique_entries = []
        seen_crons = set()
        
        for entry in adjusted_entries:
            cron_key = f"{entry['minute']} {entry['hour']} {entry['day_of_month']} {entry['month']} {entry['day_of_week']}"
            if cron_key not in seen_crons:
                seen_crons.add(cron_key)
                unique_entries.append(entry)
        
        # Sort by hour, then minute
        unique_entries.sort(key=lambda x: (x['hour'], x['minute']))
        
        # Generate the workflow YAML
        workflow_yaml = f"""name: HannesBot Slack Automation

# Auto-generated from messages.yaml on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# DO NOT EDIT - run 'python generate_workflow.py' to update

on:
  schedule:
{chr(10).join(self.format_cron_line(entry) for entry in unique_entries)}
    
  # Allow manual triggering
  workflow_dispatch:
    inputs:
      dry_run:
        description: 'Run in dry-run mode (show what would be sent)'
        required: false
        default: 'false'
        type: boolean

jobs:
  send-slack-messages:
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout repository
      uses: actions/checkout@v4
      
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
        
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install requests pyyaml
        
    - name: Run HannesBot
      env:
        SLACK_BOT_TOKEN: ${{{{ secrets.SLACK_BOT_TOKEN }}}}
      run: |
        if [ "${{{{ github.event.inputs.dry_run }}}}" = "true" ]; then
          python hannes_bot.py --dry-run
        else
          python hannes_bot.py
        fi
        
    # Optional: List all configured messages (on manual run)
    - name: List configured messages (on manual run)
      if: github.event_name == 'workflow_dispatch'
      env:
        SLACK_BOT_TOKEN: ${{{{ secrets.SLACK_BOT_TOKEN }}}}
      run: |
        echo "📋 All configured messages:"
        python hannes_bot.py --list

# Summary of scheduled messages:
{self.generate_schedule_summary(config)}
"""
        
        return workflow_yaml
    
    def generate_schedule_summary(self, config):
        """Generate a human-readable summary of the schedule"""
        summary_lines = ["#"]
        
        for message in config.get("messages", []):
            if "schedule" in message:
                name = message.get("name", "unnamed")
                schedule = message["schedule"]
                
                # Format the schedule description
                if "days" in schedule:
                    days_str = ", ".join(schedule["days"])
                    freq = schedule.get("frequency", "weekly")
                    summary_lines.append(f"# • {name}: {days_str} at {schedule.get('time', 'N/A')} ({freq})")
                elif "day" in schedule:
                    freq = schedule.get("frequency", "weekly")
                    summary_lines.append(f"# • {name}: {schedule['day']} at {schedule.get('time', 'N/A')} ({freq})")
        
        summary_lines.append("#")
        return "\n".join(summary_lines)
    
    def save_workflow(self, yaml_content, output_path=".github/workflows/slack-automation.yml"):
        """Save the generated workflow to file"""
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w') as file:
            file.write(yaml_content)
        
        print(f"✅ Generated workflow saved to {output_path}")
    
    def run(self, messages_config_path="messages.yaml", workflow_output_path=".github/workflows/slack-automation.yml"):
        """Main function to generate workflow from messages config"""
        
        print("🤖 Generating GitHub Actions workflow from messages.yaml...")
        
        # Load configuration
        try:
            config = self.load_messages_config(messages_config_path)
            print(f"📋 Loaded {len(config.get('messages', []))} message configurations")
        except Exception as e:
            print(f"❌ Error loading {messages_config_path}: {e}")
            return False
        
        # Generate workflow
        try:
            workflow_yaml = self.generate_workflow_yaml(config)
            self.save_workflow(workflow_yaml, workflow_output_path)
        except Exception as e:
            print(f"❌ Error generating workflow: {e}")
            return False
        
        print("🚀 Workflow generated successfully!")
        print("\nNext steps:")
        print("1. Review the generated .github/workflows/slack-automation.yml")
        print("2. Commit and push changes to your repository")
        print("3. GitHub Actions will now run at the exact times specified in your messages!")
        
        return True

def main():
    generator = WorkflowGenerator()
    success = generator.run()
    
    if not success:
        exit(1)

if __name__ == "__main__":
    main()