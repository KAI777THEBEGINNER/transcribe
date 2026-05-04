#!/usr/bin/env bash
# Run the transcription pipeline.
# Usage: bash run.sh "/path/to/audio.m4a" [extra args for transcribe.py]
set -euo pipefail

cd "$(dirname "$0")"

if [ "$#" -lt 1 ]; then
    cat <<EOF
Usage: bash run.sh <audio_path> [options]

Options forwarded to transcribe.py:
    --model small.en|medium.en|large-v3   (default: medium.en)
    --batch-size N                         (default: 4)
    --compute-type int8|float32            (default: int8)
    --min-speakers N --max-speakers N      (default: 2/2)
    --keep-temp                            (keep intermediate .json files)
    --from-step 1|2|3|4                    (resume from a step)

Example: bash run.sh ~/Downloads/podcast.m4a --model small.en
EOF
    exit 1
fi

# Load .env (token, proxy, cache dir)
if [ -f .env ]; then
    set -a; . ./.env; set +a
fi
if [ -n "${PROXY:-}" ]; then
    export HTTP_PROXY="$PROXY" HTTPS_PROXY="$PROXY"
    export http_proxy="$PROXY" https_proxy="$PROXY"
fi

if [ ! -d venv ]; then
    echo "venv missing — run: bash setup.sh"
    exit 1
fi
. venv/bin/activate

python transcribe.py "$@"
