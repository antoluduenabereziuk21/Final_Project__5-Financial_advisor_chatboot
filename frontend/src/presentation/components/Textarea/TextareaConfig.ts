import type { ComponentProps } from "react"

export type TextareaProps = ComponentProps<"textarea">

export const textareaCopies = {
  placeholder: "Enter text",
} as const
