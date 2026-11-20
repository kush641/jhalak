import { NextResponse } from "next/server";
import { WORKER_COOKIE, isAllowedWorkerUrl, workerUrl } from "@/lib/worker";

export async function GET() {
  const base = await workerUrl();
  let health: unknown = null;
  try {
    const r = await fetch(`${base}/health`, { cache: "no-store", signal: AbortSignal.timeout(5000) });
    health = await r.json();
  } catch {
    health = null;
  }
  return NextResponse.json({ url: base, online: !!health, health });
}

export async function POST(req: Request) {
  const { url } = await req.json().catch(() => ({ url: "" }));
  const res = NextResponse.json({ ok: true });
  if (!url) {
    res.cookies.delete(WORKER_COOKIE);
    return res;
  }
  if (!isAllowedWorkerUrl(url)) {
    return NextResponse.json({ error: "That host is not allowed (see WORKER_URL_ALLOW)" }, { status: 400 });
  }
  res.cookies.set(WORKER_COOKIE, url.replace(/\/$/, ""), { httpOnly: true, secure: true, sameSite: "lax", path: "/", maxAge: 60 * 60 * 24 * 30 });
  return res;
}
