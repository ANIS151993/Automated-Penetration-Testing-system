from __future__ import annotations

from copy import deepcopy
import re
from typing import Any
from urllib.parse import urlparse

_SECURITY_HEADERS = (
    "Content-Security-Policy",
    "Strict-Transport-Security",
    "X-Content-Type-Options",
    "X-Frame-Options",
    "Referrer-Policy",
)

_NMAP_SERVICE_LINE = re.compile(
    r"^(?P<port>\d+)/(?P<protocol>[a-z0-9]+)\s+open\s+(?P<service>[a-z0-9_-]+)"
    r"(?:\s+(?P<details>.+))?$",
    re.IGNORECASE,
)
_CURL_ERROR_LINE = re.compile(r"^curl: \((?P<code>\d+)\) (?P<message>.+)$")
_CONNECTION_REFUSED_LINE = re.compile(
    r"Failed to connect to (?P<host>[^ ]+) port (?P<port>\d+).+Connection refused",
    re.IGNORECASE,
)


def enrich_execution_document(document: dict[str, Any]) -> dict[str, Any]:
    if isinstance(document.get("parsed"), dict):
        return document

    enriched = deepcopy(document)
    invocation = (
        enriched["invocation"]
        if isinstance(enriched.get("invocation"), dict)
        else {}
    )
    tool_name = _coerce_text(enriched.get("tool_name")) or _coerce_text(
        invocation.get("tool_name")
    )
    operation_name = _coerce_text(enriched.get("operation_name")) or _coerce_text(
        invocation.get("operation_name")
    )
    stdout_lines = _output_lines(enriched.get("events"), event_type="stdout")
    stderr_lines = _output_lines(enriched.get("events"), event_type="stderr")
    observed_at = (
        _coerce_text(enriched.get("completed_at"))
        or _coerce_text(enriched.get("started_at"))
        or _coerce_text(invocation.get("created_at"))
    )
    operation_label = (
        f"{tool_name}.{operation_name}" if tool_name and operation_name else "unknown"
    )

    parsed = _empty_parsed()
    targets = _targets(invocation)

    if tool_name == "nmap" and operation_name == "service_scan":
        parsed = _parse_nmap_service_scan(
            invocation=invocation,
            stdout_lines=stdout_lines,
            operation_label=operation_label,
            observed_at=observed_at,
        )
    elif tool_name == "nmap" and operation_name == "os_detection":
        parsed = _parse_nmap_os_detection(
            invocation=invocation,
            stdout_lines=stdout_lines,
            operation_label=operation_label,
            observed_at=observed_at,
        )
    elif tool_name == "http_probe" and operation_name == "fetch_headers":
        parsed = _parse_http_headers(
            invocation=invocation,
            stdout_lines=stdout_lines,
            operation_label=operation_label,
            observed_at=observed_at,
        )
    elif tool_name == "httpx" and operation_name == "probe":
        parsed = _parse_httpx_probe(
            invocation=invocation,
            stdout_lines=stdout_lines,
            operation_label=operation_label,
            observed_at=observed_at,
        )
    elif tool_name == "whatweb" and operation_name == "fingerprint":
        parsed = _parse_whatweb(
            invocation=invocation,
            stdout_lines=stdout_lines,
            operation_label=operation_label,
            observed_at=observed_at,
        )
    elif tool_name == "nuclei" and operation_name == "targeted_scan":
        parsed = _parse_nuclei(
            invocation=invocation,
            stdout_lines=stdout_lines,
            operation_label=operation_label,
            observed_at=observed_at,
        )
    parsed["diagnostics"] = _parse_execution_diagnostics(
        stderr_lines=stderr_lines,
        tool_name=tool_name,
        operation_name=operation_name,
        targets=targets,
        operation_label=operation_label,
        observed_at=observed_at,
    )

    enriched["parsed"] = parsed
    return enriched


def _parse_nmap_service_scan(
    *,
    invocation: dict[str, Any],
    stdout_lines: list[str],
    operation_label: str,
    observed_at: str | None,
) -> dict[str, Any]:
    targets = _targets(invocation)
    services: list[dict[str, Any]] = []
    suggestions: list[dict[str, Any]] = []
    for line in stdout_lines:
        match = _NMAP_SERVICE_LINE.match(line)
        if match is None:
            continue
        for target in targets:
            service_name = match.group("service").lower()
            details = match.group("details")
            port = int(match.group("port"))
            protocol = match.group("protocol").lower()
            services.append(
                {
                    "target": target,
                    "port": port,
                    "protocol": protocol,
                    "service_name": service_name,
                    "details": details,
                    "operation": operation_label,
                    "last_observed_at": observed_at,
                }
            )
            suggestions.append(
                {
                    "title": f"Open {service_name} service on {target}:{port}/{protocol}",
                    "severity": "info",
                    "attack_technique": "T1046",
                    "summary": (
                        f"The execution parser observed {service_name} exposed on "
                        f"{target}:{port}/{protocol} during scoped enumeration."
                    ),
                    "evidence": [line],
                }
            )

    return {
        "hosts": [
            {
                "target": target,
                "operation": operation_label,
                "last_observed_at": observed_at,
                "os_guess": None,
            }
            for target in targets
        ],
        "services": services,
        "web": [],
        "fingerprints": [],
        "suggested_findings": suggestions,
    }


