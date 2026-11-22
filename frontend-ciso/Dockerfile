# Base
FROM node:22-alpine@sha256:1314fb30ec37592d5845e5a160d522c0e680972aa534549940b8d73bde88481a AS base

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# Development
FROM base AS dev

# Vite writes its cache under node_modules/.vite; the dev server runs as `node`.
RUN chown -R node:node /app
USER node

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host"]

# Builder
FROM base AS builder

COPY . .
RUN npm run build

# Production
FROM nginxinc/nginx-unprivileged:alpine AS prod

COPY nginx.conf /etc/nginx/conf.d/default.conf
# Built with base '/ciso/', so the files live under that path too.
COPY --from=builder /app/dist /usr/share/nginx/html/ciso

EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
