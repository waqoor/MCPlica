import { cva } from "class-variance-authority";

export const buttonVariants = cva(
  "inline-flex min-h-11 min-w-11 cursor-pointer items-center justify-center gap-2 rounded-md border px-4 py-2 text-sm font-semibold transition-[color,background-color,border-color,box-shadow] duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-canvas disabled:cursor-not-allowed disabled:opacity-45",
  {
    variants: {
      variant: {
        primary:
          "border-accent bg-accent text-accent-ink shadow-action hover:border-accent-strong hover:bg-accent-strong",
        secondary:
          "border-border-strong bg-panel-raised text-foreground hover:bg-panel-hover",
        outline:
          "border-border-strong bg-transparent text-foreground hover:bg-panel-hover",
        ghost:
          "border-transparent bg-transparent text-muted hover:bg-panel-hover hover:text-foreground",
        destructive:
          "border-danger bg-danger text-danger-ink hover:border-danger-strong hover:bg-danger-strong",
      },
      size: {
        sm: "min-h-11 px-3 text-xs",
        md: "min-h-11 px-4",
        icon: "size-11 p-0",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);
