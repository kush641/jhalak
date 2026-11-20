import { NextResponse } from "next/server";
import { callWorker } from "@/lib/worker";

export async function GET() {
  try {
    const r = await callWorker("/jobs");
    return NextResponse.json(r.body, { status: r.status });
  } catch {
    return NextResponse.json({ error: "Worker is offline" }, { status: 502 });
  }
}

export async function POST(req: Request) {
  const payload = await req.json();
  if (!payload?.drive_url && !payload?.upload_id) return NextResponse.json({ error: "Add a Google Drive link or upload videos" }, { status: 400 });
  try {
    const r = await callWorker("/jobs", { method: "POST", body: JSON.stringify(payload) });
    return NextResponse.json(r.body, { status: r.status });
  } catch {
    return NextResponse.json({ error: "Worker is offline. Start it on your laptop and check the worker URL." }, { status: 502 });
  }
}
