"""Assemble a promo from its script: cut chunks, mix stems + Bulbul narration, stitch, add music bed."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageFont

from . import clients, media
from .config import settings

FPS = 30
FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",  # macOS
    "/Library/Fonts/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
]


def _font(size: int):
    for p in [settings.FONT_PATH, *FONT_CANDIDATES]:
        if p and Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def text_png(text: str, out: Path, w: int, h: int) -> Path:
    """Transparent full-frame PNG with a caption band near the bottom (Latin script)."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    font = _font(int(w * 0.065))
    words, lines, cur = text.split(), [], ""
    for wd in words:
        trial = f"{cur} {wd}".strip()
        if d.textlength(trial, font=font) > w * 0.84 and cur:
            lines.append(cur)
            cur = wd
        else:
            cur = trial
    if cur:
        lines.append(cur)
    lh = int(font.size * 1.25)
    y = int(h * 0.74) - lh * len(lines) // 2
    pad = int(w * 0.04)
    d.rounded_rectangle([pad, y - pad // 2, w - pad, y + lh * len(lines) + pad // 2], radius=pad // 2, fill=(0, 0, 0, 150))
    for i, ln in enumerate(lines):
        tw = d.textlength(ln, font=font)
        d.text(((w - tw) / 2, y + i * lh), ln, font=font, fill=(255, 255, 255, 255))
    img.save(out)
    return out


def _wav_len(p: Path) -> float:
    return media.probe(p)["duration"]


def render_promo(script: dict, episodes: list[dict], out_dir: Path, opts: dict,
                 log: Callable[[str], None] = print) -> dict:
    W, H = settings.OUTPUT_WIDTH, settings.OUTPUT_HEIGHT
    out_dir.mkdir(parents=True, exist_ok=True)
    work = out_dir / "_work"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir()
    eps = {e["episode"]: e for e in episodes}
    chunks = {c["id"]: c for e in episodes for c in e["chunks"]}
    voice = opts.get("narrator_voice") or settings.DEFAULT_NARRATOR
    lang = opts.get("narration_language", "hi-IN")
    fill = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps={FPS},format=yuv420p"

    seg_files, timeline, t = [], [], 0.0
    for s in script["segments"]:
        c = chunks[s["chunk_id"]]
        ep = eps[c["episode"]]
        src = Path(ep["source"])
        i = s["order"]
        a0 = c["start"] + s["in"]
        dur = s["out"] - s["in"]

        narr_path, narr_len = None, 0.0
        if s.get("narration"):
            narr_path = clients.synthesize(s["narration"], work / f"n{i:02d}.wav", voice, lang)
            narr_len = _wav_len(narr_path)
        if s["type"] == "card":
            dur = max(2.0, narr_len + 0.5)
        elif narr_len + 0.4 > dur:  # extend the shot so the narration fits
            dur = min(narr_len + 0.4, ep["duration"] - a0)

        # --- video
        seg_v = work / f"v{i:02d}.mp4"
        overlay = None
        if s.get("overlay_text"):
            overlay = text_png(s["overlay_text"], work / f"t{i:02d}.png", W, H)
        if s["type"] == "card":
            still = work / f"still{i:02d}.jpg"
            media.run(["ffmpeg", "-y", "-ss", f"{a0:.3f}", "-i", str(src), "-frames:v", "1", str(still)])
            vf = f"{fill},boxblur=24:2,eq=brightness=-0.28"
            cmd = ["ffmpeg", "-y", "-loop", "1", "-t", f"{dur:.3f}", "-i", str(still)]
        else:
            vf = fill
            cmd = ["ffmpeg", "-y", "-ss", f"{a0:.3f}", "-t", f"{dur:.3f}", "-i", str(src)]
        if overlay:
            cmd += ["-i", str(overlay), "-filter_complex", f"[0:v]{vf}[b];[b][1:v]overlay=0:0,format=yuv420p[v]", "-map", "[v]"]
        else:
            cmd += ["-vf", vf]
        cmd += ["-an", "-t", f"{dur:.3f}", "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(seg_v)]
        media.run(cmd)

        # --- audio: scene stem (by mix mode) + narration
        seg_a = work / f"a{i:02d}.wav"
        stems = ep["stems"]
        mode = s["audio"]
        scene_src, scene_vol = None, 1.0
        if mode == "dialogue+bgm":
            scene_src = Path(stems["mix"])
        elif mode == "dialogue":
            scene_src = Path(stems["dialogue"])
        elif mode == "bgm":
            if stems.get("bgm"):
                scene_src = Path(stems["bgm"])
            else:  # no separation available: keep the mix but quieter
                scene_src, scene_vol = Path(stems["mix"]), 0.35
        if not scene_src or not scene_src.exists() or s["type"] == "card" and mode != "bgm":
            scene = media.silent_wav(work / f"s{i:02d}.wav", dur)
        else:
            scene = media.cut_audio(scene_src, a0, a0 + dur, work / f"s{i:02d}.wav", sr=44100, mono=False)
        if narr_path:
            scene_vol *= 0.28  # duck scene audio under narration
            fc = (f"[0:a]volume={scene_vol},aformat=sample_rates=44100:channel_layouts=stereo[s];"
                  f"[1:a]adelay=150|150,volume=1.6,aformat=sample_rates=44100:channel_layouts=stereo[n];"
                  f"[s][n]amix=inputs=2:duration=first:normalize=0,apad,atrim=0:{dur:.3f}[a]")
            media.run(["ffmpeg", "-y", "-i", str(scene), "-i", str(narr_path), "-filter_complex", fc,
                       "-map", "[a]", "-ar", "44100", "-ac", "2", str(seg_a)])
        else:
            media.run(["ffmpeg", "-y", "-i", str(scene), "-af",
                       f"volume={scene_vol},apad,atrim=0:{dur:.3f}", "-ar", "44100", "-ac", "2", str(seg_a)])

        seg = work / f"seg{i:02d}.mp4"
        media.run(["ffmpeg", "-y", "-i", str(seg_v), "-i", str(seg_a), "-map", "0:v", "-map", "1:a",
                   "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-shortest", str(seg)])
        seg_files.append(seg)
        timeline.append({**s, "promo_start": round(t, 2), "promo_end": round(t + dur, 2),
                         "source_episode": c["episode"], "source_start": round(a0, 2), "source_end": round(a0 + dur, 2)})
        t += dur
        log(f"  segment {i}/{len(script['segments'])} cut ({s['role']}, {dur:.1f}s)")

    # --- stitch
    lst = work / "list.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in seg_files))
    stitched = work / "stitched.mp4"
    media.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(stitched)])
    total = media.probe(stitched)["duration"]

    # --- music bed under the whole promo (ducks under dialogue/narration), fade out, loudness
    final = out_dir / "promo.mp4"
    bed_id = (script.get("music") or {}).get("bed_chunk_id")
    bed_vol = (script.get("music") or {}).get("bed_volume", 0.25)
    bed_ep = eps.get(chunks[bed_id]["episode"]) if bed_id in chunks else None
    fade = f"afade=t=out:st={max(0, total - 1.2):.2f}:d=1.2"
    if bed_ep and bed_ep["stems"].get("bgm"):
        bed_start = chunks[bed_id]["start"]
        fc = (f"[1:a]atrim=start={bed_start:.2f},asetpts=PTS-STARTPTS,aloop=loop=-1:size=2e9,atrim=0:{total:.2f},"
              f"volume={bed_vol},aformat=sample_rates=44100:channel_layouts=stereo[bed];"
              f"[0:a]asplit=2[main][key];[bed][key]sidechaincompress=threshold=0.05:ratio=8:attack=20:release=300[duck];"
              f"[main][duck]amix=inputs=2:duration=first:normalize=0,{fade},loudnorm=I=-14:TP=-1.5:LRA=11[a]")
        media.run(["ffmpeg", "-y", "-i", str(stitched), "-i", bed_ep["stems"]["bgm"], "-filter_complex", fc,
                   "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(final)])
    else:
        media.run(["ffmpeg", "-y", "-i", str(stitched), "-af", f"{fade},loudnorm=I=-14:TP=-1.5:LRA=11",
                   "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(final)])

    thumb = out_dir / "thumb.jpg"
    media.run(["ffmpeg", "-y", "-ss", f"{min(1.5, total / 2):.2f}", "-i", str(final), "-frames:v", "1",
               "-vf", "scale=540:-2", str(thumb)])
    shutil.rmtree(work, ignore_errors=True)
    result = {"video": final.name, "thumbnail": thumb.name, "duration": round(total, 2), "timeline": timeline}
    (out_dir / "timeline.json").write_text(json.dumps(result, ensure_ascii=False, indent=1))
    return result
