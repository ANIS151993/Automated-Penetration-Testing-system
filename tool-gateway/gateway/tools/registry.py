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
        ToolOperation(
            name="host_discovery",
            argument_schema={
                "type": "object",
                "required": ["target"],
                "additionalProperties": False,
                "properties": {"target": {"type": "string"}},
            },
            command_template=["nmap", "-sn", "-n", "{target}"],
            default_timeout=120,
        ),
        ToolOperation(
            name="top_ports",
            argument_schema={
                "type": "object",
                "required": ["target", "top_n"],
                "additionalProperties": False,
                "properties": {
                    "target": {"type": "string"},
                    "top_n": {"type": "string"},
                },
            },
            command_template=["nmap", "-Pn", "-sV", "--top-ports", "{top_n}", "{target}"],
            default_timeout=240,
        ),
    ),
)


WHATWEB = Tool(
    name="whatweb",
    phase="enumeration",
    risk_level="low",
    operations=(
        ToolOperation(
            name="fingerprint",
            argument_schema={
                "type": "object",
                "required": ["url"],
                "additionalProperties": False,
                "properties": {"url": {"type": "string"}},
            },
            command_template=["whatweb", "--no-errors", "-a", "1", "{url}"],
            default_timeout=60,
        ),
    ),
)


HTTPX = Tool(
    name="httpx",
    phase="enumeration",
    risk_level="low",
    operations=(
        ToolOperation(
            name="probe",
            argument_schema={
                "type": "object",
                "required": ["url"],
                "additionalProperties": False,
                "properties": {"url": {"type": "string"}},
            },
            command_template=[
                "httpx",
                "-u",
                "{url}",
                "-silent",
                "-status-code",
                "-title",
                "-tech-detect",
                "-no-color",
            ],
            default_timeout=60,
        ),
    ),
)


SSLSCAN = Tool(
    name="sslscan",
    phase="enumeration",
    risk_level="low",
    operations=(
        ToolOperation(
            name="tls_audit",
            argument_schema={
                "type": "object",
                "required": ["target", "port"],
                "additionalProperties": False,
                "properties": {
                    "target": {"type": "string"},
                    "port": {"type": "string"},
                },
            },
            command_template=["sslscan", "--no-colour", "{target}:{port}"],
            default_timeout=120,
        ),
    ),
)


DNSX = Tool(
    name="dnsx",
    phase="enumeration",
    risk_level="low",
    operations=(
        ToolOperation(
            name="resolve",
            argument_schema={
                "type": "object",
                "required": ["target"],
                "additionalProperties": False,
                "properties": {"target": {"type": "string"}},
            },
            command_template=[
                "dnsx",
                "-silent",
                "-resp",
                "-a",
                "-aaaa",
                "-cname",
                "-d",
                "{target}",
            ],
            default_timeout=60,
        ),
    ),
)


NUCLEI = Tool(
    name="nuclei",
    phase="vulnerability_scan",
    risk_level="high",
    operations=(
        ToolOperation(
            name="targeted_scan",
            argument_schema={
                "type": "object",
                "required": ["url", "severity"],
                "additionalProperties": False,
                "properties": {
                    "url": {"type": "string"},
                    "severity": {"type": "string"},
                },
            },
            command_template=[
                "nuclei",
                "-u",
                "{url}",
                "-severity",
                "{severity}",
                "-silent",
                "-no-color",
                "-disable-update-check",
            ],
            default_timeout=900,
        ),
    ),
)


GOBUSTER = Tool(
    name="gobuster",
    phase="enumeration",
    risk_level="high",
    operations=(
        ToolOperation(
            name="dir",
            argument_schema={
                "type": "object",
                "required": ["url", "wordlist"],
                "additionalProperties": False,
                "properties": {
                    "url": {"type": "string"},
                    "wordlist": {"type": "string"},
                },
            },
            command_template=[
                "gobuster",
                "dir",
                "-u",
                "{url}",
                "-w",
                "{wordlist}",
                "-q",
                "--no-error",
            ],
            default_timeout=900,
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
    WHATWEB.name: WHATWEB,
    HTTPX.name: HTTPX,
    SSLSCAN.name: SSLSCAN,
    DNSX.name: DNSX,
    NUCLEI.name: NUCLEI,
    GOBUSTER.name: GOBUSTER,
}


def find_operation(tool_name: str, operation_name: str) -> ToolOperation:
    tool = REGISTRY[tool_name]
    for operation in tool.operations:
        if operation.name == operation_name:
            return operation
    raise KeyError(f"unknown operation {operation_name} for tool {tool_name}")
