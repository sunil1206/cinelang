FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# These are baked in at build time — pass real values via --build-arg or CI env
ARG NEXTAUTH_URL=http://localhost:3000
ARG NEXTAUTH_SECRET=changeme
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ARG GOOGLE_CLIENT_ID=
ARG GOOGLE_CLIENT_SECRET=

ENV NEXTAUTH_URL=$NEXTAUTH_URL
ENV NEXTAUTH_SECRET=$NEXTAUTH_SECRET
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV GOOGLE_CLIENT_ID=$GOOGLE_CLIENT_ID
ENV GOOGLE_CLIENT_SECRET=$GOOGLE_CLIENT_SECRET

RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000

CMD ["node", "server.js"]
