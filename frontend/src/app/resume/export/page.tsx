"use client";

import axios from "axios";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { PrinterIcon } from "lucide-react";

import { ResumeExportDocument } from "@/components/resume-export-document";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { decodeResumePayload } from "@/lib/resume-export";
import {
  getDefaultResumeData,
  getResumePreviewCopy,
  getResumeStorageFallbackKeys,
  normalizeResumeData,
  normalizeResumeLocale,
  type ResumeDocument,
} from "@/lib/resume";

function ResumeExportPageContent() {
  const searchParams = useSearchParams();
  const locale = normalizeResumeLocale(searchParams.get("locale"));
  const [resume, setResume] = useState<ResumeDocument>(() => getDefaultResumeData(locale));
  const [readyToPrint, setReadyToPrint] = useState(false);
  const payloadB64 = searchParams.get("payload_b64");
  const shouldAutoPrint = searchParams.get("autoprint") !== "0";
  const copy = getResumePreviewCopy(locale);

  useEffect(() => {
    const loadResume = async () => {
      try {
        if (payloadB64) {
          setResume(normalizeResumeData(decodeResumePayload(payloadB64), locale));
          return;
        }

        for (const storageKey of getResumeStorageFallbackKeys(locale)) {
          const raw = window.localStorage.getItem(storageKey);
          if (!raw) continue;
          setResume(normalizeResumeData(JSON.parse(raw), locale));
          return;
        }

        try {
          const response = await api.get<{ payload: ResumeDocument }>("/api/v1/resume-document/", { params: { locale } });
          setResume(normalizeResumeData(response.data.payload, locale));
        } catch (error) {
          if (!axios.isAxiosError(error) || error.response?.status !== 404) {
            console.error("Nao foi possivel carregar o curriculo salvo para exportacao.", error);
          }
          setResume(getDefaultResumeData(locale));
        }
      } catch {
        setResume(getDefaultResumeData(locale));
      } finally {
        setReadyToPrint(true);
      }
    };

    void loadResume();
  }, [locale, payloadB64]);

  useEffect(() => {
    if (!readyToPrint || !shouldAutoPrint) return;
    const timer = window.setTimeout(() => window.print(), 300);
    return () => window.clearTimeout(timer);
  }, [readyToPrint, shouldAutoPrint]);

  return (
    <main data-resume-ready={readyToPrint ? "true" : "false"} className="resume-export-root min-h-screen bg-[#d8dce4] px-6 py-8 print:bg-white print:px-0 print:py-0">
      <style jsx global>{`
        @media print {
          @page {
            size: A4;
            margin: 0;
          }

          html,
          body {
            background: white !important;
          }

          .resume-export-root {
            min-height: auto !important;
            height: auto !important;
            padding: 0 !important;
            margin: 0 !important;
            background: white !important;
          }

          .resume-page {
            width: 210mm !important;
            min-width: 210mm !important;
            max-width: 210mm !important;
            height: 297mm !important;
            min-height: 297mm !important;
            max-height: 297mm !important;
            border: 0 !important;
            border-radius: 0 !important;
            box-shadow: none !important;
            margin: 0 auto !important;
            overflow: hidden !important;
            break-after: page;
            page-break-after: always;
          }

          .resume-page:last-child {
            break-after: auto;
            page-break-after: auto;
          }

          .export-controls {
            display: none !important;
          }

          nextjs-portal,
          [data-next-badge-root],
          [data-next-mark],
          [id^="__next-build"],
          [class*="nextjs-portal"] {
            display: none !important;
            visibility: hidden !important;
          }
        }
      `}</style>

      <div className="export-controls mx-auto mb-6 flex max-w-5xl items-center justify-end">
        <Button type="button" onClick={() => window.print()}>
          <PrinterIcon className="mr-2 size-4" />
          {copy.print}
        </Button>
      </div>

      <ResumeExportDocument data={resume} locale={locale} pdfMode />
    </main>
  );
}

export default function ResumeExportPage() {
  return (
    <Suspense fallback={<main className="min-h-screen bg-white" data-resume-ready="false" />}>
      <ResumeExportPageContent />
    </Suspense>
  );
}
