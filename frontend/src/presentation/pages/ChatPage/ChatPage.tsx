import { ChatComposerBar } from "./ChatComposerBar"
import { ChatHeader } from "./ChatHeader"
import { ChatMessageList } from "./ChatMessageList"
import { chatPageCopies, type ChatPageProps } from "./ChatPageConfig"

function ChatPage({
  messages,
  isSending,
  error,
  messagesEndRef,
  onSend,
}: ChatPageProps) {
  return (
    <main className="flex h-svh flex-col bg-background text-foreground">
      <ChatHeader title={chatPageCopies.title} />
      <ChatMessageList
        messages={messages}
        isSending={isSending}
        error={error}
        messagesEndRef={messagesEndRef}
      />
      <ChatComposerBar isSending={isSending} onSend={onSend} />
    </main>
  )
}

export { ChatPage }
