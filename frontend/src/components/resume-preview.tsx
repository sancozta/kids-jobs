"use client";

import {
  BriefcaseBusinessIcon,
  FlagIcon,
  GithubIcon,
  GlobeIcon,
  GraduationCapIcon,
  LanguagesIcon,
  LinkedinIcon,
  MailIcon,
  MapPinIcon,
  PhoneIcon,
  UserRoundIcon,
  XIcon,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState, type CSSProperties, type ClipboardEvent, type FormEvent, type KeyboardEvent } from "react";

import {
  DEFAULT_RESUME_LOCALE,
  getResumePreviewCopy,
  type ResumeDocument,
  type ResumeEducation,
  type ResumeExperience,
  type ResumeLanguage,
  type ResumeLocale,
  type ResumePhotoFrameStyle,
  type ResumeProfile,
  type ResumeSkillGroup,
  type ResumeSolvedProblem,
} from "@/lib/resume";

const PAGE_WIDTH_PX = 794;
const PAGE_HEIGHT_PX = 1123;
const PAGE_STYLE = {
  width: `${PAGE_WIDTH_PX}px`,
  height: `${PAGE_HEIGHT_PX}px`,
  boxSizing: "border-box",
} satisfies CSSProperties;

const INLINE_EDITABLE_TEXT_CLASSNAME = "bg-transparent outline-none focus:outline-none";
const PREVIEW_ACTION_BUTTON_CLASSNAME =
  "inline-flex h-3.5 w-3.5 items-center justify-center p-0 text-[#11111136] transition hover:text-[#11111182] focus-visible:text-[#11111182] focus-visible:outline-none";
const PREVIEW_ACTION_SLOT_CLASSNAME =
  "pointer-events-none absolute -right-2 top-0 z-10 opacity-0 transition duration-150 group-hover/resume-item:opacity-100 group-focus-within/resume-item:opacity-100";

type EditableProfileField = Exclude<keyof ResumeProfile, "photoDataUrl">;

export type ResumePreviewEditor = {
  updateProfile: (field: EditableProfileField, value: string) => void;
  updateLanguage: (index: number, field: keyof ResumeLanguage, value: string) => void;
  addLanguage: () => void;
  removeLanguage: (index: number) => void;
  updateEducation: (index: number, field: keyof ResumeEducation, value: string) => void;
  addEducation: () => void;
  removeEducation: (index: number) => void;
  updateExperience: (index: number, field: keyof ResumeExperience, value: string) => void;
  addExperience: () => void;
  removeExperience: (index: number) => void;
  updateCertification: (index: number, value: string) => void;
  addCertification: () => void;
  removeCertification: (index: number) => void;
  updateSkillGroup: (index: number, field: keyof ResumeSkillGroup, value: string | string[]) => void;
  addSkillGroup: () => void;
  removeSkillGroup: (index: number) => void;
  updateSolvedProblem: (index: number, field: keyof ResumeSolvedProblem, value: string) => void;
  addSolvedProblem: () => void;
  removeSolvedProblem: (index: number) => void;
};

type ContactLink = {
  label: string;
  value: string;
  href?: string;
  icon: React.ReactNode;
  field: EditableProfileField;
};

function scalePx(value: number, scale: number): string {
  return `${(value * scale).toFixed(2)}px`;
}

function PreviewActionButton({
  label,
  onClick,
}: {
  label: string;
  onClick: () => void;
}) {
  return (
    <button type="button" aria-label={label} title={label} onClick={onClick} className={PREVIEW_ACTION_BUTTON_CLASSNAME}>
      <XIcon className="size-[10px]" strokeWidth={2.35} />
    </button>
  );
}

function PreviewActionSlot({
  label,
  onClick,
}: {
  label: string;
  onClick: () => void;
}) {
  return (
    <div className={PREVIEW_ACTION_SLOT_CLASSNAME}>
      <div className="pointer-events-auto">
        <PreviewActionButton label={label} onClick={onClick} />
      </div>
    </div>
  );
}

