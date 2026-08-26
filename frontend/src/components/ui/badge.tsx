import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex min-h-6 items-center gap-1.5 rounded-full border px-2.5 py-0.5 font-mono text-[0.69rem] font-semibold uppercase tracking-[0.08em]",
  {
    variants: {
      tone: {
        neutral: "border-border-strong bg-panel-raised text-muted",
        info: "border-info/35 bg-info/10 text-info-soft",
        success: "border-success/35 bg-success/10 text-success-soft",
        warning: "border-warning/40 bg-warning/10 text-warning-soft",
        danger: "border-danger/40 bg-danger/10 text-danger-soft",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
);

type BadgeProps = HTMLAttributes<HTMLSpanElement> &
  VariantProps<typeof badgeVariants>;

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}
