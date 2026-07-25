import { Tooltip } from "./Tooltip"
import type { TooltipProps } from "./TooltipConfig"

function TooltipContainer(props: TooltipProps) {
  return <Tooltip {...props} />
}

export { TooltipContainer }
