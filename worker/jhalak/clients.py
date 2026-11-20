"""Thin clients for Sarvam APIs: Saaras (STT), Bulbul (TTS), Sarvam-105B and Token Factory (Gemma 4).

Every call has retries for 429/5xx. With MOCK_APIS=1 the clients return synthetic
responses so the whole pipeline can be exercised offline.
"""
from __future__ import annotations

import base64
import io
import json
import math
import random
import re
import struct
import time
import wave
from pathlib import Path
from typing import Any

import requests

from .config import settings


class APIError(RuntimeError):
    pass


def _post(url: str, *, headers: dict, retries: int = 4, timeout: int = 180, **kw) -> requests.Response:
    delay = 2.0
    last = None
    for attempt in range(retries + 1):
        try:
            r = requests.post(url, headers=headers, timeout=timeout, **kw)
        except requests.RequestException as e:  # network blip
            last = str(e)
        else:
            if r.status_code < 400:
                return r
            last = f"{r.status_code}: {r.text[:500]}"
            if r.status_code not in (408, 409, 429, 500, 502, 503, 504):
                break
        if attempt < retries:
            time.sleep(delay + random.random())
            delay *= 2
    raise APIError(f"POST {url} failed: {last}")


def extract_json(text: str) -> Any:
    """Parse JSON from a model reply that may include fences, prose or <think> blocks."""
    if text is None:
        raise ValueError("empty model reply")
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=-1)
    if start < 0:
        raise ValueError(f"no JSON found in reply: {text[:200]}")
    opener = text[start]
    closer = "}" if opener == "{" else "]"
    end = text.rfind(closer)
    return json.loads(text[start : end + 1])


# --------------------------------------------------------------------------- Saaras
def transcribe(audio_path: Path, language_code: str = "unknown") -> dict:
    """Transcribe a short (<30 s) audio chunk. Returns {transcript, language_code, phrases:[{text,start,end}]}"""
    if settings.MOCK_APIS:
        return _mock_transcribe(audio_path)
    with open(audio_path, "rb") as f:
        r = _post(
            f"{settings.SARVAM_BASE_URL}/speech-to-text",
            headers={"api-subscription-key": settings.SARVAM_API_KEY},
            files={"file": (audio_path.name, f, "audio/wav")},
            data={
                "model": settings.STT_MODEL,
                "mode": settings.STT_MODE,
                "language_code": language_code or "unknown",
                "with_timestamps": "true",
            },
        )
    body = r.json()
    phrases = []
    ts = body.get("timestamps") or {}
    words = ts.get("words") or []
    starts = ts.get("start_time_seconds") or []
    ends = ts.get("end_time_seconds") or []
    for i, w in enumerate(words):
        try:
            phrases.append({"text": w, "start": float(starts[i]), "end": float(ends[i])})
        except (IndexError, TypeError, ValueError):
            continue
    return {
        "transcript": body.get("transcript", ""),
        "language_code": body.get("language_code"),
        "phrases": phrases,
    }


# --------------------------------------------------------------------------- Bulbul
def synthesize(text: str, out_path: Path, speaker: str, language_code: str = "hi-IN", pace: float = 1.0) -> Path:
    """Text to speech with Bulbul. Writes a WAV file."""
    if settings.MOCK_APIS:
        return _mock_tts(text, out_path)
    payload = {
        "text": text[:2400],
        "language_code": language_code,
        "speaker": speaker,
        "model": settings.TTS_MODEL,
        "pace": pace,
        "speech_sample_rate": 44100,
        "output_audio_codec": "wav",
    }
    r = _post(
        f"{settings.SARVAM_BASE_URL}/text-to-speech",
        headers={"api-subscription-key": settings.SARVAM_API_KEY, "Content-Type": "application/json"},
        json=payload,
    )
    audios = r.json().get("audios") or []
    if not audios:
        raise APIError("Bulbul returned no audio")
    out_path.write_bytes(base64.b64decode(audios[0]))
    return out_path


# --------------------------------------------------------------------------- Chat (OpenAI-compatible)
def _chat(base_url: str, api_key: str, model: str, messages: list, max_tokens: int, temperature: float,
          extra: dict | None = None) -> str:
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    if extra:
        payload.update(extra)
    r = _post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "api-subscription-key": api_key,
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=300,
    )
    body = r.json()
    try:
        choice = body["choices"][0]
        msg = choice["message"]
    except (KeyError, IndexError, TypeError) as e:
        raise APIError(f"unexpected chat response: {str(body)[:300]}") from e
    text = msg.get("content") or ""
    if not text.strip():
        # Reasoning models can spend the whole budget thinking and leave `content` empty.
        text = msg.get("reasoning_content") or msg.get("reasoning") or ""
    global LAST_FINISH_REASON
    LAST_FINISH_REASON = choice.get("finish_reason")
    return text


LAST_FINISH_REASON = None


def vision_json(system: str, prompt: str, image_paths: list[Path], max_tokens: int = 1500, mock_ctx: dict | None = None) -> dict:
    """Ask the vision model (Gemma 4 on Token Factory) about a sequence of frames; returns parsed JSON."""
    if settings.MOCK_APIS:
        return _mock_vision(mock_ctx or {})
    content: list[dict] = [{"type": "text", "text": prompt}]
    for p in image_paths:
        b64 = base64.b64encode(Path(p).read_bytes()).decode()
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
    messages = [{"role": "system", "content": system}, {"role": "user", "content": content}]
    last_err = None
    for _ in range(3):
        text = _chat(settings.TOKEN_FACTORY_BASE_URL, settings.TOKEN_FACTORY_API_KEY, settings.VISION_MODEL,
                     messages, max_tokens, 0.2)
        try:
            return extract_json(text)
        except (ValueError, json.JSONDecodeError) as e:
            last_err = e
            messages = messages + [{"role": "assistant", "content": text},
                                   {"role": "user", "content": "Reply again with ONLY valid JSON matching the schema."}]
    raise APIError(f"vision model did not return JSON: {last_err}")


