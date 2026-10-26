"""Runtime settings, read from environment variables."""

import os

# Comma-separated user ids that count as event owners.
OWNER_IDS: frozenset[str] = frozenset(
    part.strip() for part in os.getenv("OWNER_IDS", "owner").split(",") if part.strip()
)

MAX_TICKETS_PER_BOOKING: int = int(os.getenv("MAX_TICKETS_PER_BOOKING", "10"))
