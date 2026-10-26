"""In-memory implementations of the repository ports. Data is lost on restart."""

from threading import Lock

from app.domain.models import Event, Ticket, TicketStatus


class InMemoryEventRepository:
    def __init__(self) -> None:
        self._events: dict[int, Event] = {}
        self._next_id = 1
        self._lock = Lock()  # protects id generation and dict mutation only

    def add(self, event: Event) -> Event:
        with self._lock:
            event.id = self._next_id
            self._next_id += 1
            self._events[event.id] = event
        return event

    def get(self, event_id: int) -> Event | None:
        with self._lock:
            return self._events.get(event_id)

    def list_all(self) -> list[Event]:
        with self._lock:
            return list(self._events.values())

    def save(self, event: Event) -> None:
        with self._lock:
            self._events[event.id] = event


class InMemoryTicketRepository:
    def __init__(self) -> None:
        self._tickets: dict[int, Ticket] = {}
        self._next_id = 1
        self._lock = Lock()

    def add(self, ticket: Ticket) -> Ticket:
        with self._lock:
            ticket.id = self._next_id
            self._next_id += 1
            self._tickets[ticket.id] = ticket
        return ticket

    def list_by_user(self, user_id: str) -> list[Ticket]:
        with self._lock:
            return [t for t in self._tickets.values() if t.user_id == user_id]

    def list_by_event(self, event_id: int) -> list[Ticket]:
        with self._lock:
            return [t for t in self._tickets.values() if t.event_id == event_id]

    def cancel_by_event(self, event_id: int) -> int:
        """Cancel all ACTIVE tickets of the event and return how many were cancelled."""
        with self._lock:
            active = [
                t
                for t in self._tickets.values()
                if t.event_id == event_id and t.status == TicketStatus.ACTIVE
            ]
            for ticket in active:
                ticket.cancel()
            return len(active)