function InlineEditableText({
  value,
  onChange,
  className = "",
  style,
  placeholder = "",
  as = "div",
  multiline = false,
  autoFocus = false,
  onEditingChange,
}: {
  value: string;
  onChange: (value: string) => void;
  className?: string;
  style?: CSSProperties;
  placeholder?: string;
  as?: "div" | "p" | "span";
  multiline?: boolean;
  autoFocus?: boolean;
  onEditingChange?: (editing: boolean) => void;
}) {
  const Tag = as;
  const ref = useRef<HTMLElement | null>(null);
  const draftValueRef = useRef(value);
  const [isEditing, setIsEditing] = useState(autoFocus);
  const resolvedColor = typeof style?.color === "string" ? style.color : "#111111";
  const mergedStyle: CSSProperties = {
    color: resolvedColor,
    caretColor: resolvedColor,
    WebkitTextFillColor: resolvedColor,
    backgroundColor: "transparent",
    borderWidth: 0,
    borderRadius: 0,
    boxShadow: "none",
    margin: 0,
    padding: 0,
    ...style,
  };

  const normalizeValue = (element: HTMLElement) => {
    const rawValue = multiline ? element.innerText : element.textContent ?? "";
    return multiline ? rawValue.replace(/\r/g, "") : rawValue.replace(/\r?\n+/g, " ");
  };

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const nextValue = isEditing ? draftValueRef.current || "" : value || "";
    const currentValue = multiline ? element.innerText.replace(/\r/g, "") : element.textContent ?? "";
    if (currentValue === nextValue) return;
    if (multiline) {
      element.innerText = nextValue;
      return;
    }
    element.textContent = nextValue;
  }, [isEditing, multiline, value]);

  useEffect(() => {
    const element = ref.current;
    if (!element || !isEditing) return;
    element.focus();
    const selection = window.getSelection();
    if (!selection) return;
    const range = document.createRange();
    range.selectNodeContents(element);
    range.collapse(false);
    selection.removeAllRanges();
    selection.addRange(range);
  }, [isEditing]);

  useEffect(() => {
    if (autoFocus) {
      draftValueRef.current = value;
      setIsEditing(true);
    }
  }, [autoFocus, value]);

  useEffect(() => {
    if (!isEditing) {
      draftValueRef.current = value;
    }
  }, [isEditing, value]);

  const handleInput = (event: FormEvent<HTMLElement>) => {
    draftValueRef.current = normalizeValue(event.currentTarget);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (!multiline && event.key === "Enter") {
      event.preventDefault();
      (event.currentTarget as HTMLElement).blur();
      return;
    }

    if (event.key === "Escape") {
      event.preventDefault();
      draftValueRef.current = value;
      const element = event.currentTarget as HTMLElement;
      if (multiline) {
        element.innerText = value;
      } else {
        element.textContent = value;
      }
      element.blur();
    }
  };

  const handlePaste = (event: ClipboardEvent<HTMLElement>) => {
    event.preventDefault();
    const pastedText = event.clipboardData.getData("text/plain");
    const normalizedText = multiline ? pastedText : pastedText.replace(/\r?\n+/g, " ");
    document.execCommand("insertText", false, normalizedText);
  };

  const activateEditing = () => {
    if (isEditing) return;
    draftValueRef.current = value;
    setIsEditing(true);
    onEditingChange?.(true);
  };

  const handleBlur = (event: FormEvent<HTMLElement>) => {
    const nextValue = normalizeValue(event.currentTarget);
    draftValueRef.current = nextValue;
    onChange(nextValue);
    setIsEditing(false);
    onEditingChange?.(false);
  };

  if (!isEditing) {
    return (
      <Tag
        tabIndex={0}
        onClick={activateEditing}
        onFocus={activateEditing}
        className={`${className} ${value ? "" : "text-[#11111140]"}`}
        style={mergedStyle}
      >
        {value || placeholder}
      </Tag>
    );
  }

  return (
    <Tag
      ref={(node) => {
        ref.current = node as HTMLElement | null;
      }}
      contentEditable={isEditing}
      suppressContentEditableWarning
      spellCheck={false}
      role="textbox"
      tabIndex={0}
      aria-label={placeholder}
      onInput={handleInput}
      onKeyDown={handleKeyDown}
      onPaste={handlePaste}
      onClick={activateEditing}
      onFocus={activateEditing}
      onBlur={handleBlur}
      className={`${INLINE_EDITABLE_TEXT_CLASSNAME} ${isEditing ? "cursor-text empty:before:pointer-events-none empty:before:text-[#11111140] empty:before:content-[attr(data-placeholder)]" : ""} ${className}`}
      data-placeholder={isEditing ? placeholder : undefined}
      style={mergedStyle}
    >
      {value}
    </Tag>
  );
}

function SectionTitle({
  children,
  accentColor,
  fontScale,
  onClick,
  actionLabel,
}: {
  children: string;
  accentColor: string;
  fontScale: number;
  onClick?: () => void;
  actionLabel?: string;
}) {
  const titleStyle = {
    fontSize: scalePx(11, fontScale),
    "--resume-title-hover": accentColor,
  } as CSSProperties;

  return (
    <div className="mb-3 flex items-center gap-3">
      <span className="h-px flex-1" style={{ backgroundColor: `${accentColor}55` }} />
      {onClick ? (
        <button
          type="button"
          onClick={onClick}
          aria-label={actionLabel ?? children}
          title={actionLabel ?? children}
          className="cursor-pointer font-black uppercase tracking-[0.16em] text-[#161616] transition-colors hover:text-[var(--resume-title-hover)] focus-visible:text-[var(--resume-title-hover)] focus-visible:outline-none"
          style={titleStyle}
        >
          {children}
        </button>
      ) : (
        <h3 className="font-black uppercase tracking-[0.16em] text-[#161616]" style={titleStyle}>
          {children}
        </h3>
      )}
      <span className="h-px flex-1" style={{ backgroundColor: `${accentColor}55` }} />
    </div>
  );
}

