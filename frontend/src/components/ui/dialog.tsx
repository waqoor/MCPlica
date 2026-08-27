import { X } from "lucide-react";
import { useEffect, useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { cn } from "@/lib/utils";
import { Button } from "./button";

const FOCUSABLE = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

let modalDepth = 0;
let savedOverflow = "";
let savedOverscroll = "";
const modalStack: symbol[] = [];

export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
  variant = "dialog",
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  variant?: "dialog" | "sheet";
}) {
  const closeButton = useRef<HTMLButtonElement>(null);
  const overlay = useRef<HTMLDivElement>(null);
  const content = useRef<HTMLDivElement>(null);
  const modalId = useRef(Symbol("modal"));
  const close = useRef(onClose);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    close.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    const id = modalId.current;
    modalStack.push(id);
    closeButton.current?.focus();
    const keydown = (event: KeyboardEvent) => {
      if (modalStack.at(-1) !== id) return;
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopImmediatePropagation();
        close.current();
        return;
      }
      if (event.key !== "Tab" || !content.current) return;
      const focusable = Array.from(
        content.current.querySelectorAll<HTMLElement>(FOCUSABLE),
      ).filter(
        (element) =>
          !element.hidden &&
          !element.closest("[hidden]") &&
          !element.closest("[inert]"),
      );
      if (!focusable.length) {
        event.preventDefault();
        content.current.focus();
        return;
      }
      const first = focusable[0]!;
      const last = focusable.at(-1)!;
      if (!content.current.contains(document.activeElement)) {
        event.preventDefault();
        (event.shiftKey ? last : first).focus();
      } else if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    const siblings = Array.from(document.body.children).filter(
      (element) => element !== overlay.current,
    );
    const siblingState = siblings.map((element) => ({
      element,
      inert: (element as HTMLElement).inert,
      inertAttribute: element.hasAttribute("inert"),
      ariaHidden: element.getAttribute("aria-hidden"),
    }));
    for (const sibling of siblings) {
      (sibling as HTMLElement).inert = true;
      sibling.setAttribute("inert", "");
      sibling.setAttribute("aria-hidden", "true");
    }
    if (modalDepth++ === 0) {
      savedOverflow = document.body.style.overflow;
      savedOverscroll = document.body.style.overscrollBehavior;
      document.body.style.overflow = "hidden";
      document.body.style.overscrollBehavior = "contain";
    }
    document.addEventListener("keydown", keydown);
    return () => {
      document.removeEventListener("keydown", keydown);
      const stackIndex = modalStack.lastIndexOf(id);
      if (stackIndex >= 0) modalStack.splice(stackIndex, 1);
      for (const state of siblingState) {
        (state.element as HTMLElement).inert = state.inert;
        if (state.inertAttribute) state.element.setAttribute("inert", "");
        else state.element.removeAttribute("inert");
        if (state.ariaHidden === null)
          state.element.removeAttribute("aria-hidden");
        else state.element.setAttribute("aria-hidden", state.ariaHidden);
      }
      modalDepth = Math.max(0, modalDepth - 1);
      if (modalDepth === 0) {
        document.body.style.overflow = savedOverflow;
        document.body.style.overscrollBehavior = savedOverscroll;
      }
      previous?.focus();
    };
  }, [open]);

  if (!open) return null;
  return createPortal(
    <div
      className={cn(
        "fixed inset-0 z-50",
        variant === "sheet" ? "flex p-0" : "grid place-items-center p-4",
      )}
      ref={overlay}
    >
      <button
        aria-hidden="true"
        className="absolute inset-0 cursor-default bg-scrim/68"
        onClick={() => close.current()}
        tabIndex={-1}
        type="button"
      />
      <div
        aria-describedby={description ? descriptionId : undefined}
        aria-labelledby={titleId}
        aria-modal="true"
        className={cn(
          "surface-panel relative z-10 overflow-y-auto border border-border-strong bg-panel shadow-dialog overscroll-contain",
          variant === "sheet"
            ? "h-full max-h-none w-[min(19rem,88vw)] rounded-none border-y-0 border-l-0 p-0"
            : "max-h-[90vh] w-full max-w-lg rounded-xl p-5",
        )}
        ref={content}
        role="dialog"
        tabIndex={-1}
      >
        <div
          className={cn(
            "flex items-start justify-between gap-4",
            variant === "sheet" && "absolute right-3 top-3 z-20",
          )}
        >
          <div>
            <h2
              className={cn(
                "text-lg font-semibold text-foreground",
                variant === "sheet" && "sr-only",
              )}
              id={titleId}
            >
              {title}
            </h2>
            {description && (
              <p
                className="mt-1 text-sm leading-6 text-muted"
                id={descriptionId}
              >
                {description}
              </p>
            )}
          </div>
          <Button
            aria-label="Close dialog"
            onClick={() => close.current()}
            ref={closeButton}
            size="icon"
            variant="ghost"
          >
            <X aria-hidden="true" className="size-5" />
          </Button>
        </div>
        <div className={variant === "sheet" ? "h-full" : "mt-5"}>
          {children}
        </div>
      </div>
    </div>,
    document.body,
  );
}
