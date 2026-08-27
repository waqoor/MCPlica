const LOCAL_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;

function localDateParts(
  value: string,
): { year: number; month: number; day: number } | undefined {
  const match = LOCAL_DATE.exec(value);
  if (!match) return undefined;
  const [, rawYear, rawMonth, rawDay] = match;
  const year = Number(rawYear);
  const month = Number(rawMonth) - 1;
  const day = Number(rawDay);
  const candidate = new Date(0);
  candidate.setHours(0, 0, 0, 0);
  candidate.setFullYear(year, month, day);
  if (
    Number.isNaN(candidate.valueOf()) ||
    candidate.getFullYear() !== year ||
    candidate.getMonth() !== month ||
    candidate.getDate() !== day
  )
    return undefined;
  return { year, month, day };
}

function localBoundary(value: string, nextDay: boolean): string | undefined {
  const parts = localDateParts(value);
  if (!parts) return undefined;
  const boundary = new Date(0);
  boundary.setHours(0, 0, 0, 0);
  boundary.setFullYear(parts.year, parts.month, parts.day + (nextDay ? 1 : 0));
  return boundary.toISOString();
}

export function isAuditCalendarDate(value: string): boolean {
  return value === "" || localDateParts(value) !== undefined;
}

export function auditCalendarRange(
  fromDate: string,
  toDate: string,
): { from?: string; to?: string } {
  return {
    from: fromDate ? localBoundary(fromDate, false) : undefined,
    // The backend uses an exclusive upper bound. Advancing in local calendar
    // time includes the entire selected final day across DST transitions.
    to: toDate ? localBoundary(toDate, true) : undefined,
  };
}

export function browserTimeZone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || "Local time";
}
