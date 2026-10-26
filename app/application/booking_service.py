"""Use cases for ticket buyers."""

from threading import RLock

from app.application.ports import Clock, EventRepository, TicketRepository
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
        # TODO: idempotency key, a retried POST currently books twice.
        # TODO: multiple processes need a DB transaction, e.g.
        #   UPDATE events SET booked = booked + :q WHERE id = :id AND booked + :q <= capacity
        raise NotImplementedError

    def tickets_of(self, user_id: str) -> list[Ticket]:
        """All tickets of the user, including cancelled ones."""
        raise NotImplementedError
