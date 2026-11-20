# Jhalak: promo studio for microdrama

Drop a Google Drive folder of episodes. Jhalak separates dialogue, music and picture, reads every episode
chunk by chunk (Saaras v4 for what is said, Gemma 4 on Token Factory for what is seen), has Sarvam-105B
write three promo scripts that reference exact chunks plus Bulbul v4 narration, then stitches three
downloadable vertical promos.

```
jhalak/
  web/      Next.js app (landing page + Studio) -> deploy on Vercel
  worker/   Python pipeline + FastAPI -> runs on your Mac for now, exposed with a Cloudflare tunnel
```

## How the pipeline maps to the plan

| Step | What runs | Where in code |
| --- | --- | --- |
| 1. Drive link | Lists the folder (one level of sub-folders), natural-sorts episodes, downloads the selected range | `worker/jhalak/drive.py` |
| 2.1 Separate | ffmpeg pulls the audio; Demucs splits it into `dialogue.wav` + `bgm.wav`; video is read from the source | `media.separate` |
| 2.2 Chunk + transcribe | Chunks are cut at pauses in the dialogue (<= 25 s, Saaras REST limit). The same boundaries are used for audio and video. Each chunk -> Saaras v4 with timestamps | `media.plan_chunks`, `intel.py` |
| 2.3 Video intelligence | 8 frames per chunk (never above 1 fps) -> `gemma4` on Token Factory -> JSON: characters, female lead on screen, emotion, intensity, visual appeal, hook score, cliffhanger score, spoiler risk, safety flags | `intel.py` |
| 2.4 Two synopses -> script | Per episode: an audio synopsis (Sarvam-105B over the transcripts) and a video synopsis (Gemma over the chunk descriptions). Both + the chunk catalog -> Sarvam-105B -> promo script JSON with chunk ids, in/out points, audio mode per segment, narration lines, 10-second hook rule, cliffhanger ending | `script.py` |
| 2.5 Stitch | Bulbul v4 voices the narration; each segment is cut, reframed to 1080x1920, mixed (scene audio ducked under narration), concatenated; a music bed from the BGM stem runs underneath with side-chain ducking; loudness to -14 LUFS | `render.py` |
| 2.6 Three promos, promptable | Three presets (Hook & Tease, Conflict Montage, Narrator Story), each with its own prompt, plus a direction for all three. Any promo can be regenerated with a new prompt; analysis is cached so only the script and cut are redone | `pipeline.py`, Studio page |

## 1. Run the worker on your Mac

```bash
cd worker
./setup_mac.sh            # installs ffmpeg, cloudflared, Python 3.11, Demucs (first run downloads ~1 GB)
nano .env                 # fill SARVAM_API_KEY, GOOGLE_API_KEY, WORKER_SECRET
./start.sh                # prints "Worker URL: https://xxxx.trycloudflare.com"
```

- **Google API key:** Google Cloud console > APIs & Services > enable "Google Drive API" > Credentials > Create API key
  (restrict it to the Drive API). The episode folder must be shared as "anyone with the link".
- **Try it without keys:** set `MOCK_APIS=1` in `.env`. Everything runs with fake transcripts, scripts and voice.
- **Command line, no web app:** `python run_local.py --drive "<folder link>" --episodes 1-8 --prompt "romance angle"`
- Outputs land in `worker/data/jobs/<id>/promo_1..3/` (`promo.mp4`, `script.json`, `timeline.json`, `thumb.jpg`).
  Per-episode analysis is cached in `worker/data/cache/`, so re-runs on the same series are fast.

## 2. Deploy the web app on Vercel (GitHub import)

```bash
cd jhalak
git init && git add . && git commit -m "Jhalak v0.1"
gh repo create jhalak --private --source=. --push      # or create the repo on github.com and push
```

In Vercel: **Add New > Project > Import** the repo, set **Root Directory = `web`**, then add these environment variables:

| Variable | Value |
| --- | --- |
| `WORKER_SECRET` | same value as `worker/.env` |
| `WORKER_URL` | the tunnel URL from `./start.sh` (default; can be changed in the Studio) |
| `APP_PASSCODE` | passcode that gates `/studio` |
| `WORKER_URL_ALLOW` | optional, defaults to `^https://[a-z0-9-]+\.trycloudflare\.com$` |

The quick-tunnel URL changes every time `start.sh` runs. Paste the new URL into **Studio > worker status chip**;
no redeploy needed. For a fixed URL, use a named Cloudflare tunnel on a Sarvam domain and set `WORKER_URL_ALLOW` to it.

The landing page (`/`) is public. `/studio` and its APIs need the passcode. Videos stream from the worker
through signed links that expire after 6 hours; the worker secret never reaches the browser.

## What has and hasn't been tested

- Tested end to end in mock mode: chunking, frame sampling, script validation, cutting, narration mixing,
  music bed ducking, loudness, three renders, regenerate-with-prompt, signed downloads, passcode gate, Studio UI.
- Not yet tested against live APIs (no keys in the build environment). Check these on the first real run:
  - Saaras `timestamps` shape (parsed as `words` / `start_time_seconds` / `end_time_seconds` lists)
  - Gemma image input on Token Factory (OpenAI `image_url` data URLs, 8 frames per call)
  - How reliably Sarvam-105B returns valid JSON (the code retries and repairs scripts)
  - Bulbul v4 persona names for non-Hindi narration
- Demucs runs on CPU or Apple GPU; expect roughly real time per episode on a MacBook Air.

## Tuning knobs (`worker/.env`)

`CHUNK_MAX_SECONDS`, `FRAMES_PER_CHUNK`, `MAX_PARALLEL_CALLS` (lower it if you hit rate limits),
`SEPARATION=none` (skip Demucs), `DEFAULT_NARRATOR`, `OUTPUT_WIDTH`/`OUTPUT_HEIGHT`.
