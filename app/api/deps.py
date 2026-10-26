"""Authentication helpers. Identity is the X-User-Id header (no real authentication)."""

from dataclasses import dataclass

from fastapi import Depends, Header

from app import config
from app.domain.errors import Forbidden, Unauthorized


@dataclass(frozen=True)
class Caller:
    user_id: str
    is_owner: bool


def get_caller(
    x_user_id: str | None = Header(
        default=None,
        description="Id of the calling user. There is no login; whoever you claim to be, you are.",
        examples=["alice"],
    ),
) -> Caller:
    """Read X-User-Id; missing or blank -> Unauthorized (401). Returns Caller(user_id, is_owner)."""
    # TODO: replace with real auth (JWT/OIDC). Only this file should change; services only see user_id.
    if x_user_id is None or not x_user_id.strip():
        raise Unauthorized("Send your user id in the X-User-Id header.")
    user_id = x_user_id.strip()
    return Caller(user_id=user_id, is_owner=user_id in config.OWNER_IDS)


def require_owner(caller: Caller = Depends(get_caller)) -> Caller:
    """Depends on get_caller; Forbidden (403) unless caller.is_owner."""
    if not caller.is_owner:
        raise Forbidden("Only event owners may do this.")
    return caller
