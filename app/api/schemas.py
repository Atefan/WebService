"""Pydantic request/response models. camelCase on the wire. Pydantic lives only in api/.

Business rules (capacity > 0, date in the future, quantity limits) are checked in the services,
so they are defined in one place. These models only check types.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.domain.models import Event, Ticket, TicketStatus


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class EventCreate(ApiModel):
    name: str = Field(description="Event name.", examples=["Event1"])
    available_tickets: int = Field(description="Number of tickets for sale (the event's capacity).", examples=[400])
    event_date: datetime = Field(
        description="ISO-8601 date and time. Must be in the future. No timezone means UTC.",
        examples=["2123-01-04T20:00:00Z"],
    )

    model_config = ConfigDict(
        json_schema_extra={"example": {"name": "Event1", "availableTickets": 400, "eventDate": "2123-01-04T20:00:00Z"}}
    )


class EventOut(ApiModel):
    id: int = Field(description="Event id.", examples=[7])
    name: str = Field(description="Event name.", examples=["Event1"])
    available_tickets: int = Field(description="Tickets still available. 0 means sold out.", examples=[400])
    event_date: datetime = Field(description="When the event takes place (UTC).", examples=["2123-01-04T20:00:00Z"])

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"id": 7, "name": "Event1", "availableTickets": 400, "eventDate": "2123-01-04T20:00:00Z"}
        }
    )

    @classmethod
    def from_domain(cls, event: Event) -> "EventOut":
        return cls(id=event.id, name=event.name, available_tickets=event.available, event_date=event.event_date)


class TicketCreate(ApiModel):
    quantity: int = Field(default=1, description="How many tickets to book (1 to 10 by default).", examples=[2])


class TicketOut(ApiModel):
    id: int = Field(description="Ticket id.", examples=[12])
    event_id: int = Field(description="Id of the event the ticket is for.", examples=[7])
    user_id: str = Field(description="Id of the user who booked.", examples=["alice"])
    quantity: int = Field(description="Number of seats this booking covers.", examples=[2])
    booked_at: datetime = Field(description="When the booking was made (UTC).", examples=["2026-06-01T12:00:00Z"])
    status: TicketStatus = Field(
        description="ACTIVE, or CANCELLED when the event was cancelled.", examples=["ACTIVE"]
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 12, "eventId": 7, "userId": "alice", "quantity": 2,
                "bookedAt": "2026-06-01T12:00:00Z", "status": "ACTIVE",
            }
        }
    )

    @classmethod
    def from_domain(cls, ticket: Ticket) -> "TicketOut":
        return cls(
            id=ticket.id, event_id=ticket.event_id, user_id=ticket.user_id, quantity=ticket.quantity,
            booked_at=ticket.booked_at, status=ticket.status,
        )


class EventStats(ApiModel):
    capacity: int = Field(description="Total tickets the event was created with.", examples=[400])
    booked: int = Field(description="Tickets booked so far (kept after cancellation).", examples=[120])
    available: int = Field(description="capacity - booked.", examples=[280])

    model_config = ConfigDict(json_schema_extra={"example": {"capacity": 400, "booked": 120, "available": 280}})

    @classmethod
    def from_domain(cls, event: Event) -> "EventStats":
        return cls(capacity=event.capacity, booked=event.booked, available=event.available)
