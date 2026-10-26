from datetime import datetime, timezone
from threading import Thread

from app.domain.models import Event, Ticket, TicketStatus
from app.infrastructure.in_memory_repos import InMemoryEventRepository, InMemoryTicketRepository

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def new_event(name: str = "Event1") -> Event:
    return Event(id=None, owner_id="owner", name=name, capacity=10, event_date=datetime(2123, 1, 4, tzinfo=timezone.utc))


def new_ticket(event_id: int = 1, user_id: str = "alice") -> Ticket:
    return Ticket(id=None, event_id=event_id, user_id=user_id, quantity=1, booked_at=NOW)


def test_event_add_assigns_incrementing_ids():
    repo = InMemoryEventRepository()
    assert repo.add(new_event()).id == 1
    assert repo.add(new_event()).id == 2


def test_event_get_returns_none_for_unknown_id():
    assert InMemoryEventRepository().get(99) is None


def test_event_get_and_list_all():
    repo = InMemoryEventRepository()
    first = repo.add(new_event("A"))
    second = repo.add(new_event("B"))
    assert repo.get(first.id) is first
    assert repo.list_all() == [first, second]


def test_event_save_persists_changes():
    repo = InMemoryEventRepository()
    event = repo.add(new_event())
    event.book(3)
    repo.save(event)
    assert repo.get(event.id).booked == 3


def test_event_ids_are_unique_under_concurrency():
    repo = InMemoryEventRepository()
    threads = [Thread(target=lambda: repo.add(new_event())) for _ in range(100)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len({e.id for e in repo.list_all()}) == 100


def test_ticket_add_assigns_ids():
    repo = InMemoryTicketRepository()
    assert repo.add(new_ticket()).id == 1
    assert repo.add(new_ticket()).id == 2


def test_ticket_list_by_user_and_by_event():
    repo = InMemoryTicketRepository()
    a = repo.add(new_ticket(event_id=1, user_id="alice"))
    b = repo.add(new_ticket(event_id=2, user_id="alice"))
    c = repo.add(new_ticket(event_id=1, user_id="bob"))
    assert repo.list_by_user("alice") == [a, b]
    assert repo.list_by_user("nobody") == []
    assert repo.list_by_event(1) == [a, c]


def test_cancel_by_event_only_touches_that_event_and_returns_count():
    repo = InMemoryTicketRepository()
    a = repo.add(new_ticket(event_id=1))
    b = repo.add(new_ticket(event_id=1))
    other = repo.add(new_ticket(event_id=2))
    assert repo.cancel_by_event(1) == 2
    assert a.status == b.status == TicketStatus.CANCELLED
    assert other.status == TicketStatus.ACTIVE


def test_cancel_by_event_is_idempotent():
    repo = InMemoryTicketRepository()
    repo.add(new_ticket(event_id=1))
    assert repo.cancel_by_event(1) == 1
    assert repo.cancel_by_event(1) == 0
