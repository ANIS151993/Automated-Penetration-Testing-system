FROM node:20-bookworm AS deps

WORKDIR /app

RUN corepack enable pnpm

COPY package.json pnpm-lock.yaml ./

RUN pnpm install --frozen-lockfile --config.confirmModulesPurge=false

FROM node:20-bookworm AS builder

WORKDIR /app

RUN corepack enable pnpm

COPY --from=deps /app/node_modules ./node_modules
COPY . .

ENV NEXT_TELEMETRY_DISABLED=1

RUN pnpm build

FROM node:20-bookworm-slim AS runner

WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000

CMD ["node", "server.js"]
