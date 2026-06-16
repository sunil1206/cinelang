import NextAuth, { DefaultSession } from 'next-auth'
import { JWT } from 'next-auth/jwt'

declare module 'next-auth' {
  interface Session {
    backendToken?: string
    backendUser?: {
      id: number
      email: string
      name: string
      picture?: string
    }
  }
}

declare module 'next-auth/jwt' {
  interface JWT {
    backendToken?:   string
    backendRefresh?: string
    backendUser?: {
      id: number
      email: string
      name: string
      picture?: string
    }
  }
}
