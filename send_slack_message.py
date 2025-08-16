#!/usr/bin/env python3
"""
Simplified Slack message sender
Run: python send_message.py
"""

import requests
import json
from datetime import datetime
import os
import argparse
from tag_users import get_channel_member_ids, tag_users
import yaml


# Load slack tokens from file
with open('slack_tokens.yaml', 'r') as file:
    tokens = yaml.safe_load(file)


def get_slack_token(workspace):
    """Load slack bot token, verify that the Slack bot token is properly configured"""
    
    slack_bot_token = tokens.get(workspace.lower())

    if not slack_bot_token:
        print(f"❌ No token for workspace {workspace} in slack_tokens.yaml")
        return None

    if not slack_bot_token.startswith('xoxb-'):
        print("❌ Token should start with 'xoxb-' (bot token)")
        return None
    
    print(f"✅ Token format looks correct: {slack_bot_token[:10]}...")
    return slack_bot_token


def send_slack_message(workspace, channel, text, blocks=None, display_name=None, icon=None):
    """
    Send a message to Slack with optional custom display name and icon
    
    Args:
        channel (str): Channel name/ID to send to
        text (str): Message text content
        blocks (list, optional): Rich formatting blocks
        display_name (str, optional): Custom display name for the message
        icon (str, optional): Custom icon (emoji name or URL)
    
    Returns:
        dict: Slack API response or None on error
    """
    
    slack_bot_token = get_slack_token(workspace)

    member_ids = get_channel_member_ids(channel, slack_bot_token)

    text = tag_users(text, member_ids)

    url = "https://slack.com/api/chat.postMessage"
    
    headers = {
        "Authorization": f"Bearer {slack_bot_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "channel": channel,
        "text": text
    }
    
    # Add custom display name and icon if provided
    if display_name:
        payload["username"] = display_name
        
        if icon:
            if icon.startswith("http"):
                payload["icon_url"] = icon
            else:
                # Handle emoji format (with or without colons)
                emoji = icon if icon.startswith(":") and icon.endswith(":") else f":{icon}:"
                payload["icon_emoji"] = emoji
    
    # Add rich formatting blocks if provided
    if blocks:
        blocks = tag_users(blocks, member_ids)
        payload["blocks"] = blocks
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        result = response.json()
        
        if result.get("ok"):
            display_info = f" as '{display_name}'" if display_name else ""
            print(f"✅ Message sent successfully to {channel}{display_info}")
            return result
        else:
            error = result.get('error')
            print(f"❌ Error sending message: {error}")
            
            # Provide specific help for common errors
            if error == 'channel_not_found':
                print("💡 Try: 1) Use channel ID instead of name, 2) Add bot to channel")
            elif error == 'not_in_channel':
                print("💡 Add your bot to the channel with /invite @botname")
            elif error == 'invalid_auth':
                print("💡 Check your bot token and permissions")
                
            return None
            
    except Exception as e:
        print(f"❌ Exception occurred: {e}")
        return None