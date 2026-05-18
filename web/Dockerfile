# base image
FROM node:22-alpine AS base

LABEL maintainer="synkora@example.com"

RUN apk add --no-cache tzdata
RUN corepack enable
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME/bin:$PNPM_HOME:$PATH"

# Accept build arguments for environment variables
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_APP_URL
ARG NEXT_PUBLIC_SENTRY_DSN

# Set them as environment variables for the build
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ENV NEXT_PUBLIC_APP_URL=${NEXT_PUBLIC_APP_URL}
ENV NEXT_PUBLIC_SENTRY_DSN=${NEXT_PUBLIC_SENTRY_DSN}


# install packages
FROM base AS packages

WORKDIR /app/web

COPY web/package.json web/pnpm-lock.yaml ./

# Install dependencies
RUN pnpm config set auto-install-peers true && pnpm config set strict-peer-dependencies false && pnpm install --frozen-lockfile


# build resources
FROM base AS builder

WORKDIR /app/web

COPY --from=packages /app/web/node_modules ./node_modules
COPY web/ .
COPY docs/docs/ /app/docs/docs/
COPY docs/blog/ /app/docs/blog/

ENV NODE_OPTIONS="--max-old-space-size=4096"

# Build for production
RUN pnpm build


# production stage
FROM base AS production

ENV NODE_ENV=production
ENV EDITION=SELF_HOSTED
ENV DEPLOY_ENV=PRODUCTION
ENV PORT=3000
ENV NEXT_TELEMETRY_DISABLED=1
ENV PM2_INSTANCES=2



# Set timezone
ENV TZ=UTC
RUN ln -s /usr/share/zoneinfo/${TZ} /etc/localtime \
    && echo ${TZ} > /etc/timezone

WORKDIR /app/web

# Copy built application
COPY --from=builder /app/web/.next/standalone ./
COPY --from=builder /app/web/.next/static ./.next/static
COPY --from=builder /app/web/public ./public

# Copy entrypoint script
COPY web/docker/entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

# Install PM2 globally for process management
RUN pnpm add -g pm2 \
    && mkdir /.pm2 \
    && chown -R 1001:0 /.pm2 /app/web \
    && chmod -R g=u /.pm2 /app/web

ARG COMMIT_SHA
ENV COMMIT_SHA=${COMMIT_SHA}

USER 1001
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD wget -q --spider http://localhost:3000/ || exit 1

ENTRYPOINT ["/bin/sh", "./entrypoint.sh"]
