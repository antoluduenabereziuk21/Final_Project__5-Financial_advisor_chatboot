import { Loader2Icon } from "lucide-react"

import { cn } from "@/lib/utils"

import { spinnerCopies, type SpinnerProps } from "./SpinnerConfig"

function Spinner({
  className,
  "aria-label": ariaLabel,
  ...props
}: SpinnerProps) {
  return (
    <Loader2Icon
      data-slot="spinner"
      role="status"
      aria-label={ariaLabel ?? spinnerCopies.loadingLabel}
      className={cn("size-4 animate-spin", className)}
      {...props}
    />
  )
}

export { Spinner }