def _parse_nmap_os_detection(
    *,
    invocation: dict[str, Any],
    stdout_lines: list[str],
    operation_label: str,
    observed_at: str | None,
) -> dict[str, Any]:
    os_guess = None
    os_details = None
    device_type = None
    cpe: list[str] = []
    for line in stdout_lines:
        if line.startswith("Running: "):
            os_guess = line.removeprefix("Running: ").strip()
        elif line.startswith("OS details: "):
            os_details = line.removeprefix("OS details: ").strip()
            if os_guess is None:
                os_guess = os_details
        elif line.startswith("Device type: "):
            device_type = line.removeprefix("Device type: ").strip()
        elif line.startswith("OS CPE: "):
            raw_cpe = line.removeprefix("OS CPE: ").strip()
            cpe = [item for item in raw_cpe.split() if item]

    targets = _targets(invocation)
    fingerprints = [
        {
            "target": target,
            "running": os_guess,
            "os_details": os_details,
            "device_type": device_type,
            "cpe": cpe,
            "operation": operation_label,
            "last_observed_at": observed_at,
        }
        for target in targets
    ]

    return {
        "hosts": [
            {
                "target": target,
                "operation": operation_label,
                "last_observed_at": observed_at,
                "os_guess": os_guess or os_details,
            }
            for target in targets
        ],
        "services": [],
        "web": [],
        "fingerprints": fingerprints,
        "suggested_findings": (
            [
                {
                    "title": f"OS fingerprint observed for {target}",
                    "severity": "info",
                    "attack_technique": "T1595",
                    "summary": (
                        f"The execution parser observed an operating-system fingerprint "
                        f"for {target}: {os_guess or os_details}."
                    ),
                    "evidence": [
                        item
                        for item in (
                            f"Running: {os_guess}" if os_guess else None,
                            f"OS details: {os_details}" if os_details else None,
                            f"Device type: {device_type}" if device_type else None,
                        )
                        if item
                    ],
                }
                for target in targets
            ]
            if os_guess or os_details
            else []
        ),
    }


def _parse_http_headers(
    *,
    invocation: dict[str, Any],
    stdout_lines: list[str],
    operation_label: str,
    observed_at: str | None,
) -> dict[str, Any]:
    url = _coerce_text(invocation.get("args", {}).get("url"))
    if url is None:
        return _empty_parsed()

    parsed_url = urlparse(url)
    target = parsed_url.hostname or url
    status_line = next(
        (line for line in stdout_lines if line.upper().startswith("HTTP/")),
        None,
    )
    headers: dict[str, str] = {}
    for line in stdout_lines:
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        headers[name.strip()] = value.strip()

    port = parsed_url.port or (443 if parsed_url.scheme == "https" else 80)
    banner = headers.get("Server") or headers.get("X-Powered-By")
    missing_security_headers = [
        header for header in _SECURITY_HEADERS if header not in headers
    ]
    status_code = _parse_status_code(status_line)
    suggestions: list[dict[str, Any]] = []
    if banner:
        suggestions.append(
            {
                "title": f"HTTP technology disclosure on {target}",
                "severity": "low",
                "attack_technique": "T1592",
                "summary": (
                    f"The execution parser observed technology disclosure via HTTP "
                    f"headers on {target}: {banner}."
                ),
                "evidence": [f"Banner: {banner}"],
            }
        )
    if missing_security_headers:
        suggestions.append(
            {
                "title": f"Missing HTTP hardening headers on {target}",
                "severity": "medium" if parsed_url.scheme == "https" else "low",
                "attack_technique": "T1592",
                "summary": (
                    f"The execution parser observed missing HTTP hardening headers on "
                    f"{target}: {', '.join(missing_security_headers)}."
                ),
                "evidence": [
                    f"Missing security headers: {', '.join(missing_security_headers)}"
                ],
            }
        )

    return {
        "hosts": [
            {
                "target": target,
                "operation": operation_label,
                "last_observed_at": observed_at,
                "os_guess": None,
            }
        ],
        "services": [
            {
                "target": target,
                "port": port,
                "protocol": "tcp",
                "service_name": parsed_url.scheme or "http",
                "details": banner,
                "operation": operation_label,
                "last_observed_at": observed_at,
            }
        ],
        "web": [
            {
                "url": url,
                "status_line": status_line,
                "status_code": status_code,
                "headers": headers,
                "server": headers.get("Server"),
                "x_powered_by": headers.get("X-Powered-By"),
                "missing_security_headers": missing_security_headers,
                "operation": operation_label,
                "last_observed_at": observed_at,
            }
        ],
        "fingerprints": [],
        "suggested_findings": suggestions,
        "diagnostics": [],
    }


