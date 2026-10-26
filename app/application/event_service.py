"""Use cases for event owners and for listing events."""

from datetime import datetime, timezone
from threading import RLock

from app.application.ports import Clock, EventRepository, TicketRepository
from app.domain.errors import EventAlreadyTookPlace, EventNotFound, ValidationError
from app.domain.models import Event, EventStatus


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
        name = name.strip()
        if not name:
            raise ValidationError("Event name must not be empty.")
        if capacity <= 0:
            raise ValidationError("Capacity must be greater than 0.")
        if event_date.tzinfo is None:
            event_date = event_date.replace(tzinfo=timezone.utc)  # naive input is treated as UTC
        if event_date <= self._clock():
            raise ValidationError("Event date must be in the future.")
        return self._events.add(
            Event(id=None, owner_id=user_id, name=name, capacity=capacity, event_date=event_date)
        )

    def list_upcoming(self) -> list[Event]:
        """ACTIVE events with event_date > now. Sold-out events are included."""
        now = self._clock()
        return [e for e in self._events.list_all() if self._is_upcoming(e, now)]

    def get(self, event_id: int) -> Event:
        """404 unless the event is upcoming, so it is visible under the same rule as list_upcoming."""
        event = self._events.get(event_id)
        if event is None or not self._is_upcoming(event, self._clock()):
            raise EventNotFound(f"Event {event_id} not found.")
        return event

    @staticmethod
    def _is_upcoming(event: Event, now: datetime) -> bool:
        return event.status == EventStatus.ACTIVE and event.event_date > now

    def cancel(self, user_id: str, event_id: int) -> None:
        """Under lock: 404 if missing, ensure_owned_by, idempotent, 409 if past, cancel event and its tickets."""
        # TODO: multiple processes need a DB transaction instead of this in-process lock.
        with self._lock:
            event = self._events.get(event_id)
            if event is None:
                raise EventNotFound(f"Event {event_id} not found.")
            event.ensure_owned_by(user_id)
            if event.status == EventStatus.CANCELLED:
                return
            if event.event_date <= self._clock():
                # Its tickets were used, so they must not turn into CANCELLED.
                raise EventAlreadyTookPlace(f"Event {event_id} already took place and cannot be cancelled.")
            event.cancel()
            self._events.save(event)
            self._tickets.cancel_by_event(event_id)

    def stats(self, user_id: str, event_id: int) -> Event:
        """404 if missing, ensure_owned_by; the caller reads capacity / booked / available."""
        event = self._events.get(event_id)
        if event is None:
            raise EventNotFound(f"Event {event_id} not found.")
        event.ensure_owned_by(user_id)
        return event
