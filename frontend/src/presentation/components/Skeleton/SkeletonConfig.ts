import type { ComponentProps } from "react"

export type SkeletonProps = ComponentProps<"div">

export const skeletonCopies = {
  loadingLabel: "Loading",
} as const
