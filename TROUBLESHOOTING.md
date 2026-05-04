# 故障排查

> 🌐 [English](TROUBLESHOOTING.en.md) | 中文

按出现频率从高到低排，每个坑都附原理 + 解决办法。

---

## 1. `prefetch.py` 下到一半连接断 / `IncompleteRead`

**症状**：HF 大文件（如 `Systran/faster-whisper-medium.en` 含 ~1.5GB 单 blob）下到一半 `requests.exceptions.ChunkedEncodingError` 或 `urllib3.exceptions.ProtocolError: ('Connection broken: IncompleteRead'...)`。

**原因**：跨境代理（如 v2ray / Clash）大流量长连接不稳定。

**解决**：

- **国内用户**：在 `.env` 设 `HF_MIRROR=https://hf-mirror.com`。`prefetch.py` 检测到这个变量会自动设 `HF_ENDPOINT` 并跳过代理（镜像在 CN，走代理反而慢）。
- **海外稳定网络**：留空 `HF_MIRROR`、保留 `PROXY=`，靠 `prefetch.py` 内置的 20 次重试 + huggingface_hub 自带的断点续传扛过去。

`.cache/...incomplete` 文件不要删，`huggingface_hub` 续传需要它。

---

## 2. `hf_xet` 把同一个文件下了 N 遍

**症状**：磁盘和流量都飙到几百 GB，但目标文件还停在 `.incomplete`，进度永远卡同一个百分比。

**原因**：HuggingFace 新启用 Xet 协议（chunk-level dedup）。`hf_xet` 包在不稳定连接上会无限循环重试同一个 chunk，且把已传字节当作"还没下"。

**解决**：

```bash
pip uninstall -y hf_xet
```

`huggingface_hub` 没有 `hf_xet` 时会回退到普通 HTTP，本仓库的 `prefetch.py` 已经按这条路径设计。

---

## 3. wav2vec2 加载报 `PytorchStreamReader failed reading zip archive`

**症状**：第 2 步对齐启动时崩，报 `failed finding central directory`。

**原因**：`torchaudio` 下载 `wav2vec2_fairseq_base_ls960_asr_ls960.pth`（约 360MB）从 `download.pytorch.org` 拉，**这不是 HF 镜像能转的**——必须走代理或直连。`torch.hub` 在连接中断时会**静默截断**（不报错），留下个 100-200MB 的损坏文件，下次直接尝试加载就崩。

**解决**：

`prefetch.py` 已绕过 `torch.hub`，自己用 `requests` + `Range` header 续传到 `.partial`，落地前校验大小 ≥ 300MB 才 rename。如果你看到这个错误，先删掉损坏文件再重跑：

```bash
rm /path/to/torch_cache/hub/checkpoints/wav2vec2_fairseq_base_ls960_asr_ls960.pth*
venv/bin/python prefetch.py
```

---

## 4. pyannote 报 `401 Unauthorized` 或 `Cannot access gated repo`

**症状**：第 3 步说话人分离启动时崩。

**原因**：pyannote 是 gated 模型，需要在 HF 网站手动同意协议。

**解决**：登录 HF 后访问以下两页，点 "Agree and access repository"：

- <https://huggingface.co/pyannote/segmentation-3.0>
- <https://huggingface.co/pyannote/speaker-diarization-3.1>

确认 `.env` 里的 `HF_TOKEN` 是 read 权限以上即可。

---

## 5. 中途内存爆 / `Killed: 9` / `MemoryError`

**症状**：`transcribe.py` 跑到一半被系统 SIGKILL，或第 1 步进度长时间不动。

**原因**：默认 `medium.en` + `int8` 在 8GB Mac 上峰值 ~3-4GB，如果其他大户应用（Chrome 多 tab / Slack / Docker）也在跑就会撞天花板。

**解决**：按优先级试：

1. 关掉浏览器、Slack、Docker，只留终端
2. 降模型：`bash run.sh "$AUDIO" --model small.en`（质量略降，内存峰值 ~1.5GB）
3. 降并行：`--batch-size 1`
4. 用 `--from-step <已完成的下一步>` 续跑，避免重头来

---

## 6. exFAT 外置盘报 `OSError: [Errno 95] Operation not supported`

**症状**：`HF_CACHE_DIR` 指向 exFAT 格式的外置 SSD 时，`huggingface_hub` 创建 symlink 失败。

**原因**：exFAT 不支持 symlink。

**解决**：`prefetch.py` 和 `transcribe.py` 已经设了 `HF_HUB_DISABLE_SYMLINKS=1`，理论上不该撞。如果还是撞，确认环境变量在 import `huggingface_hub` 之前生效（即两个脚本顶部那一段不要改）。

---

## 7. 转写出来全是空白或乱码

**症状**：docx 渲染出来 Speaker N 段都是空字符串。

**原因**：音频格式或采样率有问题，`whisperx.load_audio()` 没正确解码。

**解决**：

```bash
# 先把音频用 ffmpeg 转成 16kHz 单声道 wav，再喂给 transcribe.py
ffmpeg -i input.m4a -ac 1 -ar 16000 input.wav
bash run.sh input.wav
```

---

## 中间文件在哪

每次跑会在音频同目录建一个 `.transcribe_<音频文件名>/` 隐藏目录，里面：

```
1_segments.json   # 第 1 步：转写片段
2_aligned.json    # 第 2 步：词级对齐
3_diarize.json    # 第 3 步：说话人分离
4_final.json      # 第 4 步：合并后的最终数据
```

加 `--keep-temp` 保留这些；不加默认会清掉。下次想从中间某步续跑：`bash run.sh "$AUDIO" --from-step 3 --keep-temp`。
