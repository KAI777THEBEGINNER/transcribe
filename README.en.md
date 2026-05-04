# transcribe

> 🌐 English | [中文](README.md)

Fully **on-device** transcription for English/Chinese podcasts (m4a / mp3 / wav) into speaker-separated `.docx` with timestamps.

No cloud uploads, no remote APIs. Models are cached to a disk you choose — external SSD works fine. A 1-hour podcast takes ~2 hours of CPU on an 8GB M1/M2 Mac.

Pipeline: `faster-whisper` (transcription) → `wav2vec2` (word-level alignment) → `pyannote` (speaker diarization) → `python-docx` (rendering).

---

## Requirements

- macOS (Linux/Windows likely work but untested)
- Python 3.9+
- `ffmpeg` (`brew install ffmpeg`)
- 8GB+ RAM (5GB free recommended)
- 3GB+ disk for model cache
- HuggingFace account + read token

---

## Setup (one-time)

```bash
git clone https://github.com/KAI777THEBEGINNER/transcribe.git
cd transcribe

# 1. Copy env template, fill in your HF token + cache paths
cp .env.example .env
$EDITOR .env

# 2. Create venv and install deps (torch/whisperx, ~5-10 min)
bash setup.sh

# 3. Download models (~1.7GB, first run only)
venv/bin/python prefetch.py
```

Required `.env` fields:

```bash
HF_TOKEN=hf_xxx              # https://huggingface.co/settings/tokens (read access)
HF_CACHE_DIR=/path/to/hf_cache       # any disk with 3GB+ free
TORCH_CACHE_DIR=/path/to/torch_cache # same
```

Optional:

```bash
PROXY=http://127.0.0.1:7890   # HTTP proxy (leave empty for direct connection)
HF_MIRROR=https://hf-mirror.com   # HF mirror for CN users (prefetch auto-bypasses PROXY)
```

⚠️ Before running `prefetch.py`, accept the gated-model agreements:

- <https://huggingface.co/pyannote/segmentation-3.0>
- <https://huggingface.co/pyannote/speaker-diarization-3.1>

---

## Usage

```bash
bash run.sh "/path/to/audio.m4a"
```

Produces `/path/to/audio.docx` with `Speaker N · timestamp` segmentation.

Common flags:

| Flag | Default | Description |
|------|---------|-------------|
| `--model` | `medium.en` | Transcription model; choices: `tiny.en` / `small.en` / `medium.en` / `large-v3` |
| `--lang` | `en` | Language code |
| `--min-speakers --max-speakers` | `2 2` | Speaker count range; single speaker = `1 1`, unknown multi = `1 8` |
| `--batch-size` | `4` | Transcription parallelism; lower to `1` if memory-tight |
| `--compute-type` | `int8` | Also accepts `float32` (more accurate, more memory) |
| `--keep-temp` | off | Keep intermediate JSON files for resume |
| `--from-step N` | `1` | Resume from step N (after a crash) |

Example: 8-person roundtable, max quality:

```bash
bash run.sh meeting.m4a --model large-v3 --min-speakers 1 --max-speakers 8 --keep-temp
```

Example: resume after step 2 finished:

```bash
bash run.sh meeting.m4a --from-step 3 --keep-temp
```

---

## Output format

`.docx` structure:

```
<audio name>
Transcribed YYYY-MM-DD HH:MM
─────────────────
Speaker 0 · 0:00:00
Hello, welcome to the show...

Speaker 1 · 0:00:05
Thanks for having me...
```

Intermediate files in `<audio_dir>/.transcribe_<audio_stem>/` (only with `--keep-temp`):

| File | Content |
|------|---------|
| `1_segments.json` | Step 1: transcription segments (`{start, end, text}` list) |
| `2_aligned.json` | Step 2: word-level alignment |
| `3_diarize.json` | Step 3: speaker diarization |
| `4_final.json` | Merged final data |

---

## Performance reference

`medium.en` + `int8` + Apple M1/M2 8GB, 1-hour English dialogue:

| Step | Duration |
|------|----------|
| `[1/4] faster-whisper transcribe` | 30-45 min |
| `[2/4] word-level alignment` | 3-8 min |
| `[3/4] pyannote diarization` | 60-100 min (pyannote is slow on CPU) |
| `[4/4] merge + render docx` | seconds |
| **Total** | **~2 hours**, 3-4GB peak RAM |

Close browser, Slack and other heavy apps before running. GPU/MPS acceleration is not enabled yet (pyannote MPS support is still unstable).

---

## Troubleshooting

For mid-download drops, zip errors on model load, pyannote 401, OOM and other common issues, see [TROUBLESHOOTING.en.md](TROUBLESHOOTING.en.md).

---

## License

MIT
