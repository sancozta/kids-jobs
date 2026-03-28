"use client";

import axios from "axios";
import { useEffect, useState, useCallback, useMemo, useRef } from "react";
import {
  Search,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  MapPin,
  Image as ImageIcon,
  Video,
  Link2,
  FileText,
  Code2,
  Copy,
  Loader2,
  Trash2,
  X,
  RefreshCw,
} from "lucide-react";

import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogClose, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { api, scrapingApi } from "@/lib/api";
import { DEFAULT_PAGE_SIZE, PAGE_SIZE_OPTIONS } from "@/lib/pagination";
import { formatPhoneBR, formatZipCode } from "@/lib/mask";
import { formatDateTimeDDMMYYYYHHMM } from "@/lib/date";
import type { MouseEvent, ReactNode, SyntheticEvent, WheelEvent } from "react";

const MARKET_PLACEHOLDER_IMAGE = "/market-placeholder.svg";
const BRAZILIAN_STATES = [
  "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
  "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
  "SP", "SE", "TO",
];
const CONTRACT_TYPE_FILTER_OPTIONS = [
  { value: "all", label: "Todas" },
  { value: "pj", label: "PJ" },
  { value: "clt", label: "CLT" },
] as const;
const SENIORITY_FILTER_OPTIONS = [
  { value: "all", label: "Todos" },
  { value: "junior", label: "Junior" },
  { value: "pleno", label: "Pleno" },
  { value: "senior", label: "Senior" },
] as const;
const CONTACT_FILTER_OPTIONS = [
  { value: "all", label: "Todas" },
  { value: "with_contact", label: "Com Contato" },
] as const;
const SALARY_RANGE_FILTER_OPTIONS = [
  { value: "all", label: "Todos" },
  { value: "with_salary_range", label: "Definido" },
] as const;
const CURRENCY_FILTER_OPTIONS = [
  { value: "all", label: "Todas" },
  { value: "brl", label: "BRL" },
  { value: "usd", label: "USD" },
  { value: "other", label: "Outra" },
] as const;
const CREATED_AT_SORT_OPTIONS = [
  { value: "created_desc", label: "Mais Recentes" },
  { value: "created_asc", label: "Mais Antigas" },
] as const;

interface MarketItem {
  id: number;
  source_id: number | null;
  title: string;
  description: string;
  price: number | null;
  currency: string;
  state: string | null;
  city: string | null;
  zip_code: string | null;
  street: string | null;
  contact_name: string | null;
  contact_phone: string | null;
  contact_email: string | null;
  url: string | null;
  location?: Record<string, unknown> | null;
  images: string[];
  videos?: string[];
  documents?: string[];
  links?: string[];
  attributes?: Record<string, unknown> | null;
  version: number | null;
  created_at: string | null;
  updated_at: string | null;
}

interface SourceOption {
  id: number;
  name: string;
}

interface ScraperConfigSource {
  id: number;
  name: string;
}

interface RescrapeJobCreateResponse {
  queued_count: number;
  deduplicated_count: number;
}

interface MarketBulkDeleteResponse {
  job_id: string;
  status: "queued";
  queued_count: number;
  submitted_at: string;
}

function buildHighlightedJson(value: unknown): string {
  const safeJson = JSON.stringify(value ?? {}, null, 2)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  return safeJson.replace(
    /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(\.\d+)?([eE][+\-]?\d+)?)/g,
    (match) => {
      let className = "text-foreground";

      if (match.startsWith('"')) {
        className = match.endsWith(":") ? "text-cyan-300" : "text-emerald-300";
      } else if (match === "true" || match === "false") {
        className = "text-fuchsia-300";
      } else if (match === "null") {
        className = "text-zinc-500";
      } else {
        className = "text-amber-300";
      }

      return `<span class="${className}">${match}</span>`;
    }
  );
}

function toLabel(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatDescriptionText(value: string | null | undefined): string {
  if (!value) return "—";

  const plainText = value
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .replace(/\t+/g, "\n")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/(p|div|section|article|header|footer|h[1-6]|ul|ol|table|tr)>/gi, "\n")
    .replace(/<(p|div|section|article|header|footer|h[1-6])[^>]*>/gi, "\n")
    .replace(/<li[^>]*>/gi, "\n• ")
    .replace(/<\/li>/gi, "")
    .replace(/<td[^>]*>/gi, " ")
    .replace(/<\/td>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/gi, " ")
    .replace(/\u00a0/g, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/\?/g, "")
    .replace(/[\u00a0\u1680\u2000-\u200f\u2028\u2029\u202f\u205f\u3000]/g, " ")
    .replace(/[ \t]*\n[ \t]*/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .replace(/[ \t]{2,}/g, " ")
    .trim();

  const paragraphs = plainText
    .split(/\n+/)
    .flatMap((block) =>
      block
        .split(/(?<=[.!?])\s+(?=(?:[A-ZÀ-Ý0-9•\-]))/g)
        .map((part) => part.trim())
        .filter(Boolean),
    );

  return paragraphs.length > 0 ? paragraphs.join("\n\n") : "—";
}

function formatStructuredValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed ? trimmed : "—";
  }
  if (typeof value === "boolean") return value ? "Sim" : "Não";
  if (typeof value === "number") return Number.isFinite(value) ? String(value) : "—";
  if (Array.isArray(value)) return value.length > 0 ? value.map((entry) => String(entry)).join(", ") : "—";
  if (typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch {
      return "—";
    }
  }
  return String(value);
}

function formatUppercaseDisplayValue(value: unknown): string {
  return formatStructuredValue(value).toLocaleUpperCase("pt-BR");
}

function getPrimaryExternalUrl(item: Pick<MarketItem, "url" | "attributes"> | null | undefined): string | null {
  const telegramPublicUrl = item?.attributes?.telegram_public_url;
  if (typeof telegramPublicUrl === "string" && telegramPublicUrl.trim()) {
    return telegramPublicUrl.trim();
  }

  if (typeof item?.url === "string" && item.url.trim()) {
    return item.url.trim();
  }

  return null;
}

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  const isLink = typeof value === "string" && (value.toLowerCase().includes("http://") || value.toLowerCase().includes("https://"));
  const content = isLink ? (
    <a
      href={value as string}
      target="_blank"
      rel="noopener noreferrer"
      className="text-primary hover:underline break-all"
    >
      {value as string}
    </a>
  ) : (
    value
  );

  return (
    <div className="grid grid-cols-[116px_1fr] items-start gap-2 text-[11px] leading-4.5">
      <span className="whitespace-nowrap text-muted-foreground">{label}</span>
      <div className="min-w-0 break-words">{content}</div>
    </div>
  );
}

