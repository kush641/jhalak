"use client";
import { use, useCallback, useEffect, useState } from "react";
import { Nav } from "@/components/Brand";
import WorkerStatus from "@/components/WorkerStatus";
import { PRESETS } from "@/lib/options";

type Seg = { order: number; role: string; type: string; chunk_id: string; audio: string; narration: string; overlay_text?: string;
  promo_start?: number; promo_end?: number; source_episode?: number; source_start?: number; source_end?: number; why?: string };
type Promo = { index: number; preset: string; name: string; prompt: string; status: string; error?: string; duration?: number;
  video_url?: string | null; download_url?: string | null; thumbnail_url?: string | null;
  script?: { hook_strategy?: string; cliffhanger?: string; social_caption?: string; segments: Seg[] }; timeline?: Seg[] };
type Job = { id: string; status: string; stage: string; progress: number; error?: string; params: { series_name?: string; target_seconds?: number };
  episodes: { episode: number; name: string; duration: number; chunks: number; separation: string; video_synopsis: string; audio_synopsis: string }[];
  promos: Promo[]; log: { t: number; msg: string }[] };

const roleColor: Record<string, string> = {
  hook: "bg-[#2E6BFF]", context: "bg-[#5B7BFF]", escalation: "bg-[#8B5CF6]", cliffhanger: "bg-[#E0663A]", cta: "bg-[#FF7A2E]",
};

function fmt(s?: number) {
  if (s == null) return "";
  return `${s.toFixed(1)}s`;
}

export default function JobPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [job, setJob] = useState<Job | null>(null);
  const [err, setErr] = useState("");
  const [showLog, setShowLog] = useState(false);

  const load = useCallback(async () => {
    const r = await fetch(`/api/jobs/${id}`, { cache: "no-store" });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) setErr(j.error || j.detail || "Could not load this run");
    else {
      setErr("");
      setJob(j);
    }
    return j as Job;
  }, [id]);

  useEffect(() => {
    let stop = false;
    let t: ReturnType<typeof setTimeout>;
    const tick = async () => {
      const j = await load().catch(() => null);
      if (stop) return;
      const busy = !j || j.status === "running" || j.status === "queued" || j.promos?.some((p) => ["queued", "writing", "rendering"].includes(p.status));
      t = setTimeout(tick, busy ? 3000 : 20000);
    };
    tick();
    return () => { stop = true; clearTimeout(t); };
  }, [load]);

  if (!job) {
    return (
      <main><Nav studio />
        <div className="mx-auto max-w-6xl px-5 py-16 text-white/60">{err || "Loading run..."}</div>
      </main>
    );
  }

  const running = job.status === "running" || job.status === "queued";

  return (
    <main>
      <Nav studio />
      <div className="mx-auto max-w-6xl px-5 py-10">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-white/40">Run {job.id}</p>
            <h1 className="mt-1 text-3xl font-semibold tracking-tight">{job.params.series_name || "Untitled series"}</h1>
          </div>
          <WorkerStatus />
        </div>

        {/* progress */}
        <div className="card mt-6 p-5">
          <div className="flex items-center justify-between text-sm">
            <span className={job.status === "error" ? "text-red-400" : "text-white/80"}>{job.stage}{job.error ? `: ${job.error}` : ""}</span>
            <span className="text-white/45">{job.progress}%</span>
          </div>
          <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/10">
            <div className={`grad-bg h-full transition-all duration-700 ${running ? "pulse-soft" : ""}`} style={{ width: `${Math.max(3, job.progress)}%` }} />
          </div>
          <button className="mt-3 text-xs text-white/45 hover:text-white/70" onClick={() => setShowLog(!showLog)}>{showLog ? "Hide" : "Show"} activity log</button>
          {showLog && (
            <div className="mt-2 max-h-56 overflow-auto rounded-lg bg-black/30 p-3 font-mono text-[11px] leading-relaxed text-white/60">
              {job.log.map((l, i) => <div key={i}>{new Date(l.t * 1000).toLocaleTimeString()} · {l.msg}</div>)}
            </div>
          )}
        </div>

        {/* promos */}
        <div className="mt-8 grid gap-6 lg:grid-cols-3">
          {job.promos.map((p) => <PromoCard key={p.index} jobId={job.id} promo={p} onChange={load} disabled={running} />)}
        </div>

        {/* episodes */}
        {job.episodes.length > 0 && (
          <section className="mt-12">
            <h2 className="text-xl font-semibold">What Jhalak understood</h2>
            <p className="mt-1 text-sm text-white/50">Two synopses per episode: one from what is seen, one from what is said.</p>
            <div className="mt-5 grid gap-4 md:grid-cols-2">
              {job.episodes.map((e) => (
                <div key={e.episode} className="card p-5 text-sm">
                  <div className="flex items-center justify-between">
                    <div className="font-semibold">Episode {e.episode}</div>
                    <div className="text-xs text-white/40">{e.duration}s · {e.chunks} chunks · {e.separation === "none" ? "no music separation" : "music separated"}</div>
                  </div>
                  <p className="mt-3 text-white/45"><span className="text-white/70">Seen: </span>{e.video_synopsis || "-"}</p>
                  <p className="mt-2 text-white/45"><span className="text-white/70">Said: </span>{e.audio_synopsis || "-"}</p>
                </div>
              ))}
            </div>
          </section>
        )}
      </div>
    </main>
  );
}

