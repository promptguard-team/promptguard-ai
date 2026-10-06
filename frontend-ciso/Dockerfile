# # Base
# FROM node:20-alpine@sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293 AS base

# WORKDIR /app
# COPY package.json package-lock.json ./
# RUN npm ci

# # Development
# FROM base as dev

# USER node

# EXPOSE 5173

# CMD ["npm", "run", "dev", "--", "--host"]

# # Builder
# FROM base AS builder

# COPY . .
# RUN npm run build

# # Production
# FROM nginxinc/nginx-unprivileged:alpine AS prod

# COPY --from=builder /app/dist /usr/share/nginx/html

# EXPOSE 8080
# CMD ["nginx", "-g", "daemon off;"]

FROM nginxinc/nginx-unprivileged:alpine AS dev

USER root
RUN echo '<!DOCTYPE html><html><body style="background-color: #121212; color: #00ff00; font-family: monospace; text-align: center; margin-top: 20%;"><h1>🛡️ CISO Dashboard - Work In Progress (Mock)</h1><p>PromptGuard AI - LLM-Shield</p></body></html>' > /usr/share/nginx/html/index.html
USER nginx

EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