function SidebarBlock({
  title,
  children,
  fontScale,
  accentColor,
  onTitleClick,
  titleActionLabel,
}: {
  title: string;
  children: React.ReactNode;
  fontScale: number;
  accentColor: string;
  onTitleClick?: () => void;
  titleActionLabel?: string;
}) {
  const titleStyle = {
    fontSize: scalePx(10, fontScale),
    "--resume-title-hover": accentColor,
  } as CSSProperties;

  return (
    <section className="group/resume-section space-y-2">
      {onTitleClick ? (
        <button
          type="button"
          onClick={onTitleClick}
          aria-label={titleActionLabel ?? title}
          title={titleActionLabel ?? title}
          className="cursor-pointer text-left font-black uppercase tracking-[0.16em] text-[#171717] transition-colors hover:text-[var(--resume-title-hover)] focus-visible:text-[var(--resume-title-hover)] focus-visible:outline-none"
          style={titleStyle}
        >
          {title}
        </button>
      ) : (
        <h3 className="font-black uppercase tracking-[0.16em] text-[#171717]" style={titleStyle}>
          {title}
        </h3>
      )}
      <div className="space-y-2 leading-[1.45] text-[#202020]" style={{ fontSize: scalePx(11, fontScale) }}>
        {children}
      </div>
    </section>
  );
}

function ContactRow({
  icon,
  label,
  value,
  href,
  accentColor,
  fontScale,
  editable = false,
  onValueChange,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  href?: string;
  accentColor: string;
  fontScale: number;
  editable?: boolean;
  onValueChange?: (value: string) => void;
}) {
  const content = editable && onValueChange ? (
    <InlineEditableText
      as="span"
      value={value}
      onChange={onValueChange}
      className="block break-words font-medium leading-[1.3] text-[#111]"
      style={{ fontSize: scalePx(10.5, fontScale) }}
      placeholder={label}
    />
  ) : href ? (
    <a href={href} target="_blank" rel="noreferrer" className="underline decoration-transparent transition hover:decoration-current">
      {value}
    </a>
  ) : (
    <span>{value}</span>
  );

  return (
    <div className="flex items-start gap-2.5">
      <span className="mt-1 shrink-0" style={{ color: accentColor }}>
        {icon}
      </span>
      <div className="min-w-0 flex-1">
        <div className="font-black uppercase tracking-[0.12em] text-[#111]" style={{ fontSize: scalePx(9, fontScale) }}>
          {label}
        </div>
        <div className="break-words font-medium leading-[1.3] text-[#111]" style={{ fontSize: scalePx(10.5, fontScale) }}>
          {content}
        </div>
      </div>
    </div>
  );
}

function EducationItem({
  course,
  conclusion,
  institution,
  fontScale,
  conclusionLabel,
  screenPreview = false,
  editable = false,
  onCourseChange,
  onConclusionChange,
  onInstitutionChange,
  onRemove,
}: {
  course: string;
  conclusion: string;
  institution: string;
  fontScale: number;
  conclusionLabel: string;
  screenPreview?: boolean;
  editable?: boolean;
  onCourseChange?: (value: string) => void;
  onConclusionChange?: (value: string) => void;
  onInstitutionChange?: (value: string) => void;
  onRemove?: () => void;
}) {
  const previewCourseStyle = screenPreview ? { marginBottom: scalePx(4, fontScale) } : undefined;
  const previewConclusionStyle = screenPreview ? { marginBottom: scalePx(3, fontScale) } : undefined;

  return (
    <div className={`space-y-0 ${editable ? "group/resume-item relative" : ""}`}>
      {editable && onRemove ? <PreviewActionSlot label="Remover formação" onClick={onRemove} /> : null}
      {editable && onCourseChange ? (
        <InlineEditableText
          as="div"
          value={course}
          onChange={onCourseChange}
          className="font-black uppercase tracking-[0.12em] leading-[1.25] text-[#111]"
          style={{ fontSize: scalePx(9, fontScale), ...previewCourseStyle }}
          placeholder="Curso"
        />
      ) : (
        <div className="font-black uppercase tracking-[0.12em] leading-[1.25] text-[#111]" style={{ fontSize: scalePx(9, fontScale), ...previewCourseStyle }}>
          {course}
        </div>
      )}
      {editable && onConclusionChange ? (
        <div className="flex items-center gap-1 font-semibold uppercase tracking-[0.08em] text-[#111]" style={{ fontSize: scalePx(9, fontScale), ...previewConclusionStyle }}>
          <span className="shrink-0">{conclusionLabel}</span>
          <InlineEditableText
            as="span"
            value={conclusion}
            onChange={onConclusionChange}
            className="inline-block min-w-[1ch]"
            style={{ fontSize: scalePx(9, fontScale) }}
            placeholder="Ano"
          />
        </div>
      ) : (
        <div className="font-semibold uppercase tracking-[0.08em] text-[#111]" style={{ fontSize: scalePx(9, fontScale), ...previewConclusionStyle }}>
          {conclusionLabel} {conclusion}
        </div>
      )}
      {editable && onInstitutionChange ? (
        <InlineEditableText
          as="div"
          value={institution}
          onChange={onInstitutionChange}
          className="font-medium uppercase tracking-[0.06em] text-[#111]"
          style={{ fontSize: scalePx(9.5, fontScale) }}
          placeholder="Instituição"
        />
      ) : (
        <div className="font-medium uppercase tracking-[0.06em] text-[#111]" style={{ fontSize: scalePx(9.5, fontScale) }}>
          {institution}
        </div>
      )}
    </div>
  );
}

