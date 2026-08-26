import { afterEach, expect, test, vi } from "vitest";
import { api, jsonBody } from "./client";

afterEach(() => {
  vi.restoreAllMocks();
  document.cookie = "mcplica_csrf=; Max-Age=0; path=/";
});

test("sends cookie credentials and the CSRF header on mutations", async () => {
  document.cookie = "mcplica_csrf=signed-token; path=/";
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(new Response(null, { status: 204 }));

  await api<void>("/api/v1/projects", {
    method: "POST",
    body: jsonBody({ name: "Inventory" }),
  });

  const init = fetchMock.mock.calls[0][1]!;
  const headers = new Headers(init.headers);
  expect(init.credentials).toBe("include");
  expect(headers.get("X-CSRF-Token")).toBe("signed-token");
  expect(headers.get("Content-Type")).toBe("application/json");
});

test("preserves the stable error code and request ID for recovery", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({
        error: {
          code: "BUILD_NOT_READY",
          message: "Build must be READY.",
          details: { status: "FAILED" },
          request_id: "request-123",
        },
      }),
      { status: 409, headers: { "Content-Type": "application/json" } },
    ),
  );

  await expect(
    api("/api/v1/deployments", { method: "POST" }),
  ).rejects.toMatchObject({
    status: 409,
    code: "BUILD_NOT_READY",
    requestId: "request-123",
    message: "Build must be READY.",
  });
});
