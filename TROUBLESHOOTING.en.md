# Troubleshooting

> 🌐 English | [中文](TROUBLESHOOTING.md)

Sorted by frequency. Each entry includes root cause and fix.

---

## 1. `prefetch.py` connection drops mid-download / `IncompleteRead`

**Symptom**: large HF files (e.g. the ~1.5GB blob in `Systran/faster-whisper-medium.en`) fail with `requests.exceptions.ChunkedEncodingError` or `urllib3.exceptions.ProtocolError: ('Connection broken: IncompleteRead'...)`.

**Cause**: cross-border proxies (v2ray / Clash) are unstable on long-lived big-stream connections.

**Fix**:

- **CN users**: set `HF_MIRROR=https://hf-mirror.com` in `.env`. `prefetch.py` will set `HF_ENDPOINT` and bypass the proxy automatically (the mirror is in CN, proxy hurts).
- **Stable overseas network**: leave `HF_MIRROR` empty, keep `PROXY=`, rely on the built-in 20-attempt retry plus huggingface_hub's automatic resume.

Don't delete `.cache/...incomplete` files — `huggingface_hub` needs them to resume.

---

## 2. `hf_xet` re-downloads the same file forever

**Symptom**: disk and bandwidth shoot to hundreds of GB, but the target file stays at `.incomplete` and progress never advances.

**Cause**: HF's new Xet protocol (chunk-level dedup). `hf_xet` retries the same chunk indefinitely on flaky connections and counts already-transferred bytes as un-transferred.

**Fix**:

```bash
pip uninstall -y hf_xet
```

Without `hf_xet`, `huggingface_hub` falls back to plain HTTP — which is what `prefetch.py` is designed around.

---

## 3. wav2vec2 fails with `PytorchStreamReader failed reading zip archive`

**Symptom**: step 2 (alignment) crashes with `failed finding central directory`.

**Cause**: `torchaudio` pulls `wav2vec2_fairseq_base_ls960_asr_ls960.pth` (~360MB) from `download.pytorch.org` — **this is not an HF mirror can reach**, you need a direct route. `torch.hub` **silently truncates** on connection drop (no error raised), leaving a 100-200MB corrupted file that crashes on next load.

**Fix**:

`prefetch.py` bypasses `torch.hub` — it uses `requests` with `Range` header to resume into `.partial`, validates size ≥ 300MB before renaming. If you see this error, delete the corrupt file and re-run:

```bash
rm /path/to/torch_cache/hub/checkpoints/wav2vec2_fairseq_base_ls960_asr_ls960.pth*
venv/bin/python prefetch.py
```

---

## 4. pyannote returns `401 Unauthorized` or `Cannot access gated repo`

**Symptom**: step 3 (diarization) crashes on startup.

**Cause**: pyannote models are gated. You must accept the license on HF.

**Fix**: while logged in to HF, visit each URL and click "Agree and access repository":

- <https://huggingface.co/pyannote/segmentation-3.0>
- <https://huggingface.co/pyannote/speaker-diarization-3.1>

Make sure `HF_TOKEN` in `.env` has at least read access.

---

## 5. Out-of-memory mid-run / `Killed: 9` / `MemoryError`

**Symptom**: `transcribe.py` is SIGKILL'd by the OS, or step 1 stalls for a long time.

**Cause**: default `medium.en` + `int8` peaks at ~3-4GB on an 8GB Mac. If Chrome (lots of tabs) / Slack / Docker are also running, you hit the ceiling.

**Fix** (try in order):

1. Close browser, Slack, Docker — leave only the terminal
2. Smaller model: `bash run.sh "$AUDIO" --model small.en` (slight quality drop, peaks at ~1.5GB)
3. Reduce parallelism: `--batch-size 1`
4. Resume from where you crashed: `--from-step <next step>`

---

## 6. exFAT external drive: `OSError: [Errno 95] Operation not supported`

**Symptom**: when `HF_CACHE_DIR` points to an exFAT-formatted external SSD, `huggingface_hub` fails to create symlinks.

**Cause**: exFAT does not support symlinks.

**Fix**: `prefetch.py` and `transcribe.py` already set `HF_HUB_DISABLE_SYMLINKS=1`, so this should not happen. If it does, ensure the env var is set **before** `huggingface_hub` is imported (the top-of-file blocks in both scripts handle this — don't reorder them).

---

## 7. Output is empty / garbled

**Symptom**: rendered docx contains empty Speaker N paragraphs.

**Cause**: audio format / sample rate not decoded correctly by `whisperx.load_audio()`.

**Fix**:

```bash
# Convert to 16kHz mono wav first, then feed to transcribe.py
ffmpeg -i input.m4a -ac 1 -ar 16000 input.wav
bash run.sh input.wav
```

---

## Where the intermediate files live

Each run creates a hidden working dir next to the audio: `.transcribe_<stem>/`, containing:

```
1_segments.json   # step 1: raw transcription segments
2_aligned.json    # step 2: word-level alignment
3_diarize.json    # step 3: speaker diarization
4_final.json      # step 4: merged final
```

Pass `--keep-temp` to retain them; otherwise they're cleaned up on success. To resume from a specific step: `bash run.sh "$AUDIO" --from-step 3 --keep-temp`.
