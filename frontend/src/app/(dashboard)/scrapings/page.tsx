"use client";

import { useCallback, useEffect, useState } from "react";
import axios from "axios";
import {
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  FileText,
  Lock,
  LockOpen,
  Loader2,
  Pencil,
  Play,
  Plus,
  Power,
  Search,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { scrapingApi } from "@/lib/api";
import { formatDateTimeDDMMYYYYHHMM } from "@/lib/date";
import { DEFAULT_PAGE_SIZE, PAGE_SIZE_OPTIONS } from "@/lib/pagination";

interface SourceBase {
  id: number;
  name: string;
  enabled: boolean;
  scraper_base_url: string;
  scraper_type: string;
  scraper_schedule: string;
  analysis: string;
  description?: string;
  last_extraction_status: "SUCCESS" | "PARTIAL" | "ERROR" | null;
  last_extraction_http_status: number | null;
  last_extraction_message: string | null;
  last_extraction_at: string | null;
  next_scheduled_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

interface SourceCategory {
  id: number;
  name: string;
  enabled: boolean;
}

interface Source extends SourceBase {
  category_name: string | null;
}

interface SourceForm {
  name: string;
  enabled: boolean;
  scraper_base_url: string;
  scraper_type: string;
  scraper_schedule: string;
  analysis: string;
  category_name: string;
}

type RowAction = "run" | "toggle" | "delete";

interface ScraperRunQueuedResponse {
  job_id: string;
  status: "queued";
  queued_count: number;
  submitted_at: string;
  source_id?: number | null;
  source_name?: string | null;
}

const SCRAPER_TYPE_OPTIONS = [
  { value: "http_basic", label: "HTTP Basic" },
  { value: "http_antibot", label: "HTTP Anti-bot" },
  { value: "browser_playwright", label: "Browser (Playwright)" },
];

const DEFAULT_FORM: SourceForm = {
  name: "",
  enabled: true,
  scraper_base_url: "",
  scraper_type: "http_antibot",
  scraper_schedule: "0 */6 * * *",
  analysis: "",
  category_name: "",
};

function getApiErrorMessage(error: unknown, fallbackMessage: string): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
  }
  return fallbackMessage;
}

function getExtractionStatusLabel(status: SourceBase["last_extraction_status"]) {
  if (status === "SUCCESS") return "Extraído com dados";
  if (status === "PARTIAL") return "Extraído sem dados";
  if (status === "ERROR") return "Erro";
  return "Sem execução";
}

function getExtractionStatusVariant(status: SourceBase["last_extraction_status"]): "default" | "secondary" | "destructive" {
  if (status === "SUCCESS") return "default";
  if (status === "ERROR") return "destructive";
  return "secondary";
}

function formatDateTimeTooltip(dateString: string | null): string {
  if (!dateString) return "";
  return formatDateTimeDDMMYYYYHHMM(dateString);
}

function getScheduleCellLabel(source: Pick<SourceBase, "enabled" | "next_scheduled_at">): string {
  if (!source.enabled) {
    return "—";
  }
  return formatDateTimeTooltip(source.next_scheduled_at) || "—";
}

function getScheduleTooltip(source: Pick<SourceBase, "scraper_schedule">): string {
  const cron = source.scraper_schedule?.trim();
  return cron ? `Cron: ${cron}` : "Cron indisponível.";
}

function toExternalUrl(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) return "";
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  return `https://${trimmed}`;
}

