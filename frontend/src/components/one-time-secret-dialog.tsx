import { Check, Clipboard } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";

type CopyState = "idle" | "copied" | "failed";

export function OneTimeSecretDialog({
  secret,
  title = "Store this access token now",
  onAcknowledged,
}: {
  readonly secret: string | null;
  readonly title?: string;
  readonly onAcknowledged: () => void;
}) {
  return (
    <OneTimeSecretDialogState
      key={secret ?? "closed"}
      onAcknowledged={onAcknowledged}
      secret={secret}
      title={title}
    />
  );
}

function OneTimeSecretDialogState({
  secret,
  title,
  onAcknowledged,
}: {
  readonly secret: string | null;
  readonly title: string;
  readonly onAcknowledged: () => void;
}) {
  const [stored, setStored] = useState(false);
  const [copyState, setCopyState] = useState<CopyState>("idle");
  const [closeBlocked, setCloseBlocked] = useState(false);

  useEffect(() => {
    if (!secret || stored) return;
    const preventUnacknowledgedNavigation = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", preventUnacknowledgedNavigation);
    return () =>
      window.removeEventListener(
        "beforeunload",
        preventUnacknowledgedNavigation,
      );
  }, [secret, stored]);

  const attemptClose = useCallback(() => {
    if (!stored) {
      setCloseBlocked(true);
      return;
    }
    onAcknowledged();
  }, [onAcknowledged, stored]);

  const copy = async () => {
    if (!secret) return;
    try {
      if (!navigator.clipboard?.writeText)
        throw new Error("Clipboard access is unavailable");
      await navigator.clipboard.writeText(secret);
      setCopyState("copied");
    } catch {
      setCopyState("failed");
    }
  };

  return (
    <Dialog
      description="This plaintext value cannot be recovered after you acknowledge it."
      onClose={attemptClose}
      open={Boolean(secret)}
      title={title}
    >
      <div className="space-y-4">
        <Alert tone="warning">
          Store this value in the external MCP client&apos;s secret manager. Do
          not place it in source control, logs, or ordinary notes.
        </Alert>
        <div className="flex items-start gap-2 rounded-md border border-border-strong bg-canvas p-3">
          <code className="min-w-0 flex-1 overflow-x-auto py-1 font-mono text-xs text-foreground">
            {secret}
          </code>
          <Button
            aria-label="Copy access token"
            onClick={() => void copy()}
            size="icon"
            variant="outline"
          >
            {copyState === "copied" ? (
              <Check aria-hidden="true" className="size-4 text-success-soft" />
            ) : (
              <Clipboard aria-hidden="true" className="size-4" />
            )}
          </Button>
        </div>
        <p
          aria-live="polite"
          className={
            copyState === "failed" || closeBlocked
              ? "min-h-5 text-sm text-danger-soft"
              : "min-h-5 text-sm text-success-soft"
          }
          role="status"
        >
          {copyState === "copied"
            ? "Token copied to the clipboard."
            : copyState === "failed"
              ? "Copy failed. Select the token and copy it manually before continuing."
              : closeBlocked
                ? "Confirm that the token is stored before closing this dialog."
                : ""}
        </p>
        <label className="flex cursor-pointer items-start gap-3 rounded-md border border-border bg-input p-3 text-sm text-foreground">
          <input
            checked={stored}
            className="mt-0.5 size-4 accent-accent"
            onChange={(event) => {
              setStored(event.target.checked);
              setCloseBlocked(false);
            }}
            type="checkbox"
          />
          <span>
            I have stored this token securely and understand it cannot be shown
            again.
          </span>
        </label>
        <div className="flex justify-end">
          <Button disabled={!stored} onClick={onAcknowledged}>
            Finish and hide token
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
