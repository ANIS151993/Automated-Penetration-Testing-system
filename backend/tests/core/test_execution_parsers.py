from app.core.execution_parsers import enrich_execution_document


def test_enrich_execution_document_parses_nmap_service_scan() -> None:
    document = {
        "tool_name": "nmap",
        "operation_name": "service_scan",
        "invocation": {
            "id": "inv-1",
            "tool_name": "nmap",
            "operation_name": "service_scan",
            "targets": ["172.20.32.59"],
            "created_at": "2026-04-20T00:00:00+00:00",
            "args": {"target": "172.20.32.59", "ports": "22"},
        },
        "events": [
            {"type": "stdout", "line": "22/tcp open ssh OpenSSH 9.6p1 Ubuntu"},
            {"type": "completed", "status": "completed"},
        ],
    }

    enriched = enrich_execution_document(document)

    assert enriched["parsed"]["services"][0]["target"] == "172.20.32.59"
    assert enriched["parsed"]["services"][0]["port"] == 22
    assert enriched["parsed"]["services"][0]["service_name"] == "ssh"
    assert enriched["parsed"]["suggested_findings"][0]["attack_technique"] == "T1046"
    assert enriched["parsed"]["diagnostics"] == []


def test_enrich_execution_document_parses_http_headers() -> None:
    document = {
        "tool_name": "http_probe",
        "operation_name": "fetch_headers",
        "invocation": {
            "id": "inv-2",
            "tool_name": "http_probe",
            "operation_name": "fetch_headers",
            "targets": ["http://172.20.32.59"],
            "created_at": "2026-04-20T00:00:00+00:00",
            "args": {"url": "http://172.20.32.59"},
        },
        "events": [
            {"type": "stdout", "line": "HTTP/1.1 200 OK"},
            {"type": "stdout", "line": "Server: nginx/1.24.0"},
            {"type": "stdout", "line": "X-Powered-By: PHP/8.3"},
            {"type": "completed", "status": "completed"},
        ],
    }

    enriched = enrich_execution_document(document)

    assert enriched["parsed"]["services"][0]["service_name"] == "http"
    assert enriched["parsed"]["services"][0]["details"] == "nginx/1.24.0"
    assert enriched["parsed"]["web"][0]["status_code"] == 200
    assert enriched["parsed"]["web"][0]["x_powered_by"] == "PHP/8.3"
    assert "Content-Security-Policy" in enriched["parsed"]["web"][0]["missing_security_headers"]
    assert len(enriched["parsed"]["suggested_findings"]) == 2
    assert enriched["parsed"]["suggested_findings"][0]["severity"] == "low"
    assert enriched["parsed"]["suggested_findings"][1]["title"].startswith("Missing HTTP hardening headers")
    assert enriched["parsed"]["diagnostics"] == []


def test_enrich_execution_document_parses_os_detection_fingerprint() -> None:
    document = {
        "tool_name": "nmap",
        "operation_name": "os_detection",
        "invocation": {
            "id": "inv-3",
            "tool_name": "nmap",
            "operation_name": "os_detection",
            "targets": ["172.20.32.59"],
            "created_at": "2026-04-20T00:00:00+00:00",
            "args": {"target": "172.20.32.59", "ports": "22"},
        },
        "events": [
            {"type": "stdout", "line": "Running: Linux 6.X"},
            {"type": "stdout", "line": "OS details: Linux 6.8 - 6.11"},
            {"type": "stdout", "line": "Device type: general purpose"},
            {"type": "stdout", "line": "OS CPE: cpe:/o:linux:linux_kernel:6"},
            {"type": "completed", "status": "completed"},
        ],
    }

    enriched = enrich_execution_document(document)

    assert enriched["parsed"]["hosts"][0]["os_guess"] == "Linux 6.X"
    assert enriched["parsed"]["fingerprints"][0]["device_type"] == "general purpose"
    assert enriched["parsed"]["fingerprints"][0]["cpe"] == ["cpe:/o:linux:linux_kernel:6"]
    assert enriched["parsed"]["suggested_findings"][0]["title"].startswith("OS fingerprint observed")
    assert enriched["parsed"]["diagnostics"] == []


