# syntax=docker/dockerfile:1

# Stage 1: build
FROM node:20-alpine AS builder

WORKDIR /app

# Copy manifests first so layer is cached unless deps change
COPY package.json package-lock.json* ./
RUN npm ci --prefer-offline

# Build-time env: tell the React app where the agent API lives.
# Overridden in docker-compose via build.args; the fallback keeps the
# container usable for local docker builds without compose.
ARG VITE_API_URL=http://localhost:8080
ENV VITE_API_URL=$VITE_API_URL

COPY . .
RUN npm run build

# Stage 2: serve
FROM nginx:1.27-alpine AS runtime

# Remove default nginx page
RUN rm -rf /usr/share/nginx/html/*

# Copy the Vite output
COPY --from=builder /app/dist /usr/share/nginx/html

# Nginx config: serve the SPA and proxy /api/* + /media/* to the agent.
# The agent hostname is resolved via Docker Compose's internal DNS.
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
