"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowDown, ArrowUp, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { scrapingApi } from "@/lib/api";

interface SourceCategory {
  id: number;
  name: string;
  enabled: boolean;
}

interface SourceConfig {
  id: number;
  name: string;
  enabled: boolean;
  scraper_base_url: string;
  scraper_type: string;
  scraper_schedule: string;
  analysis: string;
  description: string;
  categories: SourceCategory[];
}

type SortColumn = "id" | "name" | "category" | "status" | "schedule";

export function SourcesPage() {
  const [sources, setSources] = useState<SourceConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [textFilter, setTextFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [sortBy, setSortBy] = useState<SortColumn>("name");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");

  useEffect(() => {
    const fetchSources = async () => {
      setLoading(true);
      try {
        const response = await scrapingApi.get("/api/v1/scrapers/config", {
          params: { enabled_only: false },
        });
        setSources(Array.isArray(response.data) ? response.data : []);
      } catch {
        toast.error("Erro ao carregar fontes");
      } finally {
        setLoading(false);
      }
    };

    void fetchSources();
  }, []);

  const normalizedFilter = textFilter.trim().toLowerCase();

  const filteredSources = useMemo(() => {
    return sources.filter((source) => {
      const primaryCategory = source.categories?.[0]?.name ?? "INDEFINIDA";
      const matchesText =
        !normalizedFilter ||
        source.name.toLowerCase().includes(normalizedFilter) ||
        primaryCategory.toLowerCase().includes(normalizedFilter) ||
        source.scraper_schedule.toLowerCase().includes(normalizedFilter);
      const matchesStatus =
        statusFilter === "all" ||
        (statusFilter === "enabled" && source.enabled) ||
        (statusFilter === "disabled" && !source.enabled);
      return matchesText && matchesStatus;
    });
  }, [normalizedFilter, sources, statusFilter]);

  const sortedSources = useMemo(() => {
    const list = [...filteredSources];
    const direction = sortDirection === "asc" ? 1 : -1;

    list.sort((left, right) => {
      if (sortBy === "id") {
        return (left.id - right.id) * direction;
      }
      if (sortBy === "category") {
        return ((left.categories?.[0]?.name ?? "INDEFINIDA").localeCompare(right.categories?.[0]?.name ?? "INDEFINIDA", "pt-BR")) * direction;
      }
      if (sortBy === "status") {
        return (String(left.enabled).localeCompare(String(right.enabled))) * direction;
      }
      if (sortBy === "schedule") {
        return left.scraper_schedule.localeCompare(right.scraper_schedule, "pt-BR") * direction;
      }
      return left.name.localeCompare(right.name, "pt-BR") * direction;
    });

    return list;
  }, [filteredSources, sortBy, sortDirection]);

  const toggleSort = (column: SortColumn) => {
    if (sortBy === column) {
      setSortDirection((current) => (current === "asc" ? "desc" : "asc"));
      return;
    }
    setSortBy(column);
    setSortDirection("asc");
  };

  const renderSortIcon = (column: SortColumn) => {
    if (sortBy !== column) return null;
    return sortDirection === "asc" ? <ArrowUp className="size-3.5" /> : <ArrowDown className="size-3.5" />;
  };

  const renderSortableHeader = (label: string, column: SortColumn, className?: string) => (
    <TableHead className={className}>
      <button
        type="button"
        onClick={() => toggleSort(column)}
        className="inline-flex items-center gap-1.5 font-medium text-left transition-colors hover:text-foreground"
      >
        <span>{label}</span>
        {renderSortIcon(column)}
      </button>
    </TableHead>
  );

  return (
    <div className="flex flex-1 flex-col gap-6 p-4 pt-6 lg:p-6 lg:pt-8 w-full">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Fontes</h1>
          <p className="text-sm text-muted-foreground">Catálogo local das fontes e suas categorias primárias.</p>
        </div>
        {loading ? <Loader2 className="size-4 animate-spin text-muted-foreground" /> : null}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="max-w-md flex-1 min-w-[260px]">
          <Input
            placeholder="Filtrar por nome, categoria ou cron..."
            value={textFilter}
            onChange={(event) => setTextFilter(event.target.value)}
          />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="h-10 w-[220px] shadow-xs">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todos os status</SelectItem>
            <SelectItem value="enabled">Ativas</SelectItem>
            <SelectItem value="disabled">Desativadas</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <Card className="shadow-xs bg-gradient-to-t from-primary/2 to-card dark:bg-card">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                {renderSortableHeader("ID", "id", "w-[80px]")}
                {renderSortableHeader("Nome", "name")}
                {renderSortableHeader("Categoria", "category", "w-[180px]")}
                {renderSortableHeader("Status", "status", "w-[140px]")}
                {renderSortableHeader("Cron", "schedule", "w-[170px]")}
                <TableHead>Base URL</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading
                ? [...Array(6)].map((_, index) => (
                    <TableRow key={index}>
                      {[...Array(6)].map((__, cellIndex) => (
                        <TableCell key={cellIndex}>
                          <Skeleton className="h-4 w-full" />
                        </TableCell>
                      ))}
                    </TableRow>
                  ))
                : sortedSources.map((source) => (
                    <TableRow key={source.id}>
                      <TableCell className="font-mono text-xs">{source.id}</TableCell>
                      <TableCell className="font-medium">{source.name.toUpperCase()}</TableCell>
                      <TableCell>
                        <Badge variant={source.categories?.[0] ? "outline" : "secondary"}>
                          {source.categories?.[0]?.name ?? "INDEFINIDA"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant={source.enabled ? "default" : "secondary"}>
                          {source.enabled ? "ATIVA" : "DESATIVADA"}
                        </Badge>
                      </TableCell>
                      <TableCell className="font-mono text-xs text-muted-foreground">{source.scraper_schedule}</TableCell>
                      <TableCell className="max-w-[320px] truncate text-sm text-muted-foreground">
                        {source.scraper_base_url || "—"}
                      </TableCell>
                    </TableRow>
                  ))}
              {!loading && sortedSources.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="h-24 text-center">
                    Nenhuma fonte encontrada.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
