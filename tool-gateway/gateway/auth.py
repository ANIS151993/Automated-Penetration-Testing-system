from __future__ import annotations

import base64
import hashlib
import hmac
import json
import socket
from datetime import datetime, timedelta, timezone
from ipaddress import ip_address, ip_network
from urllib.parse import urlparse


class ScopeViolation(Exception):
    """Raised when a requested target is outside the engagement scope."""


class GatewayAuthError(Exception):
    """Raised when a caller token cannot be verified."""


def validate_target_in_scope(target_ip: str, scope_cidrs: list[str]) -> None:
    ip = ip_address(target_ip)
    for cidr in scope_cidrs:
        if ip in ip_network(cidr, strict=False):
            return
    raise ScopeViolation(
        f"Target {target_ip} is outside authorized scope {scope_cidrs}"
    )


def resolve_target(target: str) -> str:
    try:
        ip_address(target)
        return target
    except ValueError:
        return socket.gethostbyname(target)


def extract_targets_from_command(tool_name: str, args: dict) -> list[str]:
    raw_targets: list[str] = []

    if "target" in args:
        raw_targets.append(args["target"])
    if "targets" in args:
        raw_targets.extend(args["targets"])
    if "host" in args:
        raw_targets.append(args["host"])
    if "url" in args:
        parsed = urlparse(args["url"])
        if parsed.hostname:
            raw_targets.append(parsed.hostname)

    if not raw_targets:
        raise ScopeViolation(
            f"Tool {tool_name} arguments do not expose a target for scope validation"
        )

    return [resolve_target(target) for target in raw_targets]


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def issue_gateway_token(
    *,
    subject: str,
    audience: str,
    secret: str,
    lifetime_seconds: int = 300,
) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": subject,
        "aud": audience,
        "exp": int((datetime.now(timezone.utc) + timedelta(seconds=lifetime_seconds)).timestamp()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
    }
    signing_input = ".".join(
        [
            _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
        ]
    )
    signature = hmac.new(
        secret.encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_b64url_encode(signature)}"


def verify_gateway_token(*, token: str, secret: str, audience: str) -> dict:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
    except ValueError as exc:
        raise GatewayAuthError("Malformed token") from exc

    signing_input = f"{encoded_header}.{encoded_payload}"
    expected_signature = hmac.new(
        secret.encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    signature = _b64url_decode(encoded_signature)
    if not hmac.compare_digest(signature, expected_signature):
        raise GatewayAuthError("Invalid token signature")

    payload = json.loads(_b64url_decode(encoded_payload))
    if payload.get("aud") != audience:
        raise GatewayAuthError("Invalid token audience")
    if int(payload.get("exp", 0)) < int(datetime.now(timezone.utc).timestamp()):
        raise GatewayAuthError("Expired token")
    if "sub" not in payload:
        raise GatewayAuthError("Missing token subject")
    return payload
