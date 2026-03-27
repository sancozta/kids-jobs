"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from "recharts";
import { BriefcaseBusiness, FileText, RefreshCw, ServerCog, TriangleAlert, Workflow } from "lucide-react";
import { toast } from "sonner";

import { SectionCards } from "@/components/section-cards";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import { Skeleton } from "@/components/ui/skeleton";
import { api, scrapingApi } from "@/lib/api";
import { formatDateTimeDDMMYYYYHHMM } from "@/lib/date";
import { cn } from "@/lib/utils";

type ServiceAvailability = "online" | "offline";

interface DashboardHealth {
  backend: ServiceAvailability;
  scraping: ServiceAvailability;
}

interface MarketCountResponse {
  total: number;
}

interface MarketItem {
  id: number;
  source_id: number | null;
  title: string | null;
  description?: string | null;
  url: string | null;
  city: string | null;
  state: string | null;
  attributes?: Record<string, unknown> | null;
  created_at: string | null;
}

interface SourceItem {
  id: number;
  name: string;
  enabled: boolean;
  description: string;
  last_extraction_status: string | null;
  last_extraction_at: string | null;
  next_scheduled_at: string | null;
}

interface SourceExecutionHistoryItem {
  id: number;
  source_id: number;
  source_name: string;
  trigger: string;
  status: string;
  success: boolean;
  scraped_count: number;
  published_count: number;
  duration_ms: number;
  strategy: string;
  message?: string | null;
  error_message?: string | null;
  executed_at?: string | null;
}

interface ChartPoint {
  day: string;
  label: string;
  extracted: number;
  runs: number;
  failures: number;
}

interface ScraperRunQueuedResponse {
  job_id?: string;
  queued_count?: number;
}

const SAO_PAULO_TIMEZONE = "America/Sao_Paulo";
const CHART_CONFIG = {
  extracted: {
    label: "Itens extraídos",
    color: "hsl(var(--chart-1))",
  },
} satisfies ChartConfig;
const STATUS_LABELS: Record<string, string> = {
  SUCCESS: "Sucesso",
  PARTIAL: "Parcial",
  ERROR: "Erro",
};
const STATUS_STYLES: Record<string, string> = {
  SUCCESS: "border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  PARTIAL: "border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400",
  ERROR: "border-rose-500/30 bg-rose-500/10 text-rose-600 dark:text-rose-400",
};

function normalizeStatus(value: string | null | undefined): string {
  return (value ?? "").trim().toUpperCase();
}

function getDateParts(date: Date) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: SAO_PAULO_TIMEZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);

  const year = parts.find((part) => part.type === "year")?.value ?? "0000";
  const month = parts.find((part) => part.type === "month")?.value ?? "00";
  const day = parts.find((part) => part.type === "day")?.value ?? "00";

  return { year, month, day };
}

function buildDayKey(date: Date): string {
  const { year, month, day } = getDateParts(date);
  return `${year}-${month}-${day}`;
}

function buildDayLabel(date: Date): string {
  const { month, day } = getDateParts(date);
  return `${day}/${month}`;
}

function resolveDayKey(value: string | null | undefined): string | null {
  if (!value) return null;

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;

  return buildDayKey(parsed);
}

function buildChartData(executions: SourceExecutionHistoryItem[]): ChartPoint[] {
  const days = Array.from({ length: 7 }, (_, index) => {
    const date = new Date(Date.now() - (6 - index) * 24 * 60 * 60 * 1000);
    return {
      day: buildDayKey(date),
      label: buildDayLabel(date),
      extracted: 0,
      runs: 0,
      failures: 0,
    };
  });

  const dayMap = new Map(days.map((item) => [item.day, item]));

  for (const execution of executions) {
    const dayKey = resolveDayKey(execution.executed_at ?? null);
    if (!dayKey) continue;

    const bucket = dayMap.get(dayKey);
    if (!bucket) continue;

    bucket.extracted += Math.max(0, Number(execution.scraped_count || 0));
    bucket.runs += 1;
    if (normalizeStatus(execution.status) === "ERROR" || !execution.success) {
      bucket.failures += 1;
    }
  }

  return days;
}

