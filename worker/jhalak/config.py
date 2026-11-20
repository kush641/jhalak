"""Runtime settings, read from environment variables (see .env.example)."""
import os
from pathlib import Path

try:  # optional .env support for local runs
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except Exception:  # pragma: no cover
    pass


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    # Sarvam platform (Saaras, Bulbul, Sarvam-105B, Token Factory) all use the same key
    SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
    SARVAM_BASE_URL = os.getenv("SARVAM_BASE_URL", "https://api.sarvam.ai").rstrip("/")

    # Token Factory (OpenAI-compatible) for the vision model
    TOKEN_FACTORY_BASE_URL = os.getenv("TOKEN_FACTORY_BASE_URL", "https://api.sarvam.ai/v2").rstrip("/")
    TOKEN_FACTORY_API_KEY = os.getenv("TOKEN_FACTORY_API_KEY", "") or SARVAM_API_KEY
    VISION_MODEL = os.getenv("VISION_MODEL", "gemma4")

    # Script writer
    SCRIPT_MODEL = os.getenv("SCRIPT_MODEL", "sarvam-105b")
    SCRIPT_BASE_URL = os.getenv("SCRIPT_BASE_URL", "https://api.sarvam.ai/v1").rstrip("/")

    # Speech
    STT_MODEL = os.getenv("STT_MODEL", "saaras:v4")
    STT_MODE = os.getenv("STT_MODE", "transcribe")
    TTS_MODEL = os.getenv("TTS_MODEL", "bulbul:v4-flash")
    DEFAULT_NARRATOR = os.getenv("DEFAULT_NARRATOR", "shubh_hi_stories_dramatic")

    # Google Drive (public "anyone with the link" folders)
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

    # Worker
    DATA_DIR = Path(os.getenv("DATA_DIR", "./data")).resolve()
    WORKER_SECRET = os.getenv("WORKER_SECRET", "change-me")
    MAX_PARALLEL_CALLS = int(os.getenv("MAX_PARALLEL_CALLS", "4"))
    CHUNK_MAX_SECONDS = float(os.getenv("CHUNK_MAX_SECONDS", "25"))  # Saaras REST is for <30 s
    CHUNK_MIN_SECONDS = float(os.getenv("CHUNK_MIN_SECONDS", "3"))
    FRAMES_PER_CHUNK = int(os.getenv("FRAMES_PER_CHUNK", "8"))
    FRAME_WIDTH = int(os.getenv("FRAME_WIDTH", "512"))
    SEPARATION = os.getenv("SEPARATION", "demucs")  # demucs | none
    DEMUCS_MODEL = os.getenv("DEMUCS_MODEL", "htdemucs")
    OUTPUT_WIDTH = int(os.getenv("OUTPUT_WIDTH", "1080"))
    OUTPUT_HEIGHT = int(os.getenv("OUTPUT_HEIGHT", "1920"))
    FONT_PATH = os.getenv("FONT_PATH", "")

    # Offline testing: fake every external API call
    MOCK_APIS = _bool("MOCK_APIS", False)


settings = Settings()
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