def test_enrich_execution_document_parses_connection_refused_diagnostic() -> None:
    document = {
        "tool_name": "http_probe",
        "operation_name": "fetch_headers",
        "invocation": {
            "id": "inv-4",
            "tool_name": "http_probe",
            "operation_name": "fetch_headers",
            "targets": ["http://172.20.32.59"],
            "created_at": "2026-04-20T00:00:00+00:00",
            "args": {"url": "http://172.20.32.59"},
        },
        "events": [
            {
                "type": "stderr",
                "line": "curl: (7) Failed to connect to 172.20.32.59 port 80 after 0 ms: Connection refused",
            },
            {"type": "completed", "status": "failed"},
        ],
    }

    enriched = enrich_execution_document(document)

    assert enriched["parsed"]["diagnostics"][0]["code"] == "connection_refused"
    assert enriched["parsed"]["diagnostics"][0]["kind"] == "connectivity"
    assert enriched["parsed"]["diagnostics"][0]["target"] == "172.20.32.59"
    assert enriched["parsed"]["diagnostics"][0]["port"] == 80


def test_enrich_execution_document_parses_root_required_diagnostic() -> None:
    document = {
        "tool_name": "nmap",
        "operation_name": "os_detection",
        "invocation": {
            "id": "inv-5",
            "tool_name": "nmap",
            "operation_name": "os_detection",
            "targets": ["172.20.32.59"],
            "created_at": "2026-04-20T00:00:00+00:00",
            "args": {"target": "172.20.32.59"},
        },
        "events": [
            {
                "type": "stderr",
                "line": "TCP/IP fingerprinting (for OS scan) requires root privileges.",
            },
            {"type": "stderr", "line": "QUITTING!"},
            {"type": "completed", "status": "failed"},
        ],
    }

    enriched = enrich_execution_document(document)

    assert enriched["parsed"]["diagnostics"][0]["code"] == "root_required"
    assert enriched["parsed"]["diagnostics"][0]["kind"] == "permissions"
    assert enriched["parsed"]["diagnostics"][0]["target"] == "172.20.32.59"


def test_enrich_execution_document_parses_httpx_probe() -> None:
    document = {
        "tool_name": "httpx",
        "operation_name": "probe",
        "invocation": {
            "id": "inv-h1",
            "tool_name": "httpx",
            "operation_name": "probe",
            "targets": ["172.20.32.59"],
            "created_at": "2026-04-26T00:00:00+00:00",
            "args": {"url": "http://172.20.32.59"},
        },
        "events": [
            {"type": "stdout", "line": "http://172.20.32.59 [200] [Welcome] [nginx,php]"},
            {"type": "completed", "status": "completed"},
        ],
    }

    enriched = enrich_execution_document(document)

    assert enriched["parsed"]["web"][0]["status_code"] == 200
    assert enriched["parsed"]["fingerprints"][0]["running"] == "nginx, php"
    assert enriched["parsed"]["suggested_findings"][0]["attack_technique"] == "T1592"


def test_enrich_execution_document_parses_whatweb_fingerprint() -> None:
    document = {
        "tool_name": "whatweb",
        "operation_name": "fingerprint",
        "invocation": {
            "id": "inv-w1",
            "tool_name": "whatweb",
            "operation_name": "fingerprint",
            "targets": ["172.20.32.59"],
            "created_at": "2026-04-26T00:00:00+00:00",
            "args": {"url": "http://172.20.32.59"},
        },
        "events": [
            {
                "type": "stdout",
                "line": "http://172.20.32.59 [200 OK] HTTPServer[nginx/1.24.0], PHP[8.3.0]",
            },
            {"type": "completed", "status": "completed"},
        ],
    }

    enriched = enrich_execution_document(document)
    fp = enriched["parsed"]["fingerprints"][0]
    assert "HTTPServer" in fp["running"]
    assert "PHP" in fp["running"]
    assert enriched["parsed"]["suggested_findings"][0]["severity"] == "info"


def test_enrich_execution_document_parses_nuclei_critical() -> None:
    document = {
        "tool_name": "nuclei",
        "operation_name": "targeted_scan",
        "invocation": {
            "id": "inv-n1",
            "tool_name": "nuclei",
            "operation_name": "targeted_scan",
            "targets": ["172.20.32.59"],
            "created_at": "2026-04-26T00:00:00+00:00",
            "args": {"url": "http://172.20.32.59", "severity": "critical"},
        },
        "events": [
            {
                "type": "stdout",
                "line": "[CVE-2023-1234] [http] [critical] http://172.20.32.59/admin [admin panel]",
            },
            {"type": "completed", "status": "completed"},
        ],
    }

    enriched = enrich_execution_document(document)
    findings = enriched["parsed"]["suggested_findings"]
    assert len(findings) == 1
    assert findings[0]["severity"] == "critical"
    assert findings[0]["attack_technique"] == "T1190"
    assert "CVE-2023-1234" in findings[0]["title"]
