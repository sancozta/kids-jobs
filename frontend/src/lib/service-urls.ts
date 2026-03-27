const DEFAULT_SERVICE_URLS = {
  backend: "http://localhost:8001",
  scraping: "http://localhost:8001",
  agent: "http://localhost:8001",
  cpf: "http://localhost:8001",
} as const;

export function normalizeServiceUrl(value: string | undefined, fallback: string): string {
  const normalized = value?.trim();
  return (normalized && normalized.length > 0 ? normalized : fallback).replace(/\/+$/, "");
}

export function resolveBackendApiUrl(): string {
  return normalizeServiceUrl(process.env.NEXT_PUBLIC_API_URL, DEFAULT_SERVICE_URLS.backend);
}

export function resolveScrapingApiUrl(): string {
  return normalizeServiceUrl(process.env.NEXT_PUBLIC_SCRAPING_API_URL, DEFAULT_SERVICE_URLS.scraping);
}

export function resolveAgentApiUrl(): string {
  return normalizeServiceUrl(process.env.NEXT_PUBLIC_AGENT_API_URL, DEFAULT_SERVICE_URLS.agent);
}

export function resolveCpfApiUrl(): string {
  return normalizeServiceUrl(process.env.NEXT_PUBLIC_CPF_API_URL, DEFAULT_SERVICE_URLS.cpf);
}

export function resolveBackendApiUrlForServer(): string {
  return normalizeServiceUrl(
    process.env.BACKEND_API_URL || process.env.NEXT_PUBLIC_API_URL,
    DEFAULT_SERVICE_URLS.backend,
  );
}

export function resolveScrapingApiUrlForServer(): string {
  return normalizeServiceUrl(
    process.env.SCRAPING_API_URL || process.env.NEXT_PUBLIC_SCRAPING_API_URL,
    DEFAULT_SERVICE_URLS.scraping,
  );
}

export function resolveAgentApiUrlForServer(): string {
  return normalizeServiceUrl(
    process.env.AGENT_API_URL || process.env.NEXT_PUBLIC_AGENT_API_URL,
    DEFAULT_SERVICE_URLS.agent,
  );
}

export function resolveCpfApiUrlForServer(): string {
  return normalizeServiceUrl(process.env.CPF_API_URL || process.env.NEXT_PUBLIC_CPF_API_URL, DEFAULT_SERVICE_URLS.cpf);
}

export { DEFAULT_SERVICE_URLS };
