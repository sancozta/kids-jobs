const SAO_PAULO_TIMEZONE = "America/Sao_Paulo";
const DATE_ONLY_REGEX = /^(\d{4})-(\d{2})-(\d{2})$/;
const HAS_TIMEZONE_REGEX = /([zZ]|[+\-]\d{2}:\d{2})$/;

function normalizeToDate(value: string | Date): Date | null {
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value;
  }

  const trimmed = value.trim();
  if (!trimmed) return null;

  const hasTimezone = HAS_TIMEZONE_REGEX.test(trimmed);
  const normalized = hasTimezone ? trimmed : `${trimmed}Z`;
  const parsed = new Date(normalized);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function formatDateFromParts(date: Date): string {
  const parts = new Intl.DateTimeFormat("pt-BR", {
    timeZone: SAO_PAULO_TIMEZONE,
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).formatToParts(date);

  const day = parts.find((part) => part.type === "day")?.value ?? "—";
  const month = parts.find((part) => part.type === "month")?.value ?? "—";
  const year = parts.find((part) => part.type === "year")?.value ?? "—";
  return `${day}/${month}/${year}`;
}

function formatDateTimeFromParts(date: Date): string {
  const parts = new Intl.DateTimeFormat("pt-BR", {
    timeZone: SAO_PAULO_TIMEZONE,
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(date);

  const day = parts.find((part) => part.type === "day")?.value ?? "—";
  const month = parts.find((part) => part.type === "month")?.value ?? "—";
  const year = parts.find((part) => part.type === "year")?.value ?? "—";
  const hour = parts.find((part) => part.type === "hour")?.value ?? "00";
  const minute = parts.find((part) => part.type === "minute")?.value ?? "00";
  return `${day}/${month}/${year} ${hour}:${minute}`;
}

/**
 * Formata datas para o padrão fixo DD/MM/YYYY.
 * Aceita "YYYY-MM-DD", ISO datetime e Date.
 */
export function formatDateDDMMYYYY(value: string | Date | null | undefined): string {
  if (!value) return "—";

  if (typeof value === "string") {
    const isoDateMatch = value.match(DATE_ONLY_REGEX);
    if (isoDateMatch) {
      const [, year, month, day] = isoDateMatch;
      return `${day}/${month}/${year}`;
    }
  }

  const parsed = normalizeToDate(value);
  if (!parsed) return "—";

  return formatDateFromParts(parsed);
}

/**
 * Formata data/hora para o padrão fixo DD/MM/YYYY HH:mm.
 * Aceita "YYYY-MM-DDTHH:mm", ISO datetime e Date.
 */
export function formatDateTimeDDMMYYYYHHMM(value: string | Date | null | undefined): string {
  if (!value) return "—";

  if (typeof value === "string") {
    const isoDateMatch = value.match(DATE_ONLY_REGEX);
    if (isoDateMatch) {
      const [, year, month, day] = isoDateMatch;
      return `${day}/${month}/${year} 00:00`;
    }
  }

  const parsed = normalizeToDate(value);
  if (!parsed) return "—";

  return formatDateTimeFromParts(parsed);
}
