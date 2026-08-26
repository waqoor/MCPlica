import { X } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";
import { Button } from "./button";

export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
}) {
  const closeButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    closeButton.current?.focus();
    const keydown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", keydown);
    return () => {
      document.removeEventListener("keydown", keydown);
      previous?.focus();
    };
  }, [onClose, open]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 grid place-items-center p-4">
      <button
        aria-label="Close dialog"
        className="absolute inset-0 cursor-default bg-black/65"
        onClick={onClose}
        type="button"
      />
      <div
        aria-describedby={description ? "dialog-description" : undefined}
        aria-labelledby="dialog-title"
        aria-modal="true"
        className="relative z-10 max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-xl border border-border-strong bg-panel p-5 shadow-dialog"
        role="dialog"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2
              className="text-lg font-semibold text-foreground"
              id="dialog-title"
            >
              {title}
            </h2>
            {description && (
              <p
                className="mt-1 text-sm leading-6 text-muted"
                id="dialog-description"
              >
                {description}
              </p>
            )}
          </div>
          <Button
            aria-label="Close dialog"
            onClick={onClose}
            ref={closeButton}
            size="icon"
            variant="ghost"
          >
            <X aria-hidden="true" className="size-5" />
          </Button>
        </div>
        <div className="mt-5">{children}</div>
      </div>
    </div>
  );
}
