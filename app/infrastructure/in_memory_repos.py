"""In-memory implementations of the repository ports. Data is lost on restart."""

from threading import Lock

from app.domain.models import Event, Ticket


class InMemoryEventRepository:
    def __init__(self) -> None:
        self._events: dict[int, Event] = {}
        self._next_id = 1
        self._lock = Lock()  # protects id generation and dict mutation only

    def add(self, event: Event) -> Event:
        raise NotImplementedError

    def get(self, event_id: int) -> Event | None:
        raise NotImplementedError

    def list_all(self) -> list[Event]:
        raise NotImplementedError

    def save(self, event: Event) -> None:
        raise NotImplementedError


class InMemoryTicketRepository:
    def __init__(self) -> None:
        self._tickets: dict[int, Ticket] = {}
        self._next_id = 1
        self._lock = Lock()

    def add(self, ticket: Ticket) -> Ticket:
        raise NotImplementedError

    def list_by_user(self, user_id: str) -> list[Ticket]:
        raise NotImplementedError

    def list_by_event(self, event_id: int) -> list[Ticket]:
        raise NotImplementedError

    def cancel_by_event(self, event_id: int) -> int:
        raise NotImplementedError
