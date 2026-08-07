import type { ChatComposerDisclaimerProps } from "./ChatComposerDisclaimerConfig"

function ChatComposerDisclaimer({ text }: ChatComposerDisclaimerProps) {
  return (
    <p className="text-center text-xs text-muted-foreground">{text}</p>
  )
}

export { ChatComposerDisclaimer }
