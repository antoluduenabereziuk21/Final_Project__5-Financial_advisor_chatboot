import { ChatMessageMarkdown } from "./ChatMessageMarkdown"
import type { ChatMessageMarkdownProps } from "./ChatMessageMarkdownConfig"

function ChatMessageMarkdownContainer(props: ChatMessageMarkdownProps) {
  return <ChatMessageMarkdown {...props} />
}

export { ChatMessageMarkdownContainer }
