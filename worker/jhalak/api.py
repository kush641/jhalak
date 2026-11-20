"""Worker HTTP API. The Vercel app calls it server-side with X-Worker-Secret; browsers fetch
videos straight from /files using short-lived signed URLs minted by the Vercel app."""
from __future__ import annotations

import hashlib
import hmac
import time
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import pipeline, script
from .config import settings

app = FastAPI(title="Jhalak worker", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def auth(x_worker_secret: str = Header(default="")):
    if not hmac.compare_digest(x_worker_secret, settings.WORKER_SECRET):
        raise HTTPException(401, "bad worker secret")


class PromoSpec(BaseModel):
    preset: str = "hook_tease"
    prompt: str = ""


class JobIn(BaseModel):
    drive_url: str | None = None
    local_dir: str | None = None
    series_name: str = ""
    episode_range: str = "1-10"
    language: str = "unknown"            # Saaras language_code for the episodes
    narration_language: str = "hi-IN"    # Bulbul language for the narrator
    narrator_voice: str = settings.DEFAULT_NARRATOR
    target_seconds: int = Field(45, ge=15, le=120)
    global_prompt: str = ""
    promos: list[PromoSpec] = Field(default_factory=lambda: [PromoSpec(**p) for p in pipeline.DEFAULT_PROMOS])


class RegenIn(BaseModel):
    prompt: str | None = None
    preset: str | None = None


@app.get("/health")
def health():
    return {"ok": True, "mock": settings.MOCK_APIS, "separation": settings.SEPARATION,
            "vision_model": settings.VISION_MODEL, "script_model": settings.SCRIPT_MODEL}


@app.get("/presets", dependencies=[Depends(auth)])
def presets():
    return [{"key": k, **v} for k, v in script.PRESETS.items()]


@app.post("/jobs", dependencies=[Depends(auth)])
def create(job: JobIn):
    if not job.drive_url and not job.local_dir:
        raise HTTPException(400, "drive_url is required")
    return pipeline.create_job(job.model_dump())


@app.get("/jobs", dependencies=[Depends(auth)])
def jobs():
    return pipeline.list_jobs()


@app.get("/jobs/{job_id}", dependencies=[Depends(auth)])
def get_job(job_id: str):
    try:
        return pipeline.load(job_id)
    except KeyError:
        raise HTTPException(404, "job not found")


@app.post("/jobs/{job_id}/promos/{index}/regenerate", dependencies=[Depends(auth)])
def regen(job_id: str, index: int, body: RegenIn):
    if index not in (0, 1, 2):
        raise HTTPException(400, "index must be 0, 1 or 2")
    try:
        return pipeline.regenerate(job_id, index, body.prompt, body.preset)
    except KeyError:
        raise HTTPException(404, "job not found")
    except RuntimeError as e:
        raise HTTPException(409, str(e))


def sign(path: str, exp: int) -> str:
    return hmac.new(settings.WORKER_SECRET.encode(), f"{path}:{exp}".encode(), hashlib.sha256).hexdigest()


@app.get("/files/{job_id}/{rel:path}")
def files(job_id: str, rel: str, exp: int = Query(...), sig: str = Query(...), download: int = 0):
    path = f"{job_id}/{rel}"
    if exp < time.time() or not hmac.compare_digest(sig, sign(path, exp)):
        raise HTTPException(403, "link expired or invalid")
    full = (pipeline.JOBS / job_id / rel).resolve()
    if pipeline.JOBS.resolve() not in full.parents or not full.is_file():
        raise HTTPException(404, "not found")
    headers = {"Content-Disposition": f'attachment; filename="jhalak_{job_id}_{Path(rel).parent.name}{full.suffix}"'} if download else None
    return FileResponse(full, headers=headers)
