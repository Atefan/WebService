from datetime import datetime, timedelta

import pytest

from app.domain.errors import EventAlreadyTookPlace, EventNotFound, Forbidden, ValidationError
from app.domain.models import EventStatus, TicketStatus
from tests.conftest import FUTURE, NOW


def create(ctx, user_id="owner", name="Event1", capacity=10, date=FUTURE):
    return ctx.event_service.create(user_id, name, capacity, date)


def test_create_sets_owner_and_defaults(ctx):
    event = create(ctx, user_id="olga")
    assert event.id == 1
    assert event.owner_id == "olga"
    assert event.booked == 0
    assert event.status == EventStatus.ACTIVE


def test_create_treats_naive_date_as_utc(ctx):
    event = create(ctx, date=datetime(2026, 12, 1, 20, 0))
    assert event.event_date.utcoffset() == timedelta(0)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"name": "   "},
        {"capacity": 0},
        {"capacity": -5},
        {"date": NOW - timedelta(days=1)},
        {"date": NOW},
    ],
)
def test_create_rejects_invalid_input(ctx, kwargs):
    with pytest.raises(ValidationError):
        create(ctx, **kwargs)


def test_list_upcoming_excludes_cancelled_and_past_events(ctx):
    upcoming = create(ctx, name="upcoming")
    cancelled = create(ctx, name="cancelled")
    ctx.event_service.cancel("owner", cancelled.id)
    past = create(ctx, name="past")
    past.event_date = NOW - timedelta(days=1)  # moved into the past after creation
    assert ctx.event_service.list_upcoming() == [upcoming]


def test_list_upcoming_keeps_sold_out_events(ctx):
    event = create(ctx, capacity=2)
    ctx.booking_service.book("alice", event.id, 2)
    listed = ctx.event_service.list_upcoming()
    assert listed == [event]
    assert listed[0].available == 0


def test_cancel_marks_event_and_tickets_cancelled(ctx):
    event = create(ctx)
    ticket = ctx.booking_service.book("alice", event.id, 2)
    ctx.event_service.cancel("owner", event.id)
    assert ctx.events.get(event.id).status == EventStatus.CANCELLED
    assert ticket.status == TicketStatus.CANCELLED


def test_cancel_by_non_owner_is_forbidden_and_changes_nothing(ctx):
    event = create(ctx, user_id="olga")
    with pytest.raises(Forbidden):
        ctx.event_service.cancel("mallory", event.id)
    assert event.status == EventStatus.ACTIVE


def test_cancel_past_event_is_rejected_and_changes_nothing(ctx):
    event = create(ctx)
    ticket = ctx.booking_service.book("alice", event.id, 2)
    event.event_date = NOW - timedelta(minutes=1)  # the event has taken place
    with pytest.raises(EventAlreadyTookPlace):
        ctx.event_service.cancel("owner", event.id)
    assert event.status == EventStatus.ACTIVE
    assert ticket.status == TicketStatus.ACTIVE


def test_repeating_cancel_after_the_date_is_still_a_no_op(ctx):
    event = create(ctx)
    ctx.event_service.cancel("owner", event.id)
    event.event_date = NOW - timedelta(days=1)
    ctx.event_service.cancel("owner", event.id)  # already cancelled, so no error


def test_cancel_unknown_event_raises_not_found(ctx):
    with pytest.raises(EventNotFound):
        ctx.event_service.cancel("owner", 99)


def test_cancel_is_idempotent(ctx):
    event = create(ctx)
    ctx.event_service.cancel("owner", event.id)
    ctx.event_service.cancel("owner", event.id)  # no error
    assert event.status == EventStatus.CANCELLED


def test_stats_numbers(ctx):
    event = create(ctx, capacity=10)
    ctx.booking_service.book("alice", event.id, 3)
    ctx.booking_service.book("bob", event.id, 2)
    stats = ctx.event_service.stats("owner", event.id)
    assert (stats.capacity, stats.booked, stats.available) == (10, 5, 5)


def test_stats_still_work_for_cancelled_event(ctx):
    event = create(ctx, capacity=10)
    ctx.booking_service.book("alice", event.id, 4)
    ctx.event_service.cancel("owner", event.id)
    assert ctx.event_service.stats("owner", event.id).booked == 4


def test_stats_forbidden_for_other_owner_and_not_found_for_unknown(ctx):
    event = create(ctx, user_id="olga")
    with pytest.raises(Forbidden):
        ctx.event_service.stats("mallory", event.id)
    with pytest.raises(EventNotFound):
        ctx.event_service.stats("olga", 99)
