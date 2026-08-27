import { cn } from "@/lib/utils"

import {
  chatQuestionHistoryCopies,
  type ChatQuestionHistoryProps,
} from "./ChatQuestionHistoryConfig"

function ChatQuestionHistory({
  items,
  isOpen,
  selectedId,
  onOpenChange,
  onSelect,
}: ChatQuestionHistoryProps) {
  if (items.length === 0) {
    return null
  }

  return (
    <aside
      className="pointer-events-auto absolute top-1/2 right-3 z-20 -translate-y-1/2"
      onMouseEnter={() => onOpenChange(true)}
      onMouseLeave={() => onOpenChange(false)}
      onFocusCapture={() => onOpenChange(true)}
      onBlurCapture={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
          onOpenChange(false)
        }
      }}
      aria-label={chatQuestionHistoryCopies.regionLabel}
    >
      <div
        className={cn(
          "overflow-hidden rounded-2xl border border-border bg-card/95 shadow-lg backdrop-blur-sm transition-[width,padding] duration-200",
          isOpen ? "w-64 p-2" : "w-5 px-1.5 py-3",
        )}
      >
        {isOpen ? (
          <ul className="flex max-h-[min(70vh,28rem)] flex-col gap-1 overflow-y-auto">
            {items.map((item) => {
              const isSelected = item.id === selectedId

              return (
                <li key={item.id}>
                  <button
                    type="button"
                    className={cn(
                      "w-full rounded-xl px-3 py-2 text-left text-xs leading-snug text-muted-foreground transition-colors",
                      "hover:bg-muted hover:text-foreground",
                      isSelected && "bg-muted text-foreground",
                    )}
                    aria-label={`${chatQuestionHistoryCopies.selectQuestionLabel}: ${item.content}`}
                    onClick={() => onSelect(item.id)}
                  >
                    <span className="line-clamp-2">{item.content}</span>
                  </button>
                </li>
              )
            })}
          </ul>
        ) : (
          <div
            className="flex flex-col items-center gap-1.5"
            aria-hidden="true"
          >
            {items.map((item) => (
              <span
                key={item.id}
                className={cn(
                  "h-0.5 w-2.5 rounded-full bg-muted-foreground/45",
                  item.id === selectedId && "bg-foreground/70",
                )}
              />
            ))}
          </div>
        )}
      </div>
    </aside>
  )
}

export { ChatQuestionHistory }
