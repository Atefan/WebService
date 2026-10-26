"""HTTP routes under /api/v1."""

from fastapi import APIRouter, Depends, Response

from app.api.deps import Caller, get_caller, require_owner
from app.api.errors import problem_example
from app.api.schemas import EventCreate, EventOut, EventStats, TicketCreate, TicketOut
from app.application.booking_service import BookingService
from app.application.event_service import EventService

_BAD_REQUEST = problem_example(
    400, "validation_error", "Invalid request", "Capacity must be greater than 0.", "/api/v1/events"
)
_UNAUTHORIZED = problem_example(
    401, "unauthorized", "Missing or empty X-User-Id header",
    "Send your user id in the X-User-Id header.", "/api/v1/events",
)
_FORBIDDEN = problem_example(403, "forbidden", "Not allowed", "Only event owners may do this.", "/api/v1/events")
_NOT_FOUND = problem_example(404, "event_not_found", "Event not found", "Event 7 not found.", "/api/v1/events/7")
_SOLD_OUT = problem_example(
    409, "sold_out", "Not enough tickets left",
    "Event 7 has only 1 ticket(s) left, requested 2.", "/api/v1/events/7/tickets",
)
_ALREADY_TOOK_PLACE = problem_example(
    409, "event_already_took_place", "Event already took place",
    "Event 7 already took place and cannot be cancelled.", "/api/v1/events/7",
)


def create_router(event_service: EventService, booking_service: BookingService) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.get("/health", summary="Liveness check")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.get(
        "/events",
        response_model=list[EventOut],
        tags=["events"],
        dependencies=[Depends(get_caller)],
        summary="List upcoming events",
        description="Events that are not cancelled and have not happened yet. Sold-out events are listed with `availableTickets: 0`.",
        responses={401: _UNAUTHORIZED},
    )
    def list_events() -> list[EventOut]:
        return [EventOut.from_domain(e) for e in event_service.list_upcoming()]

    @router.post(
        "/events",
        response_model=EventOut,
        status_code=201,
        tags=["owner"],
        summary="Create an event",
        description="Owner only. The caller becomes the event's owner.",
        responses={400: _BAD_REQUEST, 401: _UNAUTHORIZED, 403: _FORBIDDEN},
    )
    def create_event(
        payload: EventCreate, response: Response, caller: Caller = Depends(require_owner)
    ) -> EventOut:
        event = event_service.create(caller.user_id, payload.name, payload.available_tickets, payload.event_date)
        response.headers["Location"] = f"/api/v1/events/{event.id}"
        return EventOut.from_domain(event)

    @router.post(
        "/events/{event_id}/tickets",
        response_model=TicketOut,
        status_code=201,
        tags=["tickets"],
        summary="Book tickets for an event",
        description="Books `quantity` tickets (default 1). Cancelled, past and unknown events return 404.",
        responses={400: _BAD_REQUEST, 401: _UNAUTHORIZED, 404: _NOT_FOUND, 409: _SOLD_OUT},
    )
    def book_tickets(
        event_id: int, payload: TicketCreate | None = None, caller: Caller = Depends(get_caller)
    ) -> TicketOut:
        quantity = payload.quantity if payload else 1
        return TicketOut.from_domain(booking_service.book(caller.user_id, event_id, quantity))

    @router.get(
        "/tickets",
        response_model=list[TicketOut],
        tags=["tickets"],
        summary="List my tickets",
        description="All tickets of the caller, including cancelled ones (`status: CANCELLED`).",
        responses={401: _UNAUTHORIZED},
    )
    def my_tickets(caller: Caller = Depends(get_caller)) -> list[TicketOut]:
        return [TicketOut.from_domain(t) for t in booking_service.tickets_of(caller.user_id)]

    @router.get(
        "/events/{event_id}/stats",
        response_model=EventStats,
        tags=["owner"],
        summary="Ticket numbers for an event",
        description="Owner of the event only. Also works for cancelled events.",
        responses={401: _UNAUTHORIZED, 403: _FORBIDDEN, 404: _NOT_FOUND},
    )
    def event_stats(event_id: int, caller: Caller = Depends(require_owner)) -> EventStats:
        return EventStats.from_domain(event_service.stats(caller.user_id, event_id))

    @router.delete(
        "/events/{event_id}",
        status_code=204,
        tags=["owner"],
        summary="Cancel an event",
        description=(
            "Owner of the event only. Soft delete: the event and all its tickets become CANCELLED, "
            "nothing is erased. Repeating the call is safe. Events that already took place cannot be cancelled."
        ),
        responses={401: _UNAUTHORIZED, 403: _FORBIDDEN, 404: _NOT_FOUND, 409: _ALREADY_TOOK_PLACE},
    )
    def cancel_event(event_id: int, caller: Caller = Depends(require_owner)) -> Response:
        event_service.cancel(caller.user_id, event_id)
        return Response(status_code=204)

    return router
