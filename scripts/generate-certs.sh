#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
CERT_DIR="${PENTAI_CERT_DIR:-$REPO_ROOT/certs}"
FORCE="${PENTAI_FORCE_CERT_REGEN:-0}"
WEAPON_NODE_IP="${PENTAI_WEAPON_NODE_IP:-172.20.32.68}"
CA_SUBJECT="${PENTAI_CA_SUBJECT:-/CN=PentAI Pro Lab CA}"
COMMAND_SUBJECT="${PENTAI_COMMAND_SUBJECT:-/CN=PentAI Command Node}"
WEAPON_SUBJECT="${PENTAI_WEAPON_SUBJECT:-/CN=PentAI Weapon Node}"

mkdir -p "$CERT_DIR"

required_outputs=(
  "$CERT_DIR/ca-key.pem"
  "$CERT_DIR/ca-cert.pem"
  "$CERT_DIR/command-client-key.pem"
  "$CERT_DIR/command-client-cert.pem"
  "$CERT_DIR/weapon-server-key.pem"
  "$CERT_DIR/weapon-server-cert.pem"
)

if [[ "$FORCE" != "1" ]]; then
  for output in "${required_outputs[@]}"; do
    if [[ -e "$output" ]]; then
      echo "Refusing to overwrite existing certificate material in $CERT_DIR."
      echo "Set PENTAI_FORCE_CERT_REGEN=1 to rotate the entire lab trust chain."
      exit 1
    fi
  done
fi

tmp_dir=$(mktemp -d)
cleanup() {
  rm -rf "$tmp_dir"
}
trap cleanup EXIT

server_ext="$tmp_dir/server-ext.cnf"
client_ext="$tmp_dir/client-ext.cnf"

cat >"$server_ext" <<EOF
[v3_req]
basicConstraints = CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
IP.1 = ${WEAPON_NODE_IP}
EOF

cat >"$client_ext" <<'EOF'
[v3_req]
basicConstraints = CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = clientAuth
EOF

umask 077

openssl req -x509 -newkey rsa:4096 -sha256 -nodes \
  -days 825 \
  -subj "$CA_SUBJECT" \
  -keyout "$CERT_DIR/ca-key.pem" \
  -out "$CERT_DIR/ca-cert.pem"

openssl req -newkey rsa:4096 -sha256 -nodes \
  -subj "$COMMAND_SUBJECT" \
  -keyout "$CERT_DIR/command-client-key.pem" \
  -out "$tmp_dir/command-client.csr"

openssl x509 -req -sha256 \
  -in "$tmp_dir/command-client.csr" \
  -CA "$CERT_DIR/ca-cert.pem" \
  -CAkey "$CERT_DIR/ca-key.pem" \
  -CAcreateserial \
  -days 825 \
  -out "$CERT_DIR/command-client-cert.pem" \
  -extfile "$client_ext" \
  -extensions v3_req

openssl req -newkey rsa:4096 -sha256 -nodes \
  -subj "$WEAPON_SUBJECT" \
  -keyout "$CERT_DIR/weapon-server-key.pem" \
  -out "$tmp_dir/weapon-server.csr"

openssl x509 -req -sha256 \
  -in "$tmp_dir/weapon-server.csr" \
  -CA "$CERT_DIR/ca-cert.pem" \
  -CAkey "$CERT_DIR/ca-key.pem" \
  -CAserial "$CERT_DIR/ca-cert.srl" \
  -days 825 \
  -out "$CERT_DIR/weapon-server-cert.pem" \
  -extfile "$server_ext" \
  -extensions v3_req

chmod 600 \
  "$CERT_DIR/ca-key.pem" \
  "$CERT_DIR/command-client-key.pem" \
  "$CERT_DIR/weapon-server-key.pem"
chmod 644 \
  "$CERT_DIR/ca-cert.pem" \
  "$CERT_DIR/command-client-cert.pem" \
  "$CERT_DIR/weapon-server-cert.pem"

echo "Generated PentAI Pro mTLS materials in $CERT_DIR:"
printf '  %s\n' \
  "ca-cert.pem" \
  "command-client-cert.pem" \
  "weapon-server-cert.pem"
