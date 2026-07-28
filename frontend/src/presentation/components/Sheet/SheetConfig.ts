import type { ComponentProps } from "react"
import { Dialog as SheetPrimitive } from "@base-ui/react/dialog"

export type SheetSide = "top" | "right" | "bottom" | "left"

export type SheetProps = SheetPrimitive.Root.Props
export type SheetTriggerProps = SheetPrimitive.Trigger.Props
export type SheetCloseProps = SheetPrimitive.Close.Props
export type SheetPortalProps = SheetPrimitive.Portal.Props
export type SheetOverlayProps = SheetPrimitive.Backdrop.Props
export type SheetContentProps = SheetPrimitive.Popup.Props & {
  side?: SheetSide
  showCloseButton?: boolean
}
export type SheetHeaderProps = ComponentProps<"div">
export type SheetFooterProps = ComponentProps<"div">
export type SheetTitleProps = SheetPrimitive.Title.Props
export type SheetDescriptionProps = SheetPrimitive.Description.Props

export const sheetCopies = {
  close: "Close",
} as const
