#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source_dir="$repo_root/my-dashboard/"
host="${INKY_HOST:-hazam-inky.local}"
ssh_opts="${RSYNC_SSH_OPTS:--o StrictHostKeyChecking=accept-new}"
destination="${host}:/home/hazam/projects/my-dashboard/"

sync_config="${SYNC_CONFIG:-0}"

rsync -av --delete -e "ssh ${ssh_opts}" \
  --exclude ".git" \
  --exclude "__pycache__" \
  --exclude "*.pyc" \
  --exclude ".DS_Store" \
  --exclude ".presets/" \
  --exclude "photos/" \
  --exclude "assets/fonts/custom/" \
  --exclude-from "$repo_root/.gitignore" \
  $( [ "$sync_config" = "1" ] || printf '%s' "--exclude config.json" ) \
  "$source_dir" "$destination"
