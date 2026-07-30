import type { ComponentProps } from "react"

export type CardSize = "default" | "sm"

export type CardProps = ComponentProps<"div"> & {
  size?: CardSize
}

export type CardHeaderProps = ComponentProps<"div">
export type CardTitleProps = ComponentProps<"div">
export type CardDescriptionProps = ComponentProps<"div">
export type CardActionProps = ComponentProps<"div">
export type CardContentProps = ComponentProps<"div">
export type CardFooterProps = ComponentProps<"div">

export const cardCopies = {
  defaultTitle: "Card",
} as const
