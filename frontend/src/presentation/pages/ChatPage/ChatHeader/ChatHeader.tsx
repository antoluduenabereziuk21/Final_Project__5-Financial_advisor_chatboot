import { MenuIcon } from "lucide-react"

import { Button } from "@/presentation/components/Button"
import { Sheet, SheetContent, SheetTrigger } from "@/presentation/components/Sheet"

import { SearchHistorySidebar } from "../SearchHistorySidebar"
import { chatHeaderCopies, type ChatHeaderProps } from "./ChatHeaderConfig"

function ChatHeader({ title, searches, onNewChat }: ChatHeaderProps) {
  return (
    <header className="flex items-center gap-3 border-b border-border px-4 py-4 sm:px-6 sm:py-5">
      <Sheet>
        <SheetTrigger
          className="md:hidden"
          render={<Button variant="ghost" size="icon" />}
          aria-label={chatHeaderCopies.openMenu}
        >
          <MenuIcon aria-hidden="true" />
        </SheetTrigger>
        <SheetContent side="left" className="w-72 p-0" showCloseButton={false}>
          <SearchHistorySidebar searches={searches} onNewChat={onNewChat} />
        </SheetContent>
      </Sheet>
      <h1 className="font-heading text-xl font-semibold tracking-tight">
        {title}
      </h1>
    </header>
  )
}

export { ChatHeader }
