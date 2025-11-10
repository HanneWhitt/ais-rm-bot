from datetime import datetime, timedelta
from utils import format_date_with_ordinal, get_ordinal_suffix


def get_default_replacements():

    # Get today and tomorrow
    today = datetime.now()
    tomorrow = today + timedelta(days=1)

    return {
        '{time}': today.strftime('%I:%M %p'),
        '{year}': str(today.year),
        '{month}': today.strftime('%B'),
        '{day}': str(today.day),
        '{date}': format_date_with_ordinal(today),
        '{date_storage}': today.strftime('%Y %m %d'),
        '{date_tomorrow}': format_date_with_ordinal(tomorrow),
        '{date_tomorrow_storage}': tomorrow.strftime('%Y %m %d')
    }


def get_event_replacements(event_time):
    """
    Get replacements based on a calendar event time instead of current time.

    This is used for calendar-anchored messages so that {date}, {time}, etc.
    refer to the event's date/time, not when the message is sent.

    Args:
        event_time (datetime): The calendar event start time

    Returns:
        dict: Replacement dictionary with same keys as get_default_replacements()
    """
    # Handle both timezone-aware and naive datetimes
    if event_time.tzinfo is not None:
        # Convert to local timezone for display
        event_time = event_time.replace(tzinfo=None)

    tomorrow = event_time + timedelta(days=1)

    return {
        '{time}': event_time.strftime('%I:%M %p'),
        '{year}': str(event_time.year),
        '{month}': event_time.strftime('%B'),
        '{day}': str(event_time.day),
        '{date}': format_date_with_ordinal(event_time),
        '{date_storage}': event_time.strftime('%Y %m %d'),
        '{date_tomorrow}': format_date_with_ordinal(tomorrow),
        '{date_tomorrow_storage}': tomorrow.strftime('%Y %m %d')
    }


def replace_string(string, replacements=None):
    """Replace placeholders in a string with values from replacements dict"""
    if replacements is None:
        replacements = {}
    
    result = string
    for placeholder, value in replacements.items():
        result = result.replace(placeholder, str(value))
    
    return result


def replace_recursive_(data, replacements=None):
    """Apply string replacement recursively to all strings in nested dict/list structure"""

    if isinstance(data, str):
        # Base case: if it's a string, apply replacements
        return replace_string(data, replacements)
    elif isinstance(data, dict):
        # Recursive case: if it's a dict, apply to all values
        return {key: replace_recursive_(value, replacements) for key, value in data.items()}
    elif isinstance(data, list):
        # Recursive case: if it's a list, apply to all elements
        return [replace_recursive_(item, replacements) for item in data]
    elif isinstance(data, tuple):
        # Recursive case: if it's a tuple, apply to all elements and return tuple
        return tuple(replace_recursive_(item, replacements) for item in data)
    else:
        # Base case: if it's any other type, return as-is
        return data


def replace_recursive(data, replacements=None):

    if replacements is None:
        replacements = {}
        
    # Combine replacements with default replacements
    replacements = {**get_default_replacements(), **replacements}

    # Ensure all replacement keys have curly brackets
    replacements = {'{' + k.strip('{').strip('}') + '}':v for k, v in replacements.items()}

    return replace_recursive_(data, replacements)