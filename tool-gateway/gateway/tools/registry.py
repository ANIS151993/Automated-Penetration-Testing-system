from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ToolOperation:
    name: str
    argument_schema: dict
    command_template: list[str]
    default_timeout: int


@dataclass(frozen=True, slots=True)
class Tool:
    name: str
    phase: str
    risk_level: str
    operations: tuple[ToolOperation, ...]


NMAP = Tool(
    name="nmap",
    phase="enumeration",
    risk_level="low",
    operations=(
        ToolOperation(
            name="service_scan",
            argument_schema={
                "type": "object",
                "required": ["target", "ports"],
                "additionalProperties": False,
                "properties": {
                    "target": {"type": "string"},
                    "ports": {"type": "string"},
                },
            },
            command_template=["nmap", "-Pn", "-sV", "-p", "{ports}", "{target}"],
            default_timeout=120,
        ),
        ToolOperation(
            name="os_detection",
            argument_schema={
                "type": "object",
                "required": ["target", "ports"],
                "additionalProperties": False,
                "properties": {
                    "target": {"type": "string"},
                    "ports": {"type": "string"},
                },
            },
            command_template=["nmap", "-Pn", "-O", "-p", "{ports}", "{target}"],
            default_timeout=180,
        ),
    ),
)

HTTP_PROBE = Tool(
    name="http_probe",
    phase="enumeration",
    risk_level="low",
    operations=(
        ToolOperation(
            name="fetch_headers",
            argument_schema={
                "type": "object",
                "required": ["url"],
                "additionalProperties": False,
                "properties": {
                    "url": {"type": "string"},
                },
            },
            command_template=["curl", "-I", "--max-time", "10", "{url}"],
            default_timeout=30,
        ),
    ),
)

REGISTRY: dict[str, Tool] = {
    NMAP.name: NMAP,
    HTTP_PROBE.name: HTTP_PROBE,
}


def find_operation(tool_name: str, operation_name: str) -> ToolOperation:
    tool = REGISTRY[tool_name]
    for operation in tool.operations:
        if operation.name == operation_name:
            return operation
    raise KeyError(f"unknown operation {operation_name} for tool {tool_name}")
