import { NextResponse } from "next/server";

import {
  resolveBackendApiUrlForServer,
  resolveScrapingApiUrlForServer,
} from "@/lib/service-urls";

type ServiceAvailability = "online" | "offline";

const HEALTHCHECK_TIMEOUT_MS = 1500;

async function checkService(baseUrl: string): Promise<ServiceAvailability> {
  try {
    const response = await fetch(`${baseUrl}/health`, {
      method: "GET",
      headers: { Accept: "application/json" },
      cache: "no-store",
      signal: AbortSignal.timeout(HEALTHCHECK_TIMEOUT_MS),
    });

    return response.ok ? "online" : "offline";
  } catch {
    return "offline";
  }
}

export const dynamic = "force-dynamic";

export async function GET() {
  const [backend, scraping] = await Promise.all([
    checkService(resolveBackendApiUrlForServer()),
    checkService(resolveScrapingApiUrlForServer()),
  ]);

  return NextResponse.json(
    {
      backend,
      scraping,
    },
    { status: 200 },
  );
}
