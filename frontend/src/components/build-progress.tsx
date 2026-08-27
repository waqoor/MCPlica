import { Check, Circle, LoaderCircle, X } from "lucide-react";
import type { BuildStatus } from "@/api/contracts";
import { cn } from "@/lib/utils";

const stages: BuildStatus[] = [
  "QUEUED",
  "INGESTING",
  "PARSING",
  "INDEXING",
  "ANALYZING",
  "COMPILING",
  "VALIDATING",
  "PACKAGING",
  "READY",
];

export function BuildProgress({
  status,
  pipelineStage,
}: {
  status: BuildStatus;
  pipelineStage: BuildStatus | null;
}) {
  const terminalFailure = status === "FAILED" || status === "CANCELLED";
  const authoritativeStage = terminalFailure ? pipelineStage : status;
  const currentIndex = authoritativeStage
    ? stages.indexOf(authoritativeStage)
    : -1;
  return (
    <div
      aria-label={`Build status: ${status.toLowerCase()}`}
      className="overflow-x-auto pb-2"
      role="group"
    >
      <ol className="compile-rail flex min-w-[44rem] items-start">
        {stages.map((stage, index) => {
          const done = status === "READY" || currentIndex > index;
          const current = !terminalFailure && currentIndex === index;
          const failed = terminalFailure && currentIndex === index;
          const Icon = failed
            ? X
            : done
              ? Check
              : current
                ? LoaderCircle
                : Circle;
          return (
            <li
              className="relative flex flex-1 flex-col items-center text-center"
              key={stage}
            >
              <span
                className={cn(
                  "relative z-10 grid size-7 place-items-center rounded-full border bg-canvas",
                  done && "border-success text-success-soft",
                  current && "border-accent text-accent",
                  failed && "border-danger text-danger-soft",
                  !done &&
                    !current &&
                    !failed &&
                    "border-border-strong text-muted",
                )}
              >
                <Icon
                  aria-hidden="true"
                  className={cn(
                    "size-3.5",
                    current && "animate-spin motion-reduce:animate-none",
                  )}
                />
              </span>
              <span
                className={cn(
                  "mt-2 font-mono text-[0.62rem] uppercase tracking-[0.08em] text-muted",
                  (done || current) && "text-foreground",
                )}
              >
                {stage}
              </span>
            </li>
          );
        })}
      </ol>
      {terminalFailure && (
        <p className="mt-3 text-sm text-muted">
          {pipelineStage
            ? `${status === "FAILED" ? "Failed" : "Cancelled"} during ${pipelineStage.toLowerCase()}.`
            : "The exact terminal stage is unavailable for this legacy build."}
        </p>
      )}
    </div>
  );
}
