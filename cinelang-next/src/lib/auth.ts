import type { NextAuthOptions } from 'next-auth'
import GoogleProvider from 'next-auth/providers/google'
import CredentialsProvider from 'next-auth/providers/credentials'

const BACKEND = process.env.BACKEND_URL || 'http://localhost:8000'

export const authOptions: NextAuthOptions = {
  providers: [
    GoogleProvider({
      clientId:     process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
      authorization: { params: { scope: 'openid email profile' } },
    }),

    CredentialsProvider({
      name: 'Email',
      credentials: {
        email:    { label: 'Email',    type: 'email' },
        password: { label: 'Password', type: 'password' },
        mode:     { label: 'Mode',     type: 'text' },
        name:     { label: 'Name',     type: 'text' },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) return null

        const isRegister = credentials.mode === 'register'
        const endpoint   = isRegister ? '/api/auth/register' : '/api/auth/login'
        const body: Record<string, string> = {
          email:    credentials.email,
          password: credentials.password,
        }
        if (isRegister && credentials.name) body.name = credentials.name

        const res = await fetch(`${BACKEND}${endpoint}`, {
          method:  'POST',
          headers: { 'Content-Type': 'application/json' },
          body:    JSON.stringify(body),
        })

        if (!res.ok) {
          const err = await res.json().catch(() => ({}))
          throw new Error(err?.error?.message || 'Authentication failed')
        }

        const data = await res.json()
        return {
          id:             String(data.user.id),
          email:          data.user.email,
          name:           data.user.name,
          image:          data.user.picture ?? null,
          backendToken:   data.tokens.access_token,
          backendRefresh: data.tokens.refresh_token,
          backendUser:    data.user,
        }
      },
    }),
  ],

  callbacks: {
    async jwt({ token, account, user }) {
      if (account?.id_token) {
        try {
          const res = await fetch(`${BACKEND}/api/auth/google`, {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ id_token: account.id_token }),
          })
          if (res.ok) {
            const data = await res.json()
            token.backendToken   = data.tokens?.access_token ?? data.token
            token.backendRefresh = data.tokens?.refresh_token
            token.backendUser    = data.user
          }
        } catch (e) {
          console.error('Backend auth exchange failed:', e)
        }
      }

      if (account?.type === 'credentials' && user) {
        token.backendToken   = (user as any).backendToken
        token.backendRefresh = (user as any).backendRefresh
        token.backendUser    = (user as any).backendUser
      }

      return token
    },

    async session({ session, token }) {
      session.backendToken = token.backendToken as string | undefined
      session.backendUser  = token.backendUser  as object | undefined
      return session
    },
  },

  pages: {
    signIn: '/',
    error:  '/',
  },
}
