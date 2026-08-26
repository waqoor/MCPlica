import type { ReactNode } from "react";

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="flex flex-col justify-between gap-4 border-b border-border pb-5 sm:flex-row sm:items-end">
      <div className="min-w-0">
        {eyebrow && (
          <p className="mb-2 font-mono text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-accent">
            {eyebrow}
          </p>
        )}
        <h1 className="text-balance text-2xl font-semibold tracking-[-0.025em] text-foreground sm:text-3xl">
          {title}
        </h1>
        {description && (
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
            {description}
          </p>
        )}
      </div>
      {actions && (
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          {actions}
        </div>
      )}
    </header>
  );
}
