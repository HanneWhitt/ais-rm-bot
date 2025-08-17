from datetime import datetime
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


def get_ordinal_suffix(day):
    """Return the ordinal suffix for a given day (1st, 2nd, 3rd, etc.)"""
    if 10 <= day % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
    return suffix


def format_date_with_ordinal(date_obj):
    """Format date as '1st August 2025'"""
    day = date_obj.day
    suffix = get_ordinal_suffix(day)
    return f"{day}{suffix} {date_obj.strftime('%B %Y')}"