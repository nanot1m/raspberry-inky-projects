#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ssh hazam-inky.local 'mkdir -p /home/hazam/projects/my-dashboard'
"$repo_root/sync_to_inky.sh"

ssh hazam-inky.local <<'EOF'
sudo cp /home/hazam/projects/my-dashboard/scripts/my-dashboard-http.service \
  /etc/systemd/system/my-dashboard-http.service
sudo systemctl daemon-reload
sudo systemctl enable --now my-dashboard-http.service
sudo systemctl restart my-dashboard-http.service
EOF
