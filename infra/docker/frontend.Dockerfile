FROM node:24.16.0-alpine3.24@sha256:21f403ab171f2dc89bad4dd69d7721bfd15f084ccb46cdd225f31f2bc59b5c9a AS build
ARG VERSION
WORKDIR /app
RUN corepack enable
COPY VERSION /VERSION
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN test -n "${VERSION}" \
    && test "$(cat /VERSION)" = "${VERSION}" \
    && node -e "if (require('./package.json').version !== process.env.VERSION) process.exit(1)" \
    && pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

FROM nginxinc/nginx-unprivileged:1.31.4-alpine3.24-slim@sha256:d668aa123a6ec3216ba5ae6b398ae8001d5e81d3142d3659e20354fd0c3c3125
ARG VERSION
ARG VCS_REF=local
ARG SOURCE_URL=https://github.com/yazeedhasan97/MCPlica
LABEL org.opencontainers.image.title="MCPlica frontend" \
      org.opencontainers.image.description="MCPlica administrative web interface" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.source="${SOURCE_URL}" \
      org.opencontainers.image.licenses="AGPL-3.0-only"
USER root
COPY infra/docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
USER 101:101
EXPOSE 8080
