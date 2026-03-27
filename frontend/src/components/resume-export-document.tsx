"use client";

import { ResumePreview } from "@/components/resume-preview";
import { DEFAULT_RESUME_LOCALE, type ResumeDocument, type ResumeLocale } from "@/lib/resume";

export function ResumeExportDocument({
  data,
  locale = DEFAULT_RESUME_LOCALE,
  pdfMode = false,
}: {
  data: ResumeDocument;
  locale?: ResumeLocale;
  pdfMode?: boolean;
}) {
  return <ResumePreview data={data} locale={locale} printMode pdfMode={pdfMode} />;
}
