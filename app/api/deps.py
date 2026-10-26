"""Authentication helpers. Identity is the X-User-Id header (no real authentication)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Caller:
    user_id: str
    is_owner: bool


def get_caller() -> Caller:
    """Read X-User-Id; missing or blank -> Unauthorized (401). Returns Caller(user_id, is_owner)."""
    # TODO: replace with real auth (JWT/OIDC). Only this file should change; services only see user_id.
    raise NotImplementedError


def require_owner() -> Caller:
    """Depends on get_caller; Forbidden (403) unless caller.is_owner."""
    raise NotImplementedError
