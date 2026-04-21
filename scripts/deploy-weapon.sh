#!/usr/bin/env bash
# Deploy the PentAI Pro Tool Gateway to the Weapon Node via SSH key auth.
#
# Prerequisite on the Command Node:
#   - ~/.ssh/config has a `weapon` Host alias (User + IdentityFile)
#   - tool-gateway code + certs are current on this node
#   - PENTAI_GATEWAY_JWT_SECRET exported (or read from pentai-pro/.env)
#
# Prerequisite on the Weapon Node (one-time, before the first run):
#   sudo apt-get update && sudo apt-get install -y python3 python3-venv nmap curl rsync
#   echo '<user> ALL=(ALL) NOPASSWD: /bin/systemctl restart pentai-tool-gateway.service, /bin/systemctl status pentai-tool-gateway.service, /usr/bin/install -m 0644 * /etc/systemd/system/pentai-tool-gateway.service, /bin/systemctl daemon-reload, /bin/systemctl enable pentai-tool-gateway.service' | sudo tee /etc/sudoers.d/pentai-gateway
#
# After the first deploy, subsequent runs only need `systemctl restart` via sudoers.

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)

WEAPON_ALIAS="${WEAPON_ALIAS:-weapon}"
REMOTE_USER="${REMOTE_USER:-$(ssh -G "$WEAPON_ALIAS" | awk '/^user / {print $2}')}"
APP_DIR="${WEAPON_APP_DIR:-/home/${REMOTE_USER}/pentai-gateway}"
GATEWAY_AUDIENCE="${PENTAI_GATEWAY_AUDIENCE:-pentai-tool-gateway}"

if [[ -z "${PENTAI_GATEWAY_JWT_SECRET:-}" && -f "$REPO_ROOT/.env" ]]; then
  PENTAI_GATEWAY_JWT_SECRET=$(awk -F= '/^PENTAI_GATEWAY_JWT_SECRET=/ {sub(/^[^=]+=/,""); print}' "$REPO_ROOT/.env")
fi

if [[ -z "${PENTAI_GATEWAY_JWT_SECRET:-}" ]]; then
  echo "PENTAI_GATEWAY_JWT_SECRET must be set (export it or add to .env)." >&2
  exit 1
fi

required_local_files=(
  "$REPO_ROOT/certs/ca-cert.pem"
  "$REPO_ROOT/certs/weapon-server-cert.pem"
  "$REPO_ROOT/certs/weapon-server-key.pem"
  "$REPO_ROOT/tool-gateway/deploy/pentai-tool-gateway.service"
  "$REPO_ROOT/tool-gateway/pyproject.toml"
)

for file in "${required_local_files[@]}"; do
  if [[ ! -f "$file" ]]; then
    echo "Missing required local file: $file" >&2
    exit 1
  fi
done

echo "==> Probing weapon node at $WEAPON_ALIAS (user=$REMOTE_USER)..."
ssh "$WEAPON_ALIAS" "echo connected-as-\$(whoami) && uname -a"

echo "==> Ensuring remote directory layout..."
ssh "$WEAPON_ALIAS" "mkdir -p '$APP_DIR/tool-gateway' '$APP_DIR/certs'"

echo "==> Syncing tool-gateway code..."
rsync -az --delete \
  --exclude '__pycache__' --exclude '.venv' --exclude 'uv.lock' \
  "$REPO_ROOT/tool-gateway/" \
  "$WEAPON_ALIAS:$APP_DIR/tool-gateway/"

echo "==> Syncing mTLS material..."
rsync -az \
  "$REPO_ROOT/certs/ca-cert.pem" \
  "$REPO_ROOT/certs/weapon-server-cert.pem" \
  "$REPO_ROOT/certs/weapon-server-key.pem" \
  "$WEAPON_ALIAS:$APP_DIR/certs/"

echo "==> Writing gateway environment file..."
ssh "$WEAPON_ALIAS" "cat > '$APP_DIR/tool-gateway.env'" <<EOF
GATEWAY_HOST=0.0.0.0
GATEWAY_PORT=5000
GATEWAY_AUDIENCE=${GATEWAY_AUDIENCE}
GATEWAY_JWT_SECRET=${PENTAI_GATEWAY_JWT_SECRET}
GATEWAY_SERVER_CERT=${APP_DIR}/certs/weapon-server-cert.pem
GATEWAY_SERVER_KEY=${APP_DIR}/certs/weapon-server-key.pem
GATEWAY_CA_CERT=${APP_DIR}/certs/ca-cert.pem
EOF

echo "==> Rendering + installing systemd unit..."
unit_local=$(mktemp)
trap 'rm -f "$unit_local"' EXIT
sed \
  -e "s|__PENTAI_GATEWAY_USER__|${REMOTE_USER}|g" \
  -e "s|__PENTAI_GATEWAY_APP_DIR__|${APP_DIR}|g" \
  "$REPO_ROOT/tool-gateway/deploy/pentai-tool-gateway.service" >"$unit_local"

rsync -az "$unit_local" "$WEAPON_ALIAS:/tmp/pentai-tool-gateway.service"

ssh -t "$WEAPON_ALIAS" bash -s <<REMOTE
set -euo pipefail
cd "$APP_DIR/tool-gateway"
python3 -m venv --clear "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip >/dev/null
"$APP_DIR/.venv/bin/pip" install . >/dev/null
chmod 600 "$APP_DIR/certs/weapon-server-key.pem" "$APP_DIR/tool-gateway.env"
chmod 644 "$APP_DIR/certs/ca-cert.pem" "$APP_DIR/certs/weapon-server-cert.pem"
sudo install -m 0644 /tmp/pentai-tool-gateway.service /etc/systemd/system/pentai-tool-gateway.service
sudo systemctl daemon-reload
sudo systemctl enable pentai-tool-gateway.service
sudo systemctl restart pentai-tool-gateway.service
sleep 2
sudo systemctl status pentai-tool-gateway.service --no-pager || true
REMOTE

echo "==> Healthcheck over mTLS from the command node..."
curl --cacert "$REPO_ROOT/certs/ca-cert.pem" \
  --cert    "$REPO_ROOT/certs/command-client-cert.pem" \
  --key     "$REPO_ROOT/certs/command-client-key.pem" \
  --max-time 5 \
  -s "https://172.20.32.68:5000/healthz" \
  && echo "" \
  && echo "Tool Gateway healthy on weapon node."
