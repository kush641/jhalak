"""ffmpeg / Demucs helpers: probing, stem separation, silence-aware chunking, frame sampling."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from .config import settings


class MediaError(RuntimeError):
    pass


def run(cmd: list[str], timeout: int = 3600) -> str:
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        raise MediaError(f"{' '.join(cmd[:6])}... failed:\n{p.stderr[-1500:]}")
    return p.stderr + p.stdout


def probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height,r_frame_rate",
         "-of", "json", str(path)], capture_output=True, text=True,
    )
    info = json.loads(out.stdout or "{}")
    v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
    has_audio = any(s.get("codec_type") == "audio" for s in info.get("streams", []))
    return {
        "duration": float(info.get("format", {}).get("duration", 0) or 0),
        "width": int(v.get("width", 0) or 0),
        "height": int(v.get("height", 0) or 0),
        "has_audio": has_audio,
    }


def extract_audio(src: Path, out_wav: Path) -> Path:
    run(["ffmpeg", "-y", "-i", str(src), "-vn", "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", str(out_wav)])
    return out_wav


def extract_video_only(src: Path, out: Path) -> Path:
    """Video stream without audio (kept for completeness; renders read the source directly)."""
    run(["ffmpeg", "-y", "-i", str(src), "-an", "-c:v", "copy", str(out)])
    return out


def silent_wav(out: Path, seconds: float) -> Path:
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", f"{seconds:.3f}",
         "-c:a", "pcm_s16le", str(out)])
    return out


def separate(audio_wav: Path, out_dir: Path) -> tuple[Path, Path | None, str]:
    """Split into dialogue (vocals) and BGM+SFX (no_vocals). Returns (dialogue, bgm, method)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    dialogue, bgm = out_dir / "dialogue.wav", out_dir / "bgm.wav"
    if dialogue.exists() and bgm.exists():
        return dialogue, bgm, "cached"
    if settings.SEPARATION == "demucs":
        try:
            run([sys.executable, "-m", "demucs", "--two-stems=vocals", "-n", settings.DEMUCS_MODEL,
                 "-o", str(out_dir / "_demucs"), str(audio_wav)], timeout=7200)
            stem_dir = out_dir / "_demucs" / settings.DEMUCS_MODEL / audio_wav.stem
            shutil.move(str(stem_dir / "vocals.wav"), dialogue)
            shutil.move(str(stem_dir / "no_vocals.wav"), bgm)
            shutil.rmtree(out_dir / "_demucs", ignore_errors=True)
            return dialogue, bgm, "demucs"
        except Exception as e:  # demucs missing or failed -> degrade gracefully
            print(f"[separate] demucs unavailable, using original mix as dialogue: {e}".splitlines()[0])
    shutil.copy(audio_wav, dialogue)
    return dialogue, None, "none"


def detect_silences(wav: Path, noise_db: float = -35, min_dur: float = 0.35) -> list[tuple[float, float]]:
    log = run(["ffmpeg", "-i", str(wav), "-af", f"silencedetect=noise={noise_db}dB:d={min_dur}", "-f", "null", "-"])
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", log)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
    return list(zip(starts, ends))


def plan_chunks(duration: float, silences: list[tuple[float, float]],
                max_s: float | None = None, min_s: float | None = None) -> list[tuple[float, float]]:
    """Cut the episode at pauses in speech so each chunk is a complete thought and < max_s long."""
    max_s = max_s or settings.CHUNK_MAX_SECONDS
    min_s = min_s or settings.CHUNK_MIN_SECONDS
    cuts = sorted((a + b) / 2 for a, b in silences)
    chunks, cur = [], 0.0
    while duration - cur > max_s:
        window = [c for c in cuts if cur + min_s <= c <= cur + max_s]
        nxt = window[-1] if window else cur + max_s
        chunks.append((round(cur, 3), round(nxt, 3)))
        cur = nxt
    if duration - cur > 0.05:
        if chunks and duration - cur < min_s:
            chunks[-1] = (chunks[-1][0], round(duration, 3))
        else:
            chunks.append((round(cur, 3), round(duration, 3)))
    return chunks


def cut_audio(src: Path, start: float, end: float, out: Path, sr: int = 16000, mono: bool = True) -> Path:
    cmd = ["ffmpeg", "-y", "-ss", f"{start:.3f}", "-t", f"{end - start:.3f}", "-i", str(src)]
    if mono:
        cmd += ["-ac", "1"]
    cmd += ["-ar", str(sr), "-c:a", "pcm_s16le", str(out)]
    run(cmd)
    return out


def sample_frames(video: Path, start: float, end: float, out_dir: Path, n: int | None = None,
                  width: int | None = None) -> list[Path]:
    """Evenly sample n frames from [start, end] (Gemma 4 reads video as frames, max ~1 fps)."""
    n = n or settings.FRAMES_PER_CHUNK
    width = width or settings.FRAME_WIDTH
    out_dir.mkdir(parents=True, exist_ok=True)
    dur = max(0.1, end - start)
    n = max(2, min(n, int(dur) + 1))  # never more than ~1 fps
    fps = n / dur
    run(["ffmpeg", "-y", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(video),
         "-vf", f"fps={fps:.4f},scale={width}:-2", "-frames:v", str(n), "-q:v", "4",
         str(out_dir / "f_%02d.jpg")])
    return sorted(out_dir.glob("f_*.jpg"))


def rms_db(wav: Path) -> float:
    """Mean loudness of a clip in dB (rough energy signal, since the vision model cannot hear)."""
    try:
        log = run(["ffmpeg", "-i", str(wav), "-af", "volumedetect", "-f", "null", "-"])
        m = re.search(r"mean_volume: (-?[\d.]+) dB", log)
        return float(m.group(1)) if m else -60.0
    except MediaError:
        return -60.0
