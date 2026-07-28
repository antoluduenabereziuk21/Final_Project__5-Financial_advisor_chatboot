import { Dialog } from "./Dialog"
import type { DialogProps } from "./DialogConfig"

function DialogContainer(props: DialogProps) {
  return <Dialog {...props} />
}

export { DialogContainer }
