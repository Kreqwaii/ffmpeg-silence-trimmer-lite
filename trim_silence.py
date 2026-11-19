#!/usr/bin/env python3
"""
FFmpeg Silence Trimmer Lite — Auto Jump-Cut CLI for Shorts, Reels & TikTok.
Zero external Python dependencies (100% stdlib + system ffmpeg).
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import List, Optional, Tuple


SILENCE_START_RE = re.compile(r"silence_start:\s*([0-9]+(?:\.[0-9]+)?)")
SILENCE_END_RE = re.compile(
    r"silence_end:\s*([0-9]+(?:\.[0-9]+)?)\s*\|\s*silence_duration:\s*([0-9]+(?:\.[0-9]+)?)"
)
DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")


@dataclass
class Segment:
    start: float
    end: float

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    def to_dict(self) -> dict:
        return {
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "duration": round(self.duration, 3),
        }


def parse_ffmpeg_duration(stderr_text: str) -> Optional[float]:
    m = DURATION_RE.search(stderr_text)
    if not m:
        return None
    hours, mins, secs = int(m.group(1)), int(m.group(2)), float(m.group(3))
    return hours * 3600.0 + mins * 60.0 + secs


def parse_silencedetect_output(
    stderr_text: str, total_duration: Optional[float] = None
) -> List[Segment]:
    """Parse ffmpeg silencedetect stderr logs into silence intervals."""
    silences: List[Segment] = []
    current_start: Optional[float] = None

    for line in stderr_text.splitlines():
        m_start = SILENCE_START_RE.search(line)
        if m_start:
            current_start = float(m_start.group(1))
            continue

        m_end = SILENCE_END_RE.search(line)
        if m_end:
            end_t = float(m_end.group(1))
            start_t = current_start if current_start is not None else max(0.0, end_t - float(m_end.group(2)))
            if end_t > start_t:
                silences.append(Segment(start=start_t, end=end_t))
            current_start = None

    if current_start is not None and total_duration is not None and total_duration > current_start:
        silences.append(Segment(start=current_start, end=total_duration))

    return silences


def compute_speech_segments(
    silences: List[Segment],
    total_duration: float,
    pad: float = 0.12,
    min_segment: float = 0.05,
) -> List[Segment]:
    """Invert silence intervals into speech intervals with padding and overlap merging."""
    if total_duration <= 0:
        return []

    if not silences:
        return [Segment(0.0, total_duration)]

    raw_speech: List[Segment] = []
    cursor = 0.0

    for s in sorted(silences, key=lambda x: x.start):
        if s.start > cursor:
            raw_speech.append(Segment(cursor, s.start))
        cursor = max(cursor, s.end)

    if cursor < total_duration:
        raw_speech.append(Segment(cursor, total_duration))

    if not raw_speech:
        return []

    # Apply padding
    padded: List[Segment] = []
    for seg in raw_speech:
        start = max(0.0, seg.start - pad)
        end = min(total_duration, seg.end + pad)
        if end - start >= min_segment:
            padded.append(Segment(start, end))

    if not padded:
        return []

    # Merge overlapping or touching segments
    merged: List[Segment] = [padded[0]]
    for seg in padded[1:]:
        last = merged[-1]
        if seg.start <= last.end + 1e-4:
            last.end = max(last.end, seg.end)
        else:
            merged.append(seg)

    return merged


def build_filter_complex(segments: List[Segment], has_video: bool = True) -> str:
    """Build ffmpeg filter_complex string using trim/atrim and concat."""
    if not segments:
        raise ValueError("Cannot build filter_complex for empty segment list.")

    parts: List[str] = []
    concat_inputs: List[str] = []

    for idx, seg in enumerate(segments):
        s = f"{seg.start:.3f}"
        e = f"{seg.end:.3f}"
        if has_video:
            parts.append(f"[0:v]trim=start={s}:end={e},setpts=PTS-STARTPTS[v{idx}]")
            parts.append(f"[0:a]atrim=start={s}:end={e},asetpts=PTS-STARTPTS[a{idx}]")
            concat_inputs.append(f"[v{idx}][a{idx}]")
        else:
            parts.append(f"[0:a]atrim=start={s}:end={e},asetpts=PTS-STARTPTS[a{idx}]")
            concat_inputs.append(f"[a{idx}]")

    n = len(segments)
    if has_video:
        parts.append(f"{''.join(concat_inputs)}concat=n={n}:v=1:a=1[outv][outa]")
    else:
        parts.append(f"{''.join(concat_inputs)}concat=n={n}:v=0:a=1[outa]")

    return ";".join(parts)


def detect_silence_ffmpeg(
    input_path: str, threshold_db: float, min_silence: float
) -> Tuple[List[Segment], float]:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-i",
        input_path,
        "-af",
        f"silencedetect=noise={threshold_db}dB:d={min_silence}",
        "-f",
        "null",
        "-",
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stderr_text = proc.stderr or ""
    total_duration = parse_ffmpeg_duration(stderr_text)
    if total_duration is None:
        raise RuntimeError(f"Could not determine media duration from ffmpeg output.\n{stderr_text[-500:]}")
    silences = parse_silencedetect_output(stderr_text, total_duration=total_duration)
    return silences, total_duration


def trim_media(
    input_path: str,
    output_path: str,
    segments: List[Segment],
    has_video: bool = True,
) -> None:
    fc = build_filter_complex(segments, has_video=has_video)
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        input_path,
        "-filter_complex",
        fc,
    ]
    if has_video:
        cmd.extend(["-map", "[outv]", "-map", "[outa]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "192k"])
    else:
        cmd.extend(["-map", "[outa]", "-c:a", "aac", "-b:a", "192k"])
    cmd.append(output_path)

    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg trim failed (code {proc.returncode}): {proc.stderr}")


def run_self_test() -> int:
    checks_passed = 0
    total_checks = 4  # 3 unit checks + 1 optional ffmpeg e2e check (adjusted below if ffmpeg missing)

    # 1. Test silencedetect log parser
    sample_log = (
        "Duration: 00:00:10.00, start: 0.000000, bitrate: 128 kb/s\n"
        "[silencedetect @ 0x0] silence_start: 1.500\n"
        "[silencedetect @ 0x0] silence_end: 3.000 | silence_duration: 1.500\n"
        "[silencedetect @ 0x0] silence_start: 6.200\n"
        "[silencedetect @ 0x0] silence_end: 8.200 | silence_duration: 2.000\n"
    )
    dur = parse_ffmpeg_duration(sample_log)
    silences = parse_silencedetect_output(sample_log, total_duration=dur)
    assert dur == 10.0, f"Expected 10.0, got {dur}"
    assert len(silences) == 2, f"Expected 2 silences, got {len(silences)}"
    assert abs(silences[0].start - 1.5) < 1e-6 and abs(silences[0].end - 3.0) < 1e-6
    checks_passed += 1

    # 2. Test speech segment computation with padding & merging
    speech = compute_speech_segments(silences, total_duration=10.0, pad=0.12)
    assert len(speech) == 3, f"Expected 3 speech segments, got {len(speech)}"
    assert abs(speech[0].start - 0.0) < 1e-6 and abs(speech[0].end - 1.62) < 1e-6
    assert abs(speech[1].start - 2.88) < 1e-6 and abs(speech[1].end - 6.32) < 1e-6
    assert abs(speech[2].start - 8.08) < 1e-6 and abs(speech[2].end - 10.0) < 1e-6
    checks_passed += 1

    # 3. Test filter_complex generation
    fc = build_filter_complex(speech, has_video=True)
    assert "[0:v]trim=start=0.000:end=1.620,setpts=PTS-STARTPTS[v0]" in fc
    assert "concat=n=3:v=1:a=1[outv][outa]" in fc
    checks_passed += 1

    # 4. Optional live ffmpeg E2E test with lavfi 3s clip (1s tone + 1s silence + 1s tone)
    if shutil.which("ffmpeg"):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = os.path.join(tmpdir, "test_in.mp4")
            dst = os.path.join(tmpdir, "test_out.mp4")
            gen_cmd = [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "color=c=black:s=320x240:d=3:r=25",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:duration=1",
                "-f",
                "lavfi",
                "-i",
                "anullsrc=r=44100:cl=mono:d=1",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:duration=1",
                "-filter_complex",
                "[1:a][2:a][3:a]concat=n=3:v=0:a=1[aout]",
                "-map",
                "0:v",
                "-map",
                "[aout]",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-c:a",
                "aac",
                "-shortest",
                src,
            ]
            subprocess.run(gen_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            det_silences, total_dur = detect_silence_ffmpeg(src, threshold_db=-30.0, min_silence=0.45)
            kept = compute_speech_segments(det_silences, total_dur, pad=0.10)
            trim_media(src, dst, kept, has_video=True)
            _, out_dur = detect_silence_ffmpeg(dst, threshold_db=-30.0, min_silence=0.45)
            assert out_dur < total_dur - 0.3, f"Expected trimmed duration < {total_dur - 0.3:.2f}, got {out_dur:.2f}"
            checks_passed += 1
    else:
        total_checks = 3
        print("INFO: ffmpeg not found in PATH, skipped live E2E lavfi test.")

    print(f"{checks_passed}/{total_checks} CHECKS PASSED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="FFmpeg Silence Trimmer Lite — Auto Jump-Cut CLI for Shorts/Reels/TikTok"
    )
    parser.add_argument("input", nargs="?", help="Input video/audio file path")
    parser.add_argument("-o", "--output", help="Output file path (default: <input>_trimmed.mp4)")
    parser.add_argument("--threshold", type=float, default=-30.0, help="Silence threshold in dB (default: -30.0)")
    parser.add_argument("--min-silence", type=float, default=0.45, help="Minimum silence duration in seconds (default: 0.45)")
    parser.add_argument("--pad", type=float, default=0.12, help="Padding around speech segments in seconds (default: 0.12)")
    parser.add_argument("--audio-only", action="store_true", help="Process audio stream only (no video)")
    parser.add_argument("--dry-run", action="store_true", help="Print JSON report of detected segments without rendering")
    parser.add_argument("--self-test", action="store_true", help="Run built-in unit and ffmpeg E2E self-tests")

    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if not args.input:
        parser.print_help()
        return 1

    if not shutil.which("ffmpeg"):
        print("Error: ffmpeg is not installed or not in PATH.", file=sys.stderr)
        return 1

    if not os.path.isfile(args.input):
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        return 1

    silences, total_duration = detect_silence_ffmpeg(args.input, args.threshold, args.min_silence)
    speech = compute_speech_segments(silences, total_duration, pad=args.pad)
    kept_duration = sum(s.duration for s in speech)
    saved_duration = max(0.0, total_duration - kept_duration)

    if args.dry_run:
        report = {
            "input": args.input,
            "total_duration": round(total_duration, 3),
            "kept_duration": round(kept_duration, 3),
            "saved_seconds": round(saved_duration, 3),
            "silences_removed": [s.to_dict() for s in silences],
            "speech_segments": [s.to_dict() for s in speech],
        }
        print(json.dumps(report, indent=2))
        return 0

    if not speech:
        print("No speech segments detected (entire file is silent).", file=sys.stderr)
        return 1

    out_path = args.output
    if not out_path:
        base, ext = os.path.splitext(args.input)
        out_path = f"{base}_trimmed{ext or '.mp4'}"

    trim_media(args.input, out_path, speech, has_video=not args.audio_only)
    print(f"Done: {out_path} | Saved {saved_duration:.2f}s ({total_duration:.2f}s -> {kept_duration:.2f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
