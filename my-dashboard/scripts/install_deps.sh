#!/usr/bin/env bash
set -euo pipefail

sudo apt-get update
sudo apt-get install -y \
  python3 \
  python3-venv \
  python3-pip \
  git \
  rsync \
  libcairo2 \
  libpango-1.0-0 \
  libgdk-pixbuf-2.0-0 \
  libffi-dev

python3 -m venv /home/hazam/inky-venv
/home/hazam/inky-venv/bin/pip install --upgrade pip
/home/hazam/inky-venv/bin/pip install -r /home/hazam/projects/my-dashboard/requirements.txt
