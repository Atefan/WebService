"""Domain entities and their business invariants. Imports nothing from the project except domain errors."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.domain.errors import EventNotFound, Forbidden, SoldOut


class EventStatus(str, Enum):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"


class TicketStatus(str, Enum):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"


@dataclass
class Event:
    id: int | None
    owner_id: str
    name: str
    capacity: int
    event_date: datetime
    booked: int = 0
    status: EventStatus = EventStatus.ACTIVE

    @property
    def available(self) -> int:
        """Derived, never stored: capacity - booked."""
        return self.capacity - self.booked

    def book(self, qty: int) -> None:
        if self.status != EventStatus.ACTIVE:
            raise EventNotFound(f"Event {self.id} not found.")
        if qty > self.available:
            raise SoldOut(f"Event {self.id} has only {self.available} ticket(s) left, requested {qty}.")
        self.booked += qty

    def cancel(self) -> None:
        """Set status to CANCELLED. The booked count is kept."""
        self.status = EventStatus.CANCELLED

    def ensure_owned_by(self, user_id: str) -> None:
        """Raise Forbidden if owner_id differs from user_id."""
        if self.owner_id != user_id:
            raise Forbidden(f"Event {self.id} belongs to another owner.")


@dataclass
class Ticket:
    id: int | None
    event_id: int
    user_id: str
    quantity: int
    booked_at: datetime
    status: TicketStatus = TicketStatus.ACTIVE

    def cancel(self) -> None:
        self.status = TicketStatus.CANCELLED
