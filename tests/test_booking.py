from datetime import timedelta

import pytest

from app.domain.errors import EventNotFound, SoldOut, ValidationError
from app.domain.models import TicketStatus
from tests.conftest import FUTURE, NOW


def make_event(ctx, capacity=10):
    return ctx.event_service.create("owner", "Event1", capacity, FUTURE)


def test_book_happy_path(ctx):
    event = make_event(ctx)
    ticket = ctx.booking_service.book("alice", event.id, 3)
    assert ticket.id == 1
    assert (ticket.event_id, ticket.user_id, ticket.quantity) == (event.id, "alice", 3)
    assert ticket.status == TicketStatus.ACTIVE
    assert ticket.booked_at == NOW
    assert event.available == 7


def test_book_more_than_available_raises_sold_out_and_stores_nothing(ctx):
    event = make_event(ctx, capacity=2)
    with pytest.raises(SoldOut):
        ctx.booking_service.book("alice", event.id, 3)
    assert event.booked == 0
    assert ctx.booking_service.tickets_of("alice") == []


def test_book_unknown_event_raises_not_found(ctx):
    with pytest.raises(EventNotFound):
        ctx.booking_service.book("alice", 99, 1)


def test_book_cancelled_event_raises_not_found(ctx):
    event = make_event(ctx)
    ctx.event_service.cancel("owner", event.id)
    with pytest.raises(EventNotFound):
        ctx.booking_service.book("alice", event.id, 1)


def test_book_past_event_is_rejected(ctx):
    event = make_event(ctx)
    event.event_date = NOW - timedelta(minutes=1)
    with pytest.raises(EventNotFound):
        ctx.booking_service.book("alice", event.id, 1)


@pytest.mark.parametrize("qty", [0, -1, 11])
def test_book_rejects_invalid_quantity(ctx, qty):
    event = make_event(ctx)
    with pytest.raises(ValidationError):
        ctx.booking_service.book("alice", event.id, qty)


def test_tickets_of_returns_only_own_tickets_with_status(ctx):
    event = make_event(ctx)
    ctx.booking_service.book("alice", event.id, 1)
    ctx.booking_service.book("bob", event.id, 2)
    ctx.event_service.cancel("owner", event.id)
    mine = ctx.booking_service.tickets_of("alice")
    assert [(t.user_id, t.status) for t in mine] == [("alice", TicketStatus.CANCELLED)]
