import { AlertCircle, CheckCircle2, Info, TriangleAlert } from "lucide-react";
import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

type AlertTone = "info" | "success" | "warning" | "danger";
const icons = {
  info: Info,
  success: CheckCircle2,
  warning: TriangleAlert,
  danger: AlertCircle,
};
const tones: Record<AlertTone, string> = {
  info: "border-info/35 bg-info/8 text-info-soft",
  success: "border-success/35 bg-success/8 text-success-soft",
  warning: "border-warning/40 bg-warning/8 text-warning-soft",
  danger: "border-danger/40 bg-danger/8 text-danger-soft",
};

type AlertProps = HTMLAttributes<HTMLDivElement> & {
  tone?: AlertTone;
  title?: string;
};

export function Alert({
  tone = "info",
  title,
  className,
  children,
  ...props
}: AlertProps) {
  const Icon = icons[tone];
  return (
    <div
      className={cn(
        "flex gap-3 rounded-lg border p-4 text-sm",
        tones[tone],
        className,
      )}
      role={tone === "danger" ? "alert" : "status"}
      {...props}
    >
      <Icon aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
      <div className="min-w-0">
        {title && <p className="mb-1 font-semibold text-foreground">{title}</p>}
        <div className="leading-6">{children}</div>
      </div>
    </div>
  );
}
