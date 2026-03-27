"use client";

import axios from "axios";
import { Fragment, useEffect, useLayoutEffect, useMemo, useRef, useState, type SetStateAction } from "react";
import { DndContext, PointerSensor, closestCenter, useSensor, useSensors, type DragEndEvent } from "@dnd-kit/core";
import { SortableContext, arrayMove, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { DownloadIcon, GripVerticalIcon, ImagePlusIcon, MailIcon, RotateCcwIcon, PlusIcon, Trash2Icon, FileTextIcon, SaveIcon } from "lucide-react";
import { toast } from "sonner";

import { ResumePreview } from "@/components/resume-preview";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { api } from "@/lib/api";
import {
  createEmptyEducation,
  createEmptyExperience,
  createEmptyLanguage,
  createEmptySolvedProblem,
  createEmptySkillGroup,
  DEFAULT_RESUME_LOCALE,
  getDefaultResumeData,
  getResumePdfFilename,
  getResumeStorageFallbackKeys,
  getResumeStorageKey,
  normalizeResumeData,
  normalizeResumeLocale,
  RESUME_PHOTO_FRAME_STYLE_OPTIONS,
  RESUME_LOCALE_OPTIONS,
  RESUME_STORAGE_KEY,
  type ResumeDocument,
  type ResumeEducation,
  type ResumeExperience,
  type ResumeLanguage,
  type ResumeLocale,
  type ResumePhotoFrameStyle,
  type ResumeSolvedProblem,
  type ResumeSkillGroup,
} from "@/lib/resume";

const TEXTAREA_CLASSNAME =
  "flex min-h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm leading-5 shadow-xs outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 resize-none overflow-hidden";

const RESUME_ACCENT_COLOR_PALETTE = [
  "#111827",
  "#334155",
  "#4f46e5",
  "#4338ca",
  "#2563eb",
  "#0369a1",
  "#0f766e",
  "#059669",
  "#4d7c0f",
  "#a16207",
  "#ea580c",
  "#dc2626",
  "#be123c",
  "#c026d3",
  "#7c3aed",
  "#1d4ed8",
  "#0f172a",
  "#166534",
] as const;

const RESUME_SURFACE_COLOR_PALETTE = [
  "#ffffff",
  "#f2f4ef",
  "#f8fafc",
  "#f1f5f9",
  "#eef2ff",
  "#e0e7ff",
  "#eff6ff",
  "#dbeafe",
  "#ecfeff",
  "#cffafe",
  "#ecfdf5",
  "#dcfce7",
  "#f0fdf4",
  "#f7fee7",
  "#fefce8",
  "#fff7ed",
  "#fef2f2",
  "#fdf2f8",
  "#faf5ff",
] as const;

type ThemeColorField = "accentColor" | "sidebarBackground" | "pageBackground";
type ResumeThemePreset = {
  label: string;
  accentColor: string;
  sidebarBackground: string;
  pageBackground: string;
};

const RESUME_THEME_COLOR_FIELDS: Array<{
  id: string;
  field: ThemeColorField;
  label: string;
  palette: readonly string[];
}> = [
  { id: "accent-color", field: "accentColor", label: "Destaque", palette: RESUME_ACCENT_COLOR_PALETTE },
  { id: "sidebar-color", field: "sidebarBackground", label: "Lateral", palette: RESUME_SURFACE_COLOR_PALETTE },
  { id: "page-color", field: "pageBackground", label: "Página", palette: RESUME_SURFACE_COLOR_PALETTE },
];

const RESUME_THEME_PRESETS: ResumeThemePreset[] = [
  { label: "Padrão", accentColor: "#4f46e5", sidebarBackground: "#f2f4ef", pageBackground: "#ffffff" },
  { label: "Editorial", accentColor: "#4338ca", sidebarBackground: "#eef2ff", pageBackground: "#f8fafc" },
  { label: "Tech Clean", accentColor: "#0f172a", sidebarBackground: "#f1f5f9", pageBackground: "#ffffff" },
  { label: "Verde Sutil", accentColor: "#166534", sidebarBackground: "#ecfdf5", pageBackground: "#f0fdf4" },
  { label: "Âmbar", accentColor: "#a16207", sidebarBackground: "#fefce8", pageBackground: "#fff7ed" },
  { label: "Rose Soft", accentColor: "#be123c", sidebarBackground: "#fdf2f8", pageBackground: "#faf5ff" },
];

function ThemeColorPalettePicker({
  id,
  label,
  value,
  palette,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  palette: readonly string[];
  onChange: (value: string) => void;
}) {
  const [open, setOpen] = useState(false);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <div className="flex w-12 flex-col items-center gap-2 text-center">
        <PopoverTrigger asChild>
          <button
            id={id}
            type="button"
            aria-label={`Escolher cor de ${label}`}
            className="relative block h-12 w-12 overflow-hidden rounded-full border border-border shadow-sm transition"
          >
            <span className="absolute inset-0 rounded-full" style={{ backgroundColor: value }} />
          </button>
        </PopoverTrigger>
        <span className="min-h-4 text-center text-xs font-medium leading-none text-muted-foreground">{label}</span>
      </div>
      <PopoverContent className="w-[264px] p-3" align="start">
        <div className="mb-3 text-xs font-medium text-muted-foreground">{label}</div>
        <div className="grid grid-cols-6 gap-2">
          {palette.map((color) => {
            const isActive = value.toLowerCase() === color.toLowerCase();
            return (
              <button
                key={color}
                type="button"
                aria-label={`${label} ${color}`}
                title={color}
                onClick={() => {
                  onChange(color);
                  setOpen(false);
                }}
                className={`relative h-9 w-9 rounded-full border transition ${isActive ? "border-primary ring-2 ring-primary/20" : "border-border hover:border-primary/40"}`}
                style={{ backgroundColor: color }}
              />
            );
          })}
        </div>
      </PopoverContent>
    </Popover>
  );
}

