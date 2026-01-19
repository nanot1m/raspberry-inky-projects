#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
debounce_seconds=2

if ! command -v fswatch >/dev/null 2>&1; then
  echo "fswatch is required. Install with: brew install fswatch" >&2
  exit 1
fi

echo "Watching $repo_root/my-dashboard for changes..."
fswatch -o -l "$debounce_seconds" \
  -e "\.git/" \
  -e "__pycache__/" \
  -e "\.pyc$" \
  -e "\.DS_Store$" \
  -e "/web/" \
  "$repo_root/my-dashboard" | while read -r _; do
  "$repo_root/deploy_to_inky.sh"
done
