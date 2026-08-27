import type { SourceKind } from "@/api/contracts";

export const MAX_UPLOAD_BYTES = 100_000_000;
export const MAX_UPLOAD_LABEL = "100 MB";

const EXECUTABLE_EXTENSIONS = new Set([".json", ".yaml", ".yml"]);
const DOCUMENTATION_EXTENSIONS = new Set([
  ".csv",
  ".docx",
  ".htm",
  ".html",
  ".json",
  ".markdown",
  ".md",
  ".pdf",
  ".txt",
  ".xlsx",
]);

export const EXECUTABLE_FILE_ACCEPT =
  ".json,.yaml,.yml,application/json,application/yaml,text/yaml";
export const DOCUMENTATION_FILE_ACCEPT = [
  ".json",
  ".md",
  ".markdown",
  ".txt",
  ".csv",
  ".xlsx",
  ".docx",
  ".pdf",
  ".html",
  ".htm",
  "application/json",
  "text/markdown",
  "text/plain",
  "text/csv",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/pdf",
  "text/html",
].join(",");

export function uploadAccept(kind: SourceKind): string {
  return kind === "documentation"
    ? DOCUMENTATION_FILE_ACCEPT
    : EXECUTABLE_FILE_ACCEPT;
}

export function uploadFileError(file: File, kind: SourceKind): string | null {
  if (file.size === 0) return "Choose a non-empty file.";
  if (file.size > MAX_UPLOAD_BYTES) {
    return `File exceeds the ${MAX_UPLOAD_LABEL} upload limit.`;
  }
  const dot = file.name.lastIndexOf(".");
  const extension = dot >= 0 ? file.name.slice(dot).toLowerCase() : "";
  const supported =
    kind === "documentation" ? DOCUMENTATION_EXTENSIONS : EXECUTABLE_EXTENSIONS;
  if (!supported.has(extension)) {
    return kind === "documentation"
      ? "Use JSON, Markdown, TXT, CSV, XLSX, DOCX, HTML, or PDF."
      : "Use an OpenAPI/API Inventory JSON or YAML file.";
  }
  return null;
}
