function onlyDigits(value: string): string {
  return value.replace(/\D/g, "");
}

export function formatZipCode(value: string | null | undefined): string {
  if (!value) return "—";

  const digits = onlyDigits(value);
  if (digits.length < 8) return value;

  const normalized = digits.slice(0, 8);
  return `${normalized.slice(0, 5)}-${normalized.slice(5, 8)}`;
}

export function formatPhoneBR(value: string | null | undefined): string {
  if (!value) return "—";

  const digits = onlyDigits(value);

  // (DD) NNNNN-NNNN
  if (digits.length >= 11) {
    const normalized = digits.slice(0, 11);
    return `(${normalized.slice(0, 2)}) ${normalized.slice(2, 7)}-${normalized.slice(7, 11)}`;
  }

  // (DD) NNNN-NNNN
  if (digits.length === 10) {
    return `(${digits.slice(0, 2)}) ${digits.slice(2, 6)}-${digits.slice(6, 10)}`;
  }

  return value;
}

export function formatCpf(value: string | null | undefined): string {
  if (!value) return "—";

  const digits = onlyDigits(value);
  if (digits.length < 11) return value;

  const normalized = digits.slice(0, 11);
  return `${normalized.slice(0, 3)}.${normalized.slice(3, 6)}.${normalized.slice(6, 9)}-${normalized.slice(9, 11)}`;
}
