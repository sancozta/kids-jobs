import { NextRequest, NextResponse } from "next/server";
import { resolveScrapingApiUrlForServer } from "@/lib/service-urls";

const ALLOWED_PERIODS = new Set(["24h", "7d", "30d", "90d"]);

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const url = new URL(request.url);
  const period = url.searchParams.get("period") ?? "30d";
  const limit = url.searchParams.get("limit") ?? "5000";

  if (!ALLOWED_PERIODS.has(period)) {
    return NextResponse.json([], { status: 200 });
  }

  const limitValue = Number(limit);
  const safeLimit = Number.isFinite(limitValue) && limitValue > 0 ? Math.min(Math.trunc(limitValue), 10000) : 5000;
  const upstreamUrl = `${resolveScrapingApiUrlForServer()}/api/v1/source-executions?period=${encodeURIComponent(period)}&limit=${safeLimit}`;

  try {
    const response = await fetch(upstreamUrl, {
      method: "GET",
      headers: { Accept: "application/json" },
      cache: "no-store",
    });

    if (response.status === 404) {
      return NextResponse.json([], { status: 200 });
    }

    if (!response.ok) {
      return NextResponse.json([], { status: 200 });
    }

    const payload = await response.json();
    return NextResponse.json(Array.isArray(payload) ? payload : [], { status: 200 });
  } catch {
    return NextResponse.json([], { status: 200 });
  }
}
