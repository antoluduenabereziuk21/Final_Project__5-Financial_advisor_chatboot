import { Alert } from "./Alert"
import type { AlertProps } from "./AlertConfig"

function AlertContainer(props: AlertProps) {
  return <Alert {...props} />
}

export { AlertContainer }
