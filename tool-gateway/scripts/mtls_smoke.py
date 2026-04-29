"""mTLS smoke test against a running tool-gateway.

Usage:
  PENTAI_GATEWAY_URL=https://172.20.32.68:5000 \
  PENTAI_CA_CERT=/path/to/ca-cert.pem \
  PENTAI_CLIENT_CERT=/path/to/command-client-cert.pem \
  PENTAI_CLIENT_KEY=/path/to/command-client-key.pem \
  uv run python scripts/mtls_smoke.py

Verifies:
  1. Connection without client cert is REJECTED.
  2. Connection with client cert reaches /healthz and returns service=tool-gateway.
"""
from __future__ import annotations

import os
import ssl
import sys
from urllib.parse import urlparse

import httpx


def main() -> int:
    url = os.environ.get("PENTAI_GATEWAY_URL", "https://172.20.32.68:5000")
    ca = os.environ["PENTAI_CA_CERT"]
    cert = os.environ["PENTAI_CLIENT_CERT"]
    key = os.environ["PENTAI_CLIENT_KEY"]
    health = url.rstrip("/") + "/healthz"
    parsed = urlparse(url)
    print(f"[mtls] target={parsed.netloc}")

    print("[mtls] step 1: connect WITHOUT client cert (expect failure)...")
    no_client_ctx = ssl.create_default_context(cafile=ca)
    try:
        with httpx.Client(verify=no_client_ctx, timeout=5.0) as client:
            client.get(health)
    except (httpx.ConnectError, httpx.ReadError, ssl.SSLError) as exc:
        print(f"[mtls]   ok — gateway refused unauthenticated TLS: {exc.__class__.__name__}")
    else:
        print("[mtls]   FAIL — gateway accepted connection without client cert")
        return 1

    print("[mtls] step 2: connect WITH client cert (expect 200)...")
    auth_ctx = ssl.create_default_context(cafile=ca)
    auth_ctx.load_cert_chain(cert, key)
    with httpx.Client(verify=auth_ctx, timeout=10.0) as client:
        response = client.get(health)
    if response.status_code != 200:
        print(f"[mtls]   FAIL — status {response.status_code}: {response.text}")
        return 1
    body = response.json()
    if body.get("service") != "tool-gateway":
        print(f"[mtls]   FAIL — unexpected body: {body}")
        return 1
    print(f"[mtls]   ok — healthz returned {body}")
    print("[mtls] all checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
