"""HTTP routes under /api/v1."""

from fastapi import APIRouter

from app.application.booking_service import BookingService
from app.application.event_service import EventService


def create_router(event_service: EventService, booking_service: BookingService) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.get("/health", summary="Liveness check")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    # TODO (in this order, one vertical slice at a time):
    #   GET    /events                  user   list upcoming events
    #   POST   /events                  owner  create event, 201 + Location
    #   POST   /events/{id}/tickets     user   book tickets
    #   GET    /tickets                 user   my tickets
    #   GET    /events/{id}/stats       owner  capacity / booked / available
    #   DELETE /events/{id}             owner  soft delete, 204

    return router
