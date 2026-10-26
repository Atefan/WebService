"""Use cases for ticket buyers."""

from threading import RLock

from app.application.ports import Clock, EventRepository, TicketRepository
from app.domain.errors import EventNotFound, ValidationError
from app.domain.models import Ticket


class BookingService:
    def __init__(
        self,
        events: EventRepository,
        tickets: TicketRepository,
        clock: Clock,
        lock: RLock,
        max_tickets_per_booking: int,
    ) -> None:
        self._events = events
        self._tickets = tickets
        self._clock = clock
        self._lock = lock
        self._max_tickets_per_booking = max_tickets_per_booking

    def book(self, user_id: str, event_id: int, qty: int) -> Ticket:
        """Validate 1 <= qty <= max; under lock: get (404), date still future, event.book, save, add ticket."""
        if not 1 <= qty <= self._max_tickets_per_booking:
            raise ValidationError(f"Quantity must be between 1 and {self._max_tickets_per_booking}.")
        # TODO: idempotency key, a retried POST currently books twice.
        # TODO: multiple processes need a DB transaction, e.g.
        #   UPDATE events SET booked = booked + :q WHERE id = :id AND booked + :q <= capacity
        with self._lock:
            event = self._events.get(event_id)
            if event is None:
                raise EventNotFound(f"Event {event_id} not found.")
            now = self._clock()
            if event.event_date <= now:
                raise EventNotFound(f"Event {event_id} has already taken place.")
            event.book(qty)
            self._events.save(event)
            return self._tickets.add(
                Ticket(id=None, event_id=event_id, user_id=user_id, quantity=qty, booked_at=now)
            )

    def tickets_of(self, user_id: str) -> list[Ticket]:
        """All tickets of the user, including cancelled ones."""
        return self._tickets.list_by_user(user_id)
