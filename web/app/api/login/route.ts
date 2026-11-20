import { NextResponse } from "next/server";
import { AUTH_COOKIE, passcodeToken } from "@/lib/worker";

export async function POST(req: Request) {
  const { passcode } = await req.json().catch(() => ({ passcode: "" }));
  if (!process.env.APP_PASSCODE || passcode !== process.env.APP_PASSCODE) {
    return NextResponse.json({ error: "Wrong passcode" }, { status: 401 });
  }
  const res = NextResponse.json({ ok: true });
  res.cookies.set(AUTH_COOKIE, passcodeToken(passcode), {
    httpOnly: true, secure: true, sameSite: "lax", path: "/", maxAge: 60 * 60 * 24 * 14,
  });
  return res;
}
