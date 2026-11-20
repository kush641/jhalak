"""Promo script writing with Sarvam-105B: fuses the audio and video synopses plus the
chunk catalog into one promo script that references exact chunks, narration lines
(for Bulbul) and audio mixing per segment.
"""
from __future__ import annotations

import json
from typing import Any

from . import clients

PRESETS: dict[str, dict[str, str]] = {
    "hook_tease": {
        "name": "Hook & Tease",
        "brief": (
            "Character-led teaser. Open on the most visually striking close-ups of the female lead "
            "with a dramatic narrator line that sets up the premise in one breath. Build curiosity with "
            "2-4 fast story beats, then cut away on an unresolved cliffhanger line or look."
        ),
    },
    "drama_conflict": {
        "name": "Conflict Montage",
        "brief": (
            "Dialogue-led montage. Stack the sharpest confrontational or emotional lines back to back, "
            "rising in intensity, with the background score driving the pace. Minimal narration: one "
            "line in the hook and an optional closing tease."
        ),
    },
    "story_narrator": {
        "name": "Narrator Story",
        "brief": (
            "Narrator tells the story. 3-5 short narrator lines in the target language carry the premise "
            "(who she is, what she wants, what stands in her way) over the best visuals, with brief dialogue "
            "punctuations, ending on a question the viewer needs answered."
        ),
    },
}

SYSTEM = """You are the head of promos at an Indian microdrama OTT. You write promo scripts that an
editor can assemble mechanically from numbered chunks of the episodes. Rules:

1. THE FIRST 10 SECONDS ARE EVERYTHING. Segments covering 0-10 s must use the chunks with the highest
   visual_appeal and hook_score, featuring the female lead's most striking close-ups, with a narrator line
   that sets context instantly (who she is, what is at stake). No slow establishing shots.
2. Then escalate: each beat raises stakes or emotion.
3. END ON A CLIFFHANGER: the last clip cuts on an unresolved moment (a question, a threat, a reveal about
   to happen). Never show the resolution. Avoid chunks with spoiler_risk "high".
4. Only use chunk ids from the catalog. "in"/"out" are seconds measured from the START OF THAT CHUNK and
   must lie within its duration. Prefer cutting at phrase boundaries listed in the catalog.
5. Narration is spoken by a voice-over artist (text-to-speech) over the visuals. Write it in the requested
   narration language and script (e.g. Hindi in Devanagari), short, punchy, 4-14 words per line.
6. Audio per segment: "dialogue+bgm" (original scene audio), "dialogue" (dialogue only, original music
   removed), "bgm" (music/effects only, no dialogue - use when narration plays), or "mute".
   When a segment has narration, use "bgm" or "dialogue" (it will be ducked) - never let narration clash with a key line.
7. overlay_text: optional, very short, Latin script only (e.g. "Episode 1 streaming now").
8. Respect the target duration (+/- 15%). Typical clip segment: 1.5-6 s.
Reply with ONE JSON object only."""

SCHEMA = """{
  "promo_title": "short internal name",
  "promo_type": "preset key",
  "target_seconds": number,
  "hook_strategy": "one sentence: what happens in the first 10 s and why it stops the scroll",
  "cliffhanger": "one sentence: the unresolved moment we end on",
  "music": {"bed_chunk_id": "chunk id whose background score runs under the whole promo, or null", "bed_volume": 0.0-1.0},
  "segments": [
    {"order": 1, "role": "hook|context|escalation|cliffhanger|cta",
     "type": "clip|card", "chunk_id": "E01C03", "in": 0.0, "out": 3.2,
     "audio": "dialogue+bgm|dialogue|bgm|mute",
     "narration": "voice-over text in narration language, or empty",
     "overlay_text": "", "why": "short reason"}
  ],
  "cta_text": "closing call to action, Latin script",
  "social_caption": "a post caption in the narration language"
}"""


