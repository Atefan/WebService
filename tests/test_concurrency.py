import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import RLock

from app.application.booking_service import BookingService
from app.application.event_service import EventService
from app.domain.errors import EventNotFound, SoldOut
from app.domain.models import Ticket, TicketStatus
from app.infrastructure.in_memory_repos import InMemoryEventRepository, InMemoryTicketRepository
from tests.conftest import FUTURE, NOW


def test_parallel_bookings_never_oversell(ctx):
    # Regression check. Objects are shared by reference and Event.book() has no gap between its
    # check and its update, so this passes even without the lock. A DB-backed repo would not.
    event = ctx.event_service.create("owner", "Event1", 10, FUTURE)

    def try_book(i: int) -> str:
        try:
            ctx.booking_service.book(f"user{i}", event.id, 1)
            return "ok"
        except SoldOut:
            return "sold_out"

    with ThreadPoolExecutor(max_workers=50) as pool:
        results = list(pool.map(try_book, range(50)))

    assert results.count("ok") == 10
    assert results.count("sold_out") == 40
    assert event.booked == 10
    assert len(ctx.tickets.list_by_event(event.id)) == 10


class SlowTicketRepository(InMemoryTicketRepository):
    """Widens the gap between event.book() and the ticket being stored so a missing lock shows up."""

    def add(self, ticket: Ticket) -> Ticket:
        time.sleep(0.02)
        return super().add(ticket)


def test_parallel_book_and_cancel_leaves_no_active_ticket_on_cancelled_event():
    # Fails every time if the services stop sharing the lock: a booking that already passed the
    # status check stores its ACTIVE ticket after cancel() has cancelled the existing ones.
    events, tickets, lock = InMemoryEventRepository(), SlowTicketRepository(), RLock()
    clock = lambda: NOW  # noqa: E731
    event_service = EventService(events, tickets, clock, lock)
    booking_service = BookingService(events, tickets, clock, lock, max_tickets_per_booking=10)
    event = event_service.create("owner", "Event1", 1000, FUTURE)

    def try_book(i: int) -> None:
        try:
            booking_service.book(f"user{i}", event.id, 1)
        except EventNotFound:
            pass  # booking arrived after the cancel

    with ThreadPoolExecutor(max_workers=60) as pool:
        futures = [pool.submit(try_book, i) for i in range(30)]
        time.sleep(0.005)  # cancel while bookings are in flight
        futures.append(pool.submit(event_service.cancel, "owner", event.id))
        for f in futures:
            f.result()

    active = [t for t in tickets.list_by_event(event.id) if t.status == TicketStatus.ACTIVE]
    assert active == []
