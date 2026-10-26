from datetime import datetime, timezone

import pytest

from app.domain.errors import EventNotFound, Forbidden, SoldOut
from app.domain.models import Event, EventStatus, Ticket, TicketStatus


def make_event(capacity: int = 10, booked: int = 0) -> Event:
    return Event(
        id=1,
        owner_id="owner",
        name="Event1",
        capacity=capacity,
        event_date=datetime(2123, 1, 4, tzinfo=timezone.utc),
        booked=booked,
    )


def test_available_is_capacity_minus_booked():
    assert make_event(capacity=10, booked=3).available == 7


def test_book_increases_booked():
    event = make_event(capacity=10)
    event.book(4)
    assert event.booked == 4
    assert event.available == 6


def test_book_exactly_remaining_is_allowed():
    event = make_event(capacity=5, booked=3)
    event.book(2)
    assert event.available == 0


def test_book_more_than_available_raises_sold_out():
    event = make_event(capacity=5, booked=4)
    with pytest.raises(SoldOut) as error:
        event.book(2)
    assert "only 1 ticket(s) left, requested 2" in str(error.value)
    assert event.booked == 4  # unchanged on failure


def test_book_cancelled_event_raises_not_found():
    event = make_event()
    event.cancel()
    with pytest.raises(EventNotFound):
        event.book(1)


def test_cancel_keeps_booked_count():
    event = make_event(capacity=10, booked=6)
    event.cancel()
    assert event.status == EventStatus.CANCELLED
    assert event.booked == 6


def test_ensure_owned_by_accepts_owner_and_rejects_others():
    event = make_event()
    event.ensure_owned_by("owner")
    with pytest.raises(Forbidden):
        event.ensure_owned_by("someone-else")


def test_ticket_cancel():
    ticket = Ticket(
        id=1,
        event_id=1,
        user_id="alice",
        quantity=2,
        booked_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert ticket.status == TicketStatus.ACTIVE
    ticket.cancel()
    assert ticket.status == TicketStatus.CANCELLED
