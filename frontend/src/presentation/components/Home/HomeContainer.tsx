import { useWelcome } from "@/presentation/hooks/useWelcome"

import { Home } from "./Home"
import { homeCopies } from "./HomeConfig"

function HomeContainer() {
  const { content, isLoading, error } = useWelcome()

  function handleStartConversation() {
    return
  }

  return (
    <Home
      title={content?.title ?? homeCopies.brand}
      description={content?.description ?? ""}
      ctaLabel={content?.ctaLabel ?? homeCopies.startConversationAriaLabel}
      isLoading={isLoading}
      error={error}
      onStartConversation={handleStartConversation}
    />
  )
}

export { HomeContainer }
