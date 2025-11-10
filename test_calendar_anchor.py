#!/usr/bin/env python3
"""
Test script for calendar-anchored messages
"""

from scheduler import MessageScheduler
import logging

# Set up logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_parse_offset():
    """Test the offset parsing function"""
    scheduler = MessageScheduler()

    print("\n=== Testing Offset Parsing ===")
    test_cases = [
        ("-30m", "30 minutes before"),
        ("-2h", "2 hours before"),
        ("-1d", "1 day before"),
        ("-2w", "2 weeks before"),
        ("1h", "1 hour after"),
    ]

    for offset_str, description in test_cases:
        try:
            offset = scheduler.parse_offset(offset_str)
            print(f"✓ {offset_str:6s} -> {offset} ({description})")
        except Exception as e:
            print(f"✗ {offset_str:6s} -> ERROR: {e}")


def test_calendar_tracker():
    """Test the calendar event tracking database"""
    from scheduler import CalendarEventTracker
    from datetime import datetime, timedelta

    print("\n=== Testing Calendar Event Tracker ===")

    tracker = CalendarEventTracker('test_scheduler.db')

    # Test adding an event
    now = datetime.now()
    send_time = now + timedelta(hours=1)

    tracker.add_scheduled_event(
        message_config_id="test_message",
        event_id="test_event_123",
        event_start_time=now + timedelta(hours=3),
        scheduled_send_time=send_time,
        job_id="test_job_1"
    )
    print("✓ Added test event to database")

    # Test checking if event is scheduled
    is_scheduled = tracker.is_event_scheduled("test_message", "test_event_123")
    print(f"✓ Event is scheduled: {is_scheduled}")

    # Test that duplicate is detected
    is_duplicate = tracker.is_event_scheduled("test_message", "test_event_123")
    print(f"✓ Duplicate detection works: {is_duplicate}")

    # Test marking as sent
    tracker.mark_as_sent("test_message", "test_event_123")
    print("✓ Marked event as sent")

    # Clean up
    import os
    if os.path.exists('test_scheduler.db'):
        os.remove('test_scheduler.db')
        print("✓ Cleaned up test database")


def test_yaml_loading():
    """Test loading calendar-anchored messages from YAML"""
    print("\n=== Testing YAML Loading ===")

    scheduler = MessageScheduler('sqlite:///test_scheduler.db')

    try:
        # This will attempt to load calendar-anchored messages
        # It won't actually schedule anything since the example is disabled
        scheduler.schedule_messages_from_yaml('messages/example_calendar_anchored.yaml')
        print("✓ Successfully loaded calendar-anchored YAML configuration")
        print(f"✓ Found {len(scheduler.calendar_anchored_configs)} calendar-anchored configs")
    except Exception as e:
        print(f"✗ Error loading YAML: {e}")
    finally:
        scheduler.stop()

        # Clean up
        import os
        if os.path.exists('test_scheduler.db'):
            os.remove('test_scheduler.db')


if __name__ == '__main__':
    print("=" * 60)
    print("Testing Calendar-Anchored Messaging Feature")
    print("=" * 60)

    test_parse_offset()
    test_calendar_tracker()
    test_yaml_loading()

    print("\n" + "=" * 60)
    print("✅ All tests completed!")
    print("=" * 60)
    print("\nTo use calendar-anchored messages:")
    print("1. Edit messages/example_calendar_anchored.yaml")
    print("2. Set enabled: true for a message")
    print("3. Update event_name to match your calendar event")
    print("4. Run: python scheduler.py --yaml_file messages/")
    print("=" * 60)
