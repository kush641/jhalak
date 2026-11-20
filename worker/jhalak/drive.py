"""Read episodes from a public Google Drive folder (shared as "anyone with the link")."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

import requests

from .config import settings

API = "https://www.googleapis.com/drive/v3/files"
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}


def parse_drive_id(url: str) -> tuple[str, str]:
    """Return (kind, id) where kind is 'folder' or 'file'."""
    url = url.strip()
    m = re.search(r"/folders/([A-Za-z0-9_-]+)", url)
    if m:
        return "folder", m.group(1)
    m = re.search(r"/file/d/([A-Za-z0-9_-]+)", url) or re.search(r"[?&]id=([A-Za-z0-9_-]+)", url)
    if m:
        return "file", m.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{20,}", url):
        return "folder", url
    raise ValueError("Could not find a Google Drive folder or file ID in that link")


def natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def _list(folder_id: str) -> list[dict]:
    if not settings.GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY is not set on the worker")
    items, token = [], None
    while True:
        params = {
            "q": f"'{folder_id}' in parents and trashed = false",
            "fields": "nextPageToken, files(id, name, mimeType, size)",
            "pageSize": 1000,
            "key": settings.GOOGLE_API_KEY,
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
        }
        if token:
            params["pageToken"] = token
        r = requests.get(API, params=params, timeout=60)
        if r.status_code >= 400:
            raise RuntimeError(f"Drive listing failed ({r.status_code}). Is the folder shared as 'anyone with the link'? {r.text[:300]}")
        body = r.json()
        items += body.get("files", [])
        token = body.get("nextPageToken")
        if not token:
            return items


def list_episodes(url: str) -> list[dict]:
    """List video files (one level of sub-folders included), naturally sorted by name."""
    kind, fid = parse_drive_id(url)
    if kind == "file":
        r = requests.get(f"{API}/{fid}", params={"fields": "id,name,mimeType,size", "key": settings.GOOGLE_API_KEY,
                                                 "supportsAllDrives": "true"}, timeout=60)
        r.raise_for_status()
        return [r.json()]
    files = []
    for it in _list(fid):
        if it["mimeType"] == "application/vnd.google-apps.folder":
            files += [f for f in _list(it["id"]) if _is_video(f)]
        elif _is_video(it):
            files.append(it)
    files.sort(key=lambda f: natural_key(f["name"]))
    return files


def _is_video(f: dict) -> bool:
    return f.get("mimeType", "").startswith("video/") or Path(f.get("name", "")).suffix.lower() in VIDEO_EXT


def download(file: dict, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file["name"]).suffix or ".mp4"
    out = dest_dir / f"source{suffix}"
    if out.exists() and out.stat().st_size > 0:
        return out
    params = {"alt": "media", "key": settings.GOOGLE_API_KEY, "supportsAllDrives": "true", "acknowledgeAbuse": "true"}
    with requests.get(f"{API}/{file['id']}", params=params, stream=True, timeout=600) as r:
        if r.status_code >= 400:
            raise RuntimeError(f"Download failed for {file['name']} ({r.status_code}): {r.text[:200]}")
        tmp = out.with_suffix(".part")
        with open(tmp, "wb") as f:
            shutil.copyfileobj(r.raw, f, length=1 << 20)
        tmp.rename(out)
    return out
