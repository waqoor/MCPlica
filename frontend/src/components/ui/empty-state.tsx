import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  headingLevel = "h2",
}: {
  icon: LucideIcon;
  title: string;
  description: string;
  action?: ReactNode;
  headingLevel?: "h1" | "h2";
}) {
  const Heading = headingLevel;

  return (
    <div className="rounded-xl border border-dashed border-border-strong bg-panel/60 px-6 py-12 text-center">
      <span className="mx-auto mb-4 grid size-11 place-items-center rounded-lg border border-border bg-panel-raised text-accent">
        <Icon aria-hidden="true" className="size-5" />
      </span>
      <Heading className="text-base font-semibold text-foreground">
        {title}
      </Heading>
      <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted">
        {description}
      </p>
      {action && <div className="mt-5 flex justify-center">{action}</div>}
    </div>
  );
}
