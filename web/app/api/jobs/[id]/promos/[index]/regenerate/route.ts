import { NextResponse } from "next/server";
import { callWorker } from "@/lib/worker";

export async function POST(req: Request, ctx: { params: Promise<{ id: string; index: string }> }) {
  const { id, index } = await ctx.params;
  const body = await req.json().catch(() => ({}));
  try {
    const r = await callWorker(`/jobs/${encodeURIComponent(id)}/promos/${Number(index)}/regenerate`, {
      method: "POST", body: JSON.stringify(body),
    });
    return NextResponse.json(r.body, { status: r.status });
  } catch {
    return NextResponse.json({ error: "Worker is offline" }, { status: 502 });
  }
}
