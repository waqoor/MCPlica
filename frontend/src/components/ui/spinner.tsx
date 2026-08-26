import { LoaderCircle } from "lucide-react";
import { cn } from "@/lib/utils";

export function Spinner({
  label = "Loading",
  className,
}: {
  label?: string;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 text-sm text-muted",
        className,
      )}
      role="status"
    >
      <LoaderCircle
        aria-hidden="true"
        className="size-4 animate-spin motion-reduce:animate-none"
      />
      <span>{label}</span>
    </span>
  );
}

export function PageSpinner({
  label = "Loading workspace",
}: {
  label?: string;
}) {
  return (
    <div className="grid min-h-64 place-items-center">
      <Spinner label={label} />
    </div>
  );
}
