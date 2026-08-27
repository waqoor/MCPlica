import { Check, Clipboard, RefreshCw } from "lucide-react";
import { useState } from "react";
import { ApiError } from "@/api/client";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

const SENSITIVE_KEY =
  /authorization|cookie|credential|password|secret|token|trace|stack/i;

function safeDetails(
  details: Record<string, unknown>,
): Array<[string, string]> {
  return Object.entries(details).flatMap(([key, value]) => {
    if (SENSITIVE_KEY.test(key)) return [];
    if (["string", "number", "boolean"].includes(typeof value))
      return [[key, String(value).slice(0, 500)]];
    if (
      Array.isArray(value) &&
      value.length <= 20 &&
      value.every((item) =>
        ["string", "number", "boolean"].includes(typeof item),
      )
    )
      return [[key, value.map(String).join(", ").slice(0, 1_000)]];
    return [];
  });
}

export function ErrorNotice({
  error,
  title = "The request could not be completed",
  nextStep,
  onRetry,
}: {
  readonly error: unknown;
  readonly title?: string;
  readonly nextStep?: string;
  readonly onRetry?: () => void;
}) {
  const [copyStatus, setCopyStatus] = useState<"idle" | "success" | "error">(
    "idle",
  );
  const apiError = error instanceof ApiError ? error : null;
  const message =
    error instanceof Error && error.message
      ? error.message
      : "Check the service status and try again.";
  const details = apiError ? safeDetails(apiError.details) : [];
  return (
    <Alert title={title} tone="danger">
      <div className="space-y-3">
        <p>{message}</p>
        {(apiError?.code || apiError?.requestId) && (
          <dl className="grid gap-2 text-xs sm:grid-cols-2">
            {apiError.code && (
              <div>
                <dt className="text-muted">Error code</dt>
                <dd className="mt-1 font-mono text-foreground">
                  {apiError.code}
                </dd>
              </div>
            )}
            {apiError.requestId && (
              <div>
                <dt className="text-muted">Request ID</dt>
                <dd className="mt-1 flex items-center gap-2 font-mono text-foreground">
                  <span className="break-all">{apiError.requestId}</span>
                  <Button
                    aria-label="Copy request ID"
                    onClick={async () => {
                      try {
                        await navigator.clipboard.writeText(
                          apiError.requestId!,
                        );
                        setCopyStatus("success");
                      } catch {
                        setCopyStatus("error");
                      }
                    }}
                    size="icon"
                    variant="ghost"
                  >
                    {copyStatus === "success" ? (
                      <Check aria-hidden="true" className="size-4" />
                    ) : (
                      <Clipboard aria-hidden="true" className="size-4" />
                    )}
                  </Button>
                </dd>
              </div>
            )}
          </dl>
        )}
        {details.length > 0 && (
          <dl className="space-y-1 text-xs">
            {details.map(([key, value]) => (
              <div className="grid gap-1 sm:grid-cols-[10rem_1fr]" key={key}>
                <dt className="font-medium text-muted">{key}</dt>
                <dd className="break-words text-foreground">{value}</dd>
              </div>
            ))}
          </dl>
        )}
        {nextStep && <p className="text-sm text-muted">{nextStep}</p>}
        <div className="flex items-center justify-between gap-3">
          <span aria-live="polite" className="text-xs text-muted">
            {copyStatus === "success"
              ? "Request ID copied."
              : copyStatus === "error"
                ? "Could not copy the request ID. Select it manually."
                : ""}
          </span>
          {onRetry && (
            <Button onClick={onRetry} size="sm" variant="outline">
              <RefreshCw aria-hidden="true" className="size-4" />
              Try again
            </Button>
          )}
        </div>
      </div>
    </Alert>
  );
}

export function MutationError({
  error,
  title = "The change was not saved",
  onRetry,
}: {
  readonly error: unknown;
  readonly title?: string;
  readonly onRetry?: () => void;
}) {
  return <ErrorNotice error={error} onRetry={onRetry} title={title} />;
}
