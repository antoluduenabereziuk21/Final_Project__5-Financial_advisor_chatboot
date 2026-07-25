import type { ComponentProps } from "react"
import { Popover as PopoverPrimitive } from "@base-ui/react/popover"

export type PopoverProps = PopoverPrimitive.Root.Props
export type PopoverTriggerProps = PopoverPrimitive.Trigger.Props
export type PopoverContentProps = PopoverPrimitive.Popup.Props &
  Pick<
    PopoverPrimitive.Positioner.Props,
    "align" | "alignOffset" | "side" | "sideOffset"
  >
export type PopoverHeaderProps = ComponentProps<"div">
export type PopoverTitleProps = PopoverPrimitive.Title.Props
export type PopoverDescriptionProps = PopoverPrimitive.Description.Props

export const popoverCopies = {
  defaultTitle: "Popover",
} as const
