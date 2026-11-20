"""Per-episode intelligence: separate stems, chunk at speech pauses, then run
audio intelligence (Saaras) and video intelligence (Gemma 4) on the SAME chunks.
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

from . import clients, media
from .config import settings

VISION_SYSTEM = (
    "You are a senior promo editor for Indian vertical microdramas (short episodic shows). "
    "You are shown frames sampled in order from ONE continuous chunk of an episode. "
    "Describe only what is visible. Judge how useful the chunk is for a marketing promo. "
    "Reply with a single JSON object and nothing else."
)

VISION_PROMPT = """Chunk {chunk_id}: episode {episode}, {start:.1f}s to {end:.1f}s ({dur:.1f}s), {n} frames in order, one every {step:.1f}s.

Return JSON with exactly these keys:
{{
  "description": "1-2 sentences: who is on screen, what happens",
  "characters": [{{"label": "e.g. female lead / male lead / mother-in-law", "appearance": "short visual description", "prominence": "primary|secondary"}}],
  "female_lead_on_screen": true/false,
  "setting": "short",
  "shot_types": ["close-up|medium|wide|two-shot|over-shoulder|insert"],
  "emotion": "dominant emotion (romance, anger, shock, suspense, betrayal, joy, fear, longing...)",
  "intensity": 1-5,
  "visual_appeal": 1-10 (how visually striking for a promo: star close-ups, glamour, lighting, framing),
  "hook_score": 1-10 (would these visuals stop a scrolling viewer in the first 3 seconds?),
  "cliffhanger_score": 1-10 (does it feel like an unresolved, tense moment to end a promo on?),
  "spoiler_risk": "low|medium|high" (does it reveal a major twist or resolution?),
  "on_screen_text": "any visible text, else empty",
  "best_moment_offset_s": seconds from chunk start of the single strongest frame,
  "safety_flags": ["smoking", "alcohol", "violence", "blood", "nudity"] or []
}}"""

AUDIO_SYSTEM = (
    "You are a story editor for Indian vertical microdramas. You read time-coded dialogue chunks "
    "from one episode (transcribed from speech) and summarise the story told by the audio. "
    "Reply with a single JSON object and nothing else."
)

VIDEO_SYN_SYSTEM = (
    "You are a story editor. You read per-chunk visual descriptions of one microdrama episode, "
    "in order, and summarise the story told by the visuals. Reply with a single JSON object only."
)


def _chunk_id(ep: int, i: int) -> str:
    return f"E{ep:02d}C{i:02d}"


def process_episode(ep: int, name: str, src: Path, ep_dir: Path, language: str,
                    log: Callable[[str], None] = print) -> dict:
    cache = ep_dir / "intel.json"
    if cache.exists():
        log(f"Episode {ep}: using cached intelligence")
        return json.loads(cache.read_text())
    ep_dir.mkdir(parents=True, exist_ok=True)
    info = media.probe(src)
    if not info["has_audio"]:
        raise media.MediaError(f"{name} has no audio track")

    # 1) separate: full mix -> dialogue + BGM/SFX ; video read from source
    log(f"Episode {ep}: separating dialogue and background music")
    mix = media.extract_audio(src, ep_dir / "mix.wav")
    dialogue, bgm, method = media.separate(mix, ep_dir / "stems")

    # 2) chunk at speech pauses so audio + video chunks share boundaries
    silences = media.detect_silences(dialogue)
    spans = media.plan_chunks(info["duration"], silences)
    log(f"Episode {ep}: {len(spans)} chunks ({method} separation)")

    def analyse(i_span):
        i, (s, e) = i_span
        cid = _chunk_id(ep, i)
        cdir = ep_dir / "chunks" / cid
        cdir.mkdir(parents=True, exist_ok=True)
        # audio intelligence
        a_path = media.cut_audio(dialogue, s, e, cdir / "dialogue_16k.wav")
        stt = clients.transcribe(a_path, language)
        d_db = media.rms_db(a_path)
        b_db = media.rms_db(media.cut_audio(bgm, s, e, cdir / "bgm_16k.wav")) if bgm else -90.0
        # video intelligence
        frames = media.sample_frames(src, s, e, cdir / "frames")
        step = (e - s) / max(1, len(frames))
        vis = clients.vision_json(
            VISION_SYSTEM,
            VISION_PROMPT.format(chunk_id=cid, episode=ep, start=s, end=e, dur=e - s, n=len(frames), step=step),
            frames, mock_ctx={"chunk_id": cid},
        )
        return {
            "id": cid, "episode": ep, "index": i, "start": s, "end": e, "duration": round(e - s, 3),
            "audio": {"transcript": stt.get("transcript", ""), "phrases": stt.get("phrases", []),
                      "language": stt.get("language_code"), "dialogue_db": d_db, "bgm_db": b_db},
            "video": vis,
        }

    with ThreadPoolExecutor(max_workers=settings.MAX_PARALLEL_CALLS) as pool:
        chunks = list(pool.map(analyse, enumerate(spans, start=1)))
    log(f"Episode {ep}: audio + video intelligence done for {len(chunks)} chunks")

    # 3) two synopses per episode: one from audio intelligence, one from video intelligence
    dialogue_lines = "\n".join(f"[{c['id']} {c['start']:.0f}-{c['end']:.0f}s] {c['audio']['transcript'] or '(no dialogue)'}"
                               for c in chunks)
    audio_syn = clients.text_json(
        AUDIO_SYSTEM,
        f"Episode {ep} dialogue chunks:\n{dialogue_lines}\n\nReturn JSON: "
        '{"synopsis": "4-6 sentences in English", "chunk_notes": [{"id": "...", "key_line": "most quotable line verbatim or empty", '
        '"emotion": "...", "hook_line_score": 1-10, "cliffhanger_line_score": 1-10, "spoiler_risk": "low|medium|high"}]}',
        max_tokens=4000, mock_ctx={"kind": "episode_synopsis", "chunk_ids": [c["id"] for c in chunks]},
    )
    visual_lines = "\n".join(f"[{c['id']} {c['start']:.0f}-{c['end']:.0f}s] {c['video'].get('description', '')} "
                             f"(emotion: {c['video'].get('emotion')}, intensity {c['video'].get('intensity')})" for c in chunks)
    video_syn = clients.vision_json(
        VIDEO_SYN_SYSTEM,
        f"Episode {ep} visual chunks:\n{visual_lines}\n\nReturn JSON: "
        '{"synopsis": "4-6 sentences in English", "characters": [{"label": "...", "appearance": "..."}], '
        '"strongest_visual_chunks": ["chunk ids"]}',
        [], max_tokens=1500, mock_ctx={"chunk_id": f"E{ep:02d}syn"},
    )
    notes = {n.get("id"): n for n in (audio_syn.get("chunk_notes") or []) if isinstance(n, dict)}
    for c in chunks:
        c["audio"]["notes"] = notes.get(c["id"], {})

    result = {
        "episode": ep, "name": name, "source": str(src), "duration": info["duration"],
        "width": info["width"], "height": info["height"], "separation": method,
        "stems": {"mix": str(mix), "dialogue": str(dialogue), "bgm": str(bgm) if bgm else None},
        "audio_synopsis": audio_syn.get("synopsis", ""),
        "video_synopsis": video_syn.get("synopsis", "") if isinstance(video_syn, dict) else "",
        "chunks": chunks,
    }
    cache.write_text(json.dumps(result, ensure_ascii=False, indent=1))
    return result