export default function SourcesPage() {
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(DEFAULT_PAGE_SIZE);
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [searchFilter, setSearchFilter] = useState("");
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<SourceForm>(DEFAULT_FORM);
  const [rowLoading, setRowLoading] = useState<{ id: number; action: RowAction } | null>(null);
  const [categoryOptions, setCategoryOptions] = useState<string[]>([]);
  const [analysisDialogOpen, setAnalysisDialogOpen] = useState(false);
  const [analysisSourceId, setAnalysisSourceId] = useState<number | null>(null);
  const [analysisSourceName, setAnalysisSourceName] = useState("");
  const [analysisText, setAnalysisText] = useState("");
  const [isSavingAnalysis, setIsSavingAnalysis] = useState(false);
  const [isAnalysisEditable, setIsAnalysisEditable] = useState(false);
  const [isRunningAll, setIsRunningAll] = useState(false);
  const [isBulkDisablingCategory, setIsBulkDisablingCategory] = useState(false);

  const fetchPrimaryCategory = useCallback(async (sourceId: number): Promise<SourceCategory | null> => {
    try {
      const res = await scrapingApi.get(`/api/v1/sources/${sourceId}/categories`, {
        params: { enabled_only: false },
      });
      const categories = Array.isArray(res.data) ? (res.data as SourceCategory[]) : [];
      if (categories.length === 0) {
        return null;
      }
      return categories.sort((a, b) => a.id - b.id)[0];
    } catch {
      return null;
    }
  }, []);

  const fetchSources = useCallback(async () => {
    setLoading(true);
    try {
      const res = await scrapingApi.get("/api/v1/sources");
      const parsed = Array.isArray(res.data) ? (res.data as SourceBase[]) : [];
      const sourcesWithCategory: Source[] = await Promise.all(
        parsed.map(async (source) => {
          const category = await fetchPrimaryCategory(source.id);
          return {
            ...source,
            analysis: typeof source.analysis === "string" ? source.analysis : source.description ?? "",
            category_name: category?.name ?? null,
          };
        })
      );
      const sortedSources = sourcesWithCategory.sort((a, b) => b.id - a.id);
      setSources(sortedSources);
      setCategoryOptions(
        Array.from(
          new Set(
            sortedSources
              .map((source) => source.category_name?.trim())
              .filter((name): name is string => Boolean(name))
          )
        ).sort((a, b) => a.localeCompare(b, "pt-BR"))
      );
    } catch (error) {
      toast.error(getApiErrorMessage(error, "Erro ao carregar scrapings"));
      setCategoryOptions([]);
    } finally {
      setLoading(false);
    }
  }, [fetchPrimaryCategory]);

  useEffect(() => {
    fetchSources();
  }, [fetchSources]);

  useEffect(() => {
    setPage(1);
  }, [perPage, categoryFilter, statusFilter, searchFilter]);

  const normalizedSearchFilter = searchFilter.trim().toLowerCase();

  const categoryFilterOptions = Array.from(
    new Set(sources.map((source) => source.category_name?.trim()).filter((value): value is string => Boolean(value)))
  ).sort((a, b) => a.localeCompare(b, "pt-BR"));

  const filteredSources = sources.filter((source) => {
    const searchable = [
      source.name,
      source.category_name ?? "",
      source.scraper_type,
      source.scraper_base_url,
      source.scraper_schedule,
      source.analysis ?? source.description ?? "",
      source.enabled ? "ativo" : "inativo",
    ]
      .join(" ")
      .toLowerCase();
    const matchesSearch = !normalizedSearchFilter || searchable.includes(normalizedSearchFilter);
    const matchesCategory = categoryFilter === "all" || (source.category_name ?? "") === categoryFilter;
    const matchesStatus =
      statusFilter === "all" ||
      (statusFilter === "active" && source.enabled) ||
      (statusFilter === "inactive" && !source.enabled);
    return matchesSearch && matchesCategory && matchesStatus;
  });

  const totalPages = Math.max(1, Math.ceil(filteredSources.length / perPage));
  const currentPage = Math.min(page, totalPages);
  const paginatedSources = filteredSources.slice((currentPage - 1) * perPage, currentPage * perPage);

  useEffect(() => {
    setPage((prev) => Math.min(prev, totalPages));
  }, [totalPages]);

  const resetForm = () => {
    setForm(DEFAULT_FORM);
    setIsEditing(false);
    setEditingId(null);
  };

  const openCreateDialog = () => {
    resetForm();
    setIsDialogOpen(true);
  };

  const openEditDialog = (source: Source) => {
    setIsEditing(true);
    setEditingId(source.id);
    setForm({
      name: source.name,
      enabled: source.enabled,
      scraper_base_url: source.scraper_base_url ?? "",
      scraper_type: source.scraper_type || "http_antibot",
      scraper_schedule: source.scraper_schedule || "0 */6 * * *",
      analysis: source.analysis ?? source.description ?? "",
      category_name: source.category_name ?? "",
    });
    setIsDialogOpen(true);
  };

  const syncSourceCategory = async (sourceId: number, categoryName: string) => {
    const normalizedCategory = categoryName.trim();
    const res = await scrapingApi.get(`/api/v1/sources/${sourceId}/categories`, {
      params: { enabled_only: false },
    });
    const existing = Array.isArray(res.data) ? (res.data as SourceCategory[]).sort((a, b) => a.id - b.id) : [];
    const primary = existing[0];

    if (!normalizedCategory) {
      if (primary) {
        await scrapingApi.delete(`/api/v1/categories/${primary.id}`);
      }
      return;
    }

    if (primary) {
      await scrapingApi.put(`/api/v1/categories/${primary.id}`, {
        name: normalizedCategory,
        enabled: true,
      });
      return;
    }

    await scrapingApi.post(`/api/v1/sources/${sourceId}/categories`, {
      name: normalizedCategory,
      enabled: true,
    });
  };

  const handleSave = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const payload = {
      name: form.name.trim().toLowerCase(),
      enabled: form.enabled,
      scraper_base_url: form.scraper_base_url.trim(),
      scraper_type: form.scraper_type,
      scraper_schedule: form.scraper_schedule.trim(),
      analysis: form.analysis.trim(),
    };

    if (!payload.name) {
      toast.error("Informe o nome do scraping.");
      return;
    }

    if (!payload.scraper_schedule) {
      toast.error("Informe o agendamento (cron).");
      return;
    }

    setIsSaving(true);
    try {
      let sourceId = editingId;

      if (isEditing && editingId != null) {
        await scrapingApi.put(`/api/v1/sources/${editingId}`, payload);
        toast.success("Scraping atualizado com sucesso");
      } else {
        const created = await scrapingApi.post("/api/v1/sources", payload);
        sourceId = created.data?.id ?? null;
        toast.success("Scraping criado com sucesso");
      }

      if (sourceId != null) {
        try {
          await syncSourceCategory(sourceId, form.category_name);
        } catch (error) {
          toast.warning(getApiErrorMessage(error, "Scraping salvo, mas não foi possível atualizar a categoria"));
        }
      }

      setIsDialogOpen(false);
      resetForm();
      await fetchSources();
    } catch (error) {
      toast.error(getApiErrorMessage(error, "Erro ao salvar scraping"));
    } finally {
      setIsSaving(false);
    }
  };

  const runScraper = async (source: Source) => {
    setRowLoading({ id: source.id, action: "run" });
    try {
      const response = await scrapingApi.post<ScraperRunQueuedResponse>(`/api/v1/scrapers/${source.id}/run`);
      const jobId = response.data?.job_id;
      toast.success(
        jobId
          ? `Execução de ${source.name} enviada para segundo plano (job ${jobId.slice(0, 8)})`
          : `Execução de ${source.name} enviada para segundo plano`
      );
    } catch (error) {
      toast.error(getApiErrorMessage(error, "Erro ao iniciar execução manual"));
    } finally {
      setRowLoading(null);
    }
  };

  const runAllScrapers = async () => {
    setIsRunningAll(true);
    try {
      const response = await scrapingApi.post<ScraperRunQueuedResponse>("/api/v1/scrapers/run-all");
      const queuedCount = Number(response.data?.queued_count ?? 0);
      const jobId = response.data?.job_id;
      toast.success(
        jobId
          ? `${queuedCount} scraping(s) enviados para execução em segundo plano (job ${jobId.slice(0, 8)})`
          : `${queuedCount} scraping(s) enviados para execução em segundo plano`
      );
    } catch (error) {
      toast.error(getApiErrorMessage(error, "Erro ao executar todos os scrapings"));
    } finally {
      setIsRunningAll(false);
    }
  };

  const toggleSource = async (source: Source) => {
    setRowLoading({ id: source.id, action: "toggle" });
    try {
      await scrapingApi.patch(`/api/v1/sources/${source.id}/toggle`);
      setSources((prev) => prev.map((item) => (item.id === source.id ? { ...item, enabled: !item.enabled } : item)));
      toast.success(`Scraping ${source.enabled ? "desativado" : "ativado"} com sucesso`);
    } catch (error) {
      toast.error(getApiErrorMessage(error, "Erro ao alterar status do scraping"));
    } finally {
      setRowLoading(null);
    }
  };

  const disableCategorySources = async () => {
    if (categoryFilter === "all") {
      return;
    }

    const targets = sources.filter((source) => (source.category_name ?? "") === categoryFilter && source.enabled);

    if (targets.length === 0) {
      toast.info(`Nenhum scraping ativo encontrado em ${categoryFilter}`);
      return;
    }

    if (!confirm(`Deseja desativar ${targets.length} scraping(s) da categoria "${categoryFilter}"?`)) {
      return;
    }

    setIsBulkDisablingCategory(true);
    try {
      const results = await Promise.allSettled(
        targets.map((source) =>
          scrapingApi.put(`/api/v1/sources/${source.id}`, {
            name: source.name.trim().toLowerCase(),
            enabled: false,
            scraper_base_url: source.scraper_base_url?.trim() ?? "",
            scraper_type: source.scraper_type,
            scraper_schedule: source.scraper_schedule?.trim() ?? "",
            analysis: (source.analysis ?? source.description ?? "").trim(),
          })
        )
      );

      const disabledIds = new Set<number>();
      let failedCount = 0;

      results.forEach((result, index) => {
        if (result.status === "fulfilled") {
          disabledIds.add(targets[index].id);
          return;
        }
        failedCount += 1;
      });

      if (disabledIds.size > 0) {
        setSources((prev) => prev.map((item) => (disabledIds.has(item.id) ? { ...item, enabled: false } : item)));
      }

      if (failedCount === 0) {
        toast.success(`${disabledIds.size} scraping(s) da categoria ${categoryFilter} foram desativados`);
        return;
      }

      if (disabledIds.size === 0) {
        toast.error(`Não foi possível desativar os scrapings da categoria ${categoryFilter}`);
        return;
      }

      toast.warning(
        `${disabledIds.size} scraping(s) da categoria ${categoryFilter} foram desativados, mas ${failedCount} falharam`
      );
    } finally {
      setIsBulkDisablingCategory(false);
    }
  };

  const deleteSource = async (source: Source) => {
    if (!confirm(`Deseja excluir o scraping "${source.name}"?`)) {
      return;
    }

    setRowLoading({ id: source.id, action: "delete" });
    try {
      await scrapingApi.delete(`/api/v1/sources/${source.id}`);
      setSources((prev) => prev.filter((item) => item.id !== source.id));
      toast.success("Scraping removido com sucesso");
    } catch (error) {
      toast.error(getApiErrorMessage(error, "Erro ao remover scraping"));
    } finally {
      setRowLoading(null);
    }
  };

  const openAnalysisDialog = (source: Source) => {
    setAnalysisSourceId(source.id);
    setAnalysisSourceName(source.name);
    setAnalysisText(source.analysis ?? source.description ?? "");
    setIsAnalysisEditable(false);
    setAnalysisDialogOpen(true);
  };

  const saveAnalysis = async () => {
    if (analysisSourceId == null) {
      return;
    }
    setIsSavingAnalysis(true);
    try {
      const response = await scrapingApi.patch(`/api/v1/sources/${analysisSourceId}/analysis`, {
        analysis: analysisText,
      });
      const updatedAnalysis =
        typeof response.data?.analysis === "string"
          ? response.data.analysis
          : response.data?.description ?? analysisText;
      setSources((prev) =>
        prev.map((item) =>
          item.id === analysisSourceId
            ? {
                ...item,
                analysis: updatedAnalysis,
                description: updatedAnalysis,
                updated_at: response.data?.updated_at ?? item.updated_at,
              }
            : item
        )
      );
      toast.success("Última análise atualizada com sucesso");
      setAnalysisDialogOpen(false);
      setIsAnalysisEditable(false);
    } catch (error) {
      toast.error(getApiErrorMessage(error, "Erro ao salvar análise"));
    } finally {
      setIsSavingAnalysis(false);
    }
  };

  const isRowBusy = (sourceId: number) => rowLoading?.id === sourceId;
  const hasEnabledSources = sources.some((source) => source.enabled);
  const enabledSourcesInSelectedCategory =
    categoryFilter === "all"
      ? 0
      : sources.filter((source) => (source.category_name ?? "") === categoryFilter && source.enabled).length;
  const categorySuggestions = Array.from(
    new Set([...categoryOptions, ...(form.category_name ? [form.category_name] : [])])
  ).sort((a, b) => a.localeCompare(b, "pt-BR"));

  return (
    <div className="flex flex-1 flex-col gap-6 p-4 pt-6 lg:p-6 lg:pt-8 w-full">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Scrapings</h1>
          <p className="text-sm text-muted-foreground">Gerencie scrapings, execução manual e estratégia</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={runAllScrapers} disabled={isRunningAll || loading || !hasEnabledSources}>
            {isRunningAll ? <Loader2 className="mr-2 size-4 animate-spin" /> : <Play className="mr-2 size-4" />}
            Rodar Todos
          </Button>
          <Button
            variant="outline"
            onClick={disableCategorySources}
            disabled={loading || isBulkDisablingCategory || categoryFilter === "all" || enabledSourcesInSelectedCategory === 0}
          >
            {isBulkDisablingCategory ? <Loader2 className="mr-2 size-4 animate-spin" /> : <Power className="mr-2 size-4" />}
            Desativar Categoria
          </Button>
          <Button onClick={openCreateDialog}>
            <Plus className="mr-2 size-4" />
            Novo
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative w-full min-w-[260px] flex-1 sm:max-w-[360px]">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={searchFilter}
            onChange={(event) => setSearchFilter(event.target.value)}
            placeholder="Pesquisar scraping..."
            className="h-9 pl-9 shadow-xs"
          />
        </div>

        <div className="flex items-center gap-2">
          <Select value={categoryFilter} onValueChange={setCategoryFilter}>
            <SelectTrigger className="h-9 w-[220px] shadow-xs">
              <SelectValue placeholder="Categoria" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todas</SelectItem>
              {categoryFilterOptions.map((category) => (
                <SelectItem key={category} value={category}>
                  {category}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="flex items-center gap-2">
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="h-9 w-[170px] shadow-xs">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos</SelectItem>
              <SelectItem value="active">Ativos</SelectItem>
              <SelectItem value="inactive">Inativos</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <Card className="shadow-xs bg-gradient-to-t from-primary/2 to-card dark:bg-card">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[80px]">ID</TableHead>
                <TableHead>Nome</TableHead>
                <TableHead className="w-[160px]">Categoria</TableHead>
                <TableHead className="w-[160px]">Tipo</TableHead>
                <TableHead>Base URL</TableHead>
                <TableHead className="w-[160px]">Agendamento</TableHead>
                <TableHead className="w-[110px]">Status</TableHead>
                <TableHead className="w-[220px]">Última Extração</TableHead>
                <TableHead className="w-[120px]">Última Análise</TableHead>
                <TableHead className="w-[190px] text-right">Extraído em</TableHead>
                <TableHead className="w-[170px] text-right" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading
                ? [...Array(5)].map((_, i) => (
                    <TableRow key={i}>
                      {[...Array(11)].map((_, j) => (
                        <TableCell key={j}>
                          <Skeleton className="h-4 w-full" />
                        </TableCell>
                      ))}
                    </TableRow>
                  ))
                : paginatedSources.map((source) => (
                    <TableRow key={source.id}>
                      <TableCell className="font-mono text-xs">{source.id}</TableCell>
                      <TableCell className="font-medium">{source.name}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">{source.category_name || "—"}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">{source.scraper_type}</TableCell>
                      <TableCell className="max-w-[260px] truncate text-sm text-muted-foreground">
                        {source.scraper_base_url ? (
                          <a
                            href={toExternalUrl(source.scraper_base_url)}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="hover:text-foreground hover:underline"
                            title={source.scraper_base_url}
                          >
                            {source.scraper_base_url}
                          </a>
                        ) : (
                          "—"
                        )}
                      </TableCell>
                      <TableCell>
                        <TooltipProvider>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <span className="inline-flex cursor-default text-sm text-muted-foreground">
                                {getScheduleCellLabel(source)}
                              </span>
                            </TooltipTrigger>
                            <TooltipContent sideOffset={6}>
                              <span>{getScheduleTooltip(source)}</span>
                            </TooltipContent>
                          </Tooltip>
                        </TooltipProvider>
                      </TableCell>
                      <TableCell>
                        <Badge variant={source.enabled ? "default" : "secondary"}>
                          {source.enabled ? "Ativo" : "Inativo"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-col items-start gap-1">
                          {source.last_extraction_at || source.last_extraction_http_status ? (
                            <TooltipProvider>
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <span>
                                    <Badge variant={getExtractionStatusVariant(source.last_extraction_status)}>
                                      {getExtractionStatusLabel(source.last_extraction_status)}
                                    </Badge>
                                  </span>
                                </TooltipTrigger>
                                <TooltipContent sideOffset={6}>
                                  <div className="flex flex-col gap-1 whitespace-nowrap">
                                    <span>Última execução: {formatDateTimeTooltip(source.last_extraction_at) || "—"}</span>
                                    <span>Status HTTP: {source.last_extraction_http_status ?? "—"}</span>
                                  </div>
                                </TooltipContent>
                              </Tooltip>
                            </TooltipProvider>
                          ) : (
                            <Badge variant={getExtractionStatusVariant(source.last_extraction_status)}>
                              {getExtractionStatusLabel(source.last_extraction_status)}
                            </Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          className="size-8"
                          onClick={() => openAnalysisDialog(source)}
                          title="Abrir Última Análise"
                        >
                          <FileText className="size-4" />
                        </Button>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground text-right">
                        {formatDateTimeTooltip(source.last_extraction_at) || "—"}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            className="size-8"
                            onClick={() => openEditDialog(source)}
                            disabled={isRowBusy(source.id)}
                            title="Editar scraping"
                          >
                            <Pencil className="size-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            className="size-8"
                            onClick={() => runScraper(source)}
                            disabled={isRowBusy(source.id) || !source.enabled}
                            title={source.enabled ? "Executar manualmente" : "Ative o scraping para executar"}
                          >
                            {rowLoading?.id === source.id && rowLoading.action === "run" ? (
                              <Loader2 className="size-4 animate-spin" />
                            ) : (
                              <Play className="size-4" />
                            )}
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            className="size-8"
                            onClick={() => toggleSource(source)}
                            disabled={isRowBusy(source.id)}
                            title={source.enabled ? "Desativar scraping" : "Ativar scraping"}
                          >
                            {rowLoading?.id === source.id && rowLoading.action === "toggle" ? (
                              <Loader2 className="size-4 animate-spin" />
                            ) : (
                              <Power className="size-4" />
                            )}
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            className="size-8 text-destructive hover:text-destructive"
                            onClick={() => deleteSource(source)}
                            disabled={isRowBusy(source.id)}
                            title="Excluir scraping"
                          >
                            {rowLoading?.id === source.id && rowLoading.action === "delete" ? (
                              <Loader2 className="size-4 animate-spin" />
                            ) : (
                              <Trash2 className="size-4" />
                            )}
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
              {!loading && paginatedSources.length === 0 && (
                <TableRow>
                  <TableCell colSpan={11} className="h-24 text-center">
                    Nenhum scraping encontrado.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <p className="text-sm text-muted-foreground">
            Página {currentPage} de {totalPages}
          </p>
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">Itens por página</span>
            <Select value={String(perPage)} onValueChange={(value) => setPerPage(Number(value))}>
              <SelectTrigger className="h-8 w-[88px] shadow-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PAGE_SIZE_OPTIONS.map((size) => (
                  <SelectItem key={size} value={String(size)}>
                    {size}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <Button variant="outline" size="icon" className="size-8" disabled={currentPage <= 1} onClick={() => setPage(1)}>
            <ChevronsLeft className="size-4" />
          </Button>
          <Button
            variant="outline"
            size="icon"
            className="size-8"
            disabled={currentPage <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            <ChevronLeft className="size-4" />
          </Button>
          <Button
            variant="outline"
            size="icon"
            className="size-8"
            disabled={currentPage >= totalPages}
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
          >
            <ChevronRight className="size-4" />
          </Button>
          <Button
            variant="outline"
            size="icon"
            className="size-8"
            disabled={currentPage >= totalPages}
            onClick={() => setPage(totalPages)}
          >
            <ChevronsRight className="size-4" />
          </Button>
        </div>
      </div>

      <Dialog
        open={isDialogOpen}
        onOpenChange={(open) => {
          if (isSaving) return;
          setIsDialogOpen(open);
          if (!open) resetForm();
        }}
      >
        <DialogContent className="sm:max-w-[640px]">
          <DialogHeader>
            <DialogTitle>{isEditing ? "Editar scraping" : "Novo scraping"}</DialogTitle>
            <DialogDescription>
              Configure nome, categoria, última análise, estratégia de execução, URL base e agendamento cron.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleSave} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2 sm:col-span-2">
                <Label htmlFor="source-name">Nome do scraper</Label>
                <Input
                  id="source-name"
                  value={form.name}
                  onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
                  placeholder="ex: olx_vehicles"
                  required
                  disabled={isSaving}
                />
                <p className="text-xs text-muted-foreground">
                  Use o nome registrado no scraper loader (normalizado em lowercase).
                </p>
              </div>

              <div className="space-y-2 sm:col-span-2">
                <Label htmlFor="source-analysis">Última Análise</Label>
                <textarea
                  id="source-analysis"
                  value={form.analysis}
                  onChange={(event) => setForm((prev) => ({ ...prev, analysis: event.target.value }))}
                  placeholder="Resumo do estado recente desse scraping"
                  disabled={isSaving}
                  rows={3}
                  className="flex min-h-[84px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="source-category">Categoria</Label>
                <Input
                  id="source-category"
                  list="source-category-options"
                  value={form.category_name}
                  onChange={(event) => setForm((prev) => ({ ...prev, category_name: event.target.value }))}
                  placeholder="Ex: VEICULOS"
                  disabled={isSaving}
                />
                <datalist id="source-category-options">
                  {categorySuggestions.map((option) => (
                    <option key={option} value={option} />
                  ))}
                </datalist>
              </div>

              <div className="space-y-2">
                <Label htmlFor="source-type">Tipo de execução</Label>
                <Select
                  value={form.scraper_type}
                  onValueChange={(value) => setForm((prev) => ({ ...prev, scraper_type: value }))}
                  disabled={isSaving}
                >
                  <SelectTrigger id="source-type" className="w-full shadow-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {SCRAPER_TYPE_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="source-schedule">Agendamento (cron)</Label>
                <Input
                  id="source-schedule"
                  value={form.scraper_schedule}
                  onChange={(event) => setForm((prev) => ({ ...prev, scraper_schedule: event.target.value }))}
                  placeholder="0 */6 * * *"
                  required
                  disabled={isSaving}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="source-base-url">Base URL (opcional)</Label>
                <Input
                  id="source-base-url"
                  value={form.scraper_base_url}
                  onChange={(event) => setForm((prev) => ({ ...prev, scraper_base_url: event.target.value }))}
                  placeholder="https://site.com"
                  disabled={isSaving}
                />
              </div>
            </div>

            <div className="flex items-center gap-2 rounded-md border p-3">
              <Checkbox
                id="source-enabled"
                checked={form.enabled}
                onCheckedChange={(checked) => setForm((prev) => ({ ...prev, enabled: checked === true }))}
                disabled={isSaving}
              />
              <Label htmlFor="source-enabled" className="cursor-pointer text-sm">
                Scraping ativo no scheduler
              </Label>
            </div>

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setIsDialogOpen(false);
                  resetForm();
                }}
                disabled={isSaving}
              >
                Cancelar
              </Button>
              <Button type="submit" disabled={isSaving}>
                {isSaving ? <Loader2 className="mr-2 size-4 animate-spin" /> : null}
                {isEditing ? "Salvar alterações" : "Criar scraping"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog
        open={analysisDialogOpen}
        onOpenChange={(open) => {
          if (isSavingAnalysis) return;
          setAnalysisDialogOpen(open);
          if (!open) {
            setIsAnalysisEditable(false);
          }
        }}
      >
        <DialogContent className="sm:max-w-[700px] max-h-[85vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle>Última Análise</DialogTitle>
            <DialogDescription>
              {analysisSourceName ? `Análise do scraping ${analysisSourceName}.` : "Análise do scraping selecionado."}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2 min-h-0 flex-1">
            <div className="flex items-center justify-between">
              <Label htmlFor="analysis-content">Texto da análise</Label>
              <Button
                type="button"
                variant="outline"
                size="icon-sm"
                className="size-8"
                onClick={() => setIsAnalysisEditable((prev) => !prev)}
                disabled={isSavingAnalysis}
                title={isAnalysisEditable ? "Bloquear edição" : "Desbloquear para editar"}
              >
                {isAnalysisEditable ? <LockOpen className="size-4" /> : <Lock className="size-4" />}
              </Button>
            </div>
            <textarea
              id="analysis-content"
              value={analysisText}
              onChange={(event) => setAnalysisText(event.target.value)}
              readOnly={!isAnalysisEditable}
              className="h-[52vh] max-h-[52vh] w-full resize-none overflow-y-auto rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 read-only:cursor-default read-only:opacity-100 disabled:cursor-not-allowed disabled:opacity-50"
              disabled={isSavingAnalysis}
              placeholder="Sem análise registrada."
            />
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setAnalysisDialogOpen(false)} disabled={isSavingAnalysis}>
              Fechar
            </Button>
            <Button
              type="button"
              onClick={saveAnalysis}
              disabled={isSavingAnalysis || analysisSourceId == null || !isAnalysisEditable}
            >
              {isSavingAnalysis ? <Loader2 className="mr-2 size-4 animate-spin" /> : null}
              Salvar análise
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
