export interface ChatComposerSendButtonProps {
  isSending: boolean
  disabled: boolean
  onSend: () => void
  onCancel: () => void
}

export const chatComposerSendButtonCopies = {
  sendAriaLabel: "Send message",
  cancelAriaLabel: "Cancel message",
} as const
