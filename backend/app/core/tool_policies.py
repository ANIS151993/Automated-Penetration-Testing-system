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
}


def get_tool_policy(tool_name: str, operation_name: str) -> ToolOperationPolicy:
    try:
        return POLICIES[(tool_name, operation_name)]
    except KeyError as exc:
        raise KeyError(f"Unsupported tool operation: {tool_name}.{operation_name}") from exc
