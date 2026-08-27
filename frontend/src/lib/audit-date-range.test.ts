import { afterEach, describe, expect, it, vi } from "vitest";
import { auditCalendarRange, isAuditCalendarDate } from "./audit-date-range";

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("auditCalendarRange", () => {
  it("uses inclusive local calendar dates and an exclusive next-day bound", () => {
    vi.stubEnv("TZ", "UTC");
    expect(auditCalendarRange("2026-08-01", "2026-08-01")).toEqual({
      from: "2026-08-01T00:00:00.000Z",
      to: "2026-08-02T00:00:00.000Z",
    });
  });

  it("preserves DST-short and DST-long local days", () => {
    vi.stubEnv("TZ", "America/New_York");
    const spring = auditCalendarRange("2026-03-08", "2026-03-08");
    const fall = auditCalendarRange("2026-11-01", "2026-11-01");
    expect(
      (Date.parse(spring.to!) - Date.parse(spring.from!)) / 3_600_000,
    ).toBe(23);
    expect((Date.parse(fall.to!) - Date.parse(fall.from!)) / 3_600_000).toBe(
      25,
    );
  });

  it("omits empty boundaries instead of sending invalid datetimes", () => {
    expect(auditCalendarRange("", "")).toEqual({
      from: undefined,
      to: undefined,
    });
  });

  it.each(["2026-02-29", "2026-04-31", "2026-13-01", "2026-00-01", "bad"])(
    "rejects impossible or malformed URL date %s",
    (value) => {
      expect(isAuditCalendarDate(value)).toBe(false);
      expect(auditCalendarRange(value, value)).toEqual({
        from: undefined,
        to: undefined,
      });
    },
  );

  it.each(["", "2024-02-29", "2026-12-31"])(
    "accepts valid calendar date %s",
    (value) => {
      expect(isAuditCalendarDate(value)).toBe(true);
    },
  );
});
