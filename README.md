# FFmpeg Silence Trimmer Lite — Auto Jump-Cut Python CLI

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)
![Zero Dependencies](https://img.shields.io/badge/dependencies-zero%20(stdlib%20%2B%20ffmpeg)-brightgreen.svg)

A fast, zero-dependency Python CLI tool that automatically removes dead air and silent pauses from videos using `ffmpeg` (`silencedetect` + `trim`/`atrim`/`concat`). Built for **YouTube Shorts, Instagram Reels, TikTok**, talking-head videos, and podcasts.

---

## Features

- **100% Python Standard Library** — no `pip install` bloat, just Python + system `ffmpeg`.
- **Smart Speech Padding (`--pad`)** — keeps natural breathing room around cuts so jump cuts don't sound clipped.
- **Dry-Run JSON Mode (`--dry-run`)** — inspect detected silence intervals and exact saved seconds before rendering.
- **Tunable Detection** — configure `--threshold` (dB) and `--min-silence` (seconds) for any mic or room.
- **Built-in Self-Test (`--self-test`)** — verifies log parsing, interval merging, `filter_complex` generation, and live `ffmpeg` lavfi trimming.

---

## Quick Start

### 1. Requirements
- Python 3.8+
- `ffmpeg` available in your system `PATH`

### 2. Basic Usage

```bash
# Trim silence with default settings (-30dB, 0.45s min silence, 0.12s padding)
python trim_silence.py raw_video.mp4 -o clean_short.mp4

# Preview cuts and saved seconds without rendering
python trim_silence.py raw_video.mp4 --dry-run

# Stricter threshold for noisy rooms
python trim_silence.py raw_video.mp4 --threshold -25 --min-silence 0.35 --pad 0.10

# Audio-only mode (podcasts / voiceovers)
python trim_silence.py podcast.mp3 --audio-only -o podcast_clean.m4a
```

### 3. Run Self-Test

```bash
python trim_silence.py --self-test
```

---

## Lite vs. Pro Comparison

Need **9:16 vertical framing**, **dynamic TikTok/Reels karaoke subtitles**, and **batch folder processing**?

| Feature | **Lite Silence Trimmer (Free MIT)** | **Pro Shorts/Reels Auto-Cutter** |
| :--- | :---: | :---: |
| Auto Jump-Cut Silence Removal | ✅ | ✅ |
| Configurable dB Threshold & Padding | ✅ | ✅ |
| Dry-Run JSON Report | ✅ | ✅ |
| **9:16 Smart Vertical Crop (Face/Center)** | ❌ | ✅ |
| **Dynamic ASS Karaoke Subtitles (Word-by-Word)** | ❌ | ✅ |
| **Whisper / SRT Auto-Sync** | ❌ | ✅ |
| **Batch Folder Queue Mode** | ❌ | ✅ |
| **EBU R128 Loudness Normalization** | ❌ | ✅ |

👉 **Get the full Pro version on FunPay:** [FFmpeg Shorts/Reels Auto-Cutter Pro](https://funpay.com/lots/offer?id=82598074)

---

## Краткая справка (RU)

**FFmpeg Silence Trimmer Lite** — бесплатный консольный скрипт на Python (без сторонних библиотек, нужен только `ffmpeg` в `PATH`) для автоматической вырезки пауз и тишины из видео для **YouTube Shorts, Reels, TikTok** и подкастов.

- Поддерживает настройку порога тишины (`--threshold -30`), минимальной паузы (`--min-silence 0.45`), отступов (`--pad 0.12`) и режим предпросмотра `--dry-run`.
- Нужна полная автоматизация под вертикальный формат (**9:16 Smart Crop + динамические караоке-субтитры + пакетная обработка папок + Whisper/SRT**)? Полная Pro-версия доступна на FunPay: https://funpay.com/lots/offer?id=82598074

---

## License

MIT License — see [LICENSE](LICENSE) for details.
