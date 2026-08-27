import { afterEach, expect, test, vi } from "vitest";
import { z } from "zod/v3";
import { api, download, jsonBody, setSessionRecoveryListener } from "./client";

const idContract = z.object({ id: z.string() }).strict();
const pathContract = z.object({ path: z.string() }).strict();
const noContentContract = z.void();

afterEach(() => {
  vi.restoreAllMocks();
  setSessionRecoveryListener(null);
  document.cookie = "mcplica_csrf=; Max-Age=0; path=/";
});

test("refreshes once and retries the original request after access expiry", async () => {
  const recovery = vi.fn();
  setSessionRecoveryListener(recovery);
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(new Response(null, { status: 401 }))
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ user: {}, access_expires_at: "later" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    )
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ id: "project-1" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

  await expect(
    api<{ id: string }>("/api/v1/projects/project-1", idContract),
  ).resolves.toEqual({
    id: "project-1",
  });
  expect(fetchMock.mock.calls.map(([input]) => String(input))).toEqual([
    "/api/v1/projects/project-1",
    "/api/v1/auth/refresh",
    "/api/v1/projects/project-1",
  ]);
  expect(recovery).toHaveBeenCalledWith("refreshed");
});

test("coalesces concurrent 401 responses into one refresh", async () => {
  let releaseRefresh: ((response: Response) => void) | undefined;
  const refreshResponse = new Promise<Response>((resolve) => {
    releaseRefresh = resolve;
  });
  const attempts = new Map<string, number>();
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation((input) => {
      const path = String(input);
      if (path === "/api/v1/auth/refresh") return refreshResponse;
      const attempt = (attempts.get(path) ?? 0) + 1;
      attempts.set(path, attempt);
      return Promise.resolve(
        attempt === 1
          ? new Response(null, { status: 401 })
          : new Response(JSON.stringify({ path }), {
              status: 200,
              headers: { "Content-Type": "application/json" },
            }),
      );
    });

  const first = api<{ path: string }>("/api/v1/projects/one", pathContract);
  const second = api<{ path: string }>("/api/v1/projects/two", pathContract);
  await vi.waitFor(() => {
    expect(
      fetchMock.mock.calls.filter(
        ([input]) => String(input) === "/api/v1/auth/refresh",
      ),
    ).toHaveLength(1);
  });
  releaseRefresh?.(new Response(null, { status: 204 }));

  await expect(Promise.all([first, second])).resolves.toEqual([
    { path: "/api/v1/projects/one" },
    { path: "/api/v1/projects/two" },
  ]);
  expect(
    fetchMock.mock.calls.filter(
      ([input]) => String(input) === "/api/v1/auth/refresh",
    ),
  ).toHaveLength(1);
});

test("fails closed when refresh is revoked and never recurses on auth endpoints", async () => {
  const recovery = vi.fn();
  setSessionRecoveryListener(recovery);
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(new Response(null, { status: 401 }))
    .mockResolvedValueOnce(new Response(null, { status: 401 }));

  await expect(api("/api/v1/projects", pathContract)).rejects.toMatchObject({
    status: 401,
  });
  expect(fetchMock).toHaveBeenCalledTimes(2);
  expect(recovery).toHaveBeenCalledWith("failed");

  fetchMock.mockClear();
  fetchMock.mockResolvedValueOnce(new Response(null, { status: 401 }));
  await expect(
    api("/api/v1/auth/logout", noContentContract, { method: "POST" }),
  ).rejects.toMatchObject({ status: 401 });
  expect(fetchMock).toHaveBeenCalledTimes(1);
});

test("sends cookie credentials and the CSRF header on mutations", async () => {
  document.cookie = "mcplica_csrf=signed-token; path=/";
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(new Response(null, { status: 204 }));

  await api<void>("/api/v1/projects", noContentContract, {
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
    api("/api/v1/deployments", idContract, { method: "POST" }),
  ).rejects.toMatchObject({
    status: 409,
    code: "BUILD_NOT_READY",
    requestId: "request-123",
    message: "Build must be READY.",
  });
});

test("normalizes safe field validation details for one shared error notice", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({
        detail: [
          { loc: ["body", "issuer_url"], msg: "Enter a valid issuer URL" },
          { loc: ["body", "audiences", 0], msg: "Audience cannot be empty" },
        ],
      }),
      {
        status: 422,
        headers: {
          "Content-Type": "application/json",
          "X-Request-ID": "request-validation-1",
        },
      },
    ),
  );

  await expect(api("/api/v1/example", idContract)).rejects.toMatchObject({
    details: {
      issuer_url: "Enter a valid issuer URL",
      "audiences.0": "Audience cannot be empty",
    },
    requestId: "request-validation-1",
  });
});

test("preserves structured details and header request ID for download failures", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({
        error: {
          code: "EXPORT_NOT_READY",
          message: "The immutable export is not ready.",
          details: { build_status: "PACKAGING" },
        },
      }),
      {
        status: 409,
        headers: {
          "Content-Type": "application/json",
          "X-Request-ID": "request-download-1",
        },
      },
    ),
  );

  await expect(download("/api/v1/builds/build-1/export")).rejects.toMatchObject(
    {
      status: 409,
      code: "EXPORT_NOT_READY",
      details: { build_status: "PACKAGING" },
      requestId: "request-download-1",
    },
  );
});

test("rejects a successful response that violates its endpoint contract", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ id: 42, unexpected: true }), {
      status: 200,
      headers: {
        "Content-Type": "application/json",
        "X-Request-ID": "request-contract-1",
      },
    }),
  );

  await expect(
    api("/api/v1/projects/project-1", idContract),
  ).rejects.toMatchObject({
    status: 502,
    code: "RESPONSE_CONTRACT_INVALID",
    requestId: "request-contract-1",
    details: {
      endpoint: "GET /api/v1/projects/project-1",
      issues: expect.arrayContaining([expect.objectContaining({ path: "id" })]),
    },
  });
});
