#!/usr/bin/env python3
"""
Test that calendar-anchored messages can be serialized to database
"""

from scheduler import MessageScheduler
import logging

logging.basicConfig(level=logging.INFO)

def test_serialization():
    """Test that calendar jobs can be added without serialization errors"""

    print("\n" + "=" * 70)
    print("Testing Calendar Message Serialization")
    print("=" * 70 + "\n")

    scheduler = MessageScheduler('sqlite:///test_scheduler.db')

    try:
        scheduler.start()

        print("Loading calendar-anchored messages from YAML...")
        scheduler.schedule_messages_from_yaml('messages/example_calendar_anchored_2.yaml')

        print("\n✅ SUCCESS! No serialization errors.")
        print("\nScheduled jobs:")
        scheduler.list_jobs()

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        scheduler.stop()

        # Clean up
        import os
        if os.path.exists('test_scheduler.db'):
            os.remove('test_scheduler.db')
            print("\n✓ Cleaned up test database")

if __name__ == '__main__':
    test_serialization()
