import { useState } from "react"

import { Demo } from "./Demo"

function DemoContainer() {
  const [textareaValue, setTextareaValue] = useState("")

  return (
    <Demo
      textareaValue={textareaValue}
      onTextareaChange={setTextareaValue}
    />
  )
}

export { DemoContainer }