_HTTPX_LINE = re.compile(
    r"^(?P<url>https?://\S+)"
    r"(?:\s+\[(?P<status>\d{3})\])?"
    r"(?:\s+\[(?P<title>[^\]]*)\])?"
    r"(?:\s+\[(?P<tech>[^\]]*)\])?",
)
_NUCLEI_LINE = re.compile(
    r"^\[(?P<template>[^\]]+)\]\s+"
    r"\[(?P<protocol>[^\]]+)\]\s+"
    r"\[(?P<severity>info|low|medium|high|critical)\]\s+"
    r"(?P<target>\S+)"
    r"(?:\s+\[(?P<extra>[^\]]+)\])?",
    re.IGNORECASE,
)
_NUCLEI_SEVERITY_MAP = {
    "info": "info",
    "low": "low",
    "medium": "medium",
    "high": "high",
    "critical": "critical",
}


def _parse_httpx_probe(
    *,
    invocation: dict[str, Any],
    stdout_lines: list[str],
    operation_label: str,
    observed_at: str | None,
) -> dict[str, Any]:
    web: list[dict[str, Any]] = []
    fingerprints: list[dict[str, Any]] = []
    suggestions: list[dict[str, Any]] = []
    for line in stdout_lines:
        match = _HTTPX_LINE.match(line.strip())
        if match is None:
            continue
        url = match.group("url")
        parsed_url = urlparse(url)
        target = parsed_url.hostname or url
        status = match.group("status")
        title = match.group("title")
        tech = match.group("tech")
        web.append(
            {
                "url": url,
                "status_line": f"HTTP/1.1 {status}" if status else None,
                "status_code": int(status) if status else None,
                "headers": {},
                "server": None,
                "x_powered_by": None,
                "missing_security_headers": [],
                "operation": operation_label,
                "last_observed_at": observed_at,
            }
        )
        if tech:
            tech_items = [item.strip() for item in tech.split(",") if item.strip()]
            fingerprints.append(
                {
                    "target": target,
                    "running": ", ".join(tech_items) if tech_items else None,
                    "os_details": None,
                    "device_type": None,
                    "cpe": [],
                    "operation": operation_label,
                    "last_observed_at": observed_at,
                }
            )
            if tech_items:
                suggestions.append(
                    {
                        "title": f"Web technology disclosed at {url}",
                        "severity": "info",
                        "attack_technique": "T1592",
                        "summary": (
                            f"httpx fingerprinted {url} as: {', '.join(tech_items)}."
                            + (f" Title: {title}." if title else "")
                        ),
                        "evidence": [line],
                    }
                )
    return {
        "hosts": [],
        "services": [],
        "web": web,
        "fingerprints": fingerprints,
        "suggested_findings": suggestions,
    }


def _parse_whatweb(
    *,
    invocation: dict[str, Any],
    stdout_lines: list[str],
    operation_label: str,
    observed_at: str | None,
) -> dict[str, Any]:
    fingerprints: list[dict[str, Any]] = []
    suggestions: list[dict[str, Any]] = []
    for line in stdout_lines:
        stripped = line.strip()
        if not stripped or " " not in stripped:
            continue
        url_part, _, rest = stripped.partition(" ")
        if not url_part.startswith(("http://", "https://")):
            continue
        target = urlparse(url_part).hostname or url_part
        plugin_names = re.findall(r"([A-Za-z][A-Za-z0-9_-]*)\[", rest)
        if not plugin_names:
            continue
        fingerprints.append(
            {
                "target": target,
                "running": ", ".join(plugin_names),
                "os_details": None,
                "device_type": None,
                "cpe": [],
                "operation": operation_label,
                "last_observed_at": observed_at,
            }
        )
        suggestions.append(
            {
                "title": f"Web technology fingerprint for {target}",
                "severity": "info",
                "attack_technique": "T1592",
                "summary": f"whatweb identified {len(plugin_names)} component(s) at {url_part}.",
                "evidence": [stripped],
            }
        )
    return {
        "hosts": [],
        "services": [],
        "web": [],
        "fingerprints": fingerprints,
        "suggested_findings": suggestions,
    }


