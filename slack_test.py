#!/usr/bin/env python3
"""
Basic Slack message sender for testing
Run: python slack_test.py
"""

import requests
import json
from datetime import datetime
import os

# Configuration
SLACK_BOT_TOKEN = os.getenv('SLACK_BOT_TOKEN')
CHANNEL_NAME = "#hannes-dev-channel"

def send_slack_message(channel, text, blocks=None):
    """Send a message to Slack using the Web API"""
    
    url = "https://slack.com/api/chat.postMessage"
    
    headers = {
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "channel": channel,
        "text": text
    }
    
    # Add rich formatting blocks if provided
    if blocks:
        payload["blocks"] = blocks
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        result = response.json()
        
        if result.get("ok"):
            print(f"✅ Message sent successfully to {channel}")
            return result
        else:
            print(f"❌ Error sending message: {result.get('error')}")
            return None
            
    except Exception as e:
        print(f"❌ Exception occurred: {e}")
        return None

def test_basic_message():
    """Send a simple test message"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = f"🤖 Test message from AI Safety Automator at {timestamp}"
    
    return send_slack_message(CHANNEL_NAME, message)

def test_rich_message():
    """Send a message with rich formatting"""
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🔬 AI Safety Weekly Update"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*This is a test of automated messaging*\n\n• Research progress updates\n• Safety milestone reviews\n• Team coordination notes"
            }
        },
        {
            "type": "divider"
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Automated message • {datetime.now().strftime('%B %d, %Y at %I:%M %p')}"
                }
            ]
        }
    ]
    
    return send_slack_message(
        CHANNEL_NAME, 
        "AI Safety Weekly Update",  # Fallback text
        blocks=blocks
    )

if __name__ == "__main__":
    print("🚀 Testing Slack API connection...")
    
    # Test basic message
    print("\n1. Sending basic message...")
    test_basic_message()
    
    # Test rich message
    print("\n2. Sending rich formatted message...")
    test_rich_message()
    
    print("\n✨ Test complete! Check your Slack channel.")