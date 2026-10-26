"""Composition root: builds repositories, lock, clock, services and router by hand (no DI framework)."""

from datetime import datetime, timezone
from threading import RLock

from fastapi import FastAPI

from app import config
from app.api.errors import register_error_handlers
from app.api.routes import create_router
from app.application.booking_service import BookingService
from app.application.event_service import EventService
from app.application.ports import Clock
from app.infrastructure.in_memory_repos import InMemoryEventRepository, InMemoryTicketRepository

DESCRIPTION = """
Users book tickets for events. Owners create and cancel events.

**Identity:** there is no login. Send your user id in the `X-User-Id` header.
Ids listed in the `OWNER_IDS` environment variable (default `owner`) are event owners.
An owner can only cancel and inspect their own events.

**Errors** use RFC 7807 Problem Details (`application/problem+json`).

See the README for all assumptions.
"""

TAGS = [
    {"name": "events", "description": "Browse events."},
    {"name": "tickets", "description": "Book tickets and see your bookings."},
    {"name": "owner", "description": "Event owners only: create, cancel and inspect events."},
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_app(clock: Clock = _utc_now) -> FastAPI:
    events = InMemoryEventRepository()
    tickets = InMemoryTicketRepository()
    lock = RLock()  # shared so book() and cancel() cannot interleave

    event_service = EventService(events, tickets, clock, lock)
    booking_service = BookingService(events, tickets, clock, lock, config.MAX_TICKETS_PER_BOOKING)

    app = FastAPI(
        title="Event Ticket Booking Service",
        version="1.0.0",
        description=DESCRIPTION,
        openapi_tags=TAGS,
    )
    register_error_handlers(app)
    app.include_router(create_router(event_service, booking_service))
    return app


app = create_app()
