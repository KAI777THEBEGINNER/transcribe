# transcribe

> 🌐 [English](README.en.md) | 中文

把英文/中文播客（m4a / mp3 / wav）**全本地**转写成带说话人分段和时间戳的 `.docx`。

不上传云端，不调远程 API，模型缓存到你指定的硬盘——可以是外置 SSD，1 小时音频在 8GB M1/M2 Mac 上 CPU 跑约 2 小时。

底层 pipeline：`faster-whisper`（转写）→ `wav2vec2`（词级对齐）→ `pyannote`（说话人分离）→ `python-docx`（渲染）。

---

## 系统要求

- macOS（Linux/Windows 理论可行但未测试）
- Python 3.9+
- `ffmpeg`（`brew install ffmpeg`）
- 8GB+ 内存（推荐空出 5GB）
- 3GB+ 磁盘（模型缓存）
- HuggingFace 账号 + read token

---

## 一次性安装

```bash
git clone https://github.com/<your-username>/transcribe.git
cd transcribe

# 1. 复制环境模板，填入你的 HF token + 缓存路径
cp .env.example .env
$EDITOR .env

# 2. 装 venv 和依赖（torch/whisperx，约 5-10 分钟）
bash setup.sh

# 3. 下载模型（约 1.7GB，第一次跑）
venv/bin/python prefetch.py
```

`.env` 至少要填 3 项：

```bash
HF_TOKEN=hf_xxx              # https://huggingface.co/settings/tokens 取 read token
HF_CACHE_DIR=/path/to/hf_cache       # 任意磁盘，3GB+ 自由空间
TORCH_CACHE_DIR=/path/to/torch_cache # 同上
```

可选项：

```bash
PROXY=http://127.0.0.1:7890   # HTTP 代理（留空则直连）
HF_MIRROR=https://hf-mirror.com   # HF 国内镜像（CN 用户推荐设这个，prefetch 自动绕过 PROXY）
```

⚠️ 跑 `prefetch.py` 之前，先到这两个页面**点同意 gated 协议**：

- <https://huggingface.co/pyannote/segmentation-3.0>
- <https://huggingface.co/pyannote/speaker-diarization-3.1>

---

## 用法

```bash
bash run.sh "/path/to/audio.m4a"
```

生成 `/path/to/audio.docx`，按 `Speaker N · 时间戳` 分段。

常用参数：

| 参数 | 默认 | 说明 |
|------|------|------|
| `--model` | `medium.en` | 转写模型，可选 `tiny.en` / `small.en` / `medium.en` / `large-v3` |
| `--lang` | `en` | 语言码 |
| `--min-speakers --max-speakers` | `2 2` | 说话人数量范围；单人就 `1 1`，多人不确定就 `1 8` |
| `--batch-size` | `4` | 转写并行度，内存吃紧改 `1` |
| `--compute-type` | `int8` | 也可以 `float32`，更准但更吃内存 |
| `--keep-temp` | 关 | 保留中间 JSON 方便续跑 |
| `--from-step N` | `1` | 从第 N 步开始（崩了续跑用） |

例：8 人圆桌 + 高质量：

```bash
bash run.sh meeting.m4a --model large-v3 --min-speakers 1 --max-speakers 8 --keep-temp
```

例：续跑（已经跑完前 2 步）：

```bash
bash run.sh meeting.m4a --from-step 3 --keep-temp
```

---

## 输出格式

`.docx` 文件结构：

```
<音频名>
转写于 YYYY-MM-DD HH:MM
─────────────────
Speaker 0 · 0:00:00
Hello, welcome to the show...

Speaker 1 · 0:00:05
Thanks for having me...
```

中间文件在 `<音频目录>/.transcribe_<音频文件名>/`（仅当 `--keep-temp` 时保留）：

| 文件 | 内容 |
|------|------|
| `1_segments.json` | 第 1 步：转写片段（`{start, end, text}` 列表） |
| `2_aligned.json` | 第 2 步：词级对齐（每个词带时间戳） |
| `3_diarize.json` | 第 3 步：说话人分段 |
| `4_final.json` | 合并后的最终数据 |

---

## 性能参考

`medium.en` + `int8` + Apple M1/M2 8GB，1 小时英文双人对话：

| 步骤 | 耗时 |
|------|------|
| `[1/4] faster-whisper transcribe` | 30-45 分钟 |
| `[2/4] word-level alignment` | 3-8 分钟 |
| `[3/4] pyannote diarization` | 60-100 分钟（CPU 上 pyannote 慢） |
| `[4/4] merge + render docx` | 秒级 |
| **合计** | **~2 小时**，峰值内存 3-4GB |

跑的时候关掉浏览器和 Slack 这些大户应用。GPU/MPS 加速暂未开启（pyannote 对 MPS 支持仍不稳定）。

---

## 故障排查

下了一半网断、模型加载报 zip 错误、pyannote 401、内存爆等等，看 [TROUBLESHOOTING.md](TROUBLESHOOTING.md)。

---

## License

MIT
