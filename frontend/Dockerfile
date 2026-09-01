# The React build, served by nginx. Node is only in the build stage, so the
# published image is nginx plus a few hundred kilobytes of assets.
FROM node:22-alpine AS builder
WORKDIR /build
COPY package.json package-lock.json* ./
RUN npm ci || npm install
COPY tsconfig.json vite.config.ts index.html ./
COPY src/ ./src/
# Baked in at build time, because Vite inlines it. docker-compose passes the
# gateway's address; k8s passes the service address.
ARG VITE_API_BASE=http://localhost:8000
ENV VITE_API_BASE=$VITE_API_BASE
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=builder /build/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
# 127.0.0.1, not localhost: nginx listens on 0.0.0.0:80 (IPv4 only) while
# busybox wget resolves localhost to ::1 first and is refused, which marked a
# perfectly healthy container unhealthy.
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
