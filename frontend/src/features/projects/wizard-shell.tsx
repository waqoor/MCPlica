import { Check, Circle } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { cn } from "@/lib/utils";
import { wizardSteps } from "./wizard-steps";

export function WizardShell({
  step,
  projectId,
  buildId,
  children,
}: {
  step: number;
  projectId?: string | null;
  buildId?: string | null;
  children: ReactNode;
}) {
  return (
    <div className="mx-auto max-w-6xl">
      <header className="mb-7 border-b border-border pb-5">
        <p className="font-mono text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-accent">
          Project setup · Step {step} of 10
        </p>
        <div className="mt-2 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
              {wizardSteps[step - 1]}
            </h1>
            <p className="mt-2 text-sm text-muted">
              Complete the source-to-runtime workflow with explicit validation
              at every boundary.
            </p>
          </div>
          <Link
            className="text-sm font-medium text-muted hover:text-foreground"
            to={projectId ? `/projects/${projectId}` : "/projects"}
          >
            Exit setup
          </Link>
        </div>
      </header>

      <div className="grid gap-7 lg:grid-cols-[15rem_minmax(0,1fr)]">
        <nav aria-label="Project setup steps">
          <ol className="grid grid-cols-2 gap-1 sm:grid-cols-5 lg:grid-cols-1">
            {wizardSteps.map((label, index) => {
              const number = index + 1;
              const complete = number < step;
              const current = number === step;
              const params = new URLSearchParams({ step: String(number) });
              if (projectId) params.set("project", projectId);
              if (buildId) params.set("build", buildId);
              const content = (
                <span
                  className={cn(
                    "flex min-h-11 items-center gap-2 rounded-md border px-2.5 py-2 text-left text-xs transition",
                    current
                      ? "border-accent/50 bg-accent/10 text-foreground"
                      : "border-transparent text-muted",
                    complete && "text-foreground",
                  )}
                >
                  <span
                    className={cn(
                      "grid size-5 shrink-0 place-items-center rounded-full border font-mono text-[0.62rem]",
                      current
                        ? "border-accent text-accent"
                        : complete
                          ? "border-success text-success-soft"
                          : "border-border-strong",
                    )}
                  >
                    {complete ? (
                      <Check aria-hidden="true" className="size-3" />
                    ) : current ? (
                      <Circle
                        aria-hidden="true"
                        className="size-2 fill-current"
                      />
                    ) : (
                      number
                    )}
                  </span>
                  <span>{label}</span>
                </span>
              );
              return (
                <li key={label}>
                  {number <= step && (number === 1 || projectId) ? (
                    <Link
                      aria-current={current ? "step" : undefined}
                      className="block rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                      to={`/projects/new?${params}`}
                    >
                      {content}
                    </Link>
                  ) : (
                    content
                  )}
                </li>
              );
            })}
          </ol>
        </nav>
        <section aria-labelledby="wizard-step-title" className="min-w-0">
          {children}
        </section>
      </div>
    </div>
  );
}
