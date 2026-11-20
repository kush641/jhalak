"""Worker HTTP API. The Vercel app calls it server-side with X-Worker-Secret; browsers fetch
videos straight from /files using short-lived signed URLs minted by the Vercel app."""
from __future__ import annotations

import re
import hashlib
import hmac
import time
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import drive, pipeline, script
from .config import settings

app = FastAPI(title="Jhalak worker", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def auth(x_worker_secret: str = Header(default="")):
    if not hmac.compare_digest(x_worker_secret, settings.WORKER_SECRET):
        raise HTTPException(401, "bad worker secret")

UPLOADS = settings.DATA_DIR / "uploads"
MAX_UPLOAD_BYTES = 8 * 1024**3
_ID = re.compile(r"^[a-f0-9]{8,32}$")


def upload_auth(x_upload_token: str = Header(default="")):
    """Token minted by the Vercel app: '<expiry>.<hmac(secret, 'upload:<expiry>')>'."""
    try:
        exp, sig = x_upload_token.split(".", 1)
        ok = int(exp) > time.time() and hmac.compare_digest(
            sig, hmac.new(settings.WORKER_SECRET.encode(), f"upload:{exp}".encode(), hashlib.sha256).hexdigest())
    except Exception:
        ok = False
    if not ok:
        raise HTTPException(401, "bad or expired upload token")

class PromoSpec(BaseModel):
    preset: str = "hook_tease"
    prompt: str = ""


class JobIn(BaseModel):
    drive_url: str | None = None
    upload_id: str | None = None
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
    params = job.model_dump()
    if job.upload_id:
        if not _ID.match(job.upload_id) or not (UPLOADS / job.upload_id).is_dir():
            raise HTTPException(400, "unknown upload_id")
        params["local_dir"] = str(UPLOADS / job.upload_id)
    if not params.get("drive_url") and not params.get("local_dir"):
        raise HTTPException(400, "Add a Drive link or upload videos")
    return pipeline.create_job(params)


@app.put("/uploads/{upload_id}", dependencies=[Depends(upload_auth)])
async def upload_chunk(upload_id: str, request: Request, name: str = Query(...), offset: int = Query(0, ge=0)):
    """Receive one chunk of a video (browser sends ~16 MB pieces)."""
    if not _ID.match(upload_id):
        raise HTTPException(400, "bad upload id")
    fname = Path(name).name
    if Path(fname).suffix.lower() not in drive.VIDEO_EXT:
        raise HTTPException(400, f"unsupported file type: {fname}")
    data = await request.body()
    if offset + len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "file too large")
    folder = UPLOADS / upload_id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / fname
    if offset == 0:
        path.write_bytes(b"")
    elif not path.exists() or path.stat().st_size != offset:
        raise HTTPException(409, f"offset mismatch; worker has {path.stat().st_size if path.exists() else 0} bytes")
    with open(path, "r+b") as f:
        f.seek(offset)
        f.write(data)
    return {"ok": True, "name": fname, "size": offset + len(data)}


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
