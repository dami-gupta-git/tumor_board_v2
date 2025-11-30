# Frontend Dockerfile for TumorBoard Angular App
# Multi-stage build for optimized production image

# Stage 1: Build Angular application
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package files
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci --silent

# Copy source code
COPY frontend/ ./

# Build for production
RUN npm run build -- --configuration production

# Stage 2: Serve with nginx
FROM nginx:1.25-alpine

# Copy custom nginx configuration
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

# Copy built application from builder stage
COPY --from=builder /app/dist/tumorboard /usr/share/nginx/html

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:80/health || exit 1

# Expose port
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
