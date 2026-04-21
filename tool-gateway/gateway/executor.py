from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass, field
import json
import selectors
import shutil
import subprocess
from threading import Event, Lock
from time import monotonic
from typing import Any, Iterator

from gateway.tools.registry import ToolOperation


class ArgumentValidationError(Exception):
    """Raised when a tool operation request does not satisfy the schema."""


@dataclass(slots=True)
class ActiveExecutionHandle:
    execution_id: str
    cancel_requested: Event = field(default_factory=Event)
    process: subprocess.Popen[str] | None = None


class ActiveExecutionRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._handles: dict[str, ActiveExecutionHandle] = {}

    def register(self, execution_id: str) -> ActiveExecutionHandle:
        handle = ActiveExecutionHandle(execution_id=execution_id)
        with self._lock:
            self._handles[execution_id] = handle
        return handle

    def attach_process(
        self,
        execution_id: str,
        process: subprocess.Popen[str],
    ) -> None:
        with self._lock:
            handle = self._handles.get(execution_id)
            if handle is not None:
                handle.process = process

    def cancel(self, execution_id: str) -> bool:
        with self._lock:
            handle = self._handles.get(execution_id)
        if handle is None:
            return False
        handle.cancel_requested.set()
        if handle.process is not None and handle.process.poll() is None:
            _terminate_process(handle.process)
        return True

    def remove(self, execution_id: str) -> None:
        with self._lock:
            self._handles.pop(execution_id, None)


def validate_arguments(operation: ToolOperation, args: dict[str, Any]) -> None:
    schema = operation.argument_schema
    required = set(schema.get("required", []))
    properties = schema.get("properties", {})
    additional_allowed = schema.get("additionalProperties", False)

    missing = sorted(required.difference(args.keys()))
    if missing:
        raise ArgumentValidationError(f"Missing required arguments: {', '.join(missing)}")

    unknown = sorted(set(args.keys()).difference(properties.keys()))
    if unknown and not additional_allowed:
        raise ArgumentValidationError(f"Unknown arguments: {', '.join(unknown)}")

    for key, value in args.items():
        rule = properties.get(key)
        if rule is None:
            continue
        expected_type = rule.get("type")
        if expected_type == "string" and not isinstance(value, str):
            raise ArgumentValidationError(f"Argument {key} must be a string")
        if expected_type == "array" and not isinstance(value, list):
            raise ArgumentValidationError(f"Argument {key} must be an array")


def build_command_preview(operation: ToolOperation, args: dict[str, Any]) -> list[str]:
    validate_arguments(operation, args)
    rendered: list[str] = []
    for segment in operation.command_template:
        rendered.append(segment.format(**args))
    return rendered


def stream_command_events(
    operation: ToolOperation,
    args: dict[str, Any],
    *,
    execution_id: str,
    active_executions: ActiveExecutionRegistry,
) -> Iterator[dict[str, Any]]:
    command = build_command_preview(operation, args)
    binary = command[0]

    if shutil.which(binary) is None:
        yield _event(
            "failed",
            status="failed",
            error=f"Executable not available on gateway: {binary}",
            exit_code=127,
        )
        return

    handle = active_executions.register(execution_id)
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    active_executions.attach_process(execution_id, process)
    selector = selectors.DefaultSelector()
    if process.stdout is not None:
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    if process.stderr is not None:
        selector.register(process.stderr, selectors.EVENT_READ, "stderr")

    stdout_lines = 0
    stderr_lines = 0
    timeout_reached = False
    cancel_requested = False
    cancel_event_emitted = False
    started_at = monotonic()
    yield _event(
        "started",
        status="running",
        command_preview=command,
        timeout_seconds=operation.default_timeout,
    )

    try:
        while selector.get_map():
            if handle.cancel_requested.is_set():
                cancel_requested = True
                cancel_event_emitted = True
                _terminate_process(process)
                yield _event(
                    "cancelled",
                    status="cancelled",
                    error="Command cancelled by operator request",
                    exit_code=-15,
                    stdout_lines=stdout_lines,
                    stderr_lines=stderr_lines,
                )
                break
            if monotonic() - started_at > operation.default_timeout:
                timeout_reached = True
                _terminate_process(process)
                yield _event(
                    "timed_out",
                    status="timed_out",
                    error=f"Command timed out after {operation.default_timeout} seconds",
                    exit_code=-9,
                    stdout_lines=stdout_lines,
                    stderr_lines=stderr_lines,
                )
                break

            ready = selector.select(timeout=0.2)
            if not ready:
                if process.poll() is not None:
                    for key in list(selector.get_map().values()):
                        stream = key.fileobj
                        remainder = stream.readline()
                        if remainder:
                            channel = key.data
                            if channel == "stdout":
                                stdout_lines += 1
                            else:
                                stderr_lines += 1
                            yield _event(channel, line=remainder.rstrip("\n"))
                        selector.unregister(stream)
                    break
                continue

            for key, _ in ready:
                stream = key.fileobj
                channel = key.data
                line = stream.readline()
                if line == "":
                    selector.unregister(stream)
                    continue
                if channel == "stdout":
                    stdout_lines += 1
                else:
                    stderr_lines += 1
                yield _event(channel, line=line.rstrip("\n"))
    finally:
        selector.close()
        active_executions.remove(execution_id)

    exit_code = process.wait()
    cancel_requested = cancel_requested or handle.cancel_requested.is_set()
    if not timeout_reached and cancel_requested and not cancel_event_emitted:
        yield _event(
            "cancelled",
            status="cancelled",
            error="Command cancelled by operator request",
            exit_code=exit_code,
            stdout_lines=stdout_lines,
            stderr_lines=stderr_lines,
        )
    if not timeout_reached and not cancel_requested:
        status = "completed" if exit_code == 0 else "failed"
        yield _event(
            "completed",
            status=status,
            exit_code=exit_code,
            stdout_lines=stdout_lines,
            stderr_lines=stderr_lines,
        )


def encode_event(event: dict[str, Any]) -> bytes:
    return (json.dumps(event) + "\n").encode("utf-8")


def _event(event_type: str, **payload: Any) -> dict[str, Any]:
    return {
        "type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **payload,
    }


def _terminate_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        process.kill()