function formatJobLocation(item: MarketItem): string {
  const city = item.city?.trim();
  const state = item.state?.trim();
  const location = [city, state].filter(Boolean).join(" / ");

  if (location) return location;

  const rawLocation = item.attributes?.location;
  if (typeof rawLocation === "string" && rawLocation.trim()) {
    return rawLocation.trim();
  }

  return "Local não informado";
}

function getJobContractTypeTag(item: MarketItem): string | null {
  const contractType = item.attributes?.contract_type;
  if (typeof contractType !== "string") return null;

  const normalized = contractType.trim().toLowerCase();
  if (!normalized) return null;
  if (normalized === "pj" || normalized.includes("pessoa jurid")) return "PJ";
  if (normalized === "clt") return "CLT";

  return contractType.trim().toUpperCase();
}

function isRemoteJob(item: MarketItem): boolean {
  const candidates = [
    item.city,
    item.state,
    typeof item.attributes?.location === "string" ? item.attributes.location : null,
    typeof item.attributes?.work_model === "string" ? item.attributes.work_model : null,
  ]
    .filter((value): value is string => typeof value === "string" && value.trim().length > 0)
    .map((value) => value.trim().toLowerCase());

  return candidates.some((value) =>
    ["remote", "remoto", "home office", "anywhere", "worldwide"].some((token) => value.includes(token)),
  );
}

function getDisplayJobLocation(item: MarketItem): string | null {
  const location = formatJobLocation(item);
  if (location === "Local não informado") return null;
  if (isRemoteJob(item)) return null;
  return location;
}

function getJobSourceName(item: MarketItem, sourceNameById: Map<number, string>): string {
  if (typeof item.source_id === "number") {
    return sourceNameById.get(item.source_id) ?? `Fonte #${item.source_id}`;
  }

  const rawSource = item.attributes?.source_name ?? item.attributes?.source;
  if (typeof rawSource === "string" && rawSource.trim()) {
    return rawSource.trim();
  }

  return "Fonte local";
}

function StatusBadge({ status }: { status: string | null | undefined }) {
  const normalized = normalizeStatus(status);
  const label = STATUS_LABELS[normalized] ?? (normalized || "Sem status");

  return (
    <Badge
      variant="outline"
      className={cn("rounded-full border px-2 py-0.5 text-[11px] font-medium", STATUS_STYLES[normalized] ?? "")}
    >
      {label}
    </Badge>
  );
}

function ListSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 4 }).map((_, index) => (
        <div key={index} className="space-y-2 rounded-2xl border border-border/60 p-4">
          <Skeleton className="h-4 w-2/3" />
          <Skeleton className="h-3 w-1/3" />
        </div>
      ))}
    </div>
  );
}

