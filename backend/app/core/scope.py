from __future__ import annotations

import socket
from ipaddress import ip_address, ip_network
from urllib.parse import urlparse


class ScopeViolation(Exception):
    """Raised when a tool target falls outside the engagement scope."""


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
