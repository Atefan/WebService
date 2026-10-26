"""Use cases for event owners and for listing events."""

from datetime import datetime
from threading import RLock

from app.application.ports import Clock, EventRepository, TicketRepository
from app.domain.models import Event


class EventService:
    def __init__(
        self,
        events: EventRepository,
        tickets: TicketRepository,
        clock: Clock,
        lock: RLock,
    ) -> None:
        self._events = events
        self._tickets = tickets
        self._clock = clock
        self._lock = lock

    def create(self, user_id: str, name: str, capacity: int, event_date: datetime) -> Event:
        """Validate (capacity > 0, name non-empty, date in future), then add Event(owner_id=user_id)."""
        raise NotImplementedError

    def list_upcoming(self) -> list[Event]:
        """ACTIVE events with event_date > now. Sold-out events are included."""
        raise NotImplementedError

    def cancel(self, user_id: str, event_id: int) -> None:
        """Under lock: 404 if missing, ensure_owned_by, idempotent, cancel event and its tickets."""
        # TODO: multiple processes need a DB transaction instead of this in-process lock.
        raise NotImplementedError

    def stats(self, user_id: str, event_id: int) -> Event:
        """404 if missing, ensure_owned_by; the caller reads capacity / booked / available."""
        raise NotImplementedError