function ThemePresetPicker({
  onApply,
}: {
  onApply: (preset: ResumeThemePreset) => void;
}) {
  const [open, setOpen] = useState(false);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <div className="flex w-12 flex-col items-center gap-2 text-center">
        <PopoverTrigger asChild>
          <button
            type="button"
            aria-label="Aplicar combinação de cores"
            className="relative block h-12 w-12 overflow-hidden rounded-full border border-border shadow-sm transition"
          >
            <span className="absolute inset-0" style={{ backgroundColor: RESUME_THEME_PRESETS[0].pageBackground }} />
            <span className="absolute inset-y-0 left-0 w-1/3" style={{ backgroundColor: RESUME_THEME_PRESETS[0].accentColor }} />
            <span className="absolute inset-y-0 right-0 w-1/3" style={{ backgroundColor: RESUME_THEME_PRESETS[0].sidebarBackground }} />
          </button>
        </PopoverTrigger>
        <span className="min-h-4 text-center text-xs font-medium leading-none text-muted-foreground">Combos</span>
      </div>
      <PopoverContent className="w-[280px] p-3" align="start">
        <div className="mb-3 text-xs font-medium text-muted-foreground">Combinações prontas</div>
        <div className="grid grid-cols-2 gap-3">
          {RESUME_THEME_PRESETS.map((preset) => (
            <button
              key={preset.label}
              type="button"
              onClick={() => {
                onApply(preset);
                setOpen(false);
              }}
              className="rounded-xl border border-border p-2 text-left transition hover:border-primary/40 hover:bg-muted/30"
            >
              <div className="mb-2 flex gap-1">
                <span className="h-7 flex-1 rounded-md" style={{ backgroundColor: preset.accentColor }} />
                <span className="h-7 flex-1 rounded-md" style={{ backgroundColor: preset.sidebarBackground }} />
                <span className="h-7 flex-1 rounded-md" style={{ backgroundColor: preset.pageBackground }} />
              </div>
              <div className="text-xs font-medium text-foreground">{preset.label}</div>
            </button>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
}

function AutoTextarea({
  id,
  value,
  onChange,
  className,
  minHeight = 40,
  onPointerDown,
}: {
  id?: string;
  value: string;
  onChange: (event: React.ChangeEvent<HTMLTextAreaElement>) => void;
  className?: string;
  minHeight?: number;
  onPointerDown?: (event: React.PointerEvent<HTMLTextAreaElement>) => void;
}) {
  const ref = useRef<HTMLTextAreaElement | null>(null);

  useLayoutEffect(() => {
    const element = ref.current;
    if (!element) return;
    element.style.height = "auto";
    element.style.height = `${Math.max(minHeight, element.scrollHeight)}px`;
  }, [value, minHeight]);

  return <textarea id={id} ref={ref} className={className} value={value} onChange={onChange} onPointerDown={onPointerDown} />;
}

function splitLines(value: string): string[] {
  return value
    .split("\n")
    .map((entry) => entry.trim())
    .filter(Boolean);
}

function joinLines(value: string[]): string {
  return value.join("\n");
}

function joinSkillItems(value: string[]): string {
  return value.join(", ");
}

function buildSkillGroupItemDrafts(value: ResumeSkillGroup[]): string[] {
  return value.map((group) => joinSkillItems(group.items));
}

function splitSkillItems(value: string): string[] {
  return value
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean);
}

type EmailSenderProfile = "company" | "personal";
type ResumeDocumentMap = Record<ResumeLocale, ResumeDocument>;
type ResumeStringArrayMap = Record<ResumeLocale, string[]>;
type LoadedLocaleMap = Record<ResumeLocale, boolean>;

function createInitialResumeMap(): ResumeDocumentMap {
  return {
    pt: getDefaultResumeData("pt"),
    en: getDefaultResumeData("en"),
  };
}

function createInitialSkillDraftMap(resumeMap: ResumeDocumentMap): ResumeStringArrayMap {
  return {
    pt: buildSkillGroupItemDrafts(resumeMap.pt.skillGroups),
    en: buildSkillGroupItemDrafts(resumeMap.en.skillGroups),
  };
}

function persistResumeDraft(locale: ResumeLocale, value: ResumeDocument) {
  const serialized = JSON.stringify(value);
  window.localStorage.setItem(getResumeStorageKey(locale), serialized);
  if (locale === DEFAULT_RESUME_LOCALE) {
    window.localStorage.setItem(RESUME_STORAGE_KEY, serialized);
  }
}

function readStoredResumeDraft(locale: ResumeLocale): ResumeDocument | null {
  for (const storageKey of getResumeStorageFallbackKeys(locale)) {
    try {
      const raw = window.localStorage.getItem(storageKey);
      if (!raw) continue;
      return normalizeResumeData(JSON.parse(raw), locale);
    } catch {
      continue;
    }
  }

  return null;
}

function getEmailTemplate(profile: EmailSenderProfile, locale: ResumeLocale) {
  if (profile === "company") {
    if (locale === "en") {
      return {
        subject: "Professional Services - Sanlabz Technology - Software Engineer",
        message:
          "Hello,\n\nSanlabz Technology identified a strong fit between this opportunity and the type of technical solutions we deliver to our clients.\n\nWe work with software development, solution architecture, digital product evolution and operational efficiency, with a focus on high technical standards and measurable business impact.\n\nAttached is the profile of one of our engineers, with experience in backend, integrations, observability, cloud, automation and advanced AI applied to intelligent workflows built for scale, productivity and results.\n\nIf it is relevant for your company at this stage, we are available to discuss professional services, team augmentation or support on strategic technology demands.\n\nSee our portfolio at sanlabz.com.br\n\nBest regards,\nSanlabz Technology.",
      };
    }

    return {
      subject: "Prestação de Serviços - Sanlabz Technology - Software Engineer",
      message:
        "Olá,\n\nA Sanlabz Technology identificou aderência entre a oportunidade e o tipo de solução técnica que entregamos aos nossos clientes.\n\nAtuamos com desenvolvimento de software, arquitetura de soluções, evolução de produtos digitais e ganho de eficiência operacional, com foco em entregas de alto nível técnico e impacto real no negócio.\n\nEncaminhamos em anexo o perfil de um dos nossos colaboradores com experiência em backend, integrações, observabilidade, cloud, automação e aplicação avançada de IA em fluxos inteligentes orientados a escala, produtividade e resultado.\n\nSe fizer sentido para o momento da empresa, ficamos à disposição para conversar sobre prestação de serviços, alocação de perfil técnico ou apoio em demandas estratégicas de tecnologia.\n\nVeja nosso portfólio em sanlabz.com.br\n\nAtt, Sanlabz Technology.",
    };
  }

  if (locale === "en") {
    return {
      subject: "Resume - Samuel Costa - Sr Software Engineer",
      message:
        "Hello,\n\nI came across this opportunity and thought it would make sense to introduce myself.\n\nI have solid experience in software development, solution architecture and digital product evolution, with a background in high-demand technical environments.\n\nThroughout my career, I have worked on projects focused on backend, integrations, observability, cloud and operational efficiency gains.\n\nI have also been working extensively with AI applied to automation, analysis, productivity and the construction of intelligent workflows, always focused on practical business outcomes.\n\nI am attaching my resume for your review.\n\nIf it makes sense, I would be glad to discuss the role and how I can contribute to the team.\n\nSee my portfolio at sancozta.com.br\n\nBest regards,\nSamuel Costa.",
    };
  }

  return {
    subject: "Currículo - Samuel Costa - Sr Software Engineer",
    message:
      "Olá,\n\nTomei conhecimento da oportunidade e achei que fazia sentido me apresentar.\n\nTenho atuação sólida em desenvolvimento de software, arquitetura de soluções e evolução de produtos digitais, com experiência em ambientes de alta exigência técnica.\n\nAo longo da minha trajetória, participei de projetos com foco em backend, integrações, observabilidade, cloud e ganho de eficiência operacional.\n\nTambém venho trabalhando de forma avançada com IA aplicada a automação, análise, produtividade e construção de fluxos inteligentes, sempre com foco em resultado prático para o negócio.\n\nEstou enviando meu currículo em anexo para sua avaliação.\n\nSe fizer sentido, fico à disposição para conversar melhor sobre a vaga e sobre como posso contribuir com o time.\n\nVeja meu portfólio em sancozta.com.br\n\nAtt, Samuel Costa.",
  };
}

function SortableResumeCard({
  id,
  children,
  className = "",
  useHandle = false,
  handleLabel = "Reordenar item",
  handleClassName = "absolute left-4 top-2",
}: {
  id: string;
  children: React.ReactNode;
  className?: string;
  useHandle?: boolean;
  handleLabel?: string;
  handleClassName?: string;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });

  return (
    <div
      ref={setNodeRef}
      {...(useHandle ? {} : attributes)}
      {...(useHandle ? {} : listeners)}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
      }}
      className={`relative rounded-xl border bg-card p-4 pt-4 ${isDragging ? "z-10 shadow-lg ring-1 ring-primary/20" : ""} ${useHandle ? "" : isDragging ? "cursor-grabbing" : "cursor-grab"} ${className}`}
    >
      {useHandle && (
        <Button
          type="button"
          variant="outline"
          size="sm"
          aria-label={handleLabel}
          className={`${handleClassName} h-6 w-6 rounded-md border-border/60 bg-background p-0 text-muted-foreground shadow-none transition hover:bg-muted/30 hover:text-foreground ${isDragging ? "cursor-grabbing" : "cursor-grab"}`}
          {...attributes}
          {...listeners}
        >
          <GripVerticalIcon className="size-2" />
        </Button>
      )}
      {children}
    </div>
  );
}

