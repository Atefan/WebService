"""Fire parallel bookings at a RUNNING server and check that nothing is oversold.

Usage: start the server, then `python scripts/demo_concurrency.py [--base-url http://127.0.0.1:8000]`.
Planned: create event (capacity 50) as owner, send 200 parallel bookings as different users,
read stats, print `booked 50 | rejected (409) 150 | oversold 0 -> PASS`, exit non-zero on failure.
"""

# TODO: implement with httpx + ThreadPoolExecutor. First thing to cut if time runs out.
