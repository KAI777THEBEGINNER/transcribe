#!/usr/bin/env bash
# One-shot setup: create venv, install deps. Re-running is safe (idempotent).
set -euo pipefail

cd "$(dirname "$0")"

# Load proxy from .env so pip can reach huggingface.co / pypi mirrors
if [ -f .env ]; then
    set -a; . ./.env; set +a
fi
if [ -n "${PROXY:-}" ]; then
    export HTTP_PROXY="$PROXY" HTTPS_PROXY="$PROXY"
    export http_proxy="$PROXY" https_proxy="$PROXY"
    echo "proxy on: $PROXY"
fi

# 1. ffmpeg sanity
if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "ffmpeg not found in PATH. Install with: brew install ffmpeg"
    exit 1
fi
echo "ffmpeg: $(ffmpeg -version 2>&1 | head -1)"

# 2. venv
if [ ! -d venv ]; then
    echo "creating venv..."
    python3 -m venv venv
fi
. venv/bin/activate

# 3. tooling
python -m pip install --upgrade pip wheel setuptools

# 4. project deps (will pull torch ~200MB, expect 5-10min on first run)
echo "installing requirements (will take a few minutes — torch is the big one)..."
pip install -r requirements.txt

echo ""
echo "setup ok. next: bash run.sh '/path/to/audio.m4a'"
