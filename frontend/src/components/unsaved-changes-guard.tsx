import { useEffect } from "react";
import { useBlocker } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";

export function UnsavedChangesGuard({ active }: { readonly active: boolean }) {
  const blocker = useBlocker(active);
  useEffect(() => {
    if (!active) return;
    const guard = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", guard);
    return () => window.removeEventListener("beforeunload", guard);
  }, [active]);

  return (
    <Dialog
      description="Leaving now discards the values that have not been saved."
      onClose={() => blocker.reset?.()}
      open={blocker.state === "blocked"}
      title="Discard unsaved changes?"
    >
      <div className="flex justify-end gap-2">
        <Button onClick={() => blocker.reset?.()} variant="outline">
          Keep editing
        </Button>
        <Button onClick={() => blocker.proceed?.()} variant="destructive">
          Discard and leave
        </Button>
      </div>
    </Dialog>
  );
}
