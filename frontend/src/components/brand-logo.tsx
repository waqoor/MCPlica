import type { ImgHTMLAttributes } from "react";
import primaryLogo from "@/assets/logo.png";
import compactLogo from "@/assets/logo_draw_only.png";
import { cn } from "@/lib/utils";

type BrandLogoProps = Pick<
  ImgHTMLAttributes<HTMLImageElement>,
  "alt" | "loading"
> & {
  className?: string;
  variant?: "primary" | "compact";
};

export function BrandLogo({
  alt = "MCPlica",
  className,
  loading = "lazy",
  variant = "primary",
}: BrandLogoProps) {
  const compact = variant === "compact";

  return (
    <span
      className={cn(
        "brand-logo",
        compact ? "brand-logo--compact" : "brand-logo--primary",
        className,
      )}
    >
      <img
        alt={alt}
        decoding="async"
        draggable={false}
        height={compact ? 1254 : 941}
        loading={loading}
        src={compact ? compactLogo : primaryLogo}
        width={compact ? 1254 : 1672}
      />
    </span>
  );
}
