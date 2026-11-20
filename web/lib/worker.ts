import "server-only";
import crypto from "node:crypto";
import { cookies } from "next/headers";

export const WORKER_COOKIE = "jhalak_worker";
export const AUTH_COOKIE = "jhalak_auth";

const SECRET = process.env.WORKER_SECRET || "change-me";

function allowed(url: string): boolean {
  const pattern = process.env.WORKER_URL_ALLOW || "^https://[a-z0-9-]+\\.trycloudflare\\.com$";
  try {
    const u = new URL(url);
    return new RegExp(pattern).test(`${u.protocol}//${u.host}`);
  } catch {
    return false;
  }
}

/** Worker base URL: a Studio override (cookie, allow-listed hosts only) or the WORKER_URL env var. */
export async function workerUrl(): Promise<string> {
  const jar = await cookies();
  const override = jar.get(WORKER_COOKIE)?.value;
  if (override && allowed(override)) return override.replace(/\/$/, "");
  return (process.env.WORKER_URL || "http://localhost:8787").replace(/\/$/, "");
}

export function isAllowedWorkerUrl(url: string) {
  return allowed(url);
}

export async function callWorker(path: string, init: RequestInit = {}) {
  const base = await workerUrl();
  const res = await fetch(`${base}${path}`, {
    ...init,
    cache: "no-store",
    headers: { "Content-Type": "application/json", "X-Worker-Secret": SECRET, ...(init.headers || {}) },
  });
  const text = await res.text();
  let body: unknown = text;
  try {
    body = JSON.parse(text);
  } catch {
    /* non-JSON error page */
  }
  return { status: res.status, body, base };
}

/** Short-lived signed URL so the browser can stream a promo straight from the worker. */
export function signedFileUrl(base: string, jobId: string, rel: string, download = false, ttlSeconds = 6 * 3600) {
  const exp = Math.floor(Date.now() / 1000) + ttlSeconds;
  const path = `${jobId}/${rel}`;
  const sig = crypto.createHmac("sha256", SECRET).update(`${path}:${exp}`).digest("hex");
  return `${base}/files/${path}?exp=${exp}&sig=${sig}${download ? "&download=1" : ""}`;
}

export function passcodeToken(passcode: string) {
  return crypto.createHmac("sha256", SECRET).update(`passcode:${passcode}`).digest("hex");
}
