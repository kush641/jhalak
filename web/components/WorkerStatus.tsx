"use client";
import { useEffect, useState } from "react";

type Status = { url: string; online: boolean; health?: { mock?: boolean; separation?: string } | null };

export default function WorkerStatus() {
  const [s, setS] = useState<Status | null>(null);
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState("");
  const [msg, setMsg] = useState("");

  async function load() {
    const r = await fetch("/api/worker-url", { cache: "no-store" });
    if (r.ok) {
      const j = await r.json();
      setS(j);
      setUrl(j.url);
    }
  }
  useEffect(() => {
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, []);

  async function save() {
    setMsg("");
    const r = await fetch("/api/worker-url", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url }) });
    if (!r.ok) setMsg((await r.json()).error || "Could not save");
    else {
      setOpen(false);
      load();
    }
  }

  return (
    <div className="relative">
      <button onClick={() => setOpen(!open)} className="flex items-center gap-2 rounded-full border border-white/10 px-3 py-1.5 text-xs text-white/70 hover:bg-white/5">
        <span className={`h-2 w-2 rounded-full ${s?.online ? "bg-emerald-400" : "bg-red-400"} ${s ? "" : "pulse-soft bg-white/40"}`} />
        {s ? (s.online ? `Worker online${s.health?.mock ? " · mock mode" : ""}` : "Worker offline") : "Checking worker"}
      </button>
      {open && (
        <div className="card absolute right-0 z-40 mt-2 w-[22rem] p-4 shadow-2xl">
          <label className="label">Worker URL (your laptop tunnel)</label>
          <input className="input" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://xxxx.trycloudflare.com" />
          <p className="mt-2 text-xs text-white/45">Paste the URL printed by <code>./start.sh</code>. Leave empty to use the default from Vercel settings.</p>
          {msg && <p className="mt-2 text-xs text-red-400">{msg}</p>}
          <div className="mt-3 flex justify-end gap-2">
            <button className="btn-ghost !px-3 !py-1.5 text-xs" onClick={() => setOpen(false)}>Cancel</button>
            <button className="btn-primary !px-3 !py-1.5 text-xs" onClick={save}>Save</button>
          </div>
        </div>
      )}
    </div>
  );
}
