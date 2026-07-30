import { Button } from "./Button"
import type { ButtonProps } from "./ButtonConfig"

function ButtonContainer(props: ButtonProps) {
  return <Button {...props} />
}

export { ButtonContainer }