def catalog_line(c: dict) -> dict:
    v, a = c.get("video", {}), c.get("audio", {})
    phrases = [f"{p['start']:.1f}-{p['end']:.1f}" for p in a.get("phrases", [])][:8]
    return {
        "id": c["id"], "ep": c["episode"], "dur": c["duration"],
        "says": (a.get("transcript") or "")[:220],
        "phrase_times": phrases,
        "key_line": (a.get("notes") or {}).get("key_line", ""),
        "sees": (v.get("description") or "")[:200],
        "emotion": v.get("emotion"), "intensity": v.get("intensity"),
        "female_lead": v.get("female_lead_on_screen"), "appeal": v.get("visual_appeal"),
        "hook": v.get("hook_score"), "cliff": v.get("cliffhanger_score"),
        "spoiler": v.get("spoiler_risk"), "best_at": v.get("best_moment_offset_s"),
        "music_db": a.get("bgm_db"), "flags": v.get("safety_flags") or [],
    }


def build_catalog(episodes: list[dict], max_chunks: int = 160) -> list[dict]:
    chunks = [c for ep in episodes for c in ep["chunks"]]
    if len(chunks) > max_chunks:  # keep the most promo-worthy chunks for very long seasons
        def score(c):
            v = c.get("video", {})
            return (v.get("hook_score") or 0) + (v.get("visual_appeal") or 0) + (v.get("cliffhanger_score") or 0)
        keep = {c["id"] for c in sorted(chunks, key=score, reverse=True)[:max_chunks]}
        chunks = [c for c in chunks if c["id"] in keep]
    return [catalog_line(c) for c in chunks]


def write_script(episodes: list[dict], preset_key: str, opts: dict) -> dict:
    preset = PRESETS.get(preset_key, PRESETS["hook_tease"])
    catalog = build_catalog(episodes)
    synopses = "\n".join(
        f"Episode {e['episode']}:\n  VIDEO synopsis: {e.get('video_synopsis','')}\n  AUDIO synopsis: {e.get('audio_synopsis','')}"
        for e in episodes
    )
    direction = "\n".join(x for x in [opts.get("global_prompt", ""), opts.get("promo_prompt", "")] if x)
    prompt = f"""SERIES: {opts.get('series_name') or 'Untitled microdrama'}
NARRATION LANGUAGE: {opts.get('narration_language', 'hi-IN')}
TARGET DURATION: {opts.get('target_seconds', 45)} seconds
PROMO TYPE: {preset_key} - {preset['name']}
TYPE BRIEF: {preset['brief']}
CLIENT DIRECTION (follow this closely, it overrides the type brief where they conflict): {direction or 'none'}

STORY SO FAR (two synopses per episode, one from what is SEEN, one from what is SAID):
{synopses}

CHUNK CATALOG (says = dialogue, sees = visuals, scores 1-10, phrase_times = seconds from chunk start):
{json.dumps(catalog, ensure_ascii=False)}

Write the promo script as JSON with this shape:
{SCHEMA}"""
    raw = clients.text_json(
        SYSTEM, prompt, max_tokens=6000, temperature=0.7,
        mock_ctx={"kind": "promo_script", "mock_builder": lambda: _mock_script(catalog, preset_key, opts)},
    )
    return validate(raw, episodes, preset_key, opts)


