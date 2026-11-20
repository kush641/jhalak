"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Nav } from "@/components/Brand";
import WorkerStatus from "@/components/WorkerStatus";
import { HINDI_VOICES, LANGUAGES, PRESETS } from "@/lib/options";

type JobRow = { id: string; status: string; stage: string; progress: number; created_at: number; params: { series_name?: string; drive_url?: string } };

export default function Studio() {
  const router = useRouter();
  const [drive, setDrive] = useState("");
  const [series, setSeries] = useState("");
  const [range, setRange] = useState("1-10");
  const [epLang, setEpLang] = useState("unknown");
  const [narrLang, setNarrLang] = useState("hi-IN");
  const [voice, setVoice] = useState("shubh_hi_stories_dramatic");
  const [seconds, setSeconds] = useState(45);
  const [direction, setDirection] = useState("");
  const [promos, setPromos] = useState(PRESETS.map((p) => ({ preset: p.key, prompt: "" })));
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [jobs, setJobs] = useState<JobRow[]>([]);

  useEffect(() => {
    fetch("/api/jobs").then(async (r) => (r.ok ? setJobs(await r.json()) : null)).catch(() => null);
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    const r = await fetch("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        drive_url: drive.trim(), series_name: series, episode_range: range, language: epLang,
        narration_language: narrLang, narrator_voice: voice, target_seconds: seconds, global_prompt: direction, promos,
      }),
    });
    const j = await r.json().catch(() => ({}));
    setBusy(false);
    if (!r.ok) return setErr(j.error || j.detail || "Something went wrong");
    router.push(`/studio/${j.id}`);
  }

  const isHindi = narrLang === "hi-IN";

  return (
    <main>
      <Nav studio />
      <div className="mx-auto max-w-6xl px-5 py-10">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight">New promo run</h1>
            <p className="mt-1 text-white/55">One series in, three promos out.</p>
          </div>
          <WorkerStatus />
        </div>

        <form onSubmit={submit} className="mt-8 grid gap-6 lg:grid-cols-[1fr_340px]">
          <div className="space-y-6">
            <section className="card p-6">
              <h2 className="font-semibold">1 · Episodes</h2>
              <div className="mt-4 grid gap-4 sm:grid-cols-[1fr_160px]">
                <div>
                  <label className="label">Google Drive folder link (shared as &ldquo;anyone with the link&rdquo;)</label>
                  <input className="input" required value={drive} onChange={(e) => setDrive(e.target.value)} placeholder="https://drive.google.com/drive/folders/..." />
                </div>
                <div>
                  <label className="label">Episodes to use</label>
                  <input className="input" value={range} onChange={(e) => setRange(e.target.value)} placeholder="1-10" />
                </div>
              </div>
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="label">Series name</label>
                  <input className="input" value={series} onChange={(e) => setSeries(e.target.value)} placeholder="e.g. Dulhan Ka Badla" />
                </div>
                <div>
                  <label className="label">Episode language</label>
                  <select className="input" value={epLang} onChange={(e) => setEpLang(e.target.value)}>
                    <option value="unknown">Detect automatically</option>
                    {LANGUAGES.map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </select>
                </div>
              </div>
            </section>

            <section className="card p-6">
              <h2 className="font-semibold">2 · Three promos</h2>
              <p className="mt-1 text-sm text-white/50">Each promo gets its own angle. Add a line of direction to steer the script and the audio mix.</p>
              <div className="mt-4 grid gap-4 md:grid-cols-3">
                {promos.map((p, i) => (
                  <div key={i} className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
                    <div className="text-xs text-white/45">Promo {i + 1}</div>
                    <select className="input mt-2" value={p.preset} onChange={(e) => setPromos(promos.map((x, k) => (k === i ? { ...x, preset: e.target.value } : x)))}>
                      {PRESETS.map((pr) => <option key={pr.key} value={pr.key}>{pr.name}</option>)}
                    </select>
                    <p className="mt-2 min-h-[2.5rem] text-xs text-white/45">{PRESETS.find((x) => x.key === p.preset)?.hint}</p>
                    <textarea className="input mt-2 h-24 resize-none text-sm" value={p.prompt} placeholder="Optional: e.g. focus on the mother-in-law rivalry, keep dialogue audio loud" onChange={(e) => setPromos(promos.map((x, k) => (k === i ? { ...x, prompt: e.target.value } : x)))} />
                  </div>
                ))}
              </div>
              <div className="mt-4">
                <label className="label">Direction for all three (optional)</label>
                <textarea className="input h-20 resize-none" value={direction} onChange={(e) => setDirection(e.target.value)} placeholder="e.g. Audience is women 25-40 in tier-2 cities. Lean on romance and revenge. Don't reveal who the real father is." />
              </div>
            </section>
          </div>

          <aside className="space-y-6">
            <section className="card p-6">
              <h2 className="font-semibold">3 · Voice & length</h2>
              <div className="mt-4 space-y-4">
                <div>
                  <label className="label">Narration language</label>
                  <select className="input" value={narrLang} onChange={(e) => { setNarrLang(e.target.value); if (e.target.value !== "hi-IN") setVoice(""); else setVoice("shubh_hi_stories_dramatic"); }}>
                    {LANGUAGES.map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </select>
                </div>
                <div>
                  <label className="label">Narrator voice</label>
                  {isHindi ? (
                    <select className="input" value={voice} onChange={(e) => setVoice(e.target.value)}>
                      {HINDI_VOICES.map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                    </select>
                  ) : (
                    <input className="input" value={voice} onChange={(e) => setVoice(e.target.value)} placeholder="Bulbul v4 persona, e.g. name_ta_narration" />
                  )}
                </div>
                <div>
                  <label className="label">Promo length</label>
                  <div className="grid grid-cols-3 gap-2">
                    {[30, 45, 60].map((s) => (
                      <button type="button" key={s} onClick={() => setSeconds(s)} className={`rounded-xl border px-3 py-2 text-sm ${seconds === s ? "grad-border text-white" : "border-white/10 text-white/60"}`}>{s}s</button>
                    ))}
                  </div>
                </div>
              </div>
              {err && <p className="mt-4 text-sm text-red-400">{err}</p>}
              <button className="btn-primary mt-6 w-full" disabled={busy || !drive}>{busy ? "Starting..." : "Create 3 promos"}</button>
              <p className="mt-3 text-xs text-white/40">Every promo opens with a 10-second hook and ends on a cliffhanger.</p>
            </section>

            <section className="card p-6">
              <h2 className="font-semibold">Recent runs</h2>
              <div className="mt-3 space-y-2">
                {jobs.length === 0 && <p className="text-sm text-white/40">No runs yet.</p>}
                {jobs.slice(0, 8).map((j) => (
                  <Link key={j.id} href={`/studio/${j.id}`} className="flex items-center justify-between rounded-lg px-2 py-2 text-sm hover:bg-white/5">
                    <span className="truncate">{j.params?.series_name || j.id}</span>
                    <span className={`text-xs ${j.status === "done" ? "text-emerald-400" : j.status === "error" ? "text-red-400" : "text-white/50"}`}>{j.status}</span>
                  </Link>
                ))}
              </div>
            </section>
          </aside>
        </form>
      </div>
    </main>
  );
}
