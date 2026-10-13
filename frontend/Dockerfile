# Stage 1: Build the React + Vite static bundle
FROM node:20-alpine AS builder

WORKDIR /app

# Copy dependency specifications first for Docker cache optimization
COPY package*.json ./
RUN npm ci

# Copy application source files
COPY . .

# Build production assets (VITE_API_BASE_URL default empty for same-origin proxy)
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN npm run build

# Stage 2: Production Nginx web server
FROM nginx:1.25-alpine

# Copy built static files to Nginx docroot
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
