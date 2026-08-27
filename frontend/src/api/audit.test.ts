import { afterEach, expect, it, vi } from "vitest";
import { auditCalendarRange } from "@/lib/audit-date-range";
import { auditApi } from "./audit";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});

it("sends actor and offset-aware exclusive calendar boundaries", async () => {
  vi.stubEnv("TZ", "UTC");
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(
      new Response(
        JSON.stringify({ items: [], total: 0, page: 2, page_size: 25 }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
  const range = auditCalendarRange("2026-08-01", "2026-08-03");

  await auditApi.list({
    actor: "operator@example.com",
    project_id: "10000000-0000-4000-8000-000000000001",
    event_type: "build.created",
    ...range,
    page: 2,
    page_size: 25,
  });

  const url = new URL(String(fetchMock.mock.calls[0][0]), "https://ui.local");
  expect(url.searchParams.get("actor")).toBe("operator@example.com");
  expect(url.searchParams.get("from")).toBe("2026-08-01T00:00:00.000Z");
  expect(url.searchParams.get("to")).toBe("2026-08-04T00:00:00.000Z");
  expect(url.searchParams.get("page")).toBe("2");
  expect(url.searchParams.get("page_size")).toBe("25");
});
