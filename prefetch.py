"""
Pre-download every model to the external SSD without running the actual
transcription. Useful when memory is tight: this step is network-bound and
peaks well under 1 GB, so you can run it while still using the Mac.

After this finishes, run.sh / transcribe.py will read from the cache offline.
"""
import gc
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(SCRIPT_DIR / ".env")

HF_TOKEN = os.environ.get("HF_TOKEN")
HF_CACHE_DIR = os.environ.get("HF_CACHE_DIR")
TORCH_CACHE_DIR = os.environ.get("TORCH_CACHE_DIR")
PROXY = os.environ.get("PROXY")
HF_MIRROR = os.environ.get("HF_MIRROR")  # e.g. https://hf-mirror.com — bypasses proxy

if not HF_TOKEN or not HF_CACHE_DIR or not TORCH_CACHE_DIR:
    sys.exit("HF_TOKEN / HF_CACHE_DIR / TORCH_CACHE_DIR missing in .env")

os.environ["HF_HOME"] = HF_CACHE_DIR
os.environ["HUGGINGFACE_HUB_CACHE"] = HF_CACHE_DIR
os.environ["TRANSFORMERS_CACHE"] = HF_CACHE_DIR
os.environ["TORCH_HOME"] = TORCH_CACHE_DIR
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

if HF_MIRROR:
    # Mirror is in CN, no proxy needed — proxy actually hurts here
    os.environ["HF_ENDPOINT"] = HF_MIRROR
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
        os.environ.pop(k, None)
    print(f"using HF mirror: {HF_MIRROR} (proxy bypassed)")
elif PROXY:
    os.environ["HTTP_PROXY"] = PROXY
    os.environ["HTTPS_PROXY"] = PROXY
    os.environ["http_proxy"] = PROXY
    os.environ["https_proxy"] = PROXY

Path(HF_CACHE_DIR).mkdir(parents=True, exist_ok=True)
Path(TORCH_CACHE_DIR).mkdir(parents=True, exist_ok=True)

# Repo-id, needs-token, approx-size
HF_REPOS = [
    ("Systran/faster-whisper-medium.en", False, "~470 MB"),
    ("pyannote/segmentation-3.0", True, "~6 MB"),
    ("pyannote/speaker-diarization-3.1", True, "~6 MB"),
    ("pyannote/wespeaker-voxceleb-resnet34-LM", False, "~26 MB"),
]


def main():
    print(f"HF cache    : {HF_CACHE_DIR}")
    print(f"torch cache : {TORCH_CACHE_DIR}")
    print()

    from huggingface_hub import snapshot_download

    MAX_ATTEMPTS = 20  # proxy is flaky on big files; resume picks up where it dropped

    for repo, gated, size in HF_REPOS:
        print(f"[HF] {repo}  ({size})")
        kwargs = {
            "repo_id": repo,
            "cache_dir": HF_CACHE_DIR,
            "max_workers": 2,  # fewer parallel streams = fewer drops over flaky proxy
        }
        if gated:
            kwargs["token"] = HF_TOKEN
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                path = snapshot_download(**kwargs)
                print(f"     ok -> {path}")
                break
            except Exception as e:
                print(f"     attempt {attempt}/{MAX_ATTEMPTS} dropped: {type(e).__name__}: {e}")
                if attempt == MAX_ATTEMPTS:
                    print(f"     FAILED after {MAX_ATTEMPTS} attempts")
                    sys.exit(1)
                time.sleep(3)
        print()

    # torchaudio align model — only available via torchaudio's own CDN
    # (download.pytorch.org), which is overseas and needs the proxy.
    # We download manually with retries because torch.hub silently truncates
    # on a dropped connection (we hit a 125MB partial file once).
    print("[torchaudio] WAV2VEC2_ASR_BASE_960H  (~360 MB)")

    if PROXY:
        os.environ["HTTP_PROXY"] = PROXY
        os.environ["HTTPS_PROXY"] = PROXY
        os.environ["http_proxy"] = PROXY
        os.environ["https_proxy"] = PROXY
        print(f"     proxy restored for torchaudio CDN: {PROXY}")

    import requests

    wav2vec_url = "https://download.pytorch.org/torchaudio/models/wav2vec2_fairseq_base_ls960_asr_ls960.pth"
    target_dir = Path(TORCH_CACHE_DIR) / "hub" / "checkpoints"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "wav2vec2_fairseq_base_ls960_asr_ls960.pth"
    tmp = target.with_suffix(".pth.partial")

    if not target.exists() or target.stat().st_size < 300 * 1024 * 1024:
        # Loop until we have a complete file. requests + stream + resume.
        for attempt in range(1, MAX_ATTEMPTS + 1):
            existing = tmp.stat().st_size if tmp.exists() else 0
            headers = {"Range": f"bytes={existing}-"} if existing else {}
            try:
                with requests.get(wav2vec_url, headers=headers, stream=True, timeout=30) as r:
                    r.raise_for_status()
                    total_expected = existing + int(r.headers.get("Content-Length", 0))
                    mode = "ab" if existing else "wb"
                    with open(tmp, mode) as f:
                        for chunk in r.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                f.write(chunk)
                got = tmp.stat().st_size
                if got >= total_expected and got > 300 * 1024 * 1024:
                    tmp.rename(target)
                    print(f"     downloaded {got / (1024*1024):.1f} MB on attempt {attempt}")
                    break
                print(f"     attempt {attempt}/{MAX_ATTEMPTS}: got {got / (1024*1024):.1f}MB, expected {total_expected / (1024*1024):.1f}MB — retry")
            except Exception as e:
                print(f"     attempt {attempt}/{MAX_ATTEMPTS} dropped: {type(e).__name__}: {e}")
            if attempt == MAX_ATTEMPTS:
                print(f"     FAILED after {MAX_ATTEMPTS} attempts")
                sys.exit(1)
            time.sleep(3)

    # Now have torchaudio actually load it to validate + register the model
    import torchaudio  # noqa: E402

    bundle = torchaudio.pipelines.WAV2VEC2_ASR_BASE_960H
    m = bundle.get_model()
    del m, bundle
    gc.collect()
    print(f"     ok -> {target}")
    print()

    total = sum(
        f.stat().st_size for f in Path(HF_CACHE_DIR).rglob("*") if f.is_file()
    )
    total += sum(
        f.stat().st_size for f in Path(TORCH_CACHE_DIR).rglob("*") if f.is_file()
    )
    print(f"all models cached. total on disk: {total / (1024 ** 3):.2f} GB")
    print("next: bash run.sh '/path/to/audio.m4a'")


if __name__ == "__main__":
    main()