function PromoCard({ jobId, promo, onChange, disabled }: { jobId: string; promo: Promo; onChange: () => void; disabled: boolean }) {
  const [prompt, setPrompt] = useState(promo.prompt || "");
  const [preset, setPreset] = useState(promo.preset);
  const [tab, setTab] = useState<"script" | "direct">("script");
  const [busy, setBusy] = useState(false);
  const working = ["queued", "writing", "rendering", "pending"].includes(promo.status);
  const segs = promo.timeline || promo.script?.segments || [];

  async function regen() {
    setBusy(true);
    await fetch(`/api/jobs/${jobId}/promos/${promo.index}/regenerate`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ prompt, preset }),
    });
    setBusy(false);
    onChange();
  }

  return (
    <div className="card flex flex-col overflow-hidden">
      <div className="flex items-center justify-between px-5 pt-5">
        <div>
          <div className="text-xs text-white/40">Promo {promo.index + 1}</div>
          <div className="font-semibold">{promo.name}</div>
        </div>
        <span className="text-xs text-white/50">{promo.status === "done" ? fmt(promo.duration) : promo.status}</span>
      </div>

      <div className="mx-5 mt-4 aspect-[9/16] overflow-hidden rounded-xl bg-black/40">
        {promo.status === "done" && promo.video_url ? (
          <video key={promo.video_url} src={promo.video_url} poster={promo.thumbnail_url || undefined} controls playsInline className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center text-sm text-white/45">
            {promo.status === "error" ? <span className="text-red-400">{promo.error || "Failed"}</span> : (
              <><div className="grad-bg pulse-soft h-10 w-10 rounded-full" />{working ? `${promo.status === "rendering" ? "Stitching" : promo.status === "writing" ? "Writing script" : "Waiting"}...` : ""}</>
            )}
          </div>
        )}
      </div>

      {segs.length > 0 && (
        <div className="mx-5 mt-3 flex h-2 gap-0.5 overflow-hidden rounded-full">
          {segs.map((s) => (
            <div key={s.order} title={`${s.role} · ${s.chunk_id}`} className={roleColor[s.role] || "bg-white/30"}
              style={{ flexGrow: Math.max(0.5, (s.promo_end ?? 1) - (s.promo_start ?? 0)) }} />
          ))}
        </div>
      )}

      <div className="mt-4 flex gap-1 px-5 text-xs">
        {(["script", "direct"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)} className={`rounded-full px-3 py-1 ${tab === t ? "bg-white/10 text-white" : "text-white/50"}`}>
            {t === "script" ? "Script" : "Direct this promo"}
          </button>
        ))}
        {promo.download_url && <a href={promo.download_url} className="ml-auto rounded-full px-3 py-1 text-white/80 hover:bg-white/10">Download ↓</a>}
      </div>

      <div className="flex-1 p-5 pt-3 text-xs">
        {tab === "script" ? (
          segs.length ? (
            <div className="space-y-2">
              {promo.script?.hook_strategy && <p className="text-white/55"><span className="text-white/80">Hook: </span>{promo.script.hook_strategy}</p>}
              {promo.script?.cliffhanger && <p className="text-white/55"><span className="text-white/80">Ends on: </span>{promo.script.cliffhanger}</p>}
              <div className="mt-2 max-h-72 space-y-1.5 overflow-auto pr-1">
                {segs.map((s) => (
                  <div key={s.order} className="rounded-lg bg-white/[0.03] p-2.5">
                    <div className="flex items-center gap-2">
                      <span className={`h-2 w-2 rounded-full ${roleColor[s.role] || "bg-white/30"}`} />
                      <span className="font-medium capitalize text-white/85">{s.role}</span>
                      <span className="text-white/40">{fmt(s.promo_start)}-{fmt(s.promo_end)}</span>
                      <span className="ml-auto text-white/35">{s.type === "card" ? "card" : `Ep ${s.source_episode ?? s.chunk_id.slice(1, 3)} · ${s.chunk_id}`}</span>
                    </div>
                    {s.narration && <div className="mt-1.5 text-white/75"><span className="text-white/40">VO: </span>{s.narration}</div>}
                    <div className="mt-1 text-white/35">audio: {s.audio}{s.overlay_text ? ` · text: ${s.overlay_text}` : ""}</div>
                  </div>
                ))}
              </div>
              {promo.script?.social_caption && <p className="pt-1 text-white/55"><span className="text-white/80">Caption: </span>{promo.script.social_caption}</p>}
            </div>
          ) : <p className="text-white/40">The script appears once it is written.</p>
        ) : (
          <div className="space-y-3">
            <select className="input text-sm" value={preset} onChange={(e) => setPreset(e.target.value)}>
              {PRESETS.map((pr) => <option key={pr.key} value={pr.key}>{pr.name}</option>)}
            </select>
            <textarea className="input h-28 resize-none text-sm" value={prompt} onChange={(e) => setPrompt(e.target.value)}
              placeholder="e.g. Open on her tears at the wedding, narrator in a whisper, keep the slap dialogue loud, end before he answers" />
            <button className="btn-primary w-full text-sm" onClick={regen} disabled={busy || disabled || working}>
              {busy ? "Sending..." : "Regenerate this promo"}
            </button>
            <p className="text-white/35">Reuses the analysis, so only the script and the cut are redone.</p>
          </div>
        )}
      </div>
    </div>
  );
}
