import { cn } from "@/lib/utils"

import { skeletonCopies, type SkeletonProps } from "./SkeletonConfig"

function Skeleton({
  className,
  "aria-label": ariaLabel,
  ...props
}: SkeletonProps) {
  return (
    <div
      data-slot="skeleton"
      aria-label={ariaLabel ?? skeletonCopies.loadingLabel}
      className={cn("animate-pulse rounded-2xl bg-muted", className)}
      {...props}
    />
  )
}

export { Skeleton }
