export interface ChatComposerBarProps {
  isSending: boolean
  onSend: (content: string) => boolean | Promise<boolean>
  onCancel: () => void
}

export const chatComposerBarCopies = {} as const
