import os
import requests

# Configuration
SLACK_BOT_TOKEN = os.getenv('SLACK_BOT_TOKEN')
DEFAULT_CHANNEL = "#research-accelerator-week-august-25"

def get_channel_id(channel_name):
    headers = {
        'Authorization': f'Bearer {SLACK_BOT_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    # Remove # if present
    channel_name = channel_name.lstrip('#')
    
    # Get channel ID - check both public and private channels
    channels_url = 'https://slack.com/api/conversations.list'
    
    # Check public channels
    params = {'types': 'public_channel'}
    response = requests.get(channels_url, headers=headers, params=params)
    channels = response.json()
    
    if channels['ok']:
        for channel in channels['channels']:
            if channel['name'] == channel_name:
                return channel['id']
    
    # If not found, check private channels the bot is a member of
    params = {'types': 'private_channel'}
    response = requests.get(channels_url, headers=headers, params=params)
    channels = response.json()
    
    if channels['ok']:
        for channel in channels['channels']:
            if channel['name'] == channel_name:
                return channel['id']
    
    return None


def get_channel_members(channel_name):
    headers = {
        'Authorization': f'Bearer {SLACK_BOT_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    channel_id = get_channel_id(channel_name)
    
    if not channel_id:
        print(f"Channel '{channel_name}' not found or bot is not a member")
        print("Make sure the bot is added to the channel and has proper scopes")
        return {}
    
    # Get channel members
    members_url = f'https://slack.com/api/conversations.members?channel={channel_id}'
    response = requests.get(members_url, headers=headers)
    members_data = response.json()
    
    if not members_data['ok']:
        print(f"Error getting members: {members_data['error']}")
        return {}
    
    # Get user info for all users
    users_url = 'https://slack.com/api/users.list'
    response = requests.get(users_url, headers=headers)
    users_data = response.json()
    
    if not users_data['ok']:
        print(f"Error getting users: {users_data['error']}")
        return {}
    
    # Create user mapping
    user_map = {}
    for user in users_data['members']:
        user_map[user['id']] = {
            'name': user['name'],
            'display_name': user.get('profile', {}).get('display_name', ''),
            'real_name': user.get('profile', {}).get('real_name', '')
        }
    
    # Filter to only channel members and create name-to-ID mapping
    channel_members = {}
    for user_id in members_data['members']:
        if user_id in user_map:
            user_info = user_map[user_id]
            # Use display_name if available, otherwise fall back to name
            display_name = user_info['display_name'] or user_info['name']
            channel_members[display_name] = user_id
            # Also add the username as a key
            channel_members[user_info['name']] = user_id
    
    return channel_members

# Get members from default channel
user_ids = get_channel_members(DEFAULT_CHANNEL)

print(user_ids)

