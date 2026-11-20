"use client";
import { useState } from "react";
import { Logo } from "@/components/Brand";

export default function Login() {
  const [code, setCode] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    const r = await fetch("/api/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ passcode: code }) });
    setBusy(false);
    if (r.ok) {
      const next = new URLSearchParams(window.location.search).get("next") || "/studio";
      window.location.href = next;
    } else setErr("That passcode didn't work.");
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-5">
      <form onSubmit={submit} className="card w-full max-w-sm p-8">
        <Logo />
        <h1 className="mt-6 text-xl font-semibold">Studio access</h1>
        <p className="mt-1 text-sm text-white/55">Enter the passcode your Sarvam contact shared.</p>
        <input className="input mt-6" type="password" value={code} onChange={(e) => setCode(e.target.value)} placeholder="Passcode" autoFocus />
        {err && <p className="mt-3 text-sm text-red-400">{err}</p>}
        <button className="btn-primary mt-6 w-full" disabled={busy || !code}>{busy ? "Checking..." : "Enter Studio"}</button>
      </form>
    </main>
  );
}
