import { ChatComposerBar } from "./ChatComposerBar"
import { ChatHeader } from "./ChatHeader"
import { ChatMessageList } from "./ChatMessageList"
import { SearchHistorySidebar } from "./SearchHistorySidebar"
import { chatPageCopies, type ChatPageProps } from "./ChatPageConfig"

function ChatPage({
  messages,
  searches,
  isSending,
  error,
  messagesEndRef,
  onSend,
  onNewChat,
}: ChatPageProps) {
  return (
    <main className="flex h-svh overflow-hidden bg-background text-foreground">
      <aside className="hidden w-72 shrink-0 border-r border-border md:block">
        <SearchHistorySidebar searches={searches} onNewChat={onNewChat} />
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <ChatHeader title={chatPageCopies.title} searches={searches} onNewChat={onNewChat} />
        <ChatMessageList
          messages={messages}
          isSending={isSending}
          error={error}
          messagesEndRef={messagesEndRef}
        />
        <ChatComposerBar isSending={isSending} onSend={onSend} />
      </div>
    </main>
  )
}

export { ChatPage }
