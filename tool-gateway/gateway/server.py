from __future__ import annotations

import os
import ssl

from gateway.app import create_app


def build_ssl_context() -> ssl.SSLContext:
    server_cert = os.environ["GATEWAY_SERVER_CERT"]
    server_key = os.environ["GATEWAY_SERVER_KEY"]
    ca_cert = os.environ["GATEWAY_CA_CERT"]

    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(server_cert, server_key)
    context.load_verify_locations(ca_cert)
    context.verify_mode = ssl.CERT_REQUIRED
    return context


def main() -> None:
    app = create_app()
    host = os.environ.get("GATEWAY_HOST", "0.0.0.0")
    port = int(os.environ.get("GATEWAY_PORT", "5000"))
    app.run(host=host, port=port, ssl_context=build_ssl_context())


if __name__ == "__main__":
    main()
