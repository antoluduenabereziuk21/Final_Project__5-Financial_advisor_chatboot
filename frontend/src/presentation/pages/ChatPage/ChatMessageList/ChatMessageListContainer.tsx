import { ChatMessageList } from "./ChatMessageList"
import type { ChatMessageListProps } from "./ChatMessageListConfig"

function ChatMessageListContainer(props: ChatMessageListProps) {
  return <ChatMessageList {...props} />
}

export { ChatMessageListContainer }
