import type { KeyboardEvent } from "react"

import { Textarea } from "@/presentation/components/Textarea"

import type { ChatComposerInputProps } from "./ChatComposerInputConfig"

function ChatComposerInput({
  id,
  value,
  placeholder,
  disabled,
  canSubmit,
  onValueChange,
  onSubmit,
}: ChatComposerInputProps) {
  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault()

      if (canSubmit) {
        onSubmit()
      }
    }
  }

  return (
    <Textarea
      id={id}
      value={value}
      onChange={(event) => onValueChange(event.target.value)}
      onKeyDown={handleKeyDown}
      placeholder={placeholder}
      disabled={disabled}
      rows={1}
      className="min-h-10 flex-1 border-transparent bg-transparent px-1 py-2 shadow-none focus-visible:border-transparent focus-visible:ring-0"
      aria-label={placeholder}
    />
  )
}

export { ChatComposerInput }
