FROM node:24-alpine AS build
WORKDIR /app
RUN corepack enable
COPY frontend/package.json ./
RUN pnpm install --no-frozen-lockfile
COPY frontend/ ./
RUN pnpm build

FROM nginx:1.27-alpine
COPY infra/docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
