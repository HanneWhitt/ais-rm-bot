import os
import requests


def get_channel_id(channel_name, slack_bot_token):
    headers = {
        'Authorization': f'Bearer {slack_bot_token}',
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


def get_channel_member_ids(channel_name, slack_bot_token):
    headers = {
        'Authorization': f'Bearer {slack_bot_token}',
        'Content-Type': 'application/json'
    }
    
    channel_id = get_channel_id(channel_name, slack_bot_token)
    
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


def tag_users_string(text, user_dict):
    """
    Replace @username mentions with <@USER_ID> format in a single string.
    
    Args:
        text (str): Input text containing potential @mentions
        user_dict (dict): Dictionary mapping usernames to user IDs
    
    Returns:
        str: Text with @mentions replaced by <@USER_ID> format
    """
    result = ""
    i = 0
    
    while i < len(text):
        if text[i] == '@':
            # Find the longest matching username starting from this position
            longest_match = ""
            longest_match_length = 0
            
            # Check all possible usernames in the dictionary
            for username in user_dict:
                # Check if the text after '@' starts with this username
                if (i + 1 + len(username) <= len(text) and 
                    text[i + 1:i + 1 + len(username)] == username):
                    # If this match is longer than the current longest, use it
                    if len(username) > longest_match_length:
                        longest_match = username
                        longest_match_length = len(username)
            
            if longest_match:
                # Replace @username with <@USER_ID>
                result += f"<@{user_dict[longest_match]}>"
                i += 1 + longest_match_length  # Skip past the '@' and username
            else:
                # No match found, keep the '@' as is
                result += text[i]
                i += 1
        else:
            result += text[i]
            i += 1
    
    return result


def tag_users(data, user_dict):
    """
    Replace @username mentions with <@USER_ID> format in nested data structures.
    
    Recursively processes dictionaries, lists, and strings to find and replace
    @mentions anywhere in the data structure.
    
    Args:
        data: Input data - can be string, dict, list, or any nested combination
        user_dict (dict): Dictionary mapping usernames to user IDs
    
    Returns:
        Same type as input with @mentions replaced by <@USER_ID> format
    """
    if isinstance(data, str):
        # Base case: if it's a string, apply the string tagging function
        return tag_users_string(data, user_dict)
    elif isinstance(data, dict):
        # Recursively process each value in the dictionary
        return {key: tag_users(value, user_dict) for key, value in data.items()}
    elif isinstance(data, list):
        # Recursively process each element in the list
        return [tag_users(item, user_dict) for item in data]
    else:
        # For any other data type (int, bool, None, etc.), return as is
        return data


if __name__ == '__main__':


    from utils import get_slack_token

    workspace = 'meridian'
    channel = 'extended-meridian-team'

    slack_token = get_slack_token(workspace)

    member_ids = get_channel_member_ids(channel, slack_token)

    print(member_ids)