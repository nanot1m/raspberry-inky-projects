#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source_dir="$repo_root/my-dashboard/"
destination="hazam-inky.local:/home/hazam/projects/my-dashboard/"

sync_config="${SYNC_CONFIG:-0}"

rsync -av --delete \
  --exclude ".git" \
  --exclude "__pycache__" \
  --exclude "*.pyc" \
  --exclude ".DS_Store" \
  $( [ "$sync_config" = "1" ] || printf '%s' "--exclude config.json" ) \
  "$source_dir" "$destination"
