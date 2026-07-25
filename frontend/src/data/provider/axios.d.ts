import "axios"

declare module "axios" {
  export interface AxiosRequestConfig {
    skipSessionValidation?: boolean
    skipErrorLogging?: boolean
  }
}
