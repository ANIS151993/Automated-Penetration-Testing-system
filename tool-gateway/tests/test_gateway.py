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


def _validate(client, app, *, tool_name, operation_name, args, scope_cidrs=None):
    token = issue_gateway_token(
        subject="backend-service",
        audience=app.config["GATEWAY_AUDIENCE"],
        secret=app.config["GATEWAY_JWT_SECRET"],
    )
    return client.post(
        "/api/v1/validate-invocation",
        json={
            "token": token,
            "scope_cidrs": scope_cidrs or ["172.20.32.0/18"],
            "tool_name": tool_name,
            "operation_name": operation_name,
            "args": args,
        },
    )


def test_gateway_validates_whatweb_fingerprint() -> None:
    app = create_app()
    client = app.test_client()
    response = _validate(
        client, app,
        tool_name="whatweb",
        operation_name="fingerprint",
        args={"url": "http://172.20.32.59"},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["tool"] == "whatweb"
    assert body["risk_level"] == "low"
    assert body["command_preview"] == ["whatweb", "--no-errors", "-a", "1", "http://172.20.32.59"]


def test_gateway_validates_sslscan_tls_audit() -> None:
    app = create_app()
    client = app.test_client()
    response = _validate(
        client, app,
        tool_name="sslscan",
        operation_name="tls_audit",
        args={"target": "172.20.32.59", "port": "443"},
    )
    assert response.status_code == 200
    assert response.get_json()["command_preview"] == ["sslscan", "--no-colour", "172.20.32.59:443"]


def test_gateway_validates_nuclei_high_risk() -> None:
    app = create_app()
    client = app.test_client()
    response = _validate(
        client, app,
        tool_name="nuclei",
        operation_name="targeted_scan",
        args={"url": "http://172.20.32.59", "severity": "high,critical"},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["risk_level"] == "high"
    assert body["targets"] == ["172.20.32.59"]


def test_gateway_validates_nmap_top_ports() -> None:
    app = create_app()
    client = app.test_client()
    response = _validate(
        client, app,
        tool_name="nmap",
        operation_name="top_ports",
        args={"target": "172.20.32.59", "top_n": "100"},
    )
    assert response.status_code == 200
    assert response.get_json()["command_preview"] == [
        "nmap", "-Pn", "-sV", "--top-ports", "100", "172.20.32.59",
    ]


def test_gateway_rejects_unknown_tool_argument() -> None:
    app = create_app()
    client = app.test_client()
    response = _validate(
        client, app,
        tool_name="httpx",
        operation_name="probe",
        args={"url": "http://172.20.32.59", "extra": "bad"},
    )
    assert response.status_code == 400
