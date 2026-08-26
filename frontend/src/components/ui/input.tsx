import type { InputHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export function Input({
  className,
  ...props
}: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "min-h-11 w-full rounded-md border border-border-strong bg-input px-3 text-sm text-foreground placeholder:text-muted/75 outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/20 disabled:cursor-not-allowed disabled:opacity-55 aria-invalid:border-danger aria-invalid:ring-danger/20",
        className,
      )}
      {...props}
    />
  );
}
