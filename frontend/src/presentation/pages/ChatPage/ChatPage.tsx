import { ChatComposerBar } from "./ChatComposerBar"
import { ChatHeader } from "./ChatHeader"
import { ChatMessageList } from "./ChatMessageList"
import { ChatQuestionHistory } from "./ChatQuestionHistory"
import { chatPageCopies, type ChatPageProps } from "./ChatPageConfig"

function ChatPage({
  messages,
  conversationId,
  feedbackByMessageId,
  isSending,
  error,
  messagesEndRef,
  onSend,
  onCancel,
  onFeedback,
}: ChatPageProps) {
  return (
    <main className="flex h-svh flex-col overflow-hidden bg-background text-foreground">
      <ChatHeader title={chatPageCopies.title} />
      <div className="relative min-h-0 flex-1 overflow-hidden">
        <ChatMessageList
          messages={messages}
          conversationId={conversationId}
          feedbackByMessageId={feedbackByMessageId}
          isSending={isSending}
          error={error}
          messagesEndRef={messagesEndRef}
          onFeedback={onFeedback}
        />
        <ChatQuestionHistory messages={messages} />
      </div>
      <ChatComposerBar
        isSending={isSending}
        onSend={onSend}
        onCancel={onCancel}
      />
    </main>
  )
}

export { ChatPage }