export default function DashboardPage() {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [warning, setWarning] = useState<string | null>(null);
  const [totalJobs, setTotalJobs] = useState(0);
  const [latestJobs, setLatestJobs] = useState<MarketItem[]>([]);
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [executions, setExecutions] = useState<SourceExecutionHistoryItem[]>([]);
  const [health, setHealth] = useState<DashboardHealth>({
    backend: "offline",
    scraping: "offline",
  });
  const [runningAllScrapers, setRunningAllScrapers] = useState(false);

  const loadDashboard = useCallback(async (backgroundRefresh = false) => {
    if (backgroundRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }

    const results = await Promise.allSettled([
      api.get<MarketCountResponse>("/market/count"),
      api.get<MarketItem[]>("/market/", {
        params: {
          limit: 12,
          order_by: "created_at",
          order_direction: "desc",
        },
      }),
      api.get<SourceItem[]>("/api/v1/sources"),
      fetch("/api/dashboard/service-health", { cache: "no-store" }).then(async (response) => {
        if (!response.ok) {
          throw new Error("service-health");
        }

        return (await response.json()) as DashboardHealth;
      }),
      fetch("/api/scraping/source-executions?period=7d&limit=300", { cache: "no-store" }).then(async (response) => {
        if (!response.ok) {
          throw new Error("source-executions");
        }

        return (await response.json()) as SourceExecutionHistoryItem[];
      }),
    ]);

    const failedBlocks: string[] = [];

    const countResult = results[0];
    if (countResult.status === "fulfilled") {
      setTotalJobs(Number(countResult.value.data.total ?? 0));
    } else {
      failedBlocks.push("contagem de vagas");
      setTotalJobs(0);
    }

    const jobsResult = results[1];
    if (jobsResult.status === "fulfilled") {
      setLatestJobs(Array.isArray(jobsResult.value.data) ? jobsResult.value.data : []);
    } else {
      failedBlocks.push("últimas vagas");
      setLatestJobs([]);
    }

    const sourcesResult = results[2];
    if (sourcesResult.status === "fulfilled") {
      setSources(Array.isArray(sourcesResult.value.data) ? sourcesResult.value.data : []);
    } else {
      failedBlocks.push("fontes");
      setSources([]);
    }

    const healthResult = results[3];
    if (healthResult.status === "fulfilled") {
      setHealth(healthResult.value);
    } else {
      failedBlocks.push("saúde local");
      setHealth({ backend: "offline", scraping: "offline" });
    }

    const executionsResult = results[4];
    if (executionsResult.status === "fulfilled") {
      setExecutions(Array.isArray(executionsResult.value) ? executionsResult.value : []);
    } else {
      failedBlocks.push("histórico de scraping");
      setExecutions([]);
    }

    setWarning(failedBlocks.length > 0 ? `Nem todos os blocos foram atualizados: ${failedBlocks.join(", ")}.` : null);
    setLoading(false);
    setRefreshing(false);
  }, []);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  const runAllScrapers = useCallback(async () => {
    setRunningAllScrapers(true);
    try {
      const response = await scrapingApi.post<ScraperRunQueuedResponse>("/api/v1/scrapers/run-all");
      const queuedCount = Number(response.data?.queued_count ?? 0);
      const jobId = response.data?.job_id;

      toast.success(
        jobId
          ? `${queuedCount} scraping(s) enviados para execução (job ${jobId.slice(0, 8)})`
          : `${queuedCount} scraping(s) enviados para execução`
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : "Erro ao executar todos os scrapings";
      toast.error(message);
    } finally {
      setRunningAllScrapers(false);
    }
  }, []);

  const sourceNameById = useMemo(() => {
    return new Map(sources.map((source) => [source.id, source.name]));
  }, [sources]);

  const todayKey = useMemo(() => buildDayKey(new Date()), []);

  const stats = useMemo(
    () => ({
      totalJobs,
      jobsExtractedToday: executions.reduce((total, execution) => {
        return resolveDayKey(execution.executed_at ?? null) === todayKey
          ? total + Math.max(0, Number(execution.scraped_count || 0))
          : total;
      }, 0),
      activeSources: sources.filter((source) => source.enabled).length,
      totalSources: sources.length,
    }),
    [executions, sources, todayKey, totalJobs],
  );

  const chartData = useMemo(() => buildChartData(executions), [executions]);

  const recentExecutions = useMemo(() => executions.slice(0, 8), [executions]);

  const operationsSummary = useMemo(() => {
    return recentExecutions.reduce(
      (summary, execution) => {
        const normalized = normalizeStatus(execution.status);
        if (normalized === "SUCCESS") summary.success += 1;
        if (normalized === "PARTIAL") summary.partial += 1;
        if (normalized === "ERROR") summary.error += 1;
        return summary;
      },
      { success: 0, partial: 0, error: 0 },
    );
  }, [recentExecutions]);

  const monitoredSources = useMemo(() => {
    return [...sources]
      .sort((left, right) => {
        if (left.enabled !== right.enabled) return left.enabled ? -1 : 1;
        const leftTimestamp = left.last_extraction_at ? new Date(left.last_extraction_at).getTime() : 0;
        const rightTimestamp = right.last_extraction_at ? new Date(right.last_extraction_at).getTime() : 0;
        return rightTimestamp - leftTimestamp;
      });
  }, [sources]);

  const totalFailuresInRange = useMemo(() => {
    return chartData.reduce((total, item) => total + item.failures, 0);
  }, [chartData]);

  return (
    <main className="flex flex-1 flex-col gap-4 px-4 pt-3 pb-6 lg:px-6 lg:pt-4">
      <SectionCards stats={stats} health={health} loading={loading} />

      <section className="grid items-stretch gap-4 lg:grid-cols-3">
        <Card className="h-full gap-4 border-border/60 bg-gradient-to-br from-primary/[0.08] via-background to-background py-4">
          <CardContent className="flex h-full flex-col gap-1.5 px-4">
            <Button asChild className="min-h-7 flex-1 w-full justify-start text-xs">
              <Link href="/vagas">
                <BriefcaseBusiness className="size-3" />
                Abrir vagas
              </Link>
            </Button>
            <Button asChild variant="outline" className="min-h-7 flex-1 w-full justify-start text-xs">
              <Link href="/resume">
                <FileText className="size-3" />
                Editar currículo
              </Link>
            </Button>
            <Button asChild variant="outline" className="min-h-7 flex-1 w-full justify-start text-xs">
              <Link href="/resume">
                <FileText className="size-3" />
                Enviar currículo
              </Link>
            </Button>
            <Button asChild variant="outline" className="min-h-7 flex-1 w-full justify-start text-xs">
              <Link href="/sources">
                <ServerCog className="size-3" />
                Gerenciar fontes
              </Link>
            </Button>
            <Button
              type="button"
              variant="outline"
              className="min-h-7 flex-1 w-full justify-start text-xs"
              onClick={() => void runAllScrapers()}
              disabled={runningAllScrapers}
            >
              <RefreshCw className={cn("size-3", runningAllScrapers && "animate-spin")} />
              {runningAllScrapers ? "Rodando scrapings..." : "Rodar scrapings"}
            </Button>
            <Button asChild variant="outline" className="min-h-7 flex-1 w-full justify-start text-xs">
              <Link href="/scrapings">
                <Workflow className="size-3" />
                Ver scrapings
              </Link>
            </Button>
          </CardContent>
        </Card>

        <Card className="h-full border-border/60">
          <CardHeader className="gap-2">
            <CardTitle className="text-base">Resumo rápido</CardTitle>
            <CardDescription>Acesso às informações críticas de scraping e persistência local.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
              <div className="rounded-2xl border border-border/60 p-4">
                <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Última execução</p>
                <p className="mt-2 text-sm font-medium">
                  {recentExecutions[0]?.executed_at
                    ? formatDateTimeDDMMYYYYHHMM(recentExecutions[0].executed_at)
                    : "Nenhum histórico recente"}
                </p>
              </div>
              <div className="rounded-2xl border border-border/60 p-4">
                <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Cobertura do stack</p>
                <p className="mt-2 text-sm font-medium">
                  {[health.backend, health.scraping].filter((status) => status === "online").length}/2 serviços online
                </p>
              </div>
            </div>
            <Button
              variant="outline"
              className="w-full"
              onClick={() => void loadDashboard(true)}
              disabled={loading || refreshing}
            >
              <RefreshCw className={cn("size-4", refreshing ? "animate-spin" : "")} />
              Atualizar painel
            </Button>
          </CardContent>
        </Card>

        <Card className="h-full border-border/60">
          <CardHeader className="gap-2">
            <div className="flex items-center justify-between gap-3">
              <CardTitle className="text-base">Operação recente</CardTitle>
              <Badge variant="outline" className="rounded-lg px-1.5 text-[10px] font-mono">
                7D
              </Badge>
            </div>
            <CardDescription>Resumo dos últimos disparos registrados no histórico.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-3 gap-2">
              <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-3 py-2.5">
                <p className="text-[10px] uppercase tracking-[0.16em] text-emerald-700 dark:text-emerald-300">
                  Sucesso
                </p>
                <p className="mt-1 text-xl font-semibold">{loading ? "..." : operationsSummary.success}</p>
              </div>
              <div className="rounded-xl border border-amber-500/20 bg-amber-500/10 px-3 py-2.5">
                <p className="text-[10px] uppercase tracking-[0.16em] text-amber-700 dark:text-amber-300">Parcial</p>
                <p className="mt-1 text-xl font-semibold">{loading ? "..." : operationsSummary.partial}</p>
              </div>
              <div className="rounded-xl border border-rose-500/20 bg-rose-500/10 px-3 py-2.5">
                <p className="text-[10px] uppercase tracking-[0.16em] text-rose-700 dark:text-rose-300">Erro</p>
                <p className="mt-1 text-xl font-semibold">{loading ? "..." : operationsSummary.error}</p>
              </div>
            </div>
            <div className="space-y-3 rounded-2xl border border-border/60 p-4">
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm font-medium">Fontes cadastradas</span>
                <span className="text-sm text-muted-foreground">{sources.length.toLocaleString("pt-BR")}</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm font-medium">Fontes habilitadas</span>
                <span className="text-sm text-muted-foreground">{stats.activeSources.toLocaleString("pt-BR")}</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm font-medium">Extraídas hoje</span>
                <span className="text-sm text-muted-foreground">
                  {stats.jobsExtractedToday.toLocaleString("pt-BR")}
                </span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm font-medium">Falhas em 7 dias</span>
                <span className="text-sm text-muted-foreground">{totalFailuresInRange.toLocaleString("pt-BR")}</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </section>

      {warning ? (
        <div className="flex items-start gap-2 rounded-2xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-700 dark:text-amber-300">
          <TriangleAlert className="mt-0.5 size-4 shrink-0" />
          <span>{warning}</span>
        </div>
      ) : null}

      <section>
        <Card className="gap-4 border-border/60 py-4">
          <CardHeader className="px-5 pb-0">
            <CardTitle className="text-base">Volume de scraping</CardTitle>
            <CardDescription>Itens extraídos por dia nos últimos 7 dias.</CardDescription>
          </CardHeader>
          <CardContent className="px-5">
            {loading ? (
              <Skeleton className="h-[220px] w-full rounded-2xl" />
            ) : (
              <ChartContainer config={CHART_CONFIG} className="h-[220px] w-full">
                <AreaChart data={chartData} margin={{ left: 4, right: 4, top: 12 }}>
                  <defs>
                    <linearGradient id="fillExtracted" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="var(--color-extracted)" stopOpacity={0.35} />
                      <stop offset="95%" stopColor="var(--color-extracted)" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid vertical={false} />
                  <XAxis dataKey="label" tickLine={false} axisLine={false} tickMargin={8} />
                  <YAxis allowDecimals={false} width={30} tickLine={false} axisLine={false} />
                  <ChartTooltip
                    cursor={false}
                    content={
                      <ChartTooltipContent
                        labelFormatter={(_, payload) => {
                          const item = payload?.[0]?.payload as ChartPoint | undefined;
                          return item ? `Dia ${item.label}` : "Dia";
                        }}
                        formatter={(value, name, item) => {
                          const data = item.payload as ChartPoint;
                          return (
                            <div className="flex min-w-[10rem] items-center justify-between gap-4">
                              <span className="text-muted-foreground">{name}</span>
                              <span className="font-medium">
                                {Number(value).toLocaleString("pt-BR")} itens · {data.runs} execuções
                              </span>
                            </div>
                          );
                        }}
                      />
                    }
                  />
                  <Area
                    type="monotone"
                    dataKey="extracted"
                    name="Itens extraídos"
                    stroke="var(--color-extracted)"
                    strokeWidth={2}
                    fill="url(#fillExtracted)"
                  />
                </AreaChart>
              </ChartContainer>
            )}
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <Card className="border-border/60">
          <CardHeader>
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-1">
                <CardTitle className="text-base">Últimas vagas</CardTitle>
                <CardDescription>Oportunidades mais recentes persistidas na tabela `jobs`.</CardDescription>
              </div>
              <Button asChild size="sm" variant="outline">
                <Link href="/vagas">Ir para vagas</Link>
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <ListSkeleton />
            ) : latestJobs.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-border/70 p-6 text-sm text-muted-foreground">
                Nenhuma vaga encontrada ainda.
              </div>
            ) : (
              <div className="space-y-2">
                {latestJobs.map((item) => {
                  const contractTypeTag = getJobContractTypeTag(item);
                  const displayLocation = getDisplayJobLocation(item);
                  const tags = [
                    getJobSourceName(item, sourceNameById),
                    isRemoteJob(item) ? "Remote" : null,
                    contractTypeTag,
                  ].filter((value): value is string => Boolean(value));

                  const content = (
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div className="min-w-0 flex-1 space-y-1">
                        <p className="line-clamp-2 text-sm leading-5 font-semibold">
                          {item.title?.trim() || `Vaga #${item.id}`}
                        </p>
                        {item.description?.trim() ? (
                          <p className="line-clamp-1 text-xs text-muted-foreground">{item.description.trim()}</p>
                        ) : null}
                        {displayLocation ? <span className="text-xs text-muted-foreground">{displayLocation}</span> : null}
                      </div>
                      <div className="flex shrink-0 flex-col items-end gap-1.5">
                        <div className="text-right text-[11px] text-muted-foreground">
                          {formatDateTimeDDMMYYYYHHMM(item.created_at)}
                        </div>
                        <div className="flex max-w-[220px] flex-wrap justify-end gap-1.5">
                          {tags.map((tag) => (
                            <Badge key={`${item.id}-${tag}`} variant="outline" className="rounded-full px-1.5 py-0 text-[10px]">
                              {tag}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    </div>
                  );

                  if (item.url) {
                    return (
                      <a
                        key={item.id}
                        href={item.url}
                        target="_blank"
                        rel="noreferrer"
                        className="block rounded-xl border border-border/60 p-3 transition-colors hover:border-primary/30 hover:bg-accent/20"
                      >
                        {content}
                      </a>
                    );
                  }

                  return (
                    <div key={item.id} className="rounded-xl border border-border/60 p-3">
                      {content}
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="border-border/60">
          <CardHeader>
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-1">
                <CardTitle className="text-base">Execuções recentes</CardTitle>
                <CardDescription>Histórico mais recente de runs manuais e agendadas.</CardDescription>
              </div>
              <Button asChild size="sm" variant="outline">
                <Link href="/scrapings">Ir para scrapings</Link>
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <ListSkeleton />
            ) : recentExecutions.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-border/70 p-6 text-sm text-muted-foreground">
                Nenhuma execução registrada ainda.
              </div>
            ) : (
              <div className="space-y-2">
                {recentExecutions.map((execution) => (
                  <div key={execution.id} className="rounded-xl border border-border/60 p-3">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div className="min-w-0 space-y-1">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <p className="text-sm font-semibold">{execution.source_name}</p>
                          <StatusBadge status={execution.status} />
                        </div>
                        <p className="text-xs text-muted-foreground">
                          {execution.scraped_count.toLocaleString("pt-BR")} itens extraídos ·{" "}
                          {execution.published_count.toLocaleString("pt-BR")} publicados · trigger {execution.trigger}
                        </p>
                      </div>
                      <div className="text-right text-[11px] text-muted-foreground">
                        {formatDateTimeDDMMYYYYHHMM(execution.executed_at)}
                      </div>
                    </div>
                    <p className="mt-2 text-xs leading-4.5 text-muted-foreground">
                      {execution.message?.trim() || execution.error_message?.trim() || "Sem mensagem adicional."}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </section>

      <section>
        <Card className="border-border/60">
          <CardHeader>
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-1">
                <CardTitle className="text-base">Fontes monitoradas</CardTitle>
                <CardDescription>Estado atual de todas as fontes de jobs carregadas no seed local.</CardDescription>
              </div>
              <Button asChild size="sm" variant="outline">
                <Link href="/sources">Ir para fontes</Link>
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <ListSkeleton />
            ) : monitoredSources.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-border/70 p-6 text-sm text-muted-foreground">
                Nenhuma fonte disponível.
              </div>
            ) : (
              <div className="grid gap-3 lg:grid-cols-2">
                {monitoredSources.map((source) => (
                  <div key={source.id} className="rounded-2xl border border-border/60 p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-sm font-semibold">{source.name}</p>
                          <Badge variant="outline" className="rounded-full px-2 py-0.5 text-[11px]">
                            {source.enabled ? "Ativa" : "Pausada"}
                          </Badge>
                          <StatusBadge status={source.last_extraction_status} />
                        </div>
                        <p className="text-xs text-muted-foreground">
                          Próximo agendamento:{" "}
                          {source.next_scheduled_at
                            ? formatDateTimeDDMMYYYYHHMM(source.next_scheduled_at)
                            : "não disponível"}
                        </p>
                      </div>
                      <div className="text-right text-xs text-muted-foreground">
                        Última execução
                        <div className="mt-1 font-medium text-foreground">
                          {formatDateTimeDDMMYYYYHHMM(source.last_extraction_at)}
                        </div>
                      </div>
                    </div>
                    {source.description?.trim() ? (
                      <p className="mt-3 line-clamp-2 text-xs text-muted-foreground">{source.description.trim()}</p>
                    ) : null}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </section>
    </main>
  );
}
