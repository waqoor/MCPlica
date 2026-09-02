type ErrorEnvelope = {
  error?: {
    code?: string;
    message?: string;
    details?: Record<string, unknown>;
    request_id?: string | null;
  };
  detail?: string | Array<{ loc?: Array<string | number>; msg?: string }>;
};

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly code = "HTTP_ERROR",
    public readonly details: Record<string, unknown> = {},
    public readonly requestId: string | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type ContractIssue = {
  readonly path?: readonly (string | number)[];
  readonly message: string;
  readonly code?: string;
};

export type ResponseContract<T> = {
  safeParse(value: unknown):
    | { readonly success: true; readonly data: T }
    | {
        readonly success: false;
        readonly error: { readonly issues: readonly ContractIssue[] };
      };
};

export type PageResponse<T> = {
  readonly items: T[];
  readonly total: number;
  readonly page: number;
  readonly page_size: number;
};

export class ResponseContractError extends ApiError {
  constructor(
    path: string,
    method: string,
    issues: readonly ContractIssue[],
    requestId: string | null,
  ) {
    const endpoint = `${method.toUpperCase()} ${path.split("?", 1)[0]}`;
    super(
      502,
      `The server response for ${endpoint} did not match the published API contract. Refresh and retry; if the problem persists, report the request ID.`,
      "RESPONSE_CONTRACT_INVALID",
      {
        endpoint,
        issues: issues.map((issue) => ({
          path: issue.path?.join(".") || "$",
          message: issue.message,
          code: issue.code ?? "invalid_value",
        })),
      },
      requestId,
    );
    this.name = "ResponseContractError";
  }
}

const apiBaseUrl =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(
    /\/$/,
    "",
  ) ?? "";

type SessionRecoveryState = "refreshed" | "failed";
type SessionRecoveryListener = (state: SessionRecoveryState) => void;

let sessionRecovery: Promise<boolean> | null = null;
let sessionRecoveryListener: SessionRecoveryListener | null = null;

const recoveryExcludedPaths = new Set([
  "/api/v1/auth/login",
  "/api/v1/auth/logout",
  "/api/v1/auth/refresh",
]);

export function setSessionRecoveryListener(
  listener: SessionRecoveryListener | null,
): () => void {
  sessionRecoveryListener = listener;
  return () => {
    if (sessionRecoveryListener === listener) sessionRecoveryListener = null;
  };
}

