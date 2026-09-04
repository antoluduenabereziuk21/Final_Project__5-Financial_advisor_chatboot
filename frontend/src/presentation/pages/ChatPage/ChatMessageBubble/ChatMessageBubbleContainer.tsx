import { ChatMessageBubble } from "./ChatMessageBubble"
import type { ChatMessageBubbleProps } from "./ChatMessageBubbleConfig"

function ChatMessageBubbleContainer(props: ChatMessageBubbleProps) {
  return <ChatMessageBubble {...props} />
}

export { ChatMessageBubbleContainer }
