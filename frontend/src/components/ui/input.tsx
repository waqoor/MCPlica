import type { InputHTMLAttributes } from "react"
import { cn } from "@/lib/utils"

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-10 w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 text-sm outline-none focus:border-zinc-400",
        className,
      )}
      {...props}
    />
  )
}
