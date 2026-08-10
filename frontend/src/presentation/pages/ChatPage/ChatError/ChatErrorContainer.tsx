import { ChatError } from "./ChatError"
import type { ChatErrorProps } from "./ChatErrorConfig"

function ChatErrorContainer(props: ChatErrorProps) {
  return <ChatError {...props} />
}

export { ChatErrorContainer }
