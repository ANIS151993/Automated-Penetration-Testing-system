#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)

WEAPON_NODE_HOST="${WEAPON_NODE_HOST:-172.20.32.68}"
WEAPON_NODE_PORT="${WEAPON_NODE_PORT:-22}"
WEAPON_NODE_USER="${WEAPON_NODE_USER:-kali}"
WEAPON_NODE_PASSWORD="${WEAPON_NODE_PASSWORD:-}"
APP_DIR="${WEAPON_NODE_APP_DIR:-/home/${WEAPON_NODE_USER}/pentai-gateway}"
JWT_SECRET="${PENTAI_GATEWAY_JWT_SECRET:-}"
GATEWAY_AUDIENCE="${PENTAI_GATEWAY_AUDIENCE:-pentai-tool-gateway}"

if [[ -z "$WEAPON_NODE_PASSWORD" ]]; then
  echo "WEAPON_NODE_PASSWORD is required."
  exit 1
fi

if [[ -z "$JWT_SECRET" ]]; then
  echo "PENTAI_GATEWAY_JWT_SECRET is required."
  exit 1
fi

tool_gateway_dir="$REPO_ROOT/tool-gateway"
cert_dir="$REPO_ROOT/certs"
service_template="$tool_gateway_dir/deploy/pentai-tool-gateway.service"

required_local_files=(
  "$cert_dir/ca-cert.pem"
  "$cert_dir/weapon-server-cert.pem"
  "$cert_dir/weapon-server-key.pem"
  "$service_template"
  "$tool_gateway_dir/pyproject.toml"
)

for file in "${required_local_files[@]}"; do
  if [[ ! -f "$file" ]]; then
    echo "Missing required local file: $file"
    exit 1
  fi
done

ssh_opts=(
  -o PreferredAuthentications=password
  -o PubkeyAuthentication=no
  -o StrictHostKeyChecking=no
  -p "$WEAPON_NODE_PORT"
)

scp_opts=(
  -o PreferredAuthentications=password
  -o PubkeyAuthentication=no
  -o StrictHostKeyChecking=no
  -P "$WEAPON_NODE_PORT"
)

sshpass -p "$WEAPON_NODE_PASSWORD" ssh "${ssh_opts[@]}" \
  "${WEAPON_NODE_USER}@${WEAPON_NODE_HOST}" \
  "mkdir -p '$APP_DIR/tool-gateway' '$APP_DIR/certs'"

sshpass -p "$WEAPON_NODE_PASSWORD" rsync -az --delete \
  -e "ssh ${ssh_opts[*]}" \
  "$tool_gateway_dir/" \
  "${WEAPON_NODE_USER}@${WEAPON_NODE_HOST}:$APP_DIR/tool-gateway/"

sshpass -p "$WEAPON_NODE_PASSWORD" scp "${scp_opts[@]}" \
  "$cert_dir/ca-cert.pem" \
  "$cert_dir/weapon-server-cert.pem" \
  "$cert_dir/weapon-server-key.pem" \
  "${WEAPON_NODE_USER}@${WEAPON_NODE_HOST}:$APP_DIR/certs/"

env_file=$(mktemp)
service_file=$(mktemp)
trap 'rm -f "$env_file" "$service_file"' EXIT

cat >"$env_file" <<EOF
GATEWAY_HOST=0.0.0.0
GATEWAY_PORT=5000
GATEWAY_AUDIENCE=${GATEWAY_AUDIENCE}
GATEWAY_JWT_SECRET=${JWT_SECRET}
GATEWAY_SERVER_CERT=${APP_DIR}/certs/weapon-server-cert.pem
GATEWAY_SERVER_KEY=${APP_DIR}/certs/weapon-server-key.pem
GATEWAY_CA_CERT=${APP_DIR}/certs/ca-cert.pem
EOF

sed \
  -e "s|__PENTAI_GATEWAY_USER__|${WEAPON_NODE_USER}|g" \
  -e "s|__PENTAI_GATEWAY_APP_DIR__|${APP_DIR}|g" \
  "$service_template" >"$service_file"

sshpass -p "$WEAPON_NODE_PASSWORD" scp "${scp_opts[@]}" \
  "$env_file" \
  "$service_file" \
  "${WEAPON_NODE_USER}@${WEAPON_NODE_HOST}:/tmp/"

remote_cmd=$(cat <<EOF
set -euo pipefail
python3 -m virtualenv --clear '${APP_DIR}/.venv'
'${APP_DIR}/.venv/bin/pip' install --upgrade pip
'${APP_DIR}/.venv/bin/pip' install '${APP_DIR}/tool-gateway'
chmod 600 '${APP_DIR}/certs/weapon-server-key.pem'
chmod 644 '${APP_DIR}/certs/ca-cert.pem' '${APP_DIR}/certs/weapon-server-cert.pem'
mv /tmp/$(basename "$env_file") '${APP_DIR}/tool-gateway.env'
printf '%s\n' '${WEAPON_NODE_PASSWORD}' | sudo -S install -m 0644 /tmp/$(basename "$service_file") /etc/systemd/system/pentai-tool-gateway.service
printf '%s\n' '${WEAPON_NODE_PASSWORD}' | sudo -S systemctl daemon-reload
printf '%s\n' '${WEAPON_NODE_PASSWORD}' | sudo -S systemctl enable pentai-tool-gateway.service
printf '%s\n' '${WEAPON_NODE_PASSWORD}' | sudo -S systemctl restart pentai-tool-gateway.service
printf '%s\n' '${WEAPON_NODE_PASSWORD}' | sudo -S systemctl status pentai-tool-gateway.service --no-pager
EOF
)

sshpass -p "$WEAPON_NODE_PASSWORD" ssh "${ssh_opts[@]}" \
  "${WEAPON_NODE_USER}@${WEAPON_NODE_HOST}" \
  "$remote_cmd"

echo "Weapon node gateway deployed to ${WEAPON_NODE_USER}@${WEAPON_NODE_HOST}:${APP_DIR}"
