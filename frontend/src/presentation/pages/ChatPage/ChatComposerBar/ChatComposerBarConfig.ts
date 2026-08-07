export interface ChatComposerBarProps {
  isSending: boolean
  onSend: (content: string) => void | Promise<void>
}

export const chatComposerBarCopies = {} as const
