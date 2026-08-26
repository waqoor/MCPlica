import type { HTMLAttributes, LabelHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export function Label({
  className,
  htmlFor,
  children,
  ...props
}: LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label
      htmlFor={htmlFor}
      className={cn("text-sm font-medium text-foreground", className)}
      {...props}
    >
      {children}
    </label>
  );
}

export function FieldHelp({
  className,
  ...props
}: HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p className={cn("text-xs leading-5 text-muted", className)} {...props} />
  );
}

export function FieldError({
  className,
  ...props
}: HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p
      className={cn("text-xs leading-5 text-danger-soft", className)}
      role="alert"
      {...props}
    />
  );
}
