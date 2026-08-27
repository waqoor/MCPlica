export function formatDate(
  value: string | null | undefined,
  options?: Intl.DateTimeFormatOptions,
): string {
  if (!value) return "Not recorded";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Invalid date";
  return new Intl.DateTimeFormat(
    undefined,
    options ?? { dateStyle: "medium", timeStyle: "short" },
  ).format(date);
}

export function formatBytes(bytes: number | null | undefined): string {
  if (
    bytes === null ||
    bytes === undefined ||
    !Number.isFinite(bytes) ||
    bytes < 0
  )
    return "Unknown size";
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    units.length - 1,
  );
  const formatted = new Intl.NumberFormat(undefined, {
    maximumFractionDigits: index === 0 ? 0 : 1,
    minimumFractionDigits: 0,
  }).format(bytes / 1024 ** index);
  return `${formatted} ${units[index]}`;
}

export function shortenHash(value: string | null | undefined): string {
  return value ? `${value.slice(0, 10)}…${value.slice(-6)}` : "Not available";
}

export function titleCase(value: string): string {
  return value
    .toLowerCase()
    .replace(/(^|[_-])\w/g, (match) =>
      match.replace(/[_-]/, " ").toUpperCase(),
    );
}