function csrfToken(): string | null {
  const match = document.cookie.match(/(?:^|;\s*)mcplica_csrf=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

function errorMessage(payload: ErrorEnvelope | null, fallback: string): string {
  if (payload?.error?.message) return payload.error.message;
  if (typeof payload?.detail === "string") return payload.detail;
  if (Array.isArray(payload?.detail)) {
    const messages = payload.detail.map((item) => item.msg).filter(Boolean);
    if (messages.length) return messages.join("; ");
  }
  return fallback || "The request could not be completed.";
}

function errorDetails(payload: ErrorEnvelope | null): Record<string, unknown> {
  const details = { ...(payload?.error?.details ?? {}) };
  if (!Array.isArray(payload?.detail)) return details;
  for (const issue of payload.detail) {
    const field = issue.loc
      ?.filter((part) => part !== "body" && part !== "query" && part !== "path")
      .join(".");
    if (field && issue.msg) details[field] = issue.msg;
  }
  return details;
}

function requestHeaders(init: RequestInit): Headers {
  const headers = new Headers(init.headers);
  if (
    init.body &&
    !(init.body instanceof FormData) &&
    !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json");
  }
  const method = init.method?.toUpperCase() ?? "GET";
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const token = csrfToken();
    if (token) headers.set("X-CSRF-Token", token);
  }
  headers.set("Accept", "application/json");
  return headers;
}

function fetchRequest(path: string, init: RequestInit): Promise<Response> {
  return fetch(`${apiBaseUrl}${path}`, {
    ...init,
    credentials: "include",
    headers: requestHeaders(init),
  });
}

async function recoverSession(): Promise<boolean> {
  if (sessionRecovery) return sessionRecovery;
  sessionRecovery = (async () => {
    try {
      const response = await fetchRequest("/api/v1/auth/refresh", {
        method: "POST",
      });
      const recovered = response.ok;
      sessionRecoveryListener?.(recovered ? "refreshed" : "failed");
      return recovered;
    } catch {
      sessionRecoveryListener?.("failed");
      return false;
    } finally {
      sessionRecovery = null;
    }
  })();
  return sessionRecovery;
}

async function fetchWithRecovery(
  path: string,
  init: RequestInit,
): Promise<Response> {
  let response = await fetchRequest(path, init);
  if (
    response.status === 401 &&
    !recoveryExcludedPaths.has(path) &&
    (await recoverSession())
  ) {
    response = await fetchRequest(path, init);
  }
  return response;
}

export async function api<T>(
  path: string,
  contract: ResponseContract<T>,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetchWithRecovery(path, init);

  if (!response.ok) {
    const payload = (await response
      .json()
      .catch(() => null)) as ErrorEnvelope | null;
    throw new ApiError(
      response.status,
      errorMessage(payload, response.statusText),
      payload?.error?.code ?? "HTTP_ERROR",
      errorDetails(payload),
      payload?.error?.request_id ?? response.headers.get("X-Request-ID"),
    );
  }

  let payload: unknown = undefined;
  if (response.status !== 204) {
    try {
      payload = await response.json();
    } catch {
      throw new ResponseContractError(
        path,
        init.method ?? "GET",
        [
          {
            path: [],
            message: "Response body is not valid JSON.",
            code: "invalid_json",
          },
        ],
        response.headers.get("X-Request-ID"),
      );
    }
  }

  const parsed = contract.safeParse(payload);
  if (!parsed.success) {
    throw new ResponseContractError(
      path,
      init.method ?? "GET",
      parsed.error.issues,
      response.headers.get("X-Request-ID"),
    );
  }
  return parsed.data;
}

export async function apiAllPages<T>(
  path: string,
  contract: ResponseContract<PageResponse<T>>,
  signal?: AbortSignal,
): Promise<T[]> {
  const items: T[] = [];
  const separator = path.includes("?") ? "&" : "?";
  let page = 1;
  while (true) {
    const response = await api<PageResponse<T>>(
      `${path}${separator}page=${page}&page_size=200`,
      contract,
      { signal },
    );
    if (response.page !== page || response.page_size !== 200) {
      throw new ApiError(
        502,
        "The server returned inconsistent collection pagination metadata.",
        "RESPONSE_PAGINATION_INVALID",
      );
    }
    items.push(...response.items);
    if (items.length >= response.total) return items;
    if (response.items.length === 0) {
      throw new ApiError(
        502,
        "The server returned an incomplete collection page.",
        "RESPONSE_PAGINATION_INVALID",
      );
    }
    page += 1;
  }
}

export function jsonBody(value: unknown): string {
  return JSON.stringify(value);
}

export function queryString(
  values: Record<string, string | number | boolean | null | undefined>,
): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (value !== undefined && value !== null && value !== "")
      params.set(key, String(value));
  }
  const encoded = params.toString();
  return encoded ? `?${encoded}` : "";
}

export async function download(
  path: string,
  signal?: AbortSignal,
): Promise<Blob> {
  const response = await fetchWithRecovery(path, { signal });
  if (!response.ok) {
    const payload = (await response
      .json()
      .catch(() => null)) as ErrorEnvelope | null;
    throw new ApiError(
      response.status,
      errorMessage(payload, response.statusText),
      payload?.error?.code ?? "HTTP_ERROR",
      errorDetails(payload),
      payload?.error?.request_id ?? response.headers.get("X-Request-ID"),
    );
  }
  return response.blob();
}
