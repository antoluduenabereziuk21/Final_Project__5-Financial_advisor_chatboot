import { ChatMessageSources } from "./ChatMessageSources"
import type { ChatMessageSourcesProps } from "./ChatMessageSourcesConfig"

function ChatMessageSourcesContainer(props: ChatMessageSourcesProps) {
  return <ChatMessageSources {...props} />
}

export { ChatMessageSourcesContainer }
