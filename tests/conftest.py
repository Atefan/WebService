from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock

import pytest

from app.application.booking_service import BookingService
from app.application.event_service import EventService
from app.infrastructure.in_memory_repos import InMemoryEventRepository, InMemoryTicketRepository

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
FUTURE = NOW + timedelta(days=30)


@dataclass
class Ctx:
    events: InMemoryEventRepository
    tickets: InMemoryTicketRepository
    event_service: EventService
    booking_service: BookingService


@pytest.fixture
def ctx() -> Ctx:
    events = InMemoryEventRepository()
    tickets = InMemoryTicketRepository()
    lock = RLock()
    clock = lambda: NOW  # noqa: E731
    return Ctx(
        events=events,
        tickets=tickets,
        event_service=EventService(events, tickets, clock, lock),
        booking_service=BookingService(events, tickets, clock, lock, max_tickets_per_booking=10),
    )
