import { ChatComposerInput } from "./ChatComposerInput"
import type { ChatComposerInputProps } from "./ChatComposerInputConfig"

function ChatComposerInputContainer(props: ChatComposerInputProps) {
  return <ChatComposerInput {...props} />
}

export { ChatComposerInputContainer }
