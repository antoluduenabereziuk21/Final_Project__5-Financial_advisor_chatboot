import type { ComponentProps } from "react"

export type SpinnerProps = ComponentProps<"svg">

export const spinnerCopies = {
  loadingLabel: "Loading",
} as const
