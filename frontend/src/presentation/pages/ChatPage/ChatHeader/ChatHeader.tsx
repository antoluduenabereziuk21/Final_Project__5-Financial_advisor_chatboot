import type { ChatHeaderProps } from "./ChatHeaderConfig"

function ChatHeader({ title }: ChatHeaderProps) {
  return (
    <header className="shrink-0 border-b border-border px-6 py-5">
      <h1 className="font-heading text-xl font-semibold tracking-tight">
        {title}
      </h1>
    </header>
  )
}

export { ChatHeader }
