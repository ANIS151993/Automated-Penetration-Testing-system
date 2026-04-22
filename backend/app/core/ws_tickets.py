from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass
from uuid import UUID

TICKET_TTL_SECONDS = 60
TICKET_BYTES = 32


class TicketError(Exception):
    """Raised when a ticket cannot be redeemed."""


@dataclass(frozen=True, slots=True)
class TicketScope:
    engagement_id: UUID
    execution_id: UUID


class WSTicketStore:
    """One-shot, short-TTL tickets for authenticating WebSocket handshakes.

    Tickets are issued by an authenticated HTTP call, then redeemed exactly
    once by the WS handshake. Prefer this to carrying the operator JWT in
    the WS URL — query strings leak via access logs, browser history, and
    Referer headers.
    """

    def __init__(self, *, ttl_seconds: int = TICKET_TTL_SECONDS) -> None:
        self._tickets: dict[str, tuple[TicketScope, float]] = {}
        self._lock = threading.Lock()
        self._ttl = ttl_seconds

    def issue(self, scope: TicketScope) -> str:
        ticket = secrets.token_urlsafe(TICKET_BYTES)
        expires_at = time.monotonic() + self._ttl
        with self._lock:
            self._prune_locked()
            self._tickets[ticket] = (scope, expires_at)
        return ticket

    def redeem(self, ticket: str, *, expected: TicketScope) -> TicketScope:
        now = time.monotonic()
        with self._lock:
            self._prune_locked(now=now)
            entry = self._tickets.pop(ticket, None)
        if entry is None:
            raise TicketError("ticket not found or already used")
        scope, expires_at = entry
        if expires_at < now:
            raise TicketError("ticket expired")
        if scope != expected:
            raise TicketError("ticket scope mismatch")
        return scope

    def _prune_locked(self, *, now: float | None = None) -> None:
        cutoff = now if now is not None else time.monotonic()
        expired = [k for k, (_, exp) in self._tickets.items() if exp < cutoff]
        for key in expired:
            self._tickets.pop(key, None)
