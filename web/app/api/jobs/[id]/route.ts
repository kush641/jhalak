import { NextResponse } from "next/server";
import { callWorker, signedFileUrl } from "@/lib/worker";

type Promo = { video?: string; thumbnail?: string; version?: number; [k: string]: unknown };

export async function GET(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  try {
    const r = await callWorker(`/jobs/${encodeURIComponent(id)}`);
    if (r.status !== 200) return NextResponse.json(r.body, { status: r.status });
    const job = r.body as { promos: Promo[] };
    job.promos = job.promos.map((p) => ({
      ...p,
      video_url: p.video ? `${signedFileUrl(r.base, id, p.video)}&v=${p.version ?? 0}` : null,
      download_url: p.video ? signedFileUrl(r.base, id, p.video, true) : null,
      thumbnail_url: p.thumbnail ? `${signedFileUrl(r.base, id, p.thumbnail)}&v=${p.version ?? 0}` : null,
    }));
    return NextResponse.json(job);
  } catch {
    return NextResponse.json({ error: "Worker is offline" }, { status: 502 });
  }
}
