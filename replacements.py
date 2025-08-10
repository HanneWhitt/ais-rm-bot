from datetime import datetime, timedelta
from utils import format_date_with_ordinal, get_ordinal_suffix

# Get today and tomorrow
today = datetime.now()
tomorrow = today + timedelta(days=1)


def get_default_replacements():
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
        return {key: replace_recursive(value, replacements) for key, value in data.items()}
    elif isinstance(data, list):
        # Recursive case: if it's a list, apply to all elements
        return [replace_recursive(item, replacements) for item in data]
    elif isinstance(data, tuple):
        # Recursive case: if it's a tuple, apply to all elements and return tuple
        return tuple(replace_recursive(item, replacements) for item in data)
    else:
        # Base case: if it's any other type, return as-is
        return data


def replace_recursive(data, replacements=None):

    if replacements is None:
        replacements = {}
        
    # Combine replacements with default replacements
    replacements = {**get_default_replacements(), **replacements}

    return replace_recursive_(data, replacements)