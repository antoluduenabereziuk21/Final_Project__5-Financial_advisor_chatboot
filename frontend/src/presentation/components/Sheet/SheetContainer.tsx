import { Sheet } from "./Sheet"
import type { SheetProps } from "./SheetConfig"

function SheetContainer(props: SheetProps) {
  return <Sheet {...props} />
}

export { SheetContainer }
