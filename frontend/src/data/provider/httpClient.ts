import axios from "axios"

import { getError } from "@/data/errorMappers/getError"

const createAxiosInstance = () => {
  return axios.create({
    baseURL: import.meta.env.VITE_API_URL ?? "",
    withCredentials: false,
    headers: {
      "Content-Type": "application/json",
    },
  })
}

const httpClient = createAxiosInstance()

httpClient.interceptors.request.use(async (config) => {
  if (config.skipSessionValidation) {
    return config
  }

  return config
})

httpClient.interceptors.response.use(undefined, (error) => {
  if (error.response?.status === 428) {
    return Promise.resolve(error.response)
  }

  const skipErrorLogging = error.config?.skipErrorLogging
  const mappedError = getError(error, skipErrorLogging)

  return Promise.reject(mappedError)
})

export { httpClient }
export default httpClient
