import axios from "axios"

import { HttpError } from "@/data/errors/HttpError"

function readErrorField(
  data: unknown,
  field: "message" | "code",
): string | undefined {
  if (typeof data !== "object" || data === null || !(field in data)) {
    return undefined
  }

  const value = (data as Record<string, unknown>)[field]
  return typeof value === "string" ? value : undefined
}

export function getError(
  error: unknown,
  _skipErrorLogging?: boolean,
): HttpError {
  if (error instanceof HttpError) {
    return error
  }

  if (axios.isCancel(error)) {
    return new HttpError(
      error instanceof Error ? error.message : "Request cancelled",
      "REQUEST_CANCELLED",
    )
  }

  if (axios.isAxiosError(error)) {
    if (error.code === axios.AxiosError.ERR_CANCELED) {
      return new HttpError(error.message || "Request cancelled", "REQUEST_CANCELLED")
    }

    const status = error.response?.status
    const data = error.response?.data
    const message =
      readErrorField(data, "message") ?? error.message ?? "Unexpected error"
    const code =
      readErrorField(data, "code") ?? `HTTP_${status ?? "UNKNOWN"}`

    return new HttpError(message, code, status, data)
  }

  if (error instanceof Error) {
    return new HttpError(error.message, "UNKNOWN_ERROR")
  }

  return new HttpError("Unexpected error", "UNKNOWN_ERROR")
}
