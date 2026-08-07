import { MessageSquareTextIcon, PlusIcon, SearchIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { Button } from "@/presentation/components/Button"
import { ScrollArea } from "@/presentation/components/ScrollArea"

import {
  searchHistorySidebarCopies,
  type SearchHistorySidebarProps,
} from "./SearchHistorySidebarConfig"

function SearchHistorySidebar({ searches, onNewChat, className }: SearchHistorySidebarProps) {
  return (
    <div className={cn("flex h-full min-h-0 flex-col bg-card text-card-foreground", className)}>
      <div className="flex items-center gap-2 border-b border-border px-4 py-5">
        <MessageSquareTextIcon className="size-5 text-primary" aria-hidden="true" />
        <span className="font-heading font-semibold">{searchHistorySidebarCopies.brand}</span>
      </div>
      <div className="p-3">
        <Button className="w-full justify-start" onClick={onNewChat}>
          <PlusIcon data-icon="inline-start" aria-hidden="true" />
          {searchHistorySidebarCopies.newChat}
        </Button>
      </div>
      <div className="flex min-h-0 flex-1 flex-col px-3 pb-3">
        <div className="flex items-center gap-2 px-2 py-3 text-xs font-semibold tracking-wider text-muted-foreground uppercase">
          <SearchIcon className="size-3.5" aria-hidden="true" />
          {searchHistorySidebarCopies.historyTitle}
        </div>
        {searches.length === 0 ? (
          <p className="px-2 py-3 text-sm leading-relaxed text-muted-foreground">
            {searchHistorySidebarCopies.emptyHistory}
          </p>
        ) : (
          <ScrollArea className="min-h-0 flex-1">
            <ol className="flex flex-col gap-1 pr-2">
              {searches.map((search, index) => (
                <li key={`${index}-${search}`} className="rounded-xl px-3 py-2.5 text-sm leading-snug text-muted-foreground transition-colors hover:bg-muted hover:text-foreground" title={search}>
                  <span className="line-clamp-2">{search}</span>
                </li>
              ))}
            </ol>
          </ScrollArea>
        )}
      </div>
    </div>
  )
}

export { SearchHistorySidebar }