export default function ResumePage() {
  const [resumeLocale, setResumeLocale] = useState<ResumeLocale>(DEFAULT_RESUME_LOCALE);
  const [resumeByLocale, setResumeByLocale] = useState<ResumeDocumentMap>(() => createInitialResumeMap());
  const [defaultResumeByLocale, setDefaultResumeByLocale] = useState<ResumeDocumentMap>(() => createInitialResumeMap());
  const [skillGroupItemDraftsByLocale, setSkillGroupItemDraftsByLocale] = useState<ResumeStringArrayMap>(() => createInitialSkillDraftMap(createInitialResumeMap()));
  const [loadedLocales, setLoadedLocales] = useState<LoadedLocaleMap>({ pt: false, en: false });
  const [isSaving, setIsSaving] = useState(false);
  const [isImportJsonDialogOpen, setIsImportJsonDialogOpen] = useState(false);
  const [jsonImportText, setJsonImportText] = useState("");
  const [isEmailDialogOpen, setIsEmailDialogOpen] = useState(false);
  const [isSendingEmail, setIsSendingEmail] = useState(false);
  const [emailSenderProfile, setEmailSenderProfile] = useState<EmailSenderProfile>("personal");
  const [emailTo, setEmailTo] = useState("");
  const [emailSubject, setEmailSubject] = useState(getEmailTemplate("personal", DEFAULT_RESUME_LOCALE).subject);
  const [emailMessage, setEmailMessage] = useState(getEmailTemplate("personal", DEFAULT_RESUME_LOCALE).message);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));
  const resume = resumeByLocale[resumeLocale];
  const defaultResume = defaultResumeByLocale[resumeLocale];
  const skillGroupItemDrafts = skillGroupItemDraftsByLocale[resumeLocale];
  const isLoaded = loadedLocales[resumeLocale];

  const setResume = (value: SetStateAction<ResumeDocument>) => {
    setResumeByLocale((current) => ({
      ...current,
      [resumeLocale]: typeof value === "function" ? (value as (previous: ResumeDocument) => ResumeDocument)(current[resumeLocale]) : value,
    }));
  };

  const setDefaultResume = (value: SetStateAction<ResumeDocument>) => {
    setDefaultResumeByLocale((current) => ({
      ...current,
      [resumeLocale]: typeof value === "function" ? (value as (previous: ResumeDocument) => ResumeDocument)(current[resumeLocale]) : value,
    }));
  };

  const setSkillGroupItemDrafts = (value: SetStateAction<string[]>) => {
    setSkillGroupItemDraftsByLocale((current) => ({
      ...current,
      [resumeLocale]: typeof value === "function" ? (value as (previous: string[]) => string[])(current[resumeLocale]) : value,
    }));
  };

  useEffect(() => {
    if (loadedLocales[resumeLocale]) return;

    let isMounted = true;

    const loadResume = async () => {
      const fallback = readStoredResumeDraft(resumeLocale) ?? getDefaultResumeData(resumeLocale);

      try {
        const response = await api.get<{ payload: ResumeDocument }>("/api/v1/resume-document/", { params: { locale: resumeLocale } });
        const normalized = normalizeResumeData(response.data.payload, resumeLocale);
        if (!isMounted) return;
        setResumeByLocale((current) => ({ ...current, [resumeLocale]: normalized }));
        setDefaultResumeByLocale((current) => ({ ...current, [resumeLocale]: normalized }));
        setSkillGroupItemDraftsByLocale((current) => ({ ...current, [resumeLocale]: buildSkillGroupItemDrafts(normalized.skillGroups) }));
        persistResumeDraft(resumeLocale, normalized);
      } catch (error) {
        if (axios.isAxiosError(error) && error.response?.status !== 404) {
          toast.error("Nao foi possivel carregar o curriculo salvo no servidor. Usando rascunho local.");
        }
        if (!isMounted) return;
        setResumeByLocale((current) => ({ ...current, [resumeLocale]: fallback }));
        setDefaultResumeByLocale((current) => ({ ...current, [resumeLocale]: fallback }));
        setSkillGroupItemDraftsByLocale((current) => ({ ...current, [resumeLocale]: buildSkillGroupItemDrafts(fallback.skillGroups) }));
      } finally {
        if (isMounted) {
          setLoadedLocales((current) => ({ ...current, [resumeLocale]: true }));
        }
      }
    };

    void loadResume();
    return () => {
      isMounted = false;
    };
  }, [loadedLocales, resumeLocale]);

  useEffect(() => {
    if (!isLoaded) return;
    persistResumeDraft(resumeLocale, resume);
  }, [isLoaded, resume, resumeLocale]);

  useEffect(() => {
    const template = getEmailTemplate(emailSenderProfile, resumeLocale);
    setEmailSubject(template.subject);
    setEmailMessage(template.message);
  }, [emailSenderProfile, resumeLocale]);

  const certificationsText = useMemo(() => joinLines(resume.certifications), [resume.certifications]);

  const updateProfile = (field: keyof ResumeDocument["profile"], value: string) => {
    setResume((current) => ({
      ...current,
      profile: {
        ...current.profile,
        [field]: value,
      },
    }));
  };

  const updateTheme = <K extends keyof ResumeDocument["theme"]>(field: K, value: ResumeDocument["theme"][K]) => {
    setResume((current) => ({
      ...current,
      theme: {
        ...current.theme,
        [field]: value,
      },
    }));
  };

  const applyThemePreset = (preset: ResumeThemePreset) => {
    setResume((current) => ({
      ...current,
      theme: {
        ...current.theme,
        accentColor: preset.accentColor,
        sidebarBackground: preset.sidebarBackground,
        pageBackground: preset.pageBackground,
      },
    }));
  };

  const updateLanguage = (index: number, field: keyof ResumeLanguage, value: string) => {
    setResume((current) => ({
      ...current,
      languages: current.languages.map((item, itemIndex) => (itemIndex === index ? { ...item, [field]: value } : item)),
    }));
  };

  const updateEducation = (index: number, field: keyof ResumeEducation, value: string) => {
    setResume((current) => ({
      ...current,
      education: current.education.map((item, itemIndex) => (itemIndex === index ? { ...item, [field]: value } : item)),
    }));
  };

  const updateExperience = (index: number, field: keyof ResumeExperience, value: string) => {
    setResume((current) => ({
      ...current,
      experiences: current.experiences.map((item, itemIndex) => (itemIndex === index ? { ...item, [field]: value } : item)),
    }));
  };

  const updateSkillGroup = (index: number, field: keyof ResumeSkillGroup, value: string | string[]) => {
    if (field === "items") {
      const rawValue = Array.isArray(value) ? joinSkillItems(value) : value;
      setSkillGroupItemDrafts((current) => current.map((item, itemIndex) => (itemIndex === index ? rawValue : item)));
    }

    setResume((current) => ({
      ...current,
      skillGroups: current.skillGroups.map((item, itemIndex) => {
        if (itemIndex !== index) return item;
        if (field === "items") {
          return { ...item, items: Array.isArray(value) ? value : splitSkillItems(value) };
        }
        return { ...item, title: Array.isArray(value) ? value.join(", ") : value };
      }),
    }));
  };

  const updateSolvedProblem = (index: number, field: keyof ResumeSolvedProblem, value: string) => {
    setResume((current) => ({
      ...current,
      solvedProblems: current.solvedProblems.map((item, itemIndex) => (itemIndex === index ? { ...item, [field]: value } : item)),
    }));
  };

  const handlePhotoChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const result = typeof reader.result === "string" ? reader.result : "";
      updateProfile("photoDataUrl", result);
    };
    reader.readAsDataURL(file);
  };

  const openExportView = () => {
    const normalized = normalizeResumeData(resume, resumeLocale);
    persistResumeDraft(resumeLocale, normalized);
    window.open(`/resume/export?locale=${resumeLocale}`, "_blank", "noopener,noreferrer");
  };

  const saveResume = async () => {
    setIsSaving(true);
    try {
      const normalized = normalizeResumeData(resume, resumeLocale);
      await api.put("/api/v1/resume-document/", { payload: normalized }, { params: { locale: resumeLocale } });
      persistResumeDraft(resumeLocale, normalized);
      setDefaultResume(normalized);
      toast.success("Curriculo salvo");
    } catch {
      toast.error("Nao foi possivel salvar o curriculo");
    } finally {
      setIsSaving(false);
    }
  };

  const restoreDefaultResume = () => {
    setResume(defaultResume);
    setSkillGroupItemDrafts(buildSkillGroupItemDrafts(defaultResume.skillGroups));
    persistResumeDraft(resumeLocale, defaultResume);
    toast.success("Currículo restaurado para o padrão atual");
  };

  const copyResumeJson = async () => {
    await navigator.clipboard.writeText(JSON.stringify(resume, null, 2));
    toast.success("JSON do currículo copiado");
  };

  const handleImportJsonDialogOpenChange = (open: boolean) => {
    if (open) {
      setJsonImportText(JSON.stringify(normalizeResumeData(resume, resumeLocale), null, 2));
    }
    setIsImportJsonDialogOpen(open);
  };

  const importResumeJson = () => {
    try {
      const parsed = JSON.parse(jsonImportText);
      const normalized = normalizeResumeData(parsed, resumeLocale);
      setResume(normalized);
      setDefaultResume(normalized);
      setSkillGroupItemDrafts(buildSkillGroupItemDrafts(normalized.skillGroups));
      persistResumeDraft(resumeLocale, normalized);
      setIsImportJsonDialogOpen(false);
      toast.success("JSON importado");
    } catch {
      toast.error("JSON invalido");
    }
  };

  const sendResumeEmail = async () => {
    if (!emailTo.trim()) {
      toast.error("Informe o email de destino");
      return;
    }

    setIsSendingEmail(true);
    try {
      const normalized = normalizeResumeData(resume, resumeLocale);
      const filename = getResumePdfFilename(resumeLocale, normalized.profile.fullName);

      await api.post("/api/v1/resume-document/send-email", {
        to_email: emailTo.trim(),
        subject: emailSubject.trim() || (resumeLocale === "en" ? `Resume - ${normalized.profile.fullName}` : `Curriculo - ${normalized.profile.fullName}`),
        message: emailMessage,
        sender_profile: emailSenderProfile,
        reply_to_email: emailSenderProfile === "personal" ? normalized.profile.email : "",
        resume_payload: normalized,
        filename,
        locale: resumeLocale,
      });

      toast.success("Email enviado");
      setIsEmailDialogOpen(false);
    } catch (error) {
      const detail = axios.isAxiosError(error) ? error.response?.data?.detail : null;
      const message = error instanceof Error ? error.message : null;
      toast.error(typeof detail === "string" ? detail : message || "Nao foi possivel enviar o email");
    } finally {
      setIsSendingEmail(false);
    }
  };

  const reorderSection = <T,>(items: T[], activeId: string, overId: string, prefix: string): T[] => {
    const oldIndex = items.findIndex((_, index) => `${prefix}-${index}` === activeId);
    const newIndex = items.findIndex((_, index) => `${prefix}-${index}` === overId);
    if (oldIndex < 0 || newIndex < 0 || oldIndex === newIndex) return items;
    return arrayMove(items, oldIndex, newIndex);
  };

  const handleLanguagesDragEnd = ({ active, over }: DragEndEvent) => {
    if (!over || active.id === over.id) return;
    setResume((current) => ({ ...current, languages: reorderSection(current.languages, String(active.id), String(over.id), "language") }));
  };

  const handleEducationDragEnd = ({ active, over }: DragEndEvent) => {
    if (!over || active.id === over.id) return;
    setResume((current) => ({ ...current, education: reorderSection(current.education, String(active.id), String(over.id), "education") }));
  };

  const handleSkillGroupsDragEnd = ({ active, over }: DragEndEvent) => {
    if (!over || active.id === over.id) return;
    setResume((current) => ({ ...current, skillGroups: reorderSection(current.skillGroups, String(active.id), String(over.id), "skill-group") }));
    setSkillGroupItemDrafts((current) => reorderSection(current, String(active.id), String(over.id), "skill-group"));
  };

  const handleExperiencesDragEnd = ({ active, over }: DragEndEvent) => {
    if (!over || active.id === over.id) return;
    setResume((current) => ({ ...current, experiences: reorderSection(current.experiences, String(active.id), String(over.id), "experience") }));
  };

  const handleSolvedProblemsDragEnd = ({ active, over }: DragEndEvent) => {
    if (!over || active.id === over.id) return;
    setResume((current) => ({ ...current, solvedProblems: reorderSection(current.solvedProblems, String(active.id), String(over.id), "solved-problem") }));
  };

  if (!isLoaded) {
    return (
      <div className="flex flex-1 flex-col gap-6 p-4 pt-6 lg:p-6 lg:pt-8 w-full">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Currículo</h1>
            <p className="text-sm text-muted-foreground">
              Edite o conteúdo e gere um PDF novo mantendo o padrão do currículo atual, com identidade visual controlada.
            </p>
          </div>
        </div>
        <div className="grid gap-6 lg:grid-cols-[minmax(460px,560px)_minmax(0,1fr)_minmax(460px,560px)] lg:items-start">
          <Card>
            <CardContent className="px-6 py-8 text-sm text-muted-foreground">Carregando currículo...</CardContent>
          </Card>
          <Card>
            <CardContent className="px-6 py-8 text-sm text-muted-foreground">Montando preview...</CardContent>
          </Card>
          <Card>
            <CardContent className="px-6 py-8 text-sm text-muted-foreground">Carregando seções...</CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col gap-6 p-4 pt-6 lg:p-6 lg:pt-8 w-full">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Currículo</h1>
          <p className="text-sm text-muted-foreground">
            Edite o conteúdo e gere um PDF novo mantendo o padrão do currículo atual, com identidade visual controlada.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <ToggleGroup
            type="single"
            value={resumeLocale}
            onValueChange={(value) => {
              if (!value) return;
              setResumeLocale(normalizeResumeLocale(value));
            }}
            variant="outline"
            className="overflow-hidden"
          >
            {RESUME_LOCALE_OPTIONS.map((option) => (
              <ToggleGroupItem key={option.value} value={option.value} className="min-w-11 px-3 text-xs font-semibold">
                {option.shortLabel}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
          <Button type="button" variant="outline" onClick={() => handleImportJsonDialogOpenChange(true)}>
            <FileTextIcon className="mr-2 size-4" />
            Importar JSON
          </Button>
          <Button type="button" variant="outline" onClick={() => setIsEmailDialogOpen(true)} disabled={!isLoaded}>
            <MailIcon className="mr-2 size-4" />
            Enviar Email
          </Button>
          <Button type="button" variant="outline" onClick={saveResume} disabled={isSaving || !isLoaded}>
            <SaveIcon className="mr-2 size-4" />
            {isSaving ? "Salvando..." : "Salvar"}
          </Button>
          <Button type="button" variant="outline" onClick={copyResumeJson}>
            <FileTextIcon className="mr-2 size-4" />
            Copiar JSON
          </Button>
          <Button type="button" variant="outline" onClick={restoreDefaultResume}>
            <RotateCcwIcon className="mr-2 size-4" />
            Restaurar Base
          </Button>
          <Button type="button" onClick={openExportView}>
            <DownloadIcon className="mr-2 size-4" />
            Gerar PDF
          </Button>
        </div>
      </div>
      <Dialog open={isImportJsonDialogOpen} onOpenChange={handleImportJsonDialogOpenChange}>
        <DialogContent className="flex max-h-[calc(100vh-2rem)] flex-col overflow-hidden sm:max-w-4xl">
          <DialogHeader className="shrink-0">
            <DialogTitle>Importar JSON</DialogTitle>
            <DialogDescription>
              Cole um JSON compatível com a estrutura do currículo. O conteúdo atual será sobrescrito após a importação.
            </DialogDescription>
          </DialogHeader>

          <div className="flex min-h-0 flex-1 flex-col space-y-2 overflow-hidden">
            <Label htmlFor="resume-import-json">JSON do currículo</Label>
            <AutoTextarea
              id="resume-import-json"
              className={`${TEXTAREA_CLASSNAME} min-h-64 max-h-[calc(100vh-18rem)] overflow-y-auto font-mono text-xs leading-5`}
              minHeight={256}
              value={jsonImportText}
              onChange={(e) => setJsonImportText(e.target.value)}
            />
          </div>

          <DialogFooter className="shrink-0">
            <Button type="button" variant="outline" onClick={() => handleImportJsonDialogOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="button" onClick={importResumeJson}>
              Aplicar JSON
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={isEmailDialogOpen} onOpenChange={setIsEmailDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Enviar Email</DialogTitle>
            <DialogDescription>
              Informe o email e a mensagem. O curriculo atual sera convertido em PDF e enviado em anexo via Resend.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="resume-email-profile">Perfil de envio</Label>
              <ToggleGroup
                type="single"
                value={emailSenderProfile}
                onValueChange={(value) => {
                  if (value) setEmailSenderProfile(value as EmailSenderProfile);
                }}
                variant="outline"
                className="grid w-full grid-cols-2"
              >
                <ToggleGroupItem value="personal" className="w-full justify-center">
                  Pessoal
                </ToggleGroupItem>
                <ToggleGroupItem value="company" className="w-full justify-center">
                  Empresa
                </ToggleGroupItem>
              </ToggleGroup>
            </div>
            <div className="space-y-2">
              <Label htmlFor="resume-email-to">Email</Label>
              <Input id="resume-email-to" type="email" value={emailTo} onChange={(e) => setEmailTo(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="resume-email-subject">Assunto</Label>
              <Input id="resume-email-subject" value={emailSubject} onChange={(e) => setEmailSubject(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="resume-email-message">Mensagem</Label>
              <AutoTextarea id="resume-email-message" className={TEXTAREA_CLASSNAME} value={emailMessage} onChange={(e) => setEmailMessage(e.target.value)} />
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setIsEmailDialogOpen(false)} disabled={isSendingEmail}>
              Cancelar
            </Button>
            <Button type="button" onClick={sendResumeEmail} disabled={isSendingEmail}>
              {isSendingEmail ? "Enviando..." : "Enviar"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <div className="grid gap-6 lg:grid-cols-[minmax(460px,560px)_minmax(0,1fr)_minmax(460px,560px)] lg:items-start">
        <div className="space-y-6 lg:pr-2">
          <Card>
            <CardHeader>
              <CardTitle>Aparência</CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="overflow-x-auto pb-1">
                <div className="flex min-w-max items-start gap-4">
                  {RESUME_THEME_COLOR_FIELDS.map((item) => (
                    <ThemeColorPalettePicker
                      key={item.field}
                      id={item.id}
                      label={item.label}
                      value={resume.theme[item.field]}
                      palette={item.palette}
                      onChange={(color) => updateTheme(item.field, color)}
                    />
                  ))}
                  <ThemePresetPicker onApply={applyThemePreset} />
                  <div className="flex w-12 flex-col items-center gap-2 text-center">
                    <label
                      htmlFor="photo-upload"
                      title={resume.profile.photoDataUrl ? "Trocar foto" : "Enviar foto"}
                      className="flex h-12 w-12 cursor-pointer items-center justify-center overflow-hidden rounded-full border border-dashed border-border bg-muted/30 text-muted-foreground transition hover:bg-muted/50"
                    >
                      {resume.profile.photoDataUrl ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={resume.profile.photoDataUrl} alt="Foto de perfil" className="h-full w-full object-cover" />
                      ) : (
                        <ImagePlusIcon className="size-4" />
                      )}
                    </label>
                    <span className="min-h-4 text-center text-xs font-medium leading-none text-muted-foreground">Profile</span>
                  </div>
                  {RESUME_PHOTO_FRAME_STYLE_OPTIONS.map((option) => {
                    const isEditorial = option.value === "editorial";
                    const isActive = resume.theme.photoFrameStyle === option.value;
                    const shortLabel = "Mod";

                    return (
                      <Fragment key={option.value}>
                        <div className="flex w-12 flex-col items-center gap-2 text-center">
                          <button
                            type="button"
                            aria-label={option.label}
                            title={option.label}
                            aria-pressed={isActive}
                            onClick={() => updateTheme("photoFrameStyle", option.value as ResumePhotoFrameStyle)}
                            className={`relative flex h-12 w-12 items-center justify-center overflow-hidden rounded-full border bg-background p-0 transition ${isActive ? "border-primary bg-primary/8 ring-2 ring-primary/15" : "border-border hover:border-primary/40 hover:bg-muted/30"}`}
                          >
                            <span
                              className={`relative block h-full w-full rounded-full ${isEditorial ? "" : "bg-[linear-gradient(135deg,rgba(79,70,229,0.10),rgba(15,23,42,0.03))]"}`}
                            >
                              {isEditorial ? (
                                <>
                                  <span className="absolute inset-[8px] rounded-full bg-[linear-gradient(180deg,rgba(79,70,229,0.18),#ffffff_70%)]" />
                                  <span className="absolute inset-y-[9px] left-[8px] w-[8px] rounded-full bg-primary/25" />
                                </>
                              ) : (
                                <>
                                  <span className="absolute inset-[9px] rounded-full border border-primary/20" />
                                  <span className="absolute left-[10px] top-[13px] h-[2px] w-[14px] bg-primary/70" />
                                  <span className="absolute bottom-[13px] right-[10px] h-[2px] w-[16px] bg-primary/45" />
                                </>
                              )}
                            </span>
                          </button>
                          <span className="min-h-4 text-center text-xs font-medium leading-none text-muted-foreground">{shortLabel}</span>
                        </div>
                        {isEditorial ? (
                          <div className="flex w-12 flex-col items-center gap-2 text-center">
                            <button
                              type="button"
                              aria-label="Alternar habilidades em maiúsculas"
                              title="Habilidades em maiúsculas"
                              aria-pressed={resume.theme.uppercaseSkills}
                              onClick={() => updateTheme("uppercaseSkills", !resume.theme.uppercaseSkills)}
                              className={`relative flex h-12 w-12 items-center justify-center overflow-hidden rounded-full border bg-background p-0 transition ${resume.theme.uppercaseSkills ? "border-primary bg-primary/10 ring-2 ring-primary/15" : "border-border hover:border-primary/40 hover:bg-muted/30"}`}
                            >
                              <span className="text-[11px] font-black uppercase tracking-[0.08em] text-foreground">AA</span>
                            </button>
                            <span className="min-h-4 text-center text-xs font-medium leading-none text-muted-foreground">Caps</span>
                          </div>
                        ) : null}
                      </Fragment>
                    );
                  })}
                </div>
              </div>
              <input id="photo-upload" type="file" accept="image/*" className="hidden" onChange={handlePhotoChange} />

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-3">
                    <Label htmlFor="font-scale">Escala da fonte</Label>
                    <Input
                      id="font-scale-number"
                      type="number"
                      min="85"
                      max="120"
                      step="1"
                      value={Math.round(resume.theme.fontScale * 100)}
                      onChange={(e) => updateTheme("fontScale", Number(e.target.value || 100) / 100)}
                      className="h-9 w-24 text-right"
                    />
                  </div>
                  <input
                    id="font-scale"
                    type="range"
                    min="85"
                    max="120"
                    step="1"
                    value={Math.round(resume.theme.fontScale * 100)}
                    onChange={(e) => updateTheme("fontScale", Number(e.target.value) / 100)}
                    className="w-full accent-primary"
                  />
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-3">
                    <Label htmlFor="sidebar-width">Largura da coluna</Label>
                    <Input
                      id="sidebar-width-number"
                      type="number"
                      min="220"
                      max="340"
                      step="1"
                      value={Math.round(resume.theme.sidebarWidth)}
                      onChange={(e) => updateTheme("sidebarWidth", Number(e.target.value || 275))}
                      className="h-9 w-24 text-right"
                    />
                  </div>
                  <input
                    id="sidebar-width"
                    type="range"
                    min="220"
                    max="340"
                    step="1"
                    value={Math.round(resume.theme.sidebarWidth)}
                    onChange={(e) => updateTheme("sidebarWidth", Number(e.target.value))}
                    className="w-full accent-primary"
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Dados Pessoais</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2 md:col-span-2">
                <Label>Nome completo</Label>
                <Input value={resume.profile.fullName} onChange={(e) => updateProfile("fullName", e.target.value)} />
              </div>
              <div className="space-y-2 md:col-span-2">
                <Label>Endereço</Label>
                <Input value={resume.profile.address} onChange={(e) => updateProfile("address", e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>Telefone</Label>
                <Input value={resume.profile.phone} onChange={(e) => updateProfile("phone", e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>Email</Label>
                <Input value={resume.profile.email} onChange={(e) => updateProfile("email", e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>LinkedIn</Label>
                <Input value={resume.profile.linkedin} onChange={(e) => updateProfile("linkedin", e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>GitHub</Label>
                <Input value={resume.profile.github} onChange={(e) => updateProfile("github", e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>Portfólio</Label>
                <Input value={resume.profile.portfolio} onChange={(e) => updateProfile("portfolio", e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>Estado civil</Label>
                <Input value={resume.profile.maritalStatus} onChange={(e) => updateProfile("maritalStatus", e.target.value)} />
              </div>
              <div className="space-y-2 md:col-span-2">
                <Label>Nacionalidade</Label>
                <Input value={resume.profile.nationality} onChange={(e) => updateProfile("nationality", e.target.value)} />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between gap-3">
              <CardTitle>Idiomas</CardTitle>
              <Button type="button" variant="outline" size="sm" onClick={() => setResume((current) => ({ ...current, languages: [...current.languages, createEmptyLanguage()] }))}>
                <PlusIcon className="mr-2 size-4" />
                Adicionar
              </Button>
            </CardHeader>
            <CardContent className="space-y-4">
              <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleLanguagesDragEnd}>
                <SortableContext items={resume.languages.map((_, index) => `language-${index}`)} strategy={verticalListSortingStrategy}>
                  {resume.languages.map((language, index) => (
                    <SortableResumeCard key={`language-${index}`} id={`language-${index}`} className="grid gap-3 md:grid-cols-2">
                      <div className="absolute right-4 top-2">
                        <Button type="button" variant="outline" size="sm" className="h-6 w-6 rounded-md border-red-500/40 p-0 text-red-500 hover:bg-red-500/10 hover:text-red-400" onPointerDown={(e) => e.stopPropagation()} onClick={() => setResume((current) => ({ ...current, languages: current.languages.filter((_, itemIndex) => itemIndex !== index) }))}>
                          <Trash2Icon className="size-2" />
                        </Button>
                      </div>
                      <div className="space-y-2">
                        <Label>Idioma</Label>
                        <Input value={language.name} onPointerDown={(e) => e.stopPropagation()} onChange={(e) => updateLanguage(index, "name", e.target.value)} />
                      </div>
                      <div className="space-y-2">
                        <Label>Nível</Label>
                        <Input value={language.level} onPointerDown={(e) => e.stopPropagation()} onChange={(e) => updateLanguage(index, "level", e.target.value)} />
                      </div>
                    </SortableResumeCard>
                  ))}
                </SortableContext>
              </DndContext>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between gap-3">
              <CardTitle>Formação</CardTitle>
              <Button type="button" variant="outline" size="sm" onClick={() => setResume((current) => ({ ...current, education: [...current.education, createEmptyEducation()] }))}>
                <PlusIcon className="mr-2 size-4" />
                Adicionar
              </Button>
            </CardHeader>
            <CardContent className="space-y-4">
              <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleEducationDragEnd}>
                <SortableContext items={resume.education.map((_, index) => `education-${index}`)} strategy={verticalListSortingStrategy}>
                  {resume.education.map((item, index) => (
                    <SortableResumeCard key={`education-${index}`} id={`education-${index}`} className="grid gap-3 md:grid-cols-2">
                      <div className="absolute right-4 top-2">
                        <Button type="button" variant="outline" size="sm" className="h-6 w-6 rounded-md border-red-500/40 p-0 text-red-500 hover:bg-red-500/10 hover:text-red-400" onPointerDown={(e) => e.stopPropagation()} onClick={() => setResume((current) => ({ ...current, education: current.education.filter((_, itemIndex) => itemIndex !== index) }))}>
                          <Trash2Icon className="size-2" />
                        </Button>
                      </div>
                      <div className="space-y-2 md:col-span-2">
                        <Label>Curso</Label>
                        <Input value={item.course} onPointerDown={(e) => e.stopPropagation()} onChange={(e) => updateEducation(index, "course", e.target.value)} />
                      </div>
                      <div className="space-y-2">
                        <Label>Conclusão</Label>
                        <Input value={item.conclusion} onPointerDown={(e) => e.stopPropagation()} onChange={(e) => updateEducation(index, "conclusion", e.target.value)} />
                      </div>
                      <div className="space-y-2">
                        <Label>Instituição</Label>
                        <Input value={item.institution} onPointerDown={(e) => e.stopPropagation()} onChange={(e) => updateEducation(index, "institution", e.target.value)} />
                      </div>
                    </SortableResumeCard>
                  ))}
                </SortableContext>
              </DndContext>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Certificações</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <Label>Uma certificação por linha</Label>
              <AutoTextarea
                className={TEXTAREA_CLASSNAME}
                value={certificationsText}
                onChange={(e) => setResume((current) => ({ ...current, certifications: splitLines(e.target.value) }))}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between gap-3">
              <CardTitle>Habilidades</CardTitle>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => {
                  setResume((current) => ({ ...current, skillGroups: [...current.skillGroups, createEmptySkillGroup()] }));
                  setSkillGroupItemDrafts((current) => [...current, ""]);
                }}
              >
                <PlusIcon className="mr-2 size-4" />
                Adicionar
              </Button>
            </CardHeader>
            <CardContent className="space-y-4">
              <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleSkillGroupsDragEnd}>
                <SortableContext items={resume.skillGroups.map((_, index) => `skill-group-${index}`)} strategy={verticalListSortingStrategy}>
                  {resume.skillGroups.map((group, index) => (
                    <SortableResumeCard
                      key={`skill-group-${index}`}
                      id={`skill-group-${index}`}
                      className="grid gap-3 pt-6"
                      useHandle
                      handleLabel="Reordenar grupo de habilidades"
                      handleClassName="absolute right-12 top-2.5"
                    >
                      <div className="absolute right-4 top-2">
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          className="h-6 w-6 rounded-md border-red-500/40 p-0 text-red-500 hover:bg-red-500/10 hover:text-red-400"
                          onPointerDown={(e) => e.stopPropagation()}
                          onClick={() => {
                            setResume((current) => ({ ...current, skillGroups: current.skillGroups.filter((_, itemIndex) => itemIndex !== index) }));
                            setSkillGroupItemDrafts((current) => current.filter((_, itemIndex) => itemIndex !== index));
                          }}
                        >
                          <Trash2Icon className="size-2" />
                        </Button>
                      </div>
                      <div className="space-y-2">
                        <Label>Título do grupo</Label>
                        <Input value={group.title} onPointerDown={(e) => e.stopPropagation()} onChange={(e) => updateSkillGroup(index, "title", e.target.value)} />
                      </div>
                      <div className="space-y-2">
                        <Label>Itens separados por vírgula</Label>
                        <AutoTextarea
                          className={TEXTAREA_CLASSNAME}
                          value={skillGroupItemDrafts[index] ?? joinSkillItems(group.items)}
                          onPointerDown={(e) => e.stopPropagation()}
                          onChange={(e) => updateSkillGroup(index, "items", e.target.value)}
                        />
                      </div>
                    </SortableResumeCard>
                  ))}
                </SortableContext>
              </DndContext>
            </CardContent>
          </Card>
        </div>

        <div className="min-w-0">
          <Card className="overflow-hidden">
            <CardHeader className="border-b bg-muted/20">
              <CardTitle>Preview do PDF</CardTitle>
            </CardHeader>
            <CardContent className="overflow-auto p-4">
              <ResumePreview data={resume} locale={resumeLocale} />
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6 lg:pl-2">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between gap-3">
              <CardTitle>Experiência Profissional</CardTitle>
              <Button type="button" variant="outline" size="sm" onClick={() => setResume((current) => ({ ...current, experiences: [...current.experiences, createEmptyExperience()] }))}>
                <PlusIcon className="mr-2 size-4" />
                Adicionar
              </Button>
            </CardHeader>
            <CardContent className="space-y-4">
              <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleExperiencesDragEnd}>
                <SortableContext items={resume.experiences.map((_, index) => `experience-${index}`)} strategy={verticalListSortingStrategy}>
                  {resume.experiences.map((item, index) => (
                    <SortableResumeCard key={`experience-${index}`} id={`experience-${index}`} className="grid gap-3 md:grid-cols-2">
                      <div className="absolute right-4 top-2">
                        <Button type="button" variant="outline" size="sm" className="h-6 w-6 rounded-md border-red-500/40 p-0 text-red-500 hover:bg-red-500/10 hover:text-red-400" onPointerDown={(e) => e.stopPropagation()} onClick={() => setResume((current) => ({ ...current, experiences: current.experiences.filter((_, itemIndex) => itemIndex !== index) }))}>
                          <Trash2Icon className="size-2" />
                        </Button>
                      </div>
                      <div className="space-y-2">
                        <Label>Cargo</Label>
                        <Input value={item.role} onPointerDown={(e) => e.stopPropagation()} onChange={(e) => updateExperience(index, "role", e.target.value)} />
                      </div>
                      <div className="space-y-2">
                        <Label>Duração</Label>
                        <Input value={item.duration} onPointerDown={(e) => e.stopPropagation()} onChange={(e) => updateExperience(index, "duration", e.target.value)} />
                      </div>
                      <div className="space-y-2 md:col-span-2">
                        <Label>Empresa</Label>
                        <Input value={item.company} onPointerDown={(e) => e.stopPropagation()} onChange={(e) => updateExperience(index, "company", e.target.value)} />
                      </div>
                      <div className="space-y-2 md:col-span-2">
                        <Label>Resumo</Label>
                        <AutoTextarea className={TEXTAREA_CLASSNAME} value={item.summary} onPointerDown={(e) => e.stopPropagation()} onChange={(e) => updateExperience(index, "summary", e.target.value)} />
                      </div>
                    </SortableResumeCard>
                  ))}
                </SortableContext>
              </DndContext>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between gap-3">
              <CardTitle>Problemas Resolvidos</CardTitle>
              <Button type="button" variant="outline" size="sm" onClick={() => setResume((current) => ({ ...current, solvedProblems: [...current.solvedProblems, createEmptySolvedProblem()] }))}>
                <PlusIcon className="mr-2 size-4" />
                Adicionar
              </Button>
            </CardHeader>
            <CardContent className="space-y-4">
              <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleSolvedProblemsDragEnd}>
                <SortableContext items={resume.solvedProblems.map((_, index) => `solved-problem-${index}`)} strategy={verticalListSortingStrategy}>
                  {resume.solvedProblems.map((item, index) => (
                    <SortableResumeCard key={`solved-problem-${index}`} id={`solved-problem-${index}`} className="grid gap-3">
                      <div className="absolute right-4 top-2">
                        <Button type="button" variant="outline" size="sm" className="h-6 w-6 rounded-md border-red-500/40 p-0 text-red-500 hover:bg-red-500/10 hover:text-red-400" onPointerDown={(e) => e.stopPropagation()} onClick={() => setResume((current) => ({ ...current, solvedProblems: current.solvedProblems.filter((_, itemIndex) => itemIndex !== index) }))}>
                          <Trash2Icon className="size-2" />
                        </Button>
                      </div>
                      <div className="space-y-2">
                        <Label>Título</Label>
                        <Input value={item.title} onPointerDown={(e) => e.stopPropagation()} onChange={(e) => updateSolvedProblem(index, "title", e.target.value)} />
                      </div>
                      <div className="space-y-2">
                        <Label>Contexto</Label>
                        <AutoTextarea className={TEXTAREA_CLASSNAME} value={item.context} onPointerDown={(e) => e.stopPropagation()} onChange={(e) => updateSolvedProblem(index, "context", e.target.value)} />
                      </div>
                      <div className="space-y-2">
                        <Label>Impacto / reconhecimento</Label>
                        <AutoTextarea className={TEXTAREA_CLASSNAME} value={item.impact} onPointerDown={(e) => e.stopPropagation()} onChange={(e) => updateSolvedProblem(index, "impact", e.target.value)} />
                      </div>
                    </SortableResumeCard>
                  ))}
                </SortableContext>
              </DndContext>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
