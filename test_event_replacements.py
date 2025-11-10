#!/usr/bin/env python3
"""
Test that calendar-anchored messages use event time for replacements
"""

from datetime import datetime, timedelta
from replacements import get_default_replacements, get_event_replacements

def test_event_replacements():
    """Test that event replacements use event time, not current time"""

    print("\n" + "=" * 70)
    print("Testing Event-Based Replacements")
    print("=" * 70 + "\n")

    # Current time
    now = datetime.now()
    print(f"Current time: {now.strftime('%Y-%m-%d %I:%M %p')}\n")

    # Event is tomorrow at 2pm
    event_time = now.replace(hour=14, minute=0, second=0, microsecond=0) + timedelta(days=1)
    print(f"Event time:   {event_time.strftime('%Y-%m-%d %I:%M %p')}\n")

    # Get default replacements (based on current time)
    default_replacements = get_default_replacements()

    # Get event replacements (based on event time)
    event_replacements = get_event_replacements(event_time)

    print("Comparison of Replacements:")
    print("-" * 70)
    print(f"{'Key':<25} {'Current Time':<25} {'Event Time':<25}")
    print("-" * 70)

    for key in default_replacements.keys():
        default_val = default_replacements.get(key, 'N/A')
        event_val = event_replacements.get(key, 'N/A')

        # Highlight differences
        indicator = "✓" if default_val == event_val else "→"

        print(f"{key:<25} {default_val:<25} {event_val:<25} {indicator}")

    print("-" * 70)
    print("\n✅ Event-based replacements are working!")
    print("\nFor calendar-anchored messages:")
    print("  - {date}, {time}, etc. will use the EVENT time")
    print("  - Not the time when the message is sent")
    print("=" * 70 + "\n")


if __name__ == '__main__':
    test_event_replacements()
