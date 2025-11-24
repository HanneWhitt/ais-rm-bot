#!/usr/bin/env python3
"""
Google Calendar integration for querying calendar events
"""

from datetime import datetime, timedelta
from googleapiclient.discovery import build
from google_auth import authenticate


def list_calendars():
    """List all available calendars"""
    creds = authenticate()
    if not creds:
        return None

    service = build('calendar', 'v3', credentials=creds)

    try:
        calendar_list = service.calendarList().list().execute()
        calendars = calendar_list.get('items', [])

        print(f"\nFound {len(calendars)} calendars:")
        for calendar in calendars:
            print(f"  - {calendar['summary']} (ID: {calendar['id']})")

        return calendars

    except Exception as e:
        print(f"Error listing calendars: {e}")
        return None


def get_upcoming_events(
    calendar_id='primary',
    max_results=10,
    time_min=None,
    time_max=None,
    query=None
):
    """
    Get upcoming events from a calendar

    Args:
        calendar_id (str): Calendar ID (default: 'primary' for main calendar)
        max_results (int): Maximum number of events to return
        time_min (datetime): Start of time range (default: now)
        time_max (datetime): End of time range (optional)
        query (str): Search query to filter events (optional)

    Returns:
        list: List of event dictionaries
    """
    creds = authenticate()
    if not creds:
        return None

    service = build('calendar', 'v3', credentials=creds)

    try:
        # Set time_min to now if not specified
        if time_min is None:
            time_min = datetime.utcnow()

        # Format times as RFC3339 timestamp
        time_min_str = time_min.isoformat() + 'Z'

        params = {
            'calendarId': calendar_id,
            'timeMin': time_min_str,
            'maxResults': max_results,
            'singleEvents': True,
            'orderBy': 'startTime'
        }

        if time_max:
            params['timeMax'] = time_max.isoformat() + 'Z'

        if query:
            params['q'] = query

        events_result = service.events().list(**params).execute()
        events = events_result.get('items', [])

        return events

    except Exception as e:
        print(f"Error getting events: {e}")
        return None


def find_next_event(event_name, calendar_id='primary', days_ahead=30):
    """
    Find the next occurrence of an event with a specific name

    Args:
        event_name (str): Name/summary of the event to find
        calendar_id (str): Calendar ID to search in
        days_ahead (int): How many days ahead to search

    Returns:
        dict: Event details or None if not found
    """
    time_max = datetime.utcnow() + timedelta(days=days_ahead)

    events = get_upcoming_events(
        calendar_id=calendar_id,
        max_results=50,
        time_max=time_max,
        query=event_name
    )

    if not events:
        print(f"No events found matching '{event_name}'")
        return None

    # Find exact match
    for event in events:
        if event_name.lower() == event.get('summary', '').lower():
            return event

    return None


def get_event_time(event):
    """
    Extract start time from an event

    Args:
        event (dict): Event dictionary from Google Calendar API

    Returns:
        datetime: Event start time
    """
    start = event['start'].get('dateTime', event['start'].get('date'))

    # Parse the datetime string
    if 'T' in start:
        # It's a datetime with time
        return datetime.fromisoformat(start.replace('Z', '+00:00'))
    else:
        # It's an all-day event (just a date)
        return datetime.fromisoformat(start)


def print_event(event, calendar_id='primary'):
    """Pretty print an event"""
    summary = event.get('summary', 'No Title')
    start_time = get_event_time(event)
    location = event.get('location', 'No location')
    description = event.get('description', 'No description')

    print(f"\n{'='*60}")
    print(f"Event: {summary}")
    print(f"Calendar: {calendar_id}")
    print(f"Start: {start_time.strftime('%Y-%m-%d %H:%M')}")
    print(f"Location: {location}")
    print(f"Description: {description[:100]}{'...' if len(description) > 100 else ''}")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Query Google Calendar')
    parser.add_argument('--list-calendars', action='store_true',
                       help='List all available calendars')
    parser.add_argument('--upcoming', type=int, metavar='N',
                       help='Show N upcoming events')
    parser.add_argument('--find', type=str, metavar='EVENT_NAME',
                       help='Find next occurrence of an event by name')
    parser.add_argument('--calendar', type=str, default='primary',
                       help='Calendar ID to query (default: primary)')
    parser.add_argument('--days', type=int, default=30,
                       help='Number of days ahead to search (default: 30)')

    args = parser.parse_args()

    if args.list_calendars:
        list_calendars()

    elif args.upcoming:
        print(f"\nFetching {args.upcoming} upcoming events from '{args.calendar}'...\n")
        events = get_upcoming_events(
            calendar_id=args.calendar,
            max_results=args.upcoming
        )

        if events:
            for event in events:
                print_event(event, calendar_id=args.calendar)
        else:
            print("No upcoming events found.")

    elif args.find:
        print(f"\nSearching for next occurrence of '{args.find}'...\n")
        event = find_next_event(
            event_name=args.find,
            calendar_id=args.calendar,
            days_ahead=args.days
        )

        if event:
            print_event(event, calendar_id=args.calendar)
        else:
            print(f"No event found matching '{args.find}'")

    else:
        # Default: show next 5 events
        print("\nShowing next 5 upcoming events:\n")
        events = get_upcoming_events(max_results=5)

        if events:
            for event in events:
                print_event(event, calendar_id='primary')
        else:
            print("No upcoming events found.")
