#!/usr/bin/env python3
"""
Test script to demonstrate the latest_send_offset behavior
"""

from datetime import datetime, timedelta
from scheduler import MessageScheduler

def test_scenarios():
    """Test different scenarios with latest_send_offset"""

    scheduler = MessageScheduler()

    print("\n" + "=" * 70)
    print("Testing latest_send_offset Logic")
    print("=" * 70)

    # Simulate current time
    now = datetime.now()

    # Event is 1 hour from now
    event_time = now + timedelta(hours=1)

    scenarios = [
        {
            "name": "Scenario 1: On time",
            "offset": "-2h",
            "latest_send_offset": None,
            "scheduled_time": event_time - timedelta(hours=2),
            "description": "Scheduled send time is 2 hours before (in the past), no latest_send_offset"
        },
        {
            "name": "Scenario 2: Late but within window",
            "offset": "-2h",
            "latest_send_offset": "-30m",
            "scheduled_time": event_time - timedelta(hours=2),
            "description": "Want to send 2h before, but it's past that. Latest is 30m before (we're at 1h before)"
        },
        {
            "name": "Scenario 3: Too late - outside window",
            "offset": "-2h",
            "latest_send_offset": "-90m",
            "scheduled_time": event_time - timedelta(hours=2),
            "description": "Want to send 2h before, but latest is 90m before (we're at 1h before - too late!)"
        },
    ]

    for scenario in scenarios:
        print(f"\n{scenario['name']}")
        print("-" * 70)
        print(f"Description: {scenario['description']}")
        print(f"\nEvent time:           {event_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Current time:         {now.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"offset:               {scenario['offset']}")
        print(f"latest_send_offset:   {scenario['latest_send_offset']}")

        offset = scheduler.parse_offset(scenario['offset'])
        ideal_send_time = event_time + offset
        print(f"Ideal send time:      {ideal_send_time.strftime('%Y-%m-%d %H:%M:%S')}")

        if scenario['latest_send_offset']:
            latest_offset = scheduler.parse_offset(scenario['latest_send_offset'])
            latest_send_time = event_time + latest_offset
            print(f"Latest send time:     {latest_send_time.strftime('%Y-%m-%d %H:%M:%S')}")

            if now > latest_send_time:
                print(f"\n✗ RESULT: SKIP - We're past the latest send time")
            elif ideal_send_time < now:
                print(f"\n✓ RESULT: SEND IMMEDIATELY - Late but within window")
            else:
                print(f"\n✓ RESULT: SCHEDULE - On time")
        else:
            if ideal_send_time < now:
                print(f"\n✓ RESULT: SEND IMMEDIATELY - No latest_send_offset specified")
            else:
                print(f"\n✓ RESULT: SCHEDULE - On time")

    print("\n" + "=" * 70)
    print("\nSummary:")
    print("- offset: When you WANT to send the message")
    print("- latest_send_offset: Latest acceptable time to send")
    print("- If current time is between offset and latest_send_offset: Send immediately")
    print("- If current time is past latest_send_offset: Skip")
    print("- If no latest_send_offset: Always send (even if late)")
    print("=" * 70 + "\n")


if __name__ == '__main__':
    test_scenarios()
