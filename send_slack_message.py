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


def test_comprehensive_message(workspace, channel):

    """Send one comprehensive test message with all features"""


    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Create rich blocks with various formatting
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🤖 Slack Bot Test Message"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Test sent at:* {timestamp}\n\n"
                    "*Features demonstrated:*\n"
                    "• Custom bot name and icon\n"
                    "• Rich formatting with *bold*, _italic_, and `code` @hannes.whittingham\n"
                    "• Links: <https://anthropic.com|Anthropic> and <https://slack.com|Slack API>\n"
                    "• Emojis: :rocket: :white_check_mark: :gear:\n"
                    "• Block formatting with headers and dividers @Hannes Whittingham Hello <@U08P2P0TT4N>!"
                )
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
                    "text": "✨ This message tests all major Slack formatting features in one go!"
                }
            ]
        }
    ]
    
    return send_slack_message(
        workspace,
        channel,
        f"THIS TEXT WAS IN TEXT FIELD - {timestamp}",  # Fallback text
        blocks=blocks,
        display_name="Test Bot Pro",
        icon="robot_face"
    )

def main():
    """Main function with command line argument support"""
    parser = argparse.ArgumentParser(description='Send a comprehensive test message to Slack')
    parser.add_argument('--workspace', '-w', default='Meridian', help='slack workspace with a token in slack_tokens.json')
    parser.add_argument('--channel', '-c', default='#hannes-dev-channel', help='Channel to send to')
    parser.add_argument('--message', '-m', help='Custom message text to send')
    parser.add_argument('--name', '-n', help='Custom display name')
    parser.add_argument('--icon', '-i', help='Custom icon (emoji name or URL)')
    
    args = parser.parse_args()

    
    # Handle custom message
    if args.message:
        print(f"📤 Sending custom message to {args.channel}...")
        result = send_slack_message(
            args.channel, 
            args.message,
            display_name=args.name,
            icon=args.icon
        )
        return 0 if result else 1
    
    # Default behavior: run comprehensive test
    print(f"🚀 Sending comprehensive test message to {args.channel}...")
    result = test_comprehensive_message(args.workspace, args.channel)
    
    if result:
        print("\n✨ Test complete! Check your Slack channel.")
        print("💡 You can also send custom messages with:")
        print("   python send_message.py -m 'Your message here' -n 'Bot Name' -i 'emoji_name'")
    
    return 0 if result else 1

if __name__ == "__main__":
    exit(main())