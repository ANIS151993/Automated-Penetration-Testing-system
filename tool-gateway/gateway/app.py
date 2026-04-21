from __future__ import annotations

import os

from flask import Flask, Response, jsonify, request

from gateway.auth import (
    GatewayAuthError,
    ScopeViolation,
    extract_targets_from_command,
    validate_target_in_scope,
    verify_gateway_token,
)
from gateway.executor import (
    ActiveExecutionRegistry,
    ArgumentValidationError,
    build_command_preview,
    encode_event,
    stream_command_events,
)
from gateway.tools.registry import REGISTRY, find_operation


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.update(
        GATEWAY_AUDIENCE=os.environ.get("GATEWAY_AUDIENCE", "pentai-tool-gateway"),
        GATEWAY_JWT_SECRET=os.environ.get("GATEWAY_JWT_SECRET", "replace-this-before-use"),
        ACTIVE_EXECUTIONS=ActiveExecutionRegistry(),
    )

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok", "service": "tool-gateway"})

    @app.post("/api/v1/validate-invocation")
    def validate_invocation():
        try:
            claims, tool, operation, args, scope_cidrs, targets, preview = _validate_payload(
                request.get_json(silent=True) or {},
                audience=app.config["GATEWAY_AUDIENCE"],
                secret=app.config["GATEWAY_JWT_SECRET"],
            )
        except KeyError as exc:
            return jsonify({"error": str(exc)}), 404

        return (
            jsonify(
                {
                    "status": "validated",
                    "subject": claims["sub"],
                    "tool": tool.name,
                    "operation": operation.name,
                    "risk_level": tool.risk_level,
                    "command_preview": preview,
                    "targets": targets,
                }
            ),
            200,
        )

    @app.post("/api/v1/execute-invocation")
    def execute_invocation():
        payload = request.get_json(silent=True) or {}
        try:
            claims, tool, operation, args, _, targets, preview = _validate_payload(
                payload,
                audience=app.config["GATEWAY_AUDIENCE"],
                secret=app.config["GATEWAY_JWT_SECRET"],
            )
        except KeyError as exc:
            return jsonify({"error": str(exc)}), 404
        execution_id = payload.get("execution_id")
        if not isinstance(execution_id, str) or not execution_id:
            raise ArgumentValidationError("execution_id is required")

        def generate():
            for event in stream_command_events(
                operation,
                args,
                execution_id=execution_id,
                active_executions=app.config["ACTIVE_EXECUTIONS"],
            ):
                payload = {
                    "subject": claims["sub"],
                    "execution_id": execution_id,
                    "tool": tool.name,
                    "operation": operation.name,
                    "targets": targets,
                    "command_preview": preview,
                    **event,
                }
                yield encode_event(payload)

        return Response(generate(), mimetype="application/x-ndjson")

    @app.post("/api/v1/cancel-execution")
    def cancel_execution():
        payload = request.get_json(silent=True) or {}
        token = payload.get("token")
        execution_id = payload.get("execution_id")
        if not isinstance(token, str):
            raise ArgumentValidationError("token is required")
        if not isinstance(execution_id, str) or not execution_id:
            raise ArgumentValidationError("execution_id is required")
        claims = verify_gateway_token(
            token=token,
            secret=app.config["GATEWAY_JWT_SECRET"],
            audience=app.config["GATEWAY_AUDIENCE"],
        )
        cancelled = app.config["ACTIVE_EXECUTIONS"].cancel(execution_id)
        if not cancelled:
            return jsonify({"error": "active execution not found"}), 404
        return (
            jsonify(
                {
                    "status": "cancellation_requested",
                    "detail": "Gateway accepted the cancellation request.",
                    "execution_id": execution_id,
                    "subject": claims["sub"],
                }
            ),
            202,
        )

    @app.errorhandler(GatewayAuthError)
    def handle_auth_error(exc: GatewayAuthError):
        return jsonify({"error": str(exc)}), 401

    @app.errorhandler(ScopeViolation)
    def handle_scope_error(exc: ScopeViolation):
        return jsonify({"error": str(exc)}), 403

    @app.errorhandler(ArgumentValidationError)
    def handle_argument_error(exc: ArgumentValidationError):
        return jsonify({"error": str(exc)}), 400

    return app


def _validate_payload(payload, *, audience: str, secret: str):
    token = payload.get("token")
    scope_cidrs = payload.get("scope_cidrs") or []
    tool_name = payload.get("tool_name")
    operation_name = payload.get("operation_name")
    args = payload.get("args") or {}

    if not isinstance(token, str):
        raise ArgumentValidationError("token is required")
    if not isinstance(scope_cidrs, list) or not scope_cidrs:
        raise ArgumentValidationError("scope_cidrs is required")
    if not isinstance(tool_name, str) or not isinstance(operation_name, str):
        raise ArgumentValidationError("tool_name and operation_name are required")

    claims = verify_gateway_token(
        token=token,
        secret=secret,
        audience=audience,
    )

    tool = REGISTRY.get(tool_name)
    if tool is None:
        raise KeyError(f"unknown tool {tool_name}")

    operation = find_operation(tool_name, operation_name)
    preview = build_command_preview(operation, args)
    targets = extract_targets_from_command(tool_name, args)
    for target in targets:
        validate_target_in_scope(target, scope_cidrs)
    return claims, tool, operation, args, scope_cidrs, targets, preview


app = create_app()
