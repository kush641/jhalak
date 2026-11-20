import { NextRequest, NextResponse } from "next/server";
import crypto from "node:crypto";

// Gate the Studio and its API behind a passcode (APP_PASSCODE). Landing page stays public.
export function proxy(req: NextRequest) {
  const passcode = process.env.APP_PASSCODE;
  if (!passcode) return NextResponse.next();
  const expected = crypto
    .createHmac("sha256", process.env.WORKER_SECRET || "change-me")
    .update(`passcode:${passcode}`)
    .digest("hex");
  if (req.cookies.get("jhalak_auth")?.value === expected) return NextResponse.next();
  if (req.nextUrl.pathname.startsWith("/api/")) {
    return NextResponse.json({ error: "Not signed in" }, { status: 401 });
  }
  const url = req.nextUrl.clone();
  url.pathname = "/login";
  url.searchParams.set("next", req.nextUrl.pathname);
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ["/studio/:path*", "/api/jobs/:path*", "/api/worker-url", "/api/upload-token"],
};
