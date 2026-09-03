FROM node:24.16.0-alpine3.24@sha256:21f403ab171f2dc89bad4dd69d7721bfd15f084ccb46cdd225f31f2bc59b5c9a AS build
ARG VERSION
WORKDIR /app
RUN corepack enable
COPY VERSION /VERSION
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN test -n "${VERSION}" \
    && test "$(cat /VERSION)" = "${VERSION}" \
    && node -e "if (require('./package.json').version !== process.env.VERSION) process.exit(1)" \
    && pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

FROM nginxinc/nginx-unprivileged:1.31.5-alpine3.24-slim@sha256:7d289d4f8935051d213bc3ecee3b4fc2d52f97ea5a954273e031054b633e7934
ARG VERSION
ARG VCS_REF=local
ARG SOURCE_URL=https://github.com/waqoor/MCPlica
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
