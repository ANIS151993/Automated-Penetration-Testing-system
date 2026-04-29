from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ToolOperationPolicy:
    tool_name: str
    operation_name: str
    risk_level: str
    requires_approval: bool


POLICIES: dict[tuple[str, str], ToolOperationPolicy] = {
    ("nmap", "service_scan"): ToolOperationPolicy(
        tool_name="nmap",
        operation_name="service_scan",
        risk_level="low",
        requires_approval=False,
    ),
    ("http_probe", "fetch_headers"): ToolOperationPolicy(
        tool_name="http_probe",
        operation_name="fetch_headers",
        risk_level="low",
        requires_approval=False,
    ),
    ("nmap", "os_detection"): ToolOperationPolicy(
        tool_name="nmap",
        operation_name="os_detection",
        risk_level="high",
        requires_approval=True,
    ),
    ("nmap", "host_discovery"): ToolOperationPolicy(
        tool_name="nmap",
        operation_name="host_discovery",
        risk_level="low",
        requires_approval=False,
    ),
    ("nmap", "top_ports"): ToolOperationPolicy(
        tool_name="nmap",
        operation_name="top_ports",
        risk_level="low",
        requires_approval=False,
    ),
    ("whatweb", "fingerprint"): ToolOperationPolicy(
        tool_name="whatweb",
        operation_name="fingerprint",
        risk_level="low",
        requires_approval=False,
    ),
    ("httpx", "probe"): ToolOperationPolicy(
        tool_name="httpx",
        operation_name="probe",
        risk_level="low",
        requires_approval=False,
    ),
    ("sslscan", "tls_audit"): ToolOperationPolicy(
        tool_name="sslscan",
        operation_name="tls_audit",
        risk_level="low",
        requires_approval=False,
    ),
    ("dnsx", "resolve"): ToolOperationPolicy(
        tool_name="dnsx",
        operation_name="resolve",
        risk_level="low",
        requires_approval=False,
    ),
    ("nuclei", "targeted_scan"): ToolOperationPolicy(
        tool_name="nuclei",
        operation_name="targeted_scan",
        risk_level="high",
        requires_approval=True,
    ),
    ("gobuster", "dir"): ToolOperationPolicy(
        tool_name="gobuster",
        operation_name="dir",
        risk_level="high",
        requires_approval=True,
    ),
}


def get_tool_policy(tool_name: str, operation_name: str) -> ToolOperationPolicy:
    try:
        return POLICIES[(tool_name, operation_name)]
    except KeyError as exc:
        raise KeyError(f"Unsupported tool operation: {tool_name}.{operation_name}") from exc
