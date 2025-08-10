from datetime import datetime

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