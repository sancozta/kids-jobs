"use client";

import {
  BriefcaseBusinessIcon,
  FlagIcon,
  GraduationCapIcon,
  GithubIcon,
  LanguagesIcon,
  LinkedinIcon,
  GlobeIcon,
  MailIcon,
  MapPinIcon,
  PhoneIcon,
  UserRoundIcon,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";

import { DEFAULT_RESUME_LOCALE, getResumePreviewCopy, type ResumeDocument, type ResumeLocale, type ResumePhotoFrameStyle } from "@/lib/resume";

const PAGE_WIDTH_PX = 794;
const PAGE_HEIGHT_PX = 1123;
const PAGE_STYLE = {
  width: `${PAGE_WIDTH_PX}px`,
  height: `${PAGE_HEIGHT_PX}px`,
  boxSizing: "border-box",
} satisfies CSSProperties;

type ContactLink = {
  label: string;
  value: string;
  href?: string;
  icon: React.ReactNode;
};

function scalePx(value: number, scale: number): string {
  return `${(value * scale).toFixed(2)}px`;
}

function SectionTitle({ children, accentColor, fontScale }: { children: string; accentColor: string; fontScale: number }) {
  return (
    <div className="mb-3 flex items-center gap-3">
      <span className="h-px flex-1" style={{ backgroundColor: `${accentColor}55` }} />
      <h3 className="font-black uppercase tracking-[0.16em] text-[#161616]" style={{ fontSize: scalePx(11, fontScale) }}>{children}</h3>
      <span className="h-px flex-1" style={{ backgroundColor: `${accentColor}55` }} />
    </div>
  );
}

function SidebarBlock({ title, children, fontScale }: { title: string; children: React.ReactNode; fontScale: number }) {
  return (
    <section className="space-y-2">
      <h3 className="font-black uppercase tracking-[0.16em] text-[#171717]" style={{ fontSize: scalePx(10, fontScale) }}>{title}</h3>
      <div className="space-y-2 leading-[1.45] text-[#202020]" style={{ fontSize: scalePx(11, fontScale) }}>{children}</div>
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
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  href?: string;
  accentColor: string;
  fontScale: number;
}) {
  const content = href ? (
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
      <div className="min-w-0">
        <div className="font-black uppercase tracking-[0.12em] text-[#111]" style={{ fontSize: scalePx(9, fontScale) }}>{label}</div>
        <div className="break-words font-medium leading-[1.3] text-[#111]" style={{ fontSize: scalePx(10.5, fontScale) }}>{content}</div>
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
}: {
  course: string;
  conclusion: string;
  institution: string;
  fontScale: number;
  conclusionLabel: string;
}) {
  return (
    <div className="space-y-0.5">
      <div className="font-black uppercase tracking-[0.12em] leading-[1.25] text-[#111]" style={{ fontSize: scalePx(9, fontScale) }}>{course}</div>
      <div className="font-semibold uppercase tracking-[0.08em] text-[#111]" style={{ fontSize: scalePx(9, fontScale) }}>{conclusionLabel} {conclusion}</div>
      <div className="font-medium uppercase tracking-[0.06em] text-[#111]" style={{ fontSize: scalePx(9.5, fontScale) }}>{institution}</div>
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
}: {
  role: string;
  duration: string;
  company: string;
  summary: string;
  accentColor: string;
  fontScale: number;
}) {
  return (
    <article className="space-y-1.5 border-b border-[#11111114] pb-3 last:border-b-0 last:pb-0">
      <div className="flex items-start gap-2.5">
        <span className="mt-0.5 shrink-0" style={{ color: accentColor }}>
          <BriefcaseBusinessIcon className="size-3.5" strokeWidth={2.2} />
        </span>
        <div className="space-y-0.5">
          <div className="font-black uppercase leading-[1.25] text-[#0f0f0f]" style={{ fontSize: scalePx(10.5, fontScale) }}>
            {role} - {duration}
          </div>
          <div className="font-semibold uppercase tracking-[0.1em] text-[#5f5f5f]" style={{ fontSize: scalePx(9, fontScale) }}>{company}</div>
        </div>
      </div>
      <p className="pl-6 text-justify leading-[1.34] text-[#212121]" style={{ fontSize: scalePx(9.5, fontScale) }}>{summary}</p>
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
}: {
  title: string;
  context: string;
  impact: string;
  accentColor: string;
  fontScale: number;
  impactLabel: string;
}) {
  return (
    <article className="break-inside-avoid space-y-1.5 border-b border-[#11111114] pb-3 last:border-b-0 last:pb-0">
      <div className="font-black uppercase leading-[1.25] text-[#111]" style={{ fontSize: scalePx(10, fontScale), color: accentColor }}>
        {title}
      </div>
      <p className="leading-[1.34] text-[#212121]" style={{ fontSize: scalePx(9.4, fontScale) }}>
        {context}
      </p>
      <p className="leading-[1.34] text-[#111]" style={{ fontSize: scalePx(9.4, fontScale) }}>
        <span className="font-black">{impactLabel}:</span> {impact}
      </p>
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
          <div
            className="absolute -left-2 top-4 h-[2px] w-10"
            style={{ backgroundColor: accentColor }}
          />
          <div
            className="absolute -bottom-2 right-4 h-[2px] w-12"
            style={{ backgroundColor: `${accentColor}88` }}
          />
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
        <div
          className="absolute inset-0 translate-x-2.5 translate-y-2.5 rounded-[10px]"
          style={{ backgroundColor: `${accentColor}1f` }}
        />
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
}: {
  data: ResumeDocument;
  locale?: ResumeLocale;
  printMode?: boolean;
  pdfMode?: boolean;
}) {
  const { accentColor, sidebarBackground, pageBackground, fontScale, sidebarWidth, photoFrameStyle, uppercaseSkills } = data.theme;
  const copy = getResumePreviewCopy(locale);
  const contactLinks = useMemo<ContactLink[]>(
    () => [
      { label: copy.address, value: data.profile.address, icon: <MapPinIcon className="size-3.5" strokeWidth={2.3} /> },
      { label: copy.phone, value: data.profile.phone, icon: <PhoneIcon className="size-3.5" strokeWidth={2.3} /> },
      { label: copy.email, value: data.profile.email, href: `mailto:${data.profile.email}`, icon: <MailIcon className="size-3.5" strokeWidth={2.3} /> },
      { label: copy.linkedin, value: data.profile.linkedin, href: `https://${data.profile.linkedin.replace(/^https?:\/\//, "")}`, icon: <LinkedinIcon className="size-3.5" strokeWidth={2.3} /> },
      { label: copy.github, value: data.profile.github, href: `https://${data.profile.github.replace(/^https?:\/\//, "")}`, icon: <GithubIcon className="size-3.5" strokeWidth={2.3} /> },
      { label: copy.portfolio, value: data.profile.portfolio, href: `https://${data.profile.portfolio.replace(/^https?:\/\//, "")}`, icon: <GlobeIcon className="size-3.5" strokeWidth={2.3} /> },
    ],
    [copy.address, copy.email, copy.github, copy.linkedin, copy.phone, copy.portfolio, data.profile.address, data.profile.email, data.profile.github, data.profile.linkedin, data.profile.phone, data.profile.portfolio],
  );

  return (
    <div className={`flex w-full flex-col ${pdfMode ? "gap-0" : "gap-6"} ${printMode ? "items-center" : "items-start"}`}>
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
                <div className="font-black uppercase tracking-[0.03em] text-[#161616]" style={{ fontSize: scalePx(16, fontScale) }}>{data.profile.fullName}</div>
              </div>

              <SidebarBlock title={copy.contact} fontScale={fontScale}>
                {contactLinks.map((item) => (
                  <ContactRow key={item.label} {...item} accentColor={accentColor} fontScale={fontScale} />
                ))}
                <ContactRow label={copy.maritalStatus} value={data.profile.maritalStatus} accentColor={accentColor} fontScale={fontScale} icon={<UserRoundIcon className="size-3.5" strokeWidth={2.3} />} />
                <ContactRow label={copy.nationality} value={data.profile.nationality} accentColor={accentColor} fontScale={fontScale} icon={<FlagIcon className="size-3.5" strokeWidth={2.3} />} />
              </SidebarBlock>

              <SidebarBlock title={copy.languages} fontScale={fontScale}>
                {data.languages.map((language, index) => (
                  <div key={`${language.name}-${index}`} className="flex items-start gap-2.5">
                    <span className="mt-1 shrink-0" style={{ color: accentColor }}>
                      <LanguagesIcon className="size-3.5" strokeWidth={2.3} />
                    </span>
                    <div>
                      <div className="font-black uppercase tracking-[0.12em] text-[#111]" style={{ fontSize: scalePx(9, fontScale) }}>{language.name}</div>
                      <div className="text-[#111]" style={{ fontSize: scalePx(9.5, fontScale) }}>{language.level}</div>
                    </div>
                  </div>
                ))}
              </SidebarBlock>

              <SidebarBlock title={copy.education} fontScale={fontScale}>
                {data.education.map((item, index) => (
                  <div key={`${item.course}-${index}`} className="flex items-start gap-2.5">
                    <span className="mt-1 shrink-0" style={{ color: accentColor }}>
                      <GraduationCapIcon className="size-3.5" strokeWidth={2.2} />
                    </span>
                    <EducationItem {...item} fontScale={fontScale} conclusionLabel={copy.conclusion} />
                  </div>
                ))}
              </SidebarBlock>
            </aside>

            <main className="flex h-full flex-col gap-4 px-7 py-7">
              <SectionTitle accentColor={accentColor} fontScale={fontScale}>{copy.experience}</SectionTitle>
              <div className="space-y-3">
                {data.experiences.map((experience, index) => (
                  <ExperienceItem key={`${experience.role}-${index}`} {...experience} accentColor={accentColor} fontScale={fontScale} />
                ))}
              </div>
            </main>
          </div>
        </ResumePageFrame>
      </ResumePageViewport>

      <ResumePageViewport printMode={printMode}>
        <ResumePageFrame pageBackground={pageBackground} printMode={printMode}>
          <div className="flex h-full flex-col gap-5 px-8 py-8">
            <div>
              <SectionTitle accentColor={accentColor} fontScale={fontScale}>{copy.certifications}</SectionTitle>
              <div className="grid grid-cols-2 gap-x-6 gap-y-2.5">
                {data.certifications.map((item, index) => (
                  <div key={`${item}-${index}`} className="leading-[1.32] text-[#1f1f1f]" style={{ fontSize: scalePx(9.5, fontScale) }}>
                    <span className="mr-2 font-black" style={{ color: accentColor }}>
                      •
                    </span>
                    {item}
                  </div>
                ))}
              </div>
            </div>

            <div>
              <SectionTitle accentColor={accentColor} fontScale={fontScale}>{copy.skills}</SectionTitle>
              <div className="grid grid-cols-2 gap-x-6 gap-y-4">
                {data.skillGroups.map((group, itemIndex) => (
                  <article key={`${group.title}-${itemIndex}`} className="border-l-2 pl-3" style={{ borderColor: `${accentColor}88` }}>
                    <div className="font-black uppercase tracking-[0.12em]" style={{ color: accentColor, fontSize: scalePx(9.5, fontScale) }}>
                      {group.title}
                    </div>
                    <p className={`mt-1 leading-[1.32] text-[#222] ${uppercaseSkills ? "uppercase" : ""}`} style={{ fontSize: scalePx(9.5, fontScale) }}>
                      {group.items.join(" • ")}
                    </p>
                  </article>
                ))}
              </div>
            </div>

          </div>
        </ResumePageFrame>
      </ResumePageViewport>

      {data.solvedProblems.length > 0 && (
        <ResumePageViewport printMode={printMode}>
          <ResumePageFrame pageBackground={pageBackground} printMode={printMode}>
            <div className="flex h-full flex-col gap-5 px-8 py-8">
              <div>
                <SectionTitle accentColor={accentColor} fontScale={fontScale}>{copy.solvedProblems}</SectionTitle>
                <div className="space-y-2.5">
                  {data.solvedProblems.map((item, index) => (
                    <SolvedProblemItem key={`${item.title}-${index}`} {...item} accentColor={accentColor} fontScale={fontScale} impactLabel={copy.impact} />
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
