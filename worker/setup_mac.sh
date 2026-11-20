#!/usr/bin/env bash
# One-time setup on macOS (Apple Silicon or Intel).
set -euo pipefail
cd "$(dirname "$0")"
command -v brew >/dev/null || { echo "Install Homebrew first: https://brew.sh"; exit 1; }
brew install ffmpeg cloudflared python@3.11
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
[ -f .env ] || cp .env.example .env
echo "Done. Fill in worker/.env, then run ./start.sh"
