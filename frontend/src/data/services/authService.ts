import { storageService } from "@/data/services/storageService"

const ACCESS_TOKEN_KEY = "access_token"

export const authService = {
  getAccessToken(): string | null {
    return storageService.getItem(ACCESS_TOKEN_KEY)
  },

  async getValidAccessToken(): Promise<string | null> {
    return this.getAccessToken()
  },

  setAccessToken(token: string): void {
    storageService.setItem(ACCESS_TOKEN_KEY, token)
  },

  clearAccessToken(): void {
    storageService.removeItem(ACCESS_TOKEN_KEY)
  },
}
