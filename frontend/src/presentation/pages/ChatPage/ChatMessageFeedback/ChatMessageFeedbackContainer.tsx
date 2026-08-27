import { ChatMessageFeedback } from "./ChatMessageFeedback"
import type { ChatMessageFeedbackProps } from "./ChatMessageFeedbackConfig"

function ChatMessageFeedbackContainer(props: ChatMessageFeedbackProps) {
  return <ChatMessageFeedback {...props} />
}

export { ChatMessageFeedbackContainer }
