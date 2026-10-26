"""Domain errors. They carry a message (used as the HTTP `detail`) but know nothing about HTTP."""


class DomainError(Exception):
    """Base class for all business-rule violations."""


class ValidationError(DomainError):
    """Input breaks a business rule (e.g. capacity <= 0, date in the past)."""


class Unauthorized(DomainError):
    """Caller identity is missing."""


class Forbidden(DomainError):
    """Caller is known but not allowed to do this."""


class EventNotFound(DomainError):
    """Event does not exist or is cancelled."""


class SoldOut(DomainError):
    """Not enough tickets left for the requested quantity."""


class EventAlreadyTookPlace(DomainError):
    """The event date has passed, so the event can no longer be cancelled."""
