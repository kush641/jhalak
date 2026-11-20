"""Job orchestration: Drive -> per-episode intelligence -> 3 promo scripts -> 3 rendered promos."""
from __future__ import annotations

import hashlib
import json
import shutil
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import drive, intel, render, script
from .config import settings

JOBS = settings.DATA_DIR / "jobs"
CACHE = settings.DATA_DIR / "cache"
JOBS.mkdir(parents=True, exist_ok=True)
CACHE.mkdir(parents=True, exist_ok=True)

_lock = threading.Lock()
_executor = ThreadPoolExecutor(max_workers=1)  # one job at a time on a laptop

DEFAULT_PROMOS = [
    {"preset": "hook_tease", "prompt": ""},
    {"preset": "drama_conflict", "prompt": ""},
    {"preset": "story_narrator", "prompt": ""},
]


# ------------------------------------------------------------------ job store
def _path(job_id: str) -> Path:
    return JOBS / job_id / "job.json"


def load(job_id: str) -> dict:
    p = _path(job_id)
    if not p.exists():
        raise KeyError(job_id)
    return json.loads(p.read_text())


def save(job: dict) -> None:
    p = _path(job["id"])
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(job, ensure_ascii=False, indent=1))
    tmp.replace(p)


def update(job_id: str, **fields) -> dict:
    with _lock:
        job = load(job_id)
        job.update(fields)
        job["updated_at"] = time.time()
        save(job)
        return job


def log(job_id: str, msg: str) -> None:
    print(f"[{job_id}] {msg}", flush=True)
    with _lock:
        job = load(job_id)
        job.setdefault("log", []).append({"t": time.time(), "msg": msg})
        job["log"] = job["log"][-300:]
        job["updated_at"] = time.time()
        save(job)


