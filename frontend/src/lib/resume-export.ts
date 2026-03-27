import { type ResumeDocument } from "@/lib/resume";

function toBase64Url(value: string): string {
  const bytes = new TextEncoder().encode(value);
  let binary = "";
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte);
  });
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function fromBase64Url(value: string): string {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
  const binary = atob(padded);
  const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}

export function encodeResumePayload(data: ResumeDocument): string {
  return toBase64Url(JSON.stringify(data));
}

export function decodeResumePayload(payloadB64: string): ResumeDocument {
  return JSON.parse(fromBase64Url(payloadB64)) as ResumeDocument;
}
