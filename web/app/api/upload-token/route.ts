import { NextResponse } from "next/server";
import { uploadToken, workerUrl } from "@/lib/worker";

export async function GET() {
  return NextResponse.json({ url: await workerUrl(), token: uploadToken() });
}