def _parse_nuclei(
    *,
    invocation: dict[str, Any],
    stdout_lines: list[str],
    operation_label: str,
    observed_at: str | None,
) -> dict[str, Any]:
    suggestions: list[dict[str, Any]] = []
    for line in stdout_lines:
        match = _NUCLEI_LINE.match(line.strip())
        if match is None:
            continue
        severity = _NUCLEI_SEVERITY_MAP.get(match.group("severity").lower(), "info")
        template = match.group("template")
        target = match.group("target")
        extra = match.group("extra")
        summary = (
            f"nuclei template '{template}' triggered on {target} (severity={severity})."
        )
        if extra:
            summary += f" Detail: {extra}."
        suggestions.append(
            {
                "title": f"nuclei: {template} on {target}",
                "severity": severity,
                "attack_technique": "T1190",
                "summary": summary,
                "evidence": [line],
            }
        )
    return {
        "hosts": [],
        "services": [],
        "web": [],
        "fingerprints": [],
        "suggested_findings": suggestions,
    }


def _output_lines(value: object, *, event_type: str) -> list[str]:
    if not isinstance(value, list):
        return []
    lines: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        if item.get("type") != event_type:
            continue
        line = _coerce_text(item.get("line"))
        if line:
            lines.append(line)
    return lines


def _parse_execution_diagnostics(
    *,
    stderr_lines: list[str],
    tool_name: str | None,
    operation_name: str | None,
    targets: list[str],
    operation_label: str,
    observed_at: str | None,
) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None, str]] = set()

    def record(
        *,
        code: str,
        kind: str,
        summary: str,
        detail: str,
        target: str | None = None,
        port: int | None = None,
    ) -> None:
        key = (code, target, detail)
        if key in seen:
            return
        seen.add(key)
        diagnostics.append(
            {
                "target": target,
                "port": port,
                "kind": kind,
                "code": code,
                "summary": summary,
                "detail": detail,
                "tool_name": tool_name,
                "operation_name": operation_name,
                "operation": operation_label,
                "last_observed_at": observed_at,
            }
        )

    for line in stderr_lines:
        stripped = line.strip()
        if not stripped:
            continue

        connection_refused = _CONNECTION_REFUSED_LINE.search(stripped)
        if connection_refused is not None:
            target = _normalize_target(connection_refused.group("host"))
            port = int(connection_refused.group("port"))
            record(
                code="connection_refused",
                kind="connectivity",
                summary=f"Connection refused on {target}:{port} during {operation_label}.",
                detail=stripped,
                target=target,
                port=port,
            )
            continue

        lowered = stripped.lower()
        if "requires root privileges" in lowered or "must be root" in lowered:
            diagnostic_targets = targets or [None]
            for target in diagnostic_targets:
                scope = f" for {target}" if target else ""
                record(
                    code="root_required",
                    kind="permissions",
                    summary=f"Root privileges are required to run {operation_label}{scope}.",
                    detail=stripped,
                    target=target,
                )
            continue

        curl_error = _CURL_ERROR_LINE.match(stripped)
        if curl_error is not None:
            code = curl_error.group("code")
            message = curl_error.group("message")
            record(
                code=f"curl_exit_{code}",
                kind="tool_error",
                summary=f"curl exited with code {code} during {operation_label}: {message}",
                detail=stripped,
                target=targets[0] if targets else None,
            )

    return diagnostics


def _empty_parsed() -> dict[str, Any]:
    return {
        "hosts": [],
        "services": [],
        "web": [],
        "fingerprints": [],
        "suggested_findings": [],
        "diagnostics": [],
    }


def _targets(invocation: dict[str, Any]) -> list[str]:
    raw_targets = invocation.get("targets")
    if not isinstance(raw_targets, list):
        return []
    targets: list[str] = []
    for item in raw_targets:
        value = _coerce_text(item)
        if value:
            targets.append(_normalize_target(value))
    return targets


def _normalize_target(target: str) -> str:
    if "://" not in target:
        return target
    parsed = urlparse(target)
    return parsed.hostname or target


def _coerce_text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _parse_status_code(status_line: str | None) -> int | None:
    if status_line is None:
        return None
    parts = status_line.split()
    if len(parts) < 2 or not parts[1].isdigit():
        return None
    return int(parts[1])
