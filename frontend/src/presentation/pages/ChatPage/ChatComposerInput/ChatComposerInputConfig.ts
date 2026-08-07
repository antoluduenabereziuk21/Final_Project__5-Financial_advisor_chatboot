export interface ChatComposerInputProps {
  id: string
  value: string
  placeholder: string
  disabled: boolean
  canSubmit: boolean
  onValueChange: (value: string) => void
  onSubmit: () => void
}

export const chatComposerInputCopies = {
  id: "chat-composer-input",
  placeholder: "Ask a follow-up question...",
} as const