function ExperienceItem({
  role,
  duration,
  company,
  summary,
  accentColor,
  fontScale,
  editable = false,
  onRoleChange,
  onDurationChange,
  onCompanyChange,
  onSummaryChange,
  onRemove,
}: {
  role: string;
  duration: string;
  company: string;
  summary: string;
  accentColor: string;
  fontScale: number;
  editable?: boolean;
  onRoleChange?: (value: string) => void;
  onDurationChange?: (value: string) => void;
  onCompanyChange?: (value: string) => void;
  onSummaryChange?: (value: string) => void;
  onRemove?: () => void;
}) {
  return (
    <article className={`space-y-1.5 border-b border-[#11111114] pb-3 last:border-b-0 last:pb-0 ${editable ? "group/resume-item relative" : ""}`}>
      {editable && onRemove ? <PreviewActionSlot label="Remover experiência" onClick={onRemove} /> : null}
      <div className="flex items-start gap-2.5">
        <span className="mt-0.5 shrink-0" style={{ color: accentColor }}>
          <BriefcaseBusinessIcon className="size-3.5" strokeWidth={2.2} />
        </span>
        <div className="min-w-0 flex-1 space-y-0.5">
          {editable && onRoleChange && onDurationChange ? (
            <div className="font-black uppercase leading-[1.25] text-[#0f0f0f]" style={{ fontSize: scalePx(10.5, fontScale) }}>
              <InlineEditableText
                as="span"
                value={role}
                onChange={onRoleChange}
                className="inline"
                style={{ fontSize: scalePx(10.5, fontScale) }}
                placeholder="Cargo"
              />
              {" - "}
              <InlineEditableText
                as="span"
                value={duration}
                onChange={onDurationChange}
                className="inline"
                style={{ fontSize: scalePx(10.5, fontScale) }}
                placeholder="Duração"
              />
            </div>
          ) : (
            <div className="font-black uppercase leading-[1.25] text-[#0f0f0f]" style={{ fontSize: scalePx(10.5, fontScale) }}>
              {role} - {duration}
            </div>
          )}
          {editable && onCompanyChange ? (
            <InlineEditableText
              as="div"
              value={company}
              onChange={onCompanyChange}
              className="font-semibold uppercase tracking-[0.1em] text-[#5f5f5f]"
              style={{ fontSize: scalePx(9, fontScale) }}
              placeholder="Empresa"
            />
          ) : (
            <div className="font-semibold uppercase tracking-[0.1em] text-[#5f5f5f]" style={{ fontSize: scalePx(9, fontScale) }}>
              {company}
            </div>
          )}
        </div>
      </div>
      {editable && onSummaryChange ? (
        <InlineEditableText
          as="p"
          multiline
          value={summary}
          onChange={onSummaryChange}
          className="pl-6 text-justify leading-[1.34] text-[#212121]"
          style={{ fontSize: scalePx(9.5, fontScale) }}
          placeholder="Resumo"
        />
      ) : (
        <p className="pl-6 text-justify leading-[1.34] text-[#212121]" style={{ fontSize: scalePx(9.5, fontScale) }}>
          {summary}
        </p>
      )}
    </article>
  );
}

function SolvedProblemItem({
  title,
  context,
  impact,
  accentColor,
  fontScale,
  impactLabel,
  screenPreview = false,
  editable = false,
  onTitleChange,
  onContextChange,
  onImpactChange,
  onRemove,
}: {
  title: string;
  context: string;
  impact: string;
  accentColor: string;
  fontScale: number;
  impactLabel: string;
  screenPreview?: boolean;
  editable?: boolean;
  onTitleChange?: (value: string) => void;
  onContextChange?: (value: string) => void;
  onImpactChange?: (value: string) => void;
  onRemove?: () => void;
}) {
  const [impactEditing, setImpactEditing] = useState(false);
  const previewTitleStyle = screenPreview ? { marginBottom: scalePx(5, fontScale) } : undefined;
  const previewContextStyle = screenPreview ? { marginBottom: scalePx(3, fontScale) } : undefined;

  return (
    <article
      className={`break-inside-avoid border-b border-[#11111114] last:border-b-0 last:pb-0 ${screenPreview ? "space-y-0 pb-4" : "space-y-1.5 pb-3"} ${editable ? "group/resume-item relative" : ""}`}
    >
      {editable && onRemove ? <PreviewActionSlot label="Remover problema resolvido" onClick={onRemove} /> : null}
      {editable && onTitleChange ? (
        <InlineEditableText
          as="div"
          value={title}
          onChange={onTitleChange}
          className="font-black uppercase leading-[1.25]"
          style={{ color: accentColor, fontSize: scalePx(10, fontScale), ...previewTitleStyle }}
          placeholder="Título"
        />
      ) : (
        <div className="font-black uppercase leading-[1.25] text-[#111]" style={{ fontSize: scalePx(10, fontScale), color: accentColor, ...previewTitleStyle }}>
          {title}
        </div>
      )}
      {editable && onContextChange ? (
        <InlineEditableText
          as="p"
          multiline
          value={context}
          onChange={onContextChange}
          className={`${screenPreview ? "leading-[1.42]" : "leading-[1.34]"} text-[#212121]`}
          style={{ fontSize: scalePx(9.4, fontScale), ...previewContextStyle }}
          placeholder="Contexto"
        />
      ) : (
        <p className={`${screenPreview ? "leading-[1.42]" : "leading-[1.34]"} text-[#212121]`} style={{ fontSize: scalePx(9.4, fontScale), ...previewContextStyle }}>
          {context}
        </p>
      )}
      {editable && onImpactChange ? (
        impactEditing ? (
          <InlineEditableText
            as="p"
            multiline
            autoFocus
            value={impact}
            onChange={onImpactChange}
            onEditingChange={setImpactEditing}
            className={`${screenPreview ? "leading-[1.42]" : "leading-[1.34]"} text-[#111]`}
            style={{ fontSize: scalePx(9.4, fontScale) }}
            placeholder="Impacto"
          />
        ) : (
          <p className={`${screenPreview ? "leading-[1.42]" : "leading-[1.34]"} text-[#111]`} style={{ fontSize: scalePx(9.4, fontScale) }}>
            <span className="font-black">{impactLabel}:</span>{" "}
            <span
              role="button"
              tabIndex={0}
              className="cursor-text outline-none"
              onClick={() => setImpactEditing(true)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  setImpactEditing(true);
                }
              }}
            >
              {impact}
            </span>
          </p>
        )
      ) : (
        <p className={`${screenPreview ? "leading-[1.42]" : "leading-[1.34]"} text-[#111]`} style={{ fontSize: scalePx(9.4, fontScale) }}>
          <span className="font-black">{impactLabel}:</span> {impact}
        </p>
      )}
    </article>
  );
}

