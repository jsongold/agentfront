import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

const HOP = new Set(["host", "connection", "content-length"]);

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const base = (process.env.API_INTERNAL_URL || "http://127.0.0.1:8765").replace(/\/$/, "");
  const url = `${base}/${path.join("/")}${request.nextUrl.search}`;
  const headers = new Headers(request.headers);
  for (const name of HOP) headers.delete(name);
  const token = process.env.ADMIN_TOKEN || process.env.NEXT_PUBLIC_ADMIN_TOKEN;
  if (token && !headers.has("x-admin-token")) {
    headers.set("x-admin-token", token);
  }
  const init: RequestInit = { method: request.method, headers, redirect: "manual" };
  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = await request.arrayBuffer();
  }
  const response = await fetch(url, init);
  const out = new Headers(response.headers);
  out.delete("content-encoding");
  out.delete("transfer-encoding");
  return new Response(response.body, { status: response.status, headers: out });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
