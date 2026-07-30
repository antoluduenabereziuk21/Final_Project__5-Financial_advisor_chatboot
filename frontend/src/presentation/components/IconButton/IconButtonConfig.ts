import type { ReactNode } from "react"

import type { ButtonProps } from "@/presentation/components/Button"

export type IconButtonSize = "icon" | "icon-xs" | "icon-sm" | "icon-lg"

export type IconButtonProps = Omit<ButtonProps, "size" | "children" | "aria-label"> & {
  size?: IconButtonSize
  children: ReactNode
  ariaLabel: string
}

export const iconButtonCopies = {
  ariaLabelRequired: "Icon button requires an accessible label",
} as const