function ResumePageFrame({
  children,
  pageBackground,
  printMode,
}: {
  children: React.ReactNode;
  pageBackground: string;
  printMode: boolean;
}) {
  return (
    <section
      className={`resume-page overflow-hidden border border-[#11111110] ${printMode ? "" : "rounded-[28px] shadow-[0_30px_100px_rgba(15,23,42,0.12)]"}`}
      style={{ ...PAGE_STYLE, backgroundColor: pageBackground }}
    >
      {children}
    </section>
  );
}

function ResumePageViewport({
  children,
  printMode,
}: {
  children: React.ReactNode;
  printMode: boolean;
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [scale, setScale] = useState(1);

  useEffect(() => {
    if (printMode || !ref.current || typeof ResizeObserver === "undefined") return;

    const updateScale = () => {
      const width = ref.current?.clientWidth ?? PAGE_WIDTH_PX;
      setScale(Math.min(1, width / PAGE_WIDTH_PX));
    };

    updateScale();

    const observer = new ResizeObserver(updateScale);
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, [printMode]);

  if (printMode) {
    return <div className="mx-auto w-fit">{children}</div>;
  }

  return (
    <div ref={ref} className="w-full">
      <div
        className="mx-auto origin-top"
        style={{
          width: `${PAGE_WIDTH_PX * scale}px`,
          height: `${PAGE_HEIGHT_PX * scale}px`,
        }}
      >
        <div
          style={{
            width: `${PAGE_WIDTH_PX}px`,
            height: `${PAGE_HEIGHT_PX}px`,
            transform: `scale(${scale})`,
            transformOrigin: "top left",
          }}
        >
          {children}
        </div>
      </div>
    </div>
  );
}

function ProfilePhotoFrame({
  fullName,
  photoDataUrl,
  accentColor,
  frameStyle,
}: {
  fullName: string;
  photoDataUrl?: string;
  accentColor: string;
  frameStyle: ResumePhotoFrameStyle;
}) {
  const media = photoDataUrl ? (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={photoDataUrl} alt={fullName} className="size-full object-cover object-center" />
  ) : (
    <div className="flex size-full items-center justify-center bg-[radial-gradient(circle_at_top,_rgba(255,255,255,0.72),_rgba(255,255,255,0.18))]">
      <UserRoundIcon className="size-14 text-[#202020]/70" strokeWidth={1.8} />
    </div>
  );

  if (frameStyle === "technical") {
    return (
      <div className="mx-auto w-fit">
        <div className="relative">
          <div
            className="absolute -inset-2 rounded-[4px] border"
            style={{
              borderColor: `${accentColor}2f`,
              background: `linear-gradient(135deg, ${accentColor}12 0%, transparent 48%), repeating-linear-gradient(0deg, transparent 0 15px, rgba(15,23,42,0.04) 15px 16px)`,
            }}
          />
          <div className="absolute -left-2 top-4 h-[2px] w-10" style={{ backgroundColor: accentColor }} />
          <div className="absolute -bottom-2 right-4 h-[2px] w-12" style={{ backgroundColor: `${accentColor}88` }} />
          <div
            className="relative flex h-[148px] w-[138px] items-center justify-center overflow-hidden rounded-[4px] border border-[#1111111a] bg-white shadow-[0_18px_36px_rgba(15,23,42,0.12)]"
            style={{ background: `linear-gradient(180deg, ${accentColor}10 0%, #ffffff 26%)` }}
          >
            {media}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto w-fit">
      <div className="relative">
        <div className="absolute inset-0 translate-x-2.5 translate-y-2.5 rounded-[10px]" style={{ backgroundColor: `${accentColor}1f` }} />
        <div
          className="relative flex h-[150px] w-[138px] items-center justify-center overflow-hidden rounded-[10px] border border-[#11111114] bg-white shadow-[0_18px_40px_rgba(15,23,42,0.14)]"
          style={{ background: `linear-gradient(180deg, ${accentColor}14 0%, #ffffff 34%)` }}
        >
          {media}
        </div>
      </div>
    </div>
  );
}

export function ResumePreview({
  data,
  locale = DEFAULT_RESUME_LOCALE,
  printMode = false,
  pdfMode = false,
  screenPreview = false,
  editable = false,
  editor,
}: {
  data: ResumeDocument;
  locale?: ResumeLocale;
  printMode?: boolean;
  pdfMode?: boolean;
  screenPreview?: boolean;
  editable?: boolean;
  editor?: ResumePreviewEditor;
}) {
  const { accentColor, sidebarBackground, pageBackground, fontScale, sidebarWidth, photoFrameStyle, uppercaseSkills } = data.theme;
  const copy = getResumePreviewCopy(locale);
  const canEdit = Boolean(screenPreview && editable && editor && !printMode);
  const contactLinks = useMemo<ContactLink[]>(
    () => [
      { label: copy.address, value: data.profile.address, icon: <MapPinIcon className="size-3.5" strokeWidth={2.3} />, field: "address" },
      { label: copy.phone, value: data.profile.phone, icon: <PhoneIcon className="size-3.5" strokeWidth={2.3} />, field: "phone" },
      { label: copy.email, value: data.profile.email, href: `mailto:${data.profile.email}`, icon: <MailIcon className="size-3.5" strokeWidth={2.3} />, field: "email" },
      {
        label: copy.linkedin,
        value: data.profile.linkedin,
        href: `https://${data.profile.linkedin.replace(/^https?:\/\//, "")}`,
        icon: <LinkedinIcon className="size-3.5" strokeWidth={2.3} />,
        field: "linkedin",
      },
      {
        label: copy.github,
        value: data.profile.github,
        href: `https://${data.profile.github.replace(/^https?:\/\//, "")}`,
        icon: <GithubIcon className="size-3.5" strokeWidth={2.3} />,
        field: "github",
      },
      {
        label: copy.portfolio,
        value: data.profile.portfolio,
        href: `https://${data.profile.portfolio.replace(/^https?:\/\//, "")}`,
        icon: <GlobeIcon className="size-3.5" strokeWidth={2.3} />,
        field: "portfolio",
      },
    ],
    [
      copy.address,
      copy.email,
      copy.github,
      copy.linkedin,
      copy.phone,
      copy.portfolio,
      data.profile.address,
      data.profile.email,
      data.profile.github,
      data.profile.linkedin,
      data.profile.phone,
      data.profile.portfolio,
    ],
  );

  const pageStackGap = printMode ? "0px" : screenPreview ? "25px" : pdfMode ? "0px" : "24px";

  return (
    <div className={`flex w-full flex-col ${printMode ? "items-center" : "items-start"}`} style={{ gap: pageStackGap }}>
      <ResumePageViewport printMode={printMode}>
        <ResumePageFrame pageBackground={pageBackground} printMode={printMode}>
          <div className="grid h-full" style={{ gridTemplateColumns: `${sidebarWidth}px minmax(0, 1fr)` }}>
            <aside className="flex h-full flex-col gap-7 px-6 py-7" style={{ backgroundColor: sidebarBackground }}>
              <div className="space-y-4 text-center">
                <ProfilePhotoFrame
                  fullName={data.profile.fullName}
                  photoDataUrl={data.profile.photoDataUrl}
                  accentColor={accentColor}
                  frameStyle={photoFrameStyle}
                />
                {canEdit && editor ? (
                  <InlineEditableText
                    as="div"
                    value={data.profile.fullName}
                    onChange={(value) => editor.updateProfile("fullName", value)}
                    className="text-center font-black uppercase tracking-[0.03em] text-[#161616]"
                    style={{ fontSize: scalePx(16, fontScale) }}
                    placeholder="Nome completo"
                  />
                ) : (
                  <div className="font-black uppercase tracking-[0.03em] text-[#161616]" style={{ fontSize: scalePx(16, fontScale) }}>
                    {data.profile.fullName}
                  </div>
                )}
              </div>

              <SidebarBlock title={copy.contact} fontScale={fontScale}>
                {contactLinks.map((item) => (
                  <ContactRow
                    key={item.label}
                    {...item}
                    accentColor={accentColor}
                    fontScale={fontScale}
                    editable={canEdit}
                    onValueChange={canEdit && editor ? (value) => editor.updateProfile(item.field, value) : undefined}
                  />
                ))}
                <ContactRow
                  label={copy.maritalStatus}
                  value={data.profile.maritalStatus}
                  accentColor={accentColor}
                  fontScale={fontScale}
                  icon={<UserRoundIcon className="size-3.5" strokeWidth={2.3} />}
                  editable={canEdit}
                  onValueChange={canEdit && editor ? (value) => editor.updateProfile("maritalStatus", value) : undefined}
                />
                <ContactRow
                  label={copy.nationality}
                  value={data.profile.nationality}
                  accentColor={accentColor}
                  fontScale={fontScale}
                  icon={<FlagIcon className="size-3.5" strokeWidth={2.3} />}
                  editable={canEdit}
                  onValueChange={canEdit && editor ? (value) => editor.updateProfile("nationality", value) : undefined}
                />
              </SidebarBlock>

              <SidebarBlock
                title={copy.languages}
                fontScale={fontScale}
                accentColor={accentColor}
                onTitleClick={canEdit && editor ? editor.addLanguage : undefined}
                titleActionLabel={locale === "en" ? "Add language" : "Adicionar idioma"}
              >
                {data.languages.map((language, index) => (
                  <div key={`${language.name}-${index}`} className={`flex items-start gap-2.5 ${canEdit ? "group/resume-item relative" : ""}`}>
                    {canEdit && editor ? <PreviewActionSlot label="Remover idioma" onClick={() => editor.removeLanguage(index)} /> : null}
                    <span className="mt-1 shrink-0" style={{ color: accentColor }}>
                      <LanguagesIcon className="size-3.5" strokeWidth={2.3} />
                    </span>
                    <div className="min-w-0 flex-1">
                      {canEdit && editor ? (
                        <>
                          <InlineEditableText
                            as="div"
                            value={language.name}
                            onChange={(value) => editor.updateLanguage(index, "name", value)}
                            className="font-black uppercase tracking-[0.12em] text-[#111]"
                            style={{ fontSize: scalePx(9, fontScale) }}
                            placeholder="Idioma"
                          />
                          <InlineEditableText
                            as="div"
                            value={language.level}
                            onChange={(value) => editor.updateLanguage(index, "level", value)}
                            className="text-[#111]"
                            style={{ fontSize: scalePx(9.5, fontScale) }}
                            placeholder="Nível"
                          />
                        </>
                      ) : (
                        <>
                          <div className="font-black uppercase tracking-[0.12em] text-[#111]" style={{ fontSize: scalePx(9, fontScale) }}>
                            {language.name}
                          </div>
                          <div className="text-[#111]" style={{ fontSize: scalePx(9.5, fontScale) }}>
                            {language.level}
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                ))}
              </SidebarBlock>

              <SidebarBlock
                title={copy.education}
                fontScale={fontScale}
                accentColor={accentColor}
                onTitleClick={canEdit && editor ? editor.addEducation : undefined}
                titleActionLabel={locale === "en" ? "Add education" : "Adicionar formação"}
              >
                {data.education.map((item, index) => (
                  <div key={`${item.course}-${index}`} className="flex items-start gap-2.5">
                    <span className="mt-1 shrink-0" style={{ color: accentColor }}>
                      <GraduationCapIcon className="size-3.5" strokeWidth={2.2} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <EducationItem
                        {...item}
                        fontScale={fontScale}
                        conclusionLabel={copy.conclusion}
                        screenPreview={screenPreview}
                        editable={canEdit}
                        onCourseChange={canEdit && editor ? (value) => editor.updateEducation(index, "course", value) : undefined}
                        onConclusionChange={canEdit && editor ? (value) => editor.updateEducation(index, "conclusion", value) : undefined}
                        onInstitutionChange={canEdit && editor ? (value) => editor.updateEducation(index, "institution", value) : undefined}
                        onRemove={canEdit && editor ? () => editor.removeEducation(index) : undefined}
                      />
                    </div>
                  </div>
                ))}
              </SidebarBlock>
            </aside>

            <main className="flex h-full flex-col gap-4 px-7 py-7">
              <SectionTitle
                accentColor={accentColor}
                fontScale={fontScale}
                onClick={canEdit && editor ? editor.addExperience : undefined}
                actionLabel={locale === "en" ? "Add experience" : "Adicionar experiência"}
              >
                {copy.experience}
              </SectionTitle>
              <div className="group/resume-section space-y-3">
                {data.experiences.map((experience, index) => (
                  <ExperienceItem
                    key={`${experience.role}-${index}`}
                    {...experience}
                    accentColor={accentColor}
                    fontScale={fontScale}
                    editable={canEdit}
                    onRoleChange={canEdit && editor ? (value) => editor.updateExperience(index, "role", value) : undefined}
                    onDurationChange={canEdit && editor ? (value) => editor.updateExperience(index, "duration", value) : undefined}
                    onCompanyChange={canEdit && editor ? (value) => editor.updateExperience(index, "company", value) : undefined}
                    onSummaryChange={canEdit && editor ? (value) => editor.updateExperience(index, "summary", value) : undefined}
                    onRemove={canEdit && editor ? () => editor.removeExperience(index) : undefined}
                  />
                ))}
              </div>
            </main>
          </div>
        </ResumePageFrame>
      </ResumePageViewport>

      <ResumePageViewport printMode={printMode}>
        <ResumePageFrame pageBackground={pageBackground} printMode={printMode}>
          <div className="flex h-full flex-col gap-5 px-8 py-8">
            <div className="group/resume-section">
              <SectionTitle
                accentColor={accentColor}
                fontScale={fontScale}
                onClick={canEdit && editor ? editor.addCertification : undefined}
                actionLabel={locale === "en" ? "Add certification" : "Adicionar certificação"}
              >
                {copy.certifications}
              </SectionTitle>
              <div className="grid grid-cols-2 gap-x-6 gap-y-2.5">
                {data.certifications.map((item, index) => (
                  <div key={`${item}-${index}`} className={`leading-[1.32] text-[#1f1f1f] ${canEdit ? "group/resume-item relative" : ""}`} style={{ fontSize: scalePx(9.5, fontScale) }}>
                    {canEdit && editor ? <PreviewActionSlot label="Remover certificação" onClick={() => editor.removeCertification(index)} /> : null}
                    <div className="flex items-start gap-2">
                      <span className="mr-0.5 font-black" style={{ color: accentColor }}>
                        •
                      </span>
                      {canEdit && editor ? (
                        <InlineEditableText
                          as="span"
                          value={item}
                          onChange={(value) => editor.updateCertification(index, value)}
                          className="block leading-[1.32] text-[#1f1f1f]"
                          style={{ fontSize: scalePx(9.5, fontScale) }}
                          placeholder="Certificação"
                        />
                      ) : (
                        <span>{item}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="group/resume-section">
              <SectionTitle
                accentColor={accentColor}
                fontScale={fontScale}
                onClick={canEdit && editor ? editor.addSkillGroup : undefined}
                actionLabel={locale === "en" ? "Add skill group" : "Adicionar grupo"}
              >
                {copy.skills}
              </SectionTitle>
              <div className="grid grid-cols-2 gap-x-6 gap-y-4">
                {data.skillGroups.map((group, itemIndex) => (
                  <article key={`${group.title}-${itemIndex}`} className={`border-l-2 pl-3 ${canEdit ? "group/resume-item relative" : ""}`} style={{ borderColor: `${accentColor}88` }}>
                    {canEdit && editor ? <PreviewActionSlot label="Remover grupo de habilidades" onClick={() => editor.removeSkillGroup(itemIndex)} /> : null}
                    {canEdit && editor ? (
                      <>
                        <InlineEditableText
                          as="div"
                          value={group.title}
                          onChange={(value) => editor.updateSkillGroup(itemIndex, "title", value)}
                          className="font-black uppercase tracking-[0.12em]"
                          style={{
                            color: accentColor,
                            fontSize: scalePx(9.5, fontScale),
                            marginBottom: screenPreview ? scalePx(7, fontScale) : undefined,
                          }}
                          placeholder="Título do grupo"
                        />
                        <InlineEditableText
                          as="p"
                          multiline
                          value={group.items.join(" • ")}
                          onChange={(value) => editor.updateSkillGroup(itemIndex, "items", value)}
                          className={`mt-1 leading-[1.32] text-[#222] ${uppercaseSkills ? "uppercase" : ""}`}
                          style={{
                            fontSize: scalePx(9.5, fontScale),
                            marginTop: screenPreview ? 0 : undefined,
                          }}
                          placeholder="Habilidades"
                        />
                      </>
                    ) : (
                      <>
                        <div
                          className="font-black uppercase tracking-[0.12em]"
                          style={{
                            color: accentColor,
                            fontSize: scalePx(9.5, fontScale),
                            marginBottom: screenPreview ? scalePx(7, fontScale) : undefined,
                          }}
                        >
                          {group.title}
                        </div>
                        <p
                          className={`mt-1 leading-[1.32] text-[#222] ${uppercaseSkills ? "uppercase" : ""}`}
                          style={{
                            fontSize: scalePx(9.5, fontScale),
                            marginTop: screenPreview ? 0 : undefined,
                          }}
                        >
                          {group.items.join(" • ")}
                        </p>
                      </>
                    )}
                  </article>
                ))}
              </div>
            </div>
          </div>
        </ResumePageFrame>
      </ResumePageViewport>

      {(data.solvedProblems.length > 0 || canEdit) && (
        <ResumePageViewport printMode={printMode}>
          <ResumePageFrame pageBackground={pageBackground} printMode={printMode}>
            <div className="flex h-full flex-col gap-5 px-8 py-8">
              <div className="group/resume-section">
                <SectionTitle
                  accentColor={accentColor}
                  fontScale={fontScale}
                  onClick={canEdit && editor ? editor.addSolvedProblem : undefined}
                  actionLabel={locale === "en" ? "Add solved problem" : "Adicionar caso"}
                >
                  {copy.solvedProblems}
                </SectionTitle>
                <div className="space-y-2.5">
                  {data.solvedProblems.map((item, index) => (
                    <SolvedProblemItem
                      key={`${item.title}-${index}`}
                      {...item}
                      accentColor={accentColor}
                      fontScale={fontScale}
                      impactLabel={copy.impact}
                      screenPreview={screenPreview}
                      editable={canEdit}
                      onTitleChange={canEdit && editor ? (value) => editor.updateSolvedProblem(index, "title", value) : undefined}
                      onContextChange={canEdit && editor ? (value) => editor.updateSolvedProblem(index, "context", value) : undefined}
                      onImpactChange={canEdit && editor ? (value) => editor.updateSolvedProblem(index, "impact", value) : undefined}
                      onRemove={canEdit && editor ? () => editor.removeSolvedProblem(index) : undefined}
                    />
                  ))}
                </div>
              </div>
            </div>
          </ResumePageFrame>
        </ResumePageViewport>
      )}
    </div>
  );
}