export default function VagasPage() {
  const [items, setItems] = useState<MarketItem[]>([]);
  const [filteredTotal, setFilteredTotal] = useState(0);
  const [sources, setSources] = useState<SourceOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedSource, setSelectedSource] = useState("all");
  const [selectedState, setSelectedState] = useState("all");
  const [selectedContractType, setSelectedContractType] = useState("all");
  const [selectedSeniority, setSelectedSeniority] = useState("all");
  const [selectedContactFilter, setSelectedContactFilter] = useState("all");
  const [selectedSalaryRangeFilter, setSelectedSalaryRangeFilter] = useState("all");
  const [selectedCurrencyFilter, setSelectedCurrencyFilter] = useState("all");
  const [selectedCreatedAtSort, setSelectedCreatedAtSort] = useState<(typeof CREATED_AT_SORT_OPTIONS)[number]["value"]>("created_desc");
  const [priceMinValue, setPriceMinValue] = useState("");
  const [priceMaxValue, setPriceMaxValue] = useState("");
  const [offset, setOffset] = useState(0);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [selectedItem, setSelectedItem] = useState<MarketItem | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isImageViewerOpen, setIsImageViewerOpen] = useState(false);
  const [activeImageIndex, setActiveImageIndex] = useState(0);
  const [jsonPreviewItem, setJsonPreviewItem] = useState<MarketItem | null>(null);
  const [isJsonDialogOpen, setIsJsonDialogOpen] = useState(false);
  const [deletingItemId, setDeletingItemId] = useState<number | null>(null);
  const [isBulkDeleting, setIsBulkDeleting] = useState(false);
  const [selectedItemIds, setSelectedItemIds] = useState<number[]>([]);
  const [isRescrapeSubmitting, setIsRescrapeSubmitting] = useState(false);
  const [reprocessingItemIds, setReprocessingItemIds] = useState<number[]>([]);
  const detailImagesScrollRef = useRef<HTMLDivElement | null>(null);
  const highlightedJsonPreview = useMemo(
    () => buildHighlightedJson(jsonPreviewItem ?? {}),
    [jsonPreviewItem]
  );
  const selectedItemImages = useMemo(
    () =>
      Array.isArray(selectedItem?.images)
        ? selectedItem.images.filter((image): image is string => typeof image === "string" && image.trim().length > 0)
        : [],
    [selectedItem]
  );

  const fetchFilterOptions = useCallback(async () => {
    try {
      const response = await scrapingApi.get("/api/v1/scrapers/config", {
        params: { enabled_only: false },
      });
      const sourcesData = Array.isArray(response.data) ? (response.data as ScraperConfigSource[]) : [];
      setSources(
        sourcesData
          .map((source) => ({
            id: source.id,
            name: source.name,
          }))
          .sort((a, b) => a.name.localeCompare(b.name, "pt-BR")),
      );
    } catch {
      toast.error("Erro ao carregar filtros de fonte");
    }
  }, []);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    try {
      const trimmedQuery = searchQuery.trim();
      const parsePriceValue = (value: string): number | null => {
        const normalized = value
          .trim()
          .replace(/\./g, "")
          .replace(",", ".")
          .replace(/[^\d.-]/g, "");
        if (!normalized) return null;
        const numericValue = Number(normalized);
        if (!Number.isFinite(numericValue)) return null;
        return numericValue;
      };

      const filters: Record<string, string | number | boolean> = {};
      filters.order_by = "created_at";
      filters.order_direction = selectedCreatedAtSort === "created_asc" ? "asc" : "desc";
      if (trimmedQuery.length >= 2) {
        filters.q = trimmedQuery;
      }
      if (selectedSource !== "all") {
        filters.source = selectedSource;
      }
      if (selectedState !== "all") {
        filters.state = selectedState;
      }
      if (selectedContractType !== "all") {
        filters.contract_type = selectedContractType;
      }
      if (selectedSeniority !== "all") {
        filters.seniority = selectedSeniority;
      }
      if (selectedContactFilter === "with_contact") {
        filters.has_contact = true;
      }
      if (selectedSalaryRangeFilter === "with_salary_range") {
        filters.has_salary_range = true;
      }
      if (selectedCurrencyFilter !== "all") {
        filters.currency = selectedCurrencyFilter;
      }

      const minPrice = parsePriceValue(priceMinValue);
      const maxPrice = parsePriceValue(priceMaxValue);
      if (minPrice != null && maxPrice != null) {
        filters.min_price = Math.min(minPrice, maxPrice);
        filters.max_price = Math.max(minPrice, maxPrice);
      } else if (minPrice != null) {
        filters.min_price = minPrice;
      } else if (maxPrice != null) {
        filters.max_price = maxPrice;
      }

      const [listResult, countResult] = await Promise.allSettled([
        api.get("/market/", {
          params: {
            ...filters,
            limit: pageSize,
            offset,
          },
        }),
        api.get("/market/count", { params: filters }),
      ]);

      if (listResult.status !== "fulfilled") {
        throw new Error("Failed to load market list");
      }

      const pageItems = Array.isArray(listResult.value.data) ? listResult.value.data : [];
      setItems(pageItems);
      setFilteredTotal(
        countResult.status === "fulfilled" && typeof countResult.value.data?.total === "number"
          ? countResult.value.data.total
          : pageItems.length
      );
    } catch {
      setItems([]);
      setFilteredTotal(0);
      toast.error("Erro ao carregar vagas");
    } finally {
      setLoading(false);
    }
  }, [searchQuery, selectedSource, selectedState, selectedContractType, selectedSeniority, selectedContactFilter, selectedSalaryRangeFilter, selectedCurrencyFilter, selectedCreatedAtSort, priceMinValue, priceMaxValue, offset, pageSize]);

  useEffect(() => {
    fetchFilterOptions();
  }, [fetchFilterOptions]);

  useEffect(() => {
    const timer = setTimeout(() => fetchItems(), 300);
    return () => clearTimeout(timer);
  }, [fetchItems]);

  useEffect(() => {
    if (selectedSource === "all") return;
    const sourceStillAvailable = sources.some((source) => source.name === selectedSource);
    if (!sourceStillAvailable) {
      setSelectedSource("all");
    }
  }, [sources, selectedSource]);

  useEffect(() => {
    setOffset(0);
  }, [searchQuery, selectedSource, selectedState, selectedContractType, selectedSeniority, selectedContactFilter, selectedSalaryRangeFilter, selectedCurrencyFilter, selectedCreatedAtSort, priceMinValue, priceMaxValue, pageSize]);

  const currentPage = Math.floor(offset / pageSize) + 1;
  const canGoPrev = offset > 0;
  const canGoNext = items.length === pageSize;
  const selectedOnPageCount = items.filter((item) => selectedItemIds.includes(item.id)).length;
  const allItemsOnPageSelected = items.length > 0 && selectedOnPageCount === items.length;
  const filterLabelClassName = "text-[10px] font-semibold text-muted-foreground";

  const formatPrice = (price: number | null) => {
    if (price == null) return "—";
    return new Intl.NumberFormat("pt-BR", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(price);
  };

  const formatCardPrice = (price: number | null) => {
    if (price == null) return "NÃO INFORMADO";
    return formatPrice(price);
  };

  const getSourceLabel = (item: MarketItem): string => {
    if (item.source_id == null) {
      return "SEM ORIGEM";
    }
    const source = sources.find((entry) => entry.id === item.source_id);
    return source?.name || `ORIGEM ${item.source_id}`;
  };

  const getSourceName = (item: MarketItem): string | null => {
    if (item.source_id == null) {
      return null;
    }
    return sources.find((entry) => entry.id === item.source_id)?.name ?? null;
  };

  const getVersionLabel = (item: MarketItem): string => {
    const version = item.version ?? 1;
    return `V${version}`;
  };


  const getUpdatedAtLabel = (item: MarketItem): string => {
    return formatDateTimeDDMMYYYYHHMM(item.updated_at);
  };

  const getGoogleMapsLink = (item: MarketItem): string | null => {
    const location = item.location;
    if (!location || typeof location !== "object") return null;

    const latitude = typeof location.latitude === "number" ? location.latitude : null;
    const longitude = typeof location.longitude === "number" ? location.longitude : null;
    if (latitude != null && longitude != null) {
      return `https://www.google.com/maps?q=${latitude},${longitude}`;
    }

    const textualLocation = [item.street, item.city, item.state, item.zip_code].filter(Boolean).join(", ");
    if (textualLocation) {
      return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(textualLocation)}`;
    }

    return null;
  };

  const scrollDetailImages = (direction: "left" | "right") => {
    const container = detailImagesScrollRef.current;
    if (!container) return;
    const delta = Math.max(container.clientWidth * 0.7, 240);
    container.scrollBy({
      left: direction === "left" ? -delta : delta,
      behavior: "smooth",
    });
  };

  const handleDetailImagesWheel = (event: WheelEvent<HTMLDivElement>) => {
    const container = detailImagesScrollRef.current;
    if (!container) return;
    if (Math.abs(event.deltaY) <= Math.abs(event.deltaX)) return;
    event.preventDefault();
    container.scrollBy({
      left: event.deltaY,
      behavior: "auto",
    });
  };

  const handleImageError = (event: SyntheticEvent<HTMLImageElement>) => {
    if (event.currentTarget.src.includes("market-placeholder.svg")) {
      return;
    }
    event.currentTarget.src = MARKET_PLACEHOLDER_IMAGE;
  };

  const openImageViewer = (index: number) => {
    if (selectedItemImages.length === 0) return;
    setActiveImageIndex(index);
    setIsImageViewerOpen(true);
  };

  const navigateImageViewer = useCallback(
    (direction: "prev" | "next") => {
      if (selectedItemImages.length === 0) return;
      setActiveImageIndex((current) => {
        if (direction === "prev") {
          return current === 0 ? 0 : current - 1;
        }
        return current === selectedItemImages.length - 1 ? current : current + 1;
      });
    },
    [selectedItemImages.length]
  );

  const mediaIndicators = (item: MarketItem) => {
    const imageCount = item.images?.length ?? 0;
    const videoCount = item.videos?.length ?? 0;
    const documentCount = item.documents?.length ?? 0;
    const linkCount = item.links?.length ?? 0;
    if (imageCount + videoCount + documentCount + linkCount === 0) {
      return null;
    }

    return (
      <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
        {imageCount > 0 ? (
          <span className="inline-flex items-center gap-1" title={`${imageCount} imagem(ns)`}>
            <ImageIcon className="size-3.5" />
            {imageCount}
          </span>
        ) : null}
        {videoCount > 0 ? (
          <span className="inline-flex items-center gap-1" title={`${videoCount} vídeo(s)`}>
            <Video className="size-3.5" />
            {videoCount}
          </span>
        ) : null}
        {documentCount > 0 ? (
          <span className="inline-flex items-center gap-1" title={`${documentCount} documento(s)`}>
            <FileText className="size-3.5" />
            {documentCount}
          </span>
        ) : null}
        {linkCount > 0 ? (
          <span className="inline-flex items-center gap-1" title={`${linkCount} link(s)`}>
            <Link2 className="size-3.5" />
            {linkCount}
          </span>
        ) : null}
      </div>
    );
  };

  const handleCardClick = (event: MouseEvent<HTMLElement>, item: MarketItem) => {
    const externalUrl = getPrimaryExternalUrl(item);
    if ((event.metaKey || event.ctrlKey) && externalUrl) {
      window.open(externalUrl, "_blank", "noopener,noreferrer");
      return;
    }
    setSelectedItem(item);
  };

  useEffect(() => {
    if (!isDialogOpen) {
      setIsImageViewerOpen(false);
      setActiveImageIndex(0);
    }
  }, [isDialogOpen]);

  useEffect(() => {
    if (!isImageViewerOpen || selectedItemImages.length <= 1) return;

    const handleKeyNavigation = (event: KeyboardEvent) => {
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        navigateImageViewer("prev");
      }

      if (event.key === "ArrowRight") {
        event.preventDefault();
        navigateImageViewer("next");
      }
    };

    window.addEventListener("keydown", handleKeyNavigation);
    return () => {
      window.removeEventListener("keydown", handleKeyNavigation);
    };
  }, [isImageViewerOpen, navigateImageViewer, selectedItemImages.length]);

  const handleJsonTagClick = (event: MouseEvent<HTMLElement>, item: MarketItem) => {
    event.stopPropagation();
    setJsonPreviewItem(item);
    setIsJsonDialogOpen(true);
  };

  const handleCopyJsonPreview = async () => {
    try {
      const payload = jsonPreviewItem ? JSON.stringify(jsonPreviewItem, null, 2) : "{}";
      await navigator.clipboard.writeText(payload);
      toast.success("JSON copiado para a área de transferência");
    } catch {
      toast.error("Não foi possível copiar o JSON");
    }
  };

  const handleDeleteItem = async (event: MouseEvent<HTMLElement>, item: MarketItem) => {
    event.stopPropagation();
    if (deletingItemId != null || isBulkDeleting) return;

    const confirmed = window.confirm(`Deseja remover o item "${item.title}"?`);
    if (!confirmed) return;

    setDeletingItemId(item.id);
    try {
      await api.delete(`/market/${item.id}`);
      toast.success("Item removido com sucesso");
      setSelectedItemIds((current) => current.filter((id) => id !== item.id));

      if (selectedItem?.id === item.id) {
        setIsDialogOpen(false);
        setSelectedItem(null);
      }

      if (items.length === 1 && offset > 0) {
        setOffset((prev) => Math.max(0, prev - pageSize));
      } else {
        fetchItems();
      }
    } catch {
      toast.error("Erro ao remover vaga");
    } finally {
      setDeletingItemId(null);
    }
  };

  const handleDeleteSelectedItems = async () => {
    if (selectedItemIds.length === 0 || isBulkDeleting || isRescrapeSubmitting) {
      return;
    }

    const confirmed = window.confirm(`Deseja remover ${selectedItemIds.length} item(ns) selecionado(s)?`);
    if (!confirmed) return;

    const idsToDelete = [...selectedItemIds];
    const deletedIdsSet = new Set(idsToDelete);

    setIsBulkDeleting(true);
    try {
      const response = await api.post<MarketBulkDeleteResponse>("/market/delete-batch", {
        item_ids: idsToDelete,
      });
      const queuedCount = Number(response.data?.queued_count ?? idsToDelete.length);
      const jobId = response.data?.job_id;

      toast.success(
        jobId
          ? `${queuedCount} item(ns) removido(s) com sucesso (job ${jobId.slice(0, 8)})`
          : `${queuedCount} item(ns) removido(s) com sucesso`
      );
      setSelectedItemIds([]);

      if (selectedItem && deletedIdsSet.has(selectedItem.id)) {
        setIsDialogOpen(false);
        setSelectedItem(null);
      }

      void fetchItems();
    } catch (error) {
      const detail = axios.isAxiosError(error) ? error.response?.data?.detail : null;
      toast.error(typeof detail === "string" ? detail : "Erro ao excluir itens em lote");
    } finally {
      setIsBulkDeleting(false);
    }
  };

  const setItemSelection = (itemId: number, isSelected: boolean) => {
    setSelectedItemIds((current) => {
      if (isSelected) {
        return current.includes(itemId) ? current : [...current, itemId];
      }
      return current.filter((id) => id !== itemId);
    });
  };

  const toggleSelectCurrentPage = () => {
    const pageIds = items.map((item) => item.id);
    if (pageIds.length === 0) return;

    setSelectedItemIds((current) => {
      if (allItemsOnPageSelected) {
        return [];
      }
      return Array.from(new Set([...current, ...pageIds]));
    });
  };

  const enqueueRescrapeForItems = async (marketItems: MarketItem[]) => {
    if (marketItems.length === 0 || isRescrapeSubmitting) {
      return;
    }

    const payloadItems = marketItems
      .map((item) => {
        const sourceName = getSourceName(item);
        if (!item.url || !sourceName) {
          return null;
        }
        return {
          market_item_id: item.id,
          source_name: sourceName,
          url: item.url,
        };
      })
      .filter((item): item is { market_item_id: number; source_name: string; url: string } => item !== null);

    if (payloadItems.length === 0) {
      toast.error("Os itens selecionados não têm URL ou origem válida para reprocessamento");
      return;
    }

    const skippedCount = marketItems.length - payloadItems.length;
    const targetIds = payloadItems.map((item) => item.market_item_id);

    setIsRescrapeSubmitting(true);
    setReprocessingItemIds(targetIds);
    try {
      const response = await scrapingApi.post<RescrapeJobCreateResponse>("/api/v1/rescrape-jobs", {
        items: payloadItems,
      });

      const queuedCount = Number(response.data?.queued_count ?? 0);
      const deduplicatedCount = Number(response.data?.deduplicated_count ?? 0);
      const summary = [
        queuedCount > 0 ? `${queuedCount} item(ns) enfileirado(s)` : null,
        deduplicatedCount > 0 ? `${deduplicatedCount} já estavam na fila` : null,
        skippedCount > 0 ? `${skippedCount} ignorado(s) por falta de URL/origem` : null,
      ]
        .filter(Boolean)
        .join(" • ");

      toast.success(summary || "Reprocessamento enviado para a fila");
    } catch (error) {
      const detail = axios.isAxiosError(error) ? error.response?.data?.detail : null;
      toast.error(typeof detail === "string" ? detail : "Erro ao enviar itens para a fila de reprocessamento");
    } finally {
      setIsRescrapeSubmitting(false);
      setReprocessingItemIds([]);
    }
  };

  const handleRescrapeSelectedItems = async () => {
    if (selectedItemIds.length === 0 || isRescrapeSubmitting) {
      return;
    }

    const confirmed = window.confirm(
      `Enviar ${selectedItemIds.length} item(ns) selecionado(s) para a fila de reprocessamento?`
    );
    if (!confirmed) return;

    try {
      const response = await api.post<MarketItem[]>("/market/lookup", {
        item_ids: selectedItemIds,
      });
      const selectedItems = response.data ?? [];
      if (selectedItems.length === 0) {
        toast.error("Nenhum item selecionado pôde ser carregado para reprocessamento");
        return;
      }
      await enqueueRescrapeForItems(selectedItems);
    } catch {
      toast.error("Erro ao carregar os itens selecionados para reprocessamento");
    }
  };

  const handleRescrapeItem = async (event: MouseEvent<HTMLElement>, item: MarketItem) => {
    event.stopPropagation();
    await enqueueRescrapeForItems([item]);
  };

  return (
    <div className="flex w-full min-w-0 flex-1 flex-col gap-6 p-4 pt-6 lg:h-[calc(100svh-98px)] lg:min-h-0 lg:max-h-[calc(100svh-98px)] lg:flex-row lg:overflow-hidden lg:px-6 lg:pt-[17px] lg:pb-0">
      {/* Sidebar - Filtros */}
      <aside className="flex w-full shrink-0 flex-col gap-4 lg:h-full lg:min-h-0 lg:w-[280px] lg:self-stretch lg:overflow-y-auto lg:pr-1 xl:w-[320px] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        <Card className="py-0">
          <CardContent className="px-5 pb-5 pt-4 flex flex-col gap-4">
            <div className="space-y-0.5">
              <p className="text-sm font-semibold uppercase tracking-wide text-primary">Vagas</p>
              <p className="text-xs text-muted-foreground">Explore oportunidades capturadas ({filteredTotal})</p>
            </div>

            <h2 className="font-semibold text-sm uppercase tracking-wide text-primary">Filtros</h2>

            <div className="space-y-2">
              <label className={filterLabelClassName}>BUSCA POR TERMOS</label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="Palavra-chave..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9 h-9"
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className={filterLabelClassName}>TIPO DE CONTRATO</label>
              <div className="grid grid-cols-3 gap-2">
                {CONTRACT_TYPE_FILTER_OPTIONS.map((option) => {
                  const isActive = selectedContractType === option.value;
                  return (
                    <Button
                      key={option.value}
                      type="button"
                      variant={isActive ? "default" : "outline"}
                      size="sm"
                      className="h-9 w-full px-2 text-[11px] uppercase tracking-[0.08em]"
                      onClick={() => setSelectedContractType(option.value)}
                    >
                      {option.label}
                    </Button>
                  );
                })}
              </div>
            </div>

            <div className="space-y-2">
              <label className={filterLabelClassName}>SENIORIDADE</label>
              <div className="grid grid-cols-4 gap-2">
                {SENIORITY_FILTER_OPTIONS.map((option) => {
                  const isActive = selectedSeniority === option.value;
                  return (
                    <Button
                      key={option.value}
                      type="button"
                      variant={isActive ? "default" : "outline"}
                      size="sm"
                      className="h-9 w-full px-2 text-[11px] uppercase tracking-[0.08em]"
                      onClick={() => setSelectedSeniority(option.value)}
                    >
                      {option.label}
                    </Button>
                  );
                })}
              </div>
            </div>

            <div className="space-y-2">
              <label className={filterLabelClassName}>MOEDA</label>
              <div className="grid grid-cols-4 gap-2">
                {CURRENCY_FILTER_OPTIONS.map((option) => {
                  const isActive = selectedCurrencyFilter === option.value;
                  return (
                    <Button
                      key={option.value}
                      type="button"
                      variant={isActive ? "default" : "outline"}
                      size="sm"
                      className="h-9 w-full px-2 text-[11px] uppercase tracking-[0.08em]"
                      onClick={() => setSelectedCurrencyFilter(option.value)}
                    >
                      {option.label}
                    </Button>
                  );
                })}
              </div>
            </div>

            <div className="space-y-2">
              <label className={filterLabelClassName}>CONTATO</label>
              <div className="grid grid-cols-2 gap-2">
                {CONTACT_FILTER_OPTIONS.map((option) => {
                  const isActive = selectedContactFilter === option.value;
                  return (
                    <Button
                      key={option.value}
                      type="button"
                      variant={isActive ? "default" : "outline"}
                      size="sm"
                      className="h-9 w-full px-2 text-[11px] uppercase tracking-[0.08em]"
                      onClick={() => setSelectedContactFilter(option.value)}
                    >
                      {option.label}
                    </Button>
                  );
                })}
              </div>
            </div>

            <div className="space-y-2">
              <label className={filterLabelClassName}>SALARY RANGE</label>
              <div className="grid grid-cols-2 gap-2">
                {SALARY_RANGE_FILTER_OPTIONS.map((option) => {
                  const isActive = selectedSalaryRangeFilter === option.value;
                  return (
                    <Button
                      key={option.value}
                      type="button"
                      variant={isActive ? "default" : "outline"}
                      size="sm"
                      className="h-9 w-full px-2 text-[11px] uppercase tracking-[0.08em]"
                      onClick={() => setSelectedSalaryRangeFilter(option.value)}
                    >
                      {option.label}
                    </Button>
                  );
                })}
              </div>
            </div>

            <div className="space-y-2">
              <label className={filterLabelClassName}>FAIXA SALARIAL (BRL)</label>
              <div className="grid grid-cols-2 gap-2">
                <Input
                  value={priceMinValue}
                  onChange={(event) => setPriceMinValue(event.target.value)}
                  placeholder="Min"
                  className="h-9"
                  inputMode="decimal"
                />
                <Input
                  value={priceMaxValue}
                  onChange={(event) => setPriceMaxValue(event.target.value)}
                  placeholder="Max"
                  className="h-9"
                  inputMode="decimal"
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className={filterLabelClassName}>ORIGEM DA VAGA</label>
              <Select value={selectedSource} onValueChange={setSelectedSource}>
                <SelectTrigger className="h-9 w-full shadow-xs">
                  <SelectValue placeholder="Fonte" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todas as Fontes</SelectItem>
                  {sources.map((source) => (
                    <SelectItem key={source.id} value={source.name}>
                      {source.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <label className={filterLabelClassName}>LOCALIDADE (ESTADO)</label>
              <Select value={selectedState} onValueChange={setSelectedState}>
                <SelectTrigger className="h-9 w-full shadow-xs">
                  <SelectValue placeholder="UF" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos os Estados</SelectItem>
                  {BRAZILIAN_STATES.map((state) => (
                    <SelectItem key={state} value={state}>
                      {state}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

          </CardContent>
        </Card>
      </aside>

      {/* Main Content */}
      <main className="flex h-full w-full min-w-0 flex-1 flex-col gap-6 lg:min-h-0 lg:self-stretch lg:overflow-hidden">
        {/* Top actions/Toolbar */}
        <div className="shrink-0 rounded-lg border bg-card p-3 shadow-xs">
          <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-9 px-3"
            onClick={toggleSelectCurrentPage}
            disabled={loading || items.length === 0 || isRescrapeSubmitting || isBulkDeleting}
          >
            {allItemsOnPageSelected ? "Desmarcar Todas" : "Marcar Todas"}
          </Button>
          <Button
            type="button"
            variant="destructive"
            size="sm"
            className="h-9 px-3"
            onClick={handleDeleteSelectedItems}
            disabled={isBulkDeleting || selectedItemIds.length === 0 || isRescrapeSubmitting}
          >
            {isBulkDeleting ? <Loader2 className="mr-2 size-4 animate-spin" /> : <Trash2 className="mr-2 size-4" />}
            {isBulkDeleting ? "Excluindo..." : "Excluir"}
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-9 px-3"
            onClick={handleRescrapeSelectedItems}
            disabled={isRescrapeSubmitting || selectedItemIds.length === 0 || isBulkDeleting}
          >
            {isRescrapeSubmitting ? (
              <Loader2 className="mr-2 size-4 animate-spin" />
            ) : (
              <RefreshCw className="mr-2 size-4" />
            )}
            {isRescrapeSubmitting ? "Enfileirando..." : "Reprocessar"}
          </Button>
          </div>
          <div className="ml-auto flex items-center gap-2">
          <Select value={String(pageSize)} onValueChange={(value) => setPageSize(Number(value))}>
            <SelectTrigger className="h-9 w-[88px] shadow-xs">
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
          <Select value={selectedCreatedAtSort} onValueChange={(value) => setSelectedCreatedAtSort(value as (typeof CREATED_AT_SORT_OPTIONS)[number]["value"])}>
            <SelectTrigger className="h-9 w-[152px] shadow-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {CREATED_AT_SORT_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            variant="outline"
            size="icon"
            className="h-9 w-9"
            disabled={!canGoPrev}
            onClick={() => setOffset((value) => Math.max(0, value - pageSize))}
          >
            <ChevronLeft className="size-4" />
          </Button>
          <Button variant="outline" size="sm" className="h-9 min-w-10 px-3" disabled>
            {currentPage}
          </Button>
          <Button
            variant="outline"
            size="icon"
            className="h-9 w-9"
            disabled={!canGoNext}
            onClick={() => setOffset((value) => value + pageSize)}
          >
            <ChevronRight className="size-4" />
          </Button>
          </div>
          </div>
        </div>

        <div className="lg:flex-1 lg:min-h-0 lg:overflow-y-auto lg:pr-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {/* Content */}
          {loading ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {[...Array(8)].map((_, i) => (
                <Card key={i}>
                  <CardContent className="p-4">
                    <Skeleton className="mb-3 h-32 w-full rounded-md" />
                    <Skeleton className="mb-2 h-5 w-3/4" />
                    <Skeleton className="h-4 w-1/2" />
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : items.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16">
              <Search className="mb-4 size-12 text-muted-foreground/40" />
              <p className="text-lg text-muted-foreground">Nenhum item encontrado</p>
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {items.map((item) => {
                const externalUrl = getPrimaryExternalUrl(item);
                const isItemChecked = selectedItemIds.includes(item.id);
                const isItemActive = selectedItem?.id === item.id;
                const shouldShowCardActions = isItemChecked || isItemActive;
                return (
                <Card
                  key={item.id}
                  className="group relative h-[200px] gap-0 overflow-hidden py-0 transition-all hover:shadow-lg hover:shadow-primary/5 hover:border-primary/20 cursor-pointer shadow-xs bg-gradient-to-t from-primary/2 to-card dark:bg-card"
                  onClick={(event) => handleCardClick(event, item)}
                >
                  <div
                    className={`absolute right-2 top-2 z-10 flex items-center gap-1 transition-opacity ${shouldShowCardActions ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0 group-hover:pointer-events-auto group-hover:opacity-100"}`}
                  >
                    <div
                      className="flex h-7 w-7 items-center justify-center rounded-md border border-border/60 bg-background/80"
                      onClick={(event) => event.stopPropagation()}
                    >
                      <Checkbox
                        checked={isItemChecked}
                        onCheckedChange={(checked) => setItemSelection(item.id, checked === true)}
                        aria-label={`Selecionar item ${item.id}`}
                      />
                    </div>
                    {externalUrl && (
                      <a
                        href={externalUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="rounded-md border border-border/60 bg-background/80 p-1.5 text-muted-foreground transition-colors hover:text-primary"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <ExternalLink className="size-3.5" />
                      </a>
                    )}
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-7 rounded-md border border-border/60 bg-background/80 text-muted-foreground hover:text-primary"
                      onClick={(event) => handleRescrapeItem(event, item)}
                      disabled={reprocessingItemIds.includes(item.id)}
                      title="Reprocessar item"
                    >
                      {reprocessingItemIds.includes(item.id) ? (
                        <Loader2 className="size-3.5 animate-spin" />
                      ) : (
                        <RefreshCw className="size-3.5" />
                      )}
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-7 rounded-md border border-border/60 bg-background/80 text-muted-foreground hover:text-destructive"
                      onClick={(event) => handleDeleteItem(event, item)}
                      disabled={deletingItemId === item.id || isBulkDeleting}
                      title="Excluir item"
                    >
                      <Trash2 className="size-3.5" />
                    </Button>
                  </div>
                  <div className="flex h-full items-stretch">
                    <CardContent className="flex h-full w-full flex-col p-3 pt-5">
                      <h3 className="line-clamp-2 min-h-8 text-sm leading-4 font-semibold">{item.title || "—"}</h3>
                      <p className="mt-1.5 line-clamp-2 min-h-8 text-xs leading-4 text-muted-foreground whitespace-pre-wrap">
                        {formatDescriptionText(item.description)}
                      </p>
                      <div className="mt-2 text-sm font-bold text-primary">
                        {formatCardPrice(item.price)}
                      </div>
                      <div className="mt-2">{mediaIndicators(item)}</div>
                      <div className="mt-auto flex flex-wrap items-center justify-end gap-1.5 pt-3">
                        {item.state && (
                          <Badge variant="outline" className="h-5 px-1.5 text-[10px] border-primary/30 text-primary">
                            {item.state}
                          </Badge>
                        )}
                        {(item.attributes?.contract_type || (item.currency && item.currency !== "BRL")) && (
                          <Badge variant="outline" className="h-5 px-1.5 text-[10px] border-blue-400/30 text-blue-400 font-bold">
                            {String((item.currency && item.currency !== "BRL") ? "PJ" : (item.attributes?.contract_type ?? "")).toUpperCase()}
                          </Badge>
                        )}
                        <Badge
                          variant="outline"
                          className="h-5 cursor-pointer px-1.5 text-[10px]"
                          onClick={(event) => handleJsonTagClick(event, item)}
                          title="Ver JSON"
                        >
                          <Code2 className="size-3.5" />
                        </Badge>
                        <Badge variant="outline" className="h-5 px-1.5 text-[10px]" title={item.updated_at ?? undefined}>
                          {getUpdatedAtLabel(item)}
                        </Badge>
                        <Badge variant="secondary" className="h-5 px-1.5 text-[10px] bg-muted text-muted-foreground">
                          {getSourceLabel(item)}
                        </Badge>
                      </div>
                    </CardContent>
                  </div>
                </Card>
                );
              })}
            </div>
          )}
        </div>



      <Dialog open={isImageViewerOpen} onOpenChange={setIsImageViewerOpen}>
        <DialogContent
          showCloseButton={false}
          className="w-[85vw] max-w-none overflow-hidden p-0 sm:max-w-[85vw]"
        >
          <DialogHeader className="border-b px-5 py-4">
            <div className="flex items-center justify-between gap-3">
              <DialogTitle className="truncate text-base">
                {selectedItem?.title || "Visualização de imagem"}
              </DialogTitle>
              <div className="flex items-center gap-2">
                {selectedItemImages[activeImageIndex] && (
                  <Button type="button" variant="outline" size="icon" asChild>
                    <a
                      href={selectedItemImages[activeImageIndex]}
                      target="_blank"
                      rel="noopener noreferrer"
                      title="Abrir imagem em nova aba"
                    >
                      <ExternalLink className="size-4" />
                      <span className="sr-only">Abrir imagem em nova aba</span>
                    </a>
                  </Button>
                )}
                <DialogClose asChild>
                  <Button type="button" variant="ghost" size="icon" className="size-8">
                    <X className="size-4" />
                    <span className="sr-only">Fechar visualização de imagem</span>
                  </Button>
                </DialogClose>
              </div>
            </div>
          </DialogHeader>
          <div className="grid h-[80vh] grid-rows-[minmax(0,1fr)_auto]">
            <div className="relative flex min-h-0 items-center justify-center bg-black/80 px-16 py-6">
              {selectedItemImages[activeImageIndex] ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={selectedItemImages[activeImageIndex]}
                  alt={`Imagem ${activeImageIndex + 1}`}
                  className="max-h-full max-w-full object-contain"
                  onError={handleImageError}
                />
              ) : null}
            </div>
            <div className="flex items-center justify-between border-t bg-background px-5 py-3">
              <span className="text-sm text-muted-foreground">
                {selectedItemImages.length > 0 ? `${activeImageIndex + 1} de ${selectedItemImages.length}` : "Sem imagens"}
              </span>
              <span className="text-xs text-muted-foreground">
                {selectedItemImages.length > 1
                  ? activeImageIndex === 0
                    ? "Primeira imagem · Use → para avançar"
                    : activeImageIndex === selectedItemImages.length - 1
                      ? "Última imagem · Use ← para voltar"
                      : "Use ← e → para navegar"
                  : ""}
              </span>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={isJsonDialogOpen} onOpenChange={setIsJsonDialogOpen}>
        <DialogContent showCloseButton={false} className="w-[70vw] max-w-none sm:max-w-[70vw]">
          <DialogHeader className="flex-row items-center justify-between gap-3 space-y-0">
            <DialogTitle>Propriedades do anúncio</DialogTitle>
            <div className="flex items-center gap-2">
              <Button type="button" variant="outline" size="sm" onClick={handleCopyJsonPreview}>
                <Copy className="mr-2 size-4" />
                Copiar JSON
              </Button>
              <DialogClose asChild>
                <Button type="button" variant="ghost" size="icon" className="size-8">
                  <X className="size-4" />
                  <span className="sr-only">Fechar modal</span>
                </Button>
              </DialogClose>
            </div>
          </DialogHeader>
          <div className="max-h-[85vh] overflow-y-auto overflow-x-hidden rounded-md border bg-muted/20 p-3">
            <pre
              className="font-mono text-xs leading-relaxed whitespace-pre-wrap break-words"
              dangerouslySetInnerHTML={{ __html: highlightedJsonPreview }}
            />
          </div>
        </DialogContent>
      </Dialog>

      </main>

      {/* Right Sidebar - Item Details */}
      {selectedItem && (
        <aside className="hidden w-[500px] shrink-0 min-h-0 flex-col overflow-hidden border-l border-border/40 pl-6 xl:flex xl:h-full xl:self-stretch">
          <div className="flex flex-col gap-4 mb-4">
            <div className="flex items-center justify-end gap-2 pr-2">
              <Button
                type="button"
                variant="outline"
                size="icon"
                className="shrink-0"
                onClick={(event) => handleRescrapeItem(event, selectedItem!)}
                disabled={reprocessingItemIds.includes(selectedItem.id)}
                title="Reprocessar item"
              >
                {reprocessingItemIds.includes(selectedItem.id) ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <RefreshCw className="size-4" />
                )}
                <span className="sr-only">Reprocessar item</span>
              </Button>
              {getGoogleMapsLink(selectedItem) && (
                <Button asChild variant="outline" size="icon" className="shrink-0">
                  <a
                    href={getGoogleMapsLink(selectedItem) ?? "#"}
                    target="_blank"
                    rel="noopener noreferrer"
                    title="Abrir no Google Maps"
                  >
                    <MapPin className="size-4" />
                    <span className="sr-only">Abrir no Google Maps</span>
                  </a>
                </Button>
              )}
              {getPrimaryExternalUrl(selectedItem) && (
                <Button asChild variant="outline" size="icon" className="shrink-0">
                  <a
                    href={getPrimaryExternalUrl(selectedItem) ?? "#"}
                    target="_blank"
                    rel="noopener noreferrer"
                    title="Abrir anúncio original"
                  >
                    <ExternalLink className="size-4" />
                    <span className="sr-only">Abrir anúncio original</span>
                  </a>
                </Button>
              )}
              <Button type="button" variant="outline" size="icon" className="shrink-0" onClick={() => setSelectedItem(null)} title="Fechar detalhes">
                <X className="size-4" />
                <span className="sr-only">Fechar detalhes</span>
              </Button>
            </div>
            <div className="space-y-2 pr-6">
              <h2 className="text-xl font-semibold leading-tight">{selectedItem.title}</h2>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="secondary" className="h-5 px-2 text-[10px]">
                  {getSourceLabel(selectedItem)}
                </Badge>
                <Badge variant="outline" className="h-5 px-2 text-[10px]">
                  {getUpdatedAtLabel(selectedItem)}
                </Badge>
                <Badge variant="outline" className="h-5 px-2 text-[10px] bg-primary/5 text-primary border-primary/20 font-bold">
                  {getVersionLabel(selectedItem)}
                </Badge>
              </div>
            </div>
          </div>

          <div className="min-h-0 flex-1 -mx-2 overflow-y-auto overflow-x-hidden px-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            {(() => {
              const imageList = selectedItemImages;
              const attributeEntries = Object.entries(selectedItem.attributes ?? {}).filter(
                ([key, value]) => key !== "dedupe_key" && value !== null && value !== undefined && !(typeof value === "string" && value.trim() === "")
              );

              return (
                <div className="flex flex-col gap-6 pb-6">
                  {imageList.length > 0 && (
                    <div className="min-w-0 space-y-2 overflow-x-hidden pt-2">
                      <div className="flex items-center justify-between">
                        <h4 className="text-sm font-semibold text-muted-foreground">Imagens</h4>
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-muted-foreground">
                            {imageList.length} {imageList.length === 1 ? "imagem" : "imagens"}
                          </span>
                          {imageList.length > 1 && (
                            <>
                              <Button
                                type="button"
                                variant="outline"
                                size="icon"
                                className="size-6 h-6 w-6"
                                onClick={() => scrollDetailImages("left")}
                              >
                                <ChevronLeft className="size-3" />
                                <span className="sr-only">Voltar imagens</span>
                              </Button>
                              <Button
                                type="button"
                                variant="outline"
                                size="icon"
                                className="size-6 h-6 w-6"
                                onClick={() => scrollDetailImages("right")}
                              >
                                <ChevronRight className="size-3" />
                                <span className="sr-only">Avançar imagens</span>
                              </Button>
                            </>
                          )}
                        </div>
                      </div>
                      <div
                        ref={detailImagesScrollRef}
                        onWheel={handleDetailImagesWheel}
                        className="flex items-stretch gap-2 overflow-x-auto overflow-y-hidden pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
                      >
                        {imageList.map((image, index) => (
                          <button
                            key={`${image}-${index}`}
                            type="button"
                            onClick={() => openImageViewer(index)}
                            className="group flex h-24 w-fit shrink-0 items-center justify-center overflow-hidden rounded-md border bg-muted/20"
                            title={`Expandir imagem ${index + 1}`}
                          >
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img
                              src={image}
                              alt={`Imagem ${index + 1}`}
                              className="block h-full w-auto max-w-none object-contain transition-transform group-hover:scale-[1.01]"
                              onError={handleImageError}
                            />
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="grid grid-cols-1 gap-4">
                    <div className="space-y-2 rounded-md border bg-muted/20 p-4">
                      <h4 className="text-sm font-semibold text-muted-foreground">Descrição</h4>
                      <div className="min-h-[100px] text-[13px] leading-6 whitespace-pre-wrap break-words text-pretty">
                        {formatDescriptionText(selectedItem.description)}
                      </div>
                    </div>

                    <div className="space-y-2">
                      <h4 className="text-sm font-semibold text-muted-foreground">Informações Gerais</h4>
                      <div className="rounded-md border bg-muted/20 p-4 space-y-2">
                        <DetailRow label="Salário" value={formatPrice(selectedItem.price)} />
                        <DetailRow label="Moeda" value={formatStructuredValue(selectedItem.currency)} />
                        <DetailRow label="Estado" value={formatStructuredValue(selectedItem.state)} />
                        <DetailRow label="Cidade" value={formatStructuredValue(selectedItem.city)} />
                        <DetailRow
                          label="CEP"
                          value={selectedItem.zip_code ? formatZipCode(selectedItem.zip_code) : "—"}
                        />
                        <DetailRow label="Endereço" value={formatStructuredValue(selectedItem.street)} />
                      </div>
                    </div>

                    {selectedItem.links && selectedItem.links.length > 0 && (
                      <div className="space-y-2">
                        <h4 className="text-sm font-semibold text-muted-foreground">Links</h4>
                        <div className="rounded-md border bg-muted/20 p-4 space-y-2">
                          {selectedItem.links.map((link, index) => (
                            <DetailRow
                              key={index}
                              label={`Link ${index + 1}`}
                              value={
                                <a
                                  href={link}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-primary hover:underline"
                                >
                                  Abrir
                                </a>
                              }
                            />
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="space-y-2">
                      <h4 className="text-sm font-semibold text-muted-foreground">Contato</h4>
                      <div className="rounded-md border bg-muted/20 p-4 space-y-2">
                        <DetailRow label="Nome" value={formatStructuredValue(selectedItem.contact_name)} />
                        <DetailRow
                          label="Telefone"
                          value={selectedItem.contact_phone ? formatPhoneBR(selectedItem.contact_phone) : "—"}
                        />
                        <DetailRow label="E-mail" value={formatStructuredValue(selectedItem.contact_email)} />
                      </div>
                    </div>

                    <div className="space-y-2">
                      <h4 className="text-sm font-semibold text-muted-foreground">Detalhes Extras</h4>
                      <div className="rounded-md border bg-muted/20 p-4 space-y-2">
                        <DetailRow
                          label="Criado"
                          value={formatUppercaseDisplayValue(formatDateTimeDDMMYYYYHHMM(selectedItem.created_at))}
                        />
                        {(() => {
                          const otherAttributes = attributeEntries.filter(
                            ([key]) => !key.toLowerCase().includes("telegram")
                          );
                          
                          if (otherAttributes.length === 0) return null;

                          return (
                            <div className="grid grid-cols-1 gap-2">
                              {otherAttributes.map(([key, value]) => (
                                <DetailRow key={key} label={toLabel(key)} value={formatUppercaseDisplayValue(value)} />
                              ))}
                            </div>
                          );
                        })()}
                      </div>
                    </div>

                    {attributeEntries.some(([key]) => key.toLowerCase().includes("telegram")) && (
                      <div className="space-y-2">
                        <h4 className="text-sm font-semibold text-muted-foreground">Informações Telegram</h4>
                        <div className="rounded-md border bg-muted/20 p-4 space-y-2">
                          {attributeEntries
                            .filter(([key]) => key.toLowerCase().includes("telegram"))
                            .map(([key, value]) => (
                              <DetailRow key={key} label={toLabel(key)} value={formatUppercaseDisplayValue(value)} />
                            ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              );
            })()}
          </div>
        </aside>
      )}
    </div>
  );
}