def text_json(system: str, prompt: str, max_tokens: int = 6000, temperature: float = 0.6,
              model: str | None = None, mock_ctx: dict | None = None) -> Any:
    """Ask the script model (Sarvam-105B) for JSON."""
    if settings.MOCK_APIS:
        return _mock_text(mock_ctx or {})
    model = model or settings.SCRIPT_MODEL
    messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    extra = {"reasoning_effort": "low"} if model.startswith("sarvam-105b") else None
    last_err = None
    budget = max_tokens
    for attempt in range(4):
        text = _chat(settings.SCRIPT_BASE_URL, settings.SARVAM_API_KEY, model, messages, budget, temperature, extra)
        print(f"[script-model] attempt={attempt} finish={LAST_FINISH_REASON} chars={len(text)} head={text[:160]!r}", flush=True)
        try:
            return extract_json(text)
        except (ValueError, json.JSONDecodeError) as e:
            last_err = f"{e} (finish_reason={LAST_FINISH_REASON}, reply_chars={len(text)}, head={text[:200]!r})"
            if not text.strip() or LAST_FINISH_REASON == "length":
                budget = min(budget * 2, 16000)   # ran out of tokens: give it more room
                continue
            messages = messages + [{"role": "assistant", "content": text[:4000]},
                                   {"role": "user", "content": "That was not valid JSON. Reply with ONLY the JSON object, no prose, no code fences."}]
    raise APIError(f"script model did not return JSON: {last_err}")


# --------------------------------------------------------------------------- mocks
_MOCK_LINES = [
    "तुमने मुझसे झूठ क्यों बोला?", "ये शादी नहीं हो सकती।", "मैं तुम्हारे बिना नहीं रह सकती।",
    "कल सुबह सब कुछ बदल जाएगा।", "वो लड़की कौन थी?", "मुझे सच जानना है।",
    "तुम्हारे पापा ने ये सब पहले से प्लान किया था।", "अब बहुत देर हो चुकी है।",
]


def _wav_duration(path: Path) -> float:
    with wave.open(str(path)) as w:
        return w.getnframes() / float(w.getframerate())


def _mock_transcribe(audio_path: Path) -> dict:
    try:
        dur = _wav_duration(audio_path)
    except Exception:
        dur = 10.0
    rnd = random.Random(audio_path.name)
    n = max(1, int(dur // 4))
    phrases, t = [], 0.3
    for _ in range(n):
        line = rnd.choice(_MOCK_LINES)
        end = min(dur, t + 2.5)
        phrases.append({"text": line, "start": round(t, 2), "end": round(end, 2)})
        t = end + 1.0
        if t >= dur:
            break
    return {"transcript": " ".join(p["text"] for p in phrases), "language_code": "hi-IN", "phrases": phrases}


def _mock_tts(text: str, out_path: Path) -> Path:
    dur = max(1.2, min(9.0, len(text) / 14.0))
    sr = 44100
    frames = bytearray()
    for i in range(int(sr * dur)):
        v = int(2500 * math.sin(2 * math.pi * 220 * i / sr) * (0.5 + 0.5 * math.sin(2 * math.pi * 3 * i / sr)))
        frames += struct.pack("<h", v)
    with wave.open(str(out_path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(bytes(frames))
    return out_path


def _mock_vision(ctx: dict) -> dict:
    rnd = random.Random(ctx.get("chunk_id", "x"))
    return {
        "description": "Close-up of the female lead in a red saree confronting a man in a dimly lit hallway.",
        "characters": [{"label": "female lead", "appearance": "young woman, red saree", "prominence": "primary"},
                       {"label": "male lead", "appearance": "man in black suit", "prominence": "secondary"}],
        "female_lead_on_screen": rnd.random() > 0.3,
        "setting": rnd.choice(["mansion hallway", "office", "wedding mandap", "car at night"]),
        "shot_types": ["close-up", "medium"],
        "emotion": rnd.choice(["anger", "romance", "shock", "suspense", "betrayal"]),
        "intensity": rnd.randint(1, 5),
        "visual_appeal": rnd.randint(3, 10),
        "hook_score": rnd.randint(2, 10),
        "cliffhanger_score": rnd.randint(1, 10),
        "spoiler_risk": rnd.choice(["low", "low", "medium", "high"]),
        "on_screen_text": "",
        "best_moment_offset_s": round(rnd.uniform(0, 3), 1),
        "safety_flags": [],
    }


def _mock_text(ctx: dict) -> Any:
    kind = ctx.get("kind")
    if kind == "episode_synopsis":
        return {"synopsis": "Mock synopsis: the female lead discovers a secret about her fiancé's family.",
                "key_moments": [c for c in ctx.get("chunk_ids", [])[:3]]}
    if kind == "series_synopsis":
        return {"title_guess": "Mock Series", "genre": "romantic drama", "logline": "A bride uncovers a family conspiracy.",
                "characters": [{"name": "Female lead", "description": "determined bride"}],
                "synopsis": "Mock series synopsis.", "spoilers_to_avoid": ["The final reveal"]}
    if kind == "promo_script":
        return ctx["mock_builder"]()
    return {}