def validate(raw: Any, episodes: list[dict], preset_key: str, opts: dict) -> dict:
    """Repair the model's script so it is always renderable."""
    by_id = {c["id"]: c for ep in episodes for c in ep["chunks"]}
    script = raw if isinstance(raw, dict) else {"segments": raw if isinstance(raw, list) else []}
    segs = []
    for s in script.get("segments") or []:
        if not isinstance(s, dict):
            continue
        c = by_id.get(str(s.get("chunk_id", "")).strip())
        if not c:
            continue
        dur = c["duration"]
        try:
            a = float(s.get("in", 0) or 0)
            b = float(s.get("out", dur) or dur)
        except (TypeError, ValueError):
            a, b = 0.0, dur
        a = max(0.0, min(a, dur - 0.5))
        b = max(a + 0.8, min(b, dur))
        seg_type = "card" if s.get("type") == "card" else "clip"
        audio = s.get("audio") if s.get("audio") in {"dialogue+bgm", "dialogue", "bgm", "mute"} else "dialogue+bgm"
        segs.append({
            "order": len(segs) + 1, "role": s.get("role", "escalation"), "type": seg_type,
            "chunk_id": c["id"], "in": round(a, 2), "out": round(b, 2), "audio": audio,
            "narration": (s.get("narration") or "").strip(), "overlay_text": (s.get("overlay_text") or "").strip()[:60],
            "why": s.get("why", ""),
        })
    if not segs:
        raise ValueError("The script model returned no usable segments")
    target = float(opts.get("target_seconds", 45))
    # trim middle escalation beats if far too long (narration may extend clips later)
    while sum(s["out"] - s["in"] for s in segs) > target * 1.25 and len(segs) > 3:
        mids = [i for i, s in enumerate(segs[1:-1], start=1) if s["role"] not in {"hook", "cliffhanger"}] or list(range(1, len(segs) - 1))
        segs.pop(max(mids, key=lambda i: segs[i]["out"] - segs[i]["in"]))
    for i, s in enumerate(segs, start=1):
        s["order"] = i
    music = script.get("music") or {}
    bed = music.get("bed_chunk_id")
    script.update({
        "promo_type": preset_key,
        "promo_name": PRESETS.get(preset_key, {}).get("name", preset_key),
        "target_seconds": target,
        "segments": segs,
        "music": {"bed_chunk_id": bed if bed in by_id else None,
                  "bed_volume": max(0.0, min(1.0, float(music.get("bed_volume", 0.25) or 0.25)))},
    })
    return script


def _mock_script(catalog: list[dict], preset_key: str, opts: dict) -> dict:
    def s(c, k):
        return c.get(k) or 0
    hook = sorted(catalog, key=lambda c: s(c, "appeal") + s(c, "hook") + (3 if c.get("female_lead") else 0), reverse=True)
    cliff = max(catalog, key=lambda c: s(c, "cliff"))
    mids = [c for c in hook[2:] if c["id"] != cliff["id"]][:4]
    segs = []
    for i, c in enumerate(hook[:2]):
        segs.append({"role": "hook", "type": "clip", "chunk_id": c["id"], "in": 0, "out": min(c["dur"], 4.5),
                     "audio": "bgm", "narration": "एक दुल्हन... और एक ऐसा राज़ जो सब बदल देगा।" if i == 0 else "",
                     "why": "highest appeal + hook"})
    for c in mids:
        segs.append({"role": "escalation", "type": "clip", "chunk_id": c["id"], "in": 0.5, "out": min(c["dur"], 5),
                     "audio": "dialogue+bgm", "narration": "", "why": "rising stakes"})
    segs.append({"role": "cliffhanger", "type": "clip", "chunk_id": cliff["id"], "in": 0, "out": min(cliff["dur"], 4),
                 "audio": "dialogue+bgm", "narration": "", "why": "unresolved"})
    segs.append({"role": "cta", "type": "card", "chunk_id": cliff["id"], "in": 0, "out": 2.0, "audio": "bgm",
                 "narration": "क्या वो सच जान पाएगी? देखिए अभी।", "overlay_text": "Watch Episode 1 now"})
    return {"promo_title": f"Mock {preset_key}", "hook_strategy": "Female lead close-ups + narrator premise",
            "cliffhanger": "Cut on the threat", "music": {"bed_chunk_id": hook[0]["id"], "bed_volume": 0.25},
            "segments": segs, "cta_text": "Watch now", "social_caption": "देखिए अभी!"}
