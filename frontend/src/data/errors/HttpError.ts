export class HttpError extends Error {
  readonly code: string
  readonly status?: number
  readonly data?: unknown

  constructor(
    message: string,
    code: string,
    status?: number,
    data?: unknown,
  ) {
    super(message)
    this.name = "HttpError"
    this.code = code
    this.status = status
    this.data = data
  }
}
