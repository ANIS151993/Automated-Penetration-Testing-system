import socket

import pytest

from app.core.scope import ScopeViolation, extract_targets_from_command, validate_target_in_scope


def test_validate_target_in_scope_accepts_in_scope_ip() -> None:
    validate_target_in_scope("172.20.32.59", ["172.20.32.0/18"])


def test_validate_target_in_scope_rejects_out_of_scope_ip() -> None:
    with pytest.raises(ScopeViolation):
        validate_target_in_scope("8.8.8.8", ["172.20.32.0/18"])


def test_extract_targets_from_command_resolves_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "gethostbyname", lambda hostname: "172.20.32.59")

    targets = extract_targets_from_command(
        "http_probe",
        {"url": "https://target.lab.local/login"},
    )

    assert targets == ["172.20.32.59"]


def test_extract_targets_from_command_requires_a_target() -> None:
    with pytest.raises(ScopeViolation):
        extract_targets_from_command("nmap", {"ports": "80,443"})
