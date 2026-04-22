from __future__ import annotations

import time
from uuid import uuid4

import pytest

from app.core.ws_tickets import TicketError, TicketScope, WSTicketStore


def _scope() -> TicketScope:
    return TicketScope(engagement_id=uuid4(), execution_id=uuid4())


def test_issue_and_redeem_roundtrip():
    store = WSTicketStore()
    scope = _scope()
    ticket = store.issue(scope)
    redeemed = store.redeem(ticket, expected=scope)
    assert redeemed == scope


def test_redeem_is_single_use():
    store = WSTicketStore()
    scope = _scope()
    ticket = store.issue(scope)
    store.redeem(ticket, expected=scope)
    with pytest.raises(TicketError):
        store.redeem(ticket, expected=scope)


def test_redeem_with_wrong_scope_is_rejected_and_consumed():
    store = WSTicketStore()
    issued = _scope()
    other = _scope()
    ticket = store.issue(issued)
    with pytest.raises(TicketError):
        store.redeem(ticket, expected=other)
    # A scope mismatch still burns the ticket — a second attempt (even with
    # the right scope) must fail, so attackers cannot brute-force scopes.
    with pytest.raises(TicketError):
        store.redeem(ticket, expected=issued)


def test_redeem_expired_ticket_is_rejected():
    store = WSTicketStore(ttl_seconds=0)
    scope = _scope()
    ticket = store.issue(scope)
    time.sleep(0.01)
    with pytest.raises(TicketError):
        store.redeem(ticket, expected=scope)


def test_redeem_unknown_ticket_is_rejected():
    store = WSTicketStore()
    with pytest.raises(TicketError):
        store.redeem("nope", expected=_scope())
