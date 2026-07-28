import { Button } from "@/presentation/components/Button"

import type { IconButtonProps } from "./IconButtonConfig"

function IconButton({
  size = "icon",
  ariaLabel,
  children,
  ...props
}: IconButtonProps) {
  return (
    <Button size={size} aria-label={ariaLabel} {...props}>
      {children}
    </Button>
  )
}

export { IconButton }
