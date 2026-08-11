export interface ChatComposerSendButtonProps {
  disabled: boolean
  onSend: () => void
}

export const chatComposerSendButtonCopies = {
  ariaLabel: "Send message",
} as const
