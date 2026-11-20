"""Run the pipeline without the web app.

    python run_local.py --drive "https://drive.google.com/drive/folders/..." --episodes 1-8 \
        --prompt "Romance angle, end on the slap"
    python run_local.py --dir ./sample_episodes
"""
import argparse
import json
import time

from jhalak import pipeline

ap = argparse.ArgumentParser()
ap.add_argument("--drive")
ap.add_argument("--dir")
ap.add_argument("--episodes", default="1-10")
ap.add_argument("--series", default="")
ap.add_argument("--prompt", default="", help="direction applied to all three promos")
ap.add_argument("--seconds", type=int, default=45)
ap.add_argument("--narration-language", default="hi-IN")
ap.add_argument("--voice", default=None)
a = ap.parse_args()

params = {"drive_url": a.drive, "local_dir": a.dir, "episode_range": a.episodes, "series_name": a.series,
          "global_prompt": a.prompt, "target_seconds": a.seconds, "narration_language": a.narration_language,
          "language": "unknown"}
if a.voice:
    params["narrator_voice"] = a.voice
job = pipeline.create_job(params)
print("job", job["id"])
while True:
    time.sleep(2)
    j = pipeline.load(job["id"])
    if j["status"] in ("done", "error"):
        break
print(json.dumps({"status": j["status"], "stage": j["stage"],
                  "promos": [{k: p.get(k) for k in ("name", "status", "video", "duration", "error")} for p in j["promos"]]},
                 indent=1, ensure_ascii=False))
print("outputs in", pipeline.JOBS / job["id"])
