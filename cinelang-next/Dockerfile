FROM node:20-alpine AS deps
WORKDIR /app
# Limit Node memory for low-RAM servers (1GB)
ENV NODE_OPTIONS="--max-old-space-size=512"
COPY package.json package-lock.json* ./
# --prefer-offline avoids re-downloading, --no-audit skips slow audit network call
RUN npm ci --prefer-offline --no-audit --no-fund

FROM node:20-alpine AS builder
WORKDIR /app
ENV NODE_OPTIONS="--max-old-space-size=512"
COPY --from=deps /app/node_modules ./node_modules
COPY . .

ARG NEXTAUTH_URL=http://localhost:3000
ARG NEXTAUTH_SECRET=changeme
ARG NEXT_PUBLIC_API_URL=
ARG GOOGLE_CLIENT_ID=
ARG GOOGLE_CLIENT_SECRET=

ENV NEXTAUTH_URL=$NEXTAUTH_URL
ENV NEXTAUTH_SECRET=$NEXTAUTH_SECRET
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV GOOGLE_CLIENT_ID=$GOOGLE_CLIENT_ID
ENV GOOGLE_CLIENT_SECRET=$GOOGLE_CLIENT_SECRET
ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000
CMD ["node", "server.js"]
