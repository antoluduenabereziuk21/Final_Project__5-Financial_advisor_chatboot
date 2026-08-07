import { Alert, AlertDescription, AlertTitle } from "@/presentation/components/Alert"

import type { ChatErrorProps } from "./ChatErrorConfig"

function ChatError({ title, message }: ChatErrorProps) {
  return (
    <Alert variant="destructive">
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  )
}

export { ChatError }
