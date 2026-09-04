export interface ChatComposerProps {
  value: string
  isSending: boolean
  onValueChange: (value: string) => void
  onSend: () => void
  onCancel: () => void
  onAttach?: () => void
}

export interface ChatComposerContainerProps {
  isSending: boolean
  onSend: (content: string) => boolean | Promise<boolean>
  onCancel: () => void
}

export const chatComposerCopies = {
  inputId: "chat-composer-input",
  placeholder: "Ask a follow-up question...",
  disclaimer:
    "Financial data may be delayed. Verify important information in the original sources.",
} as const
