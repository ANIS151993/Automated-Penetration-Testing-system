from gateway.app import create_app
from gateway.auth import issue_gateway_token


def test_gateway_healthz() -> None:
    app = create_app()
    client = app.test_client()

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.get_json()["service"] == "tool-gateway"


def test_gateway_validates_in_scope_request() -> None:
    app = create_app()
    client = app.test_client()
    token = issue_gateway_token(
        subject="backend-service",
        audience=app.config["GATEWAY_AUDIENCE"],
        secret=app.config["GATEWAY_JWT_SECRET"],
    )

    response = client.post(
        "/api/v1/validate-invocation",
        json={
            "token": token,
            "scope_cidrs": ["172.20.32.0/18"],
            "tool_name": "nmap",
            "operation_name": "service_scan",
            "args": {"target": "172.20.32.59", "ports": "22,80,443"},
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "validated"
    assert payload["targets"] == ["172.20.32.59"]


def test_gateway_rejects_out_of_scope_request() -> None:
    app = create_app()
    client = app.test_client()
    token = issue_gateway_token(
        subject="backend-service",
        audience=app.config["GATEWAY_AUDIENCE"],
        secret=app.config["GATEWAY_JWT_SECRET"],
    )

    response = client.post(
        "/api/v1/validate-invocation",
        json={
            "token": token,
            "scope_cidrs": ["172.20.32.0/18"],
            "tool_name": "nmap",
            "operation_name": "service_scan",
            "args": {"target": "8.8.8.8", "ports": "53"},
        },
    )

    assert response.status_code == 403


def test_gateway_rejects_malformed_arguments() -> None:
    app = create_app()
    client = app.test_client()
    token = issue_gateway_token(
        subject="backend-service",
        audience=app.config["GATEWAY_AUDIENCE"],
        secret=app.config["GATEWAY_JWT_SECRET"],
    )

    response = client.post(
        "/api/v1/validate-invocation",
        json={
            "token": token,
            "scope_cidrs": ["172.20.32.0/18"],
            "tool_name": "nmap",
            "operation_name": "service_scan",
            "args": {"target": "172.20.32.59"},
        },
    )

    assert response.status_code == 400


def test_gateway_streams_execution_events(monkeypatch) -> None:
    app = create_app()
    client = app.test_client()
    token = issue_gateway_token(
        subject="backend-service",
        audience=app.config["GATEWAY_AUDIENCE"],
        secret=app.config["GATEWAY_JWT_SECRET"],
    )

    def fake_stream(_operation, _args, *, execution_id, active_executions):
        assert execution_id == "exec-1"
        assert active_executions is app.config["ACTIVE_EXECUTIONS"]
        yield {"type": "started", "status": "running"}
        yield {"type": "stdout", "line": "scan output"}
        yield {"type": "completed", "status": "completed", "exit_code": 0}

    monkeypatch.setattr("gateway.app.stream_command_events", fake_stream)

    response = client.post(
        "/api/v1/execute-invocation",
        json={
            "token": token,
            "execution_id": "exec-1",
            "scope_cidrs": ["172.20.32.0/18"],
            "tool_name": "nmap",
            "operation_name": "service_scan",
            "args": {"target": "172.20.32.59", "ports": "22"},
        },
    )

    assert response.status_code == 200
    lines = [line for line in response.data.decode().splitlines() if line]
    assert '"type": "started"' in lines[0]
    assert '"type": "stdout"' in lines[1]
    assert '"type": "completed"' in lines[2]


def test_gateway_accepts_cancellation_request() -> None:
    app = create_app()
    client = app.test_client()
    token = issue_gateway_token(
        subject="backend-service",
        audience=app.config["GATEWAY_AUDIENCE"],
        secret=app.config["GATEWAY_JWT_SECRET"],
    )

    handle = app.config["ACTIVE_EXECUTIONS"].register("exec-2")

    response = client.post(
        "/api/v1/cancel-execution",
        json={
            "token": token,
            "execution_id": "exec-2",
        },
    )

    assert response.status_code == 202
    assert response.get_json()["status"] == "cancellation_requested"
    assert handle.cancel_requested.is_set() is True
