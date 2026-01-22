#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source_dir="$repo_root/"
host="${INKY_HOST:-hazam-inky.local}"
ssh_opts="${RSYNC_SSH_OPTS:--o StrictHostKeyChecking=accept-new}"
destination="${host}:/home/hazam/projects/"

sync_config="${SYNC_CONFIG:-0}"
sync_git="${SYNC_GIT:-0}"

if [ "$sync_git" = "1" ]; then
  rsync -av -e "ssh ${ssh_opts}" \
    "$repo_root/.git" "$destination"
fi

rsync -av --delete -e "ssh ${ssh_opts}" \
  --exclude ".git" \
  --exclude "__pycache__" \
  --exclude "*.pyc" \
  --exclude ".DS_Store" \
  --exclude ".presets/" \
  --exclude "my-dashboard/.env" \
  --exclude "my-dashboard/.cache/" \
  --exclude "my-dashboard/photos/" \
  --exclude "my-dashboard/assets/fonts/custom/" \
  --exclude-from "$repo_root/.gitignore" \
  $( [ "$sync_config" = "1" ] || printf '%s' "--exclude config.json" ) \
  "$source_dir" "$destination"
