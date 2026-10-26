"""Composition root: builds repositories, lock, clock, services and router by hand (no DI framework)."""

from datetime import datetime, timezone
from threading import RLock

from fastapi import FastAPI

from app import config
from app.api.routes import create_router
from app.application.booking_service import BookingService
from app.application.event_service import EventService
from app.infrastructure.in_memory_repos import InMemoryEventRepository, InMemoryTicketRepository


def create_app() -> FastAPI:
    events = InMemoryEventRepository()
    tickets = InMemoryTicketRepository()
    lock = RLock()  # shared so book() and cancel() cannot interleave
    clock = lambda: datetime.now(timezone.utc)  # noqa: E731

    event_service = EventService(events, tickets, clock, lock)
    booking_service = BookingService(events, tickets, clock, lock, config.MAX_TICKETS_PER_BOOKING)

    app = FastAPI(title="Event Ticket Booking Service", version="1.0.0")
    # TODO: register_error_handlers(app) once api/errors.py is implemented.
    app.include_router(create_router(event_service, booking_service))
    return app


app = create_app()
