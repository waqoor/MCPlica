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

const apiBaseUrl =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(
    /\/$/,
    "",
  ) ?? "";

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

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    credentials: "include",
    headers: requestHeaders(init),
  });

  if (!response.ok) {
    const payload = (await response
      .json()
      .catch(() => null)) as ErrorEnvelope | null;
    throw new ApiError(
      response.status,
      errorMessage(payload, response.statusText),
      payload?.error?.code ?? "HTTP_ERROR",
      payload?.error?.details ?? {},
      payload?.error?.request_id ?? response.headers.get("X-Request-ID"),
    );
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
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
  const response = await fetch(`${apiBaseUrl}${path}`, {
    credentials: "include",
    headers: requestHeaders({ signal }),
    signal,
  });
  if (!response.ok) {
    const payload = (await response
      .json()
      .catch(() => null)) as ErrorEnvelope | null;
    throw new ApiError(
      response.status,
      errorMessage(payload, response.statusText),
      payload?.error?.code ?? "HTTP_ERROR",
    );
  }
  return response.blob();
}