def list_jobs() -> list[dict]:
    out = []
    for p in sorted(JOBS.glob("*/job.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:50]:
        j = json.loads(p.read_text())
        out.append({k: j.get(k) for k in ("id", "status", "stage", "progress", "created_at", "params")})
    return out


# ------------------------------------------------------------------ public API
def create_job(params: dict) -> dict:
    promos = params.get("promos") or DEFAULT_PROMOS
    promos = (promos + DEFAULT_PROMOS)[:3]
    job = {
        "id": uuid.uuid4().hex[:10], "status": "queued", "stage": "Queued", "progress": 0,
        "created_at": time.time(), "updated_at": time.time(), "params": {**params, "promos": promos},
        "episodes": [], "series": {},
        "promos": [{"index": i, "preset": p.get("preset", "hook_tease"),
                    "name": script.PRESETS.get(p.get("preset", ""), {}).get("name", p.get("preset")),
                    "prompt": p.get("prompt", ""), "status": "pending"} for i, p in enumerate(promos)],
        "log": [],
    }
    save(job)
    _executor.submit(_run_safe, job["id"])
    return job


def regenerate(job_id: str, index: int, prompt: str | None = None, preset: str | None = None) -> dict:
    job = load(job_id)
    if job["status"] not in {"done", "error"} or not job.get("episodes"):
        raise RuntimeError("Job must finish analysing episodes before a promo can be regenerated")
    p = job["promos"][index]
    if prompt is not None:
        p["prompt"] = prompt
    if preset:
        p["preset"] = preset
        p["name"] = script.PRESETS.get(preset, {}).get("name", preset)
    p["status"] = "queued"
    update(job_id, promos=job["promos"], status="running", stage=f"Regenerating promo {index + 1}")
    _executor.submit(_regen_safe, job_id, index)
    return load(job_id)


# ------------------------------------------------------------------ workers
def _parse_range(spec: str | None, n: int) -> list[int]:
    if not spec:
        return list(range(1, min(n, 10) + 1))
    picked = set()
    for part in str(spec).replace(" ", "").split(","):
        if "-" in part:
            a, b = part.split("-", 1)
            picked.update(range(int(a), int(b) + 1))
        elif part:
            picked.add(int(part))
    return [i for i in sorted(picked) if 1 <= i <= n]


def _sources(params: dict) -> list[dict]:
    """Return [{name, key, path?|drive_file}] in episode order."""
    if params.get("local_dir"):
        files = sorted((p for p in Path(params["local_dir"]).iterdir() if p.suffix.lower() in drive.VIDEO_EXT),
                       key=lambda p: drive.natural_key(p.name))
        return [{"name": p.name, "key": hashlib.md5(str(p.resolve()).encode()).hexdigest()[:12], "path": p} for p in files]
    files = drive.list_episodes(params["drive_url"])
    return [{"name": f["name"], "key": f["id"], "drive_file": f} for f in files]


def _run_safe(job_id: str) -> None:
    try:
        _run(job_id)
    except Exception as e:
        traceback.print_exc()
        log(job_id, f"ERROR: {e}")
        update(job_id, status="error", stage="Failed", error=str(e))


def _run(job_id: str) -> None:
    job = update(job_id, status="running", stage="Reading episode list", progress=2)
    params = job["params"]
    sources = _sources(params)
    if not sources:
        raise RuntimeError("No video files found at that link")
    picks = _parse_range(params.get("episode_range"), len(sources))
    log(job_id, f"Found {len(sources)} episodes; using {len(picks)}: {picks[0]}-{picks[-1]}")
    episodes = []
    for k, n in enumerate(picks):
        src = sources[n - 1]
        ep_dir = CACHE / src["key"]
        pct = 5 + int(70 * k / len(picks))
        update(job_id, stage=f"Episode {n}: downloading and analysing", progress=pct)
        if "path" in src:
            ep_dir.mkdir(parents=True, exist_ok=True)
            local = ep_dir / f"source{src['path'].suffix}"
            if not local.exists():
                shutil.copy(src["path"], local)
        else:
            log(job_id, f"Episode {n}: downloading {src['name']}")
            local = drive.download(src["drive_file"], ep_dir)
        ep = intel.process_episode(n, src["name"], local, ep_dir, params.get("language", "unknown"),
                                   log=lambda m: log(job_id, m))
        episodes.append(ep)
        update(job_id, episodes=[_ep_summary(e) for e in episodes])

    _save_intel(job_id, episodes)
    for i in range(3):
        _make_promo(job_id, i, episodes, base_progress=75 + i * 8)
    job = load(job_id)
    ok = any(p["status"] == "done" for p in job["promos"])
    update(job_id, status="done" if ok else "error", stage="Promos ready" if ok else "All promos failed", progress=100)


def _regen_safe(job_id: str, index: int) -> None:
    try:
        episodes = json.loads((JOBS / job_id / "intel.json").read_text())
        _make_promo(job_id, index, episodes, base_progress=90)
        update(job_id, status="done", stage="Promos ready", progress=100)
    except Exception as e:
        traceback.print_exc()
        log(job_id, f"ERROR regenerating promo {index + 1}: {e}")
        update(job_id, status="done", stage="Regeneration failed")


def _make_promo(job_id: str, i: int, episodes: list[dict], base_progress: int) -> None:
    job = load(job_id)
    params, p = job["params"], job["promos"][i]
    opts = {**params, "promo_prompt": p.get("prompt", "")}
    out_dir = JOBS / job_id / f"promo_{i + 1}"
    try:
        _set_promo(job_id, i, status="writing")
        update(job_id, stage=f"Writing promo script {i + 1} of 3 ({p['name']})", progress=base_progress)
        log(job_id, f"Promo {i + 1}: writing script ({p['name']})")
        sc = script.write_script(episodes, p["preset"], opts)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "script.json").write_text(json.dumps(sc, ensure_ascii=False, indent=1))
        _set_promo(job_id, i, status="rendering", script=sc)
        update(job_id, stage=f"Stitching promo {i + 1} of 3", progress=base_progress + 4)
        log(job_id, f"Promo {i + 1}: narrating and stitching {len(sc['segments'])} segments")
        res = render.render_promo(sc, episodes, out_dir, opts, log=lambda m: log(job_id, m))
        _set_promo(job_id, i, status="done", video=f"promo_{i + 1}/{res['video']}",
                   thumbnail=f"promo_{i + 1}/{res['thumbnail']}", duration=res["duration"],
                   timeline=res["timeline"], version=int(time.time()), error=None)
        log(job_id, f"Promo {i + 1}: ready ({res['duration']:.1f}s)")
    except Exception as e:
        traceback.print_exc()
        _set_promo(job_id, i, status="error", error=str(e)[:500])
        log(job_id, f"Promo {i + 1} failed: {e}")


def _set_promo(job_id: str, i: int, **fields) -> None:
    with _lock:
        job = load(job_id)
        job["promos"][i].update(fields)
        job["updated_at"] = time.time()
        save(job)


def _ep_summary(e: dict) -> dict:
    return {"episode": e["episode"], "name": e["name"], "duration": round(e["duration"], 1),
            "chunks": len(e["chunks"]), "separation": e["separation"],
            "video_synopsis": e.get("video_synopsis", ""), "audio_synopsis": e.get("audio_synopsis", "")}


def _save_intel(job_id: str, episodes: list[dict]) -> None:
    (JOBS / job_id / "intel.json").write_text(json.dumps(episodes, ensure_ascii=False))
