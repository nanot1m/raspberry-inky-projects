#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
host="${INKY_HOST:-hazam-inky.local}"
ssh_opts="${RSYNC_SSH_OPTS:--o StrictHostKeyChecking=accept-new}"

ssh $ssh_opts "$host" 'mkdir -p /home/hazam/projects/my-dashboard'
"$repo_root/sync_to_inky.sh"

ssh $ssh_opts "$host" <<'EOF'
sudo cp /home/hazam/projects/my-dashboard/scripts/my-dashboard-http.service \
  /etc/systemd/system/my-dashboard-http.service
sudo systemctl daemon-reload
sudo systemctl enable --now my-dashboard-http.service
sudo systemctl restart my-dashboard-http.service
EOF
