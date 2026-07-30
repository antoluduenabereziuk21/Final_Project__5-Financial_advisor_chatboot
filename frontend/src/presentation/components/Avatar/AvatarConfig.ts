import type { ComponentProps } from "react"
import { Avatar as AvatarPrimitive } from "@base-ui/react/avatar"

export type AvatarSize = "default" | "sm" | "lg"

export type AvatarProps = AvatarPrimitive.Root.Props & {
  size?: AvatarSize
}

export type AvatarImageProps = AvatarPrimitive.Image.Props
export type AvatarFallbackProps = AvatarPrimitive.Fallback.Props
export type AvatarBadgeProps = ComponentProps<"span">
export type AvatarGroupProps = ComponentProps<"div">
export type AvatarGroupCountProps = ComponentProps<"div">

export const avatarCopies = {
  fallbackLabel: "Avatar",
} as const
