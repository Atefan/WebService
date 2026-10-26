"""Interfaces the application layer needs from the outside world (implemented in infrastructure/)."""

from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from app.domain.models import Event, Ticket

# Injected so "upcoming" and "past date" are testable. Default: datetime.now(timezone.utc).
Clock = Callable[[], datetime]


class EventRepository(Protocol):
    def add(self, event: Event) -> Event: ...

    def get(self, event_id: int) -> Event | None: ...

    def list_all(self) -> list[Event]: ...

    def save(self, event: Event) -> None: ...


class TicketRepository(Protocol):
    def add(self, ticket: Ticket) -> Ticket: ...

    def list_by_user(self, user_id: str) -> list[Ticket]: ...

    def list_by_event(self, event_id: int) -> list[Ticket]: ...

    def cancel_by_event(self, event_id: int) -> int: ...
