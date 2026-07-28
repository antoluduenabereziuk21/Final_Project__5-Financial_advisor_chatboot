import { ScrollArea as ScrollAreaPrimitive } from "@base-ui/react/scroll-area"

export type ScrollAreaProps = ScrollAreaPrimitive.Root.Props
export type ScrollBarProps = ScrollAreaPrimitive.Scrollbar.Props

export const scrollAreaCopies = {
  scrollbarLabel: "Scroll",
} as const
