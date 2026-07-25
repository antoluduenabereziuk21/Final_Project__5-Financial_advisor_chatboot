import { Card } from "./Card"
import type { CardProps } from "./CardConfig"

function CardContainer(props: CardProps) {
  return <Card {...props} />
}

export { CardContainer }
