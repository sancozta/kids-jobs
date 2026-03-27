import { BriefcaseBusiness, Database, Download } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface SectionCardsProps {
  stats: {
    totalJobs: number;
    jobsExtractedToday: number;
    activeSources: number;
    totalSources: number;
  };
  health: {
    backend: "online" | "offline";
    scraping: "online" | "offline";
  };
  loading: boolean;
}

function StatusIndicator({ label, value }: { label: string; value: "online" | "offline" }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-[10px]">
        <span className="text-muted-foreground uppercase tracking-widest font-bold">{label}</span>
        <span className={cn("font-mono", value === "online" ? "text-emerald-500" : "text-rose-500")}>
          {value === "online" ? "UP" : "DOWN"}
        </span>
      </div>
      <div className="h-[2px] w-full overflow-hidden rounded-full bg-border">
        <div className={cn("h-full w-full", value === "online" ? "bg-emerald-500" : "bg-rose-500")} />
      </div>
    </div>
  );
}

export function SectionCards({ stats, health, loading }: SectionCardsProps) {
  return (
    <div className="grid grid-cols-1 gap-4 *:data-[slot=card]:bg-gradient-to-t *:data-[slot=card]:from-primary/5 *:data-[slot=card]:shadow-xs *:data-[slot=card]:to-card md:grid-cols-2 xl:grid-cols-4 dark:*:data-[slot=card]:bg-card">
      <Card className="@container/card gap-4 py-4">
        <CardHeader className="flex flex-row items-center justify-between px-4 pb-0 space-y-0">
          <CardDescription className="text-sm font-medium">Total de vagas</CardDescription>
          <Badge variant="outline" className="flex gap-1 rounded-lg text-[10px] px-1.5 font-mono">
            <BriefcaseBusiness className="size-3" />
            JOBS
          </Badge>
        </CardHeader>
        <CardContent className="px-4 pb-0">
          {loading ? (
            <Skeleton className="h-7 w-28" />
          ) : (
            <div className="text-[2rem] font-bold tracking-tight">{stats.totalJobs.toLocaleString("pt-BR")}</div>
          )}
          <p className="mt-2 text-xs leading-5 text-muted-foreground">Acervo local persistido no monólito.</p>
        </CardContent>
      </Card>

      <Card className="@container/card gap-4 py-4">
        <CardHeader className="flex flex-row items-center justify-between px-4 pb-0 space-y-0">
          <CardDescription className="text-sm font-medium">Extraídas hoje</CardDescription>
          <Badge variant="outline" className="flex gap-1 rounded-lg px-1.5 text-[10px] font-mono">
            <Download className="size-3" />
            24H
          </Badge>
        </CardHeader>
        <CardContent className="px-4 pb-0">
          {loading ? (
            <Skeleton className="h-7 w-28" />
          ) : (
            <div className="text-[2rem] font-bold tracking-tight">
              {stats.jobsExtractedToday.toLocaleString("pt-BR")}
            </div>
          )}
          <p className="mt-2 text-xs leading-5 text-muted-foreground">
            Volume agregado a partir do histórico de execução.
          </p>
        </CardContent>
      </Card>

      <Card className="@container/card gap-4 py-4">
        <CardHeader className="flex flex-row items-center justify-between px-4 pb-0 space-y-0">
          <CardDescription className="text-sm font-medium">Fontes ativas</CardDescription>
          <Badge variant="outline" className="flex gap-1 rounded-lg text-[10px] px-1.5 font-mono">
            <Database className="size-3" />
            {loading ? "..." : `${stats.activeSources}/${stats.totalSources}`}
          </Badge>
        </CardHeader>
        <CardContent className="px-4 pb-0">
          {loading ? (
            <Skeleton className="h-7 w-28" />
          ) : (
            <div className="text-[2rem] font-bold tracking-tight">{stats.activeSources.toLocaleString("pt-BR")}</div>
          )}
          <p className="mt-2 text-xs leading-5 text-muted-foreground">Rotinas habilitadas para scraping agendado.</p>
        </CardContent>
      </Card>

      <Card className="@container/card gap-4 py-4">
        <CardHeader className="flex flex-row items-center justify-between px-4 pb-0 space-y-0">
          <CardDescription className="text-sm font-medium">Saúde local</CardDescription>
          <div className="flex gap-1.5">
            <div
              className={`size-2 rounded-full ${health.backend === "online" ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]" : "bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.6)]"}`}
            />
            <div
              className={`size-2 rounded-full ${health.scraping === "online" ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]" : "bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.6)]"}`}
            />
          </div>
        </CardHeader>
        <CardContent className="px-4 pb-0">
          <div className="mt-1 flex flex-col gap-1.5">
            <StatusIndicator label="Backend" value={health.backend} />
            <StatusIndicator label="Scraping" value={health.scraping} />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
