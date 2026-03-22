# Stage 1: Build frontend
FROM node:22-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Production backend
FROM python:3.11-slim AS production

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /usr/local/bin/uv

# Create non-root user
RUN groupadd -r mirofish && useradd -r -g mirofish -m mirofish

WORKDIR /app

# Install Python dependencies
COPY backend/pyproject.toml backend/uv.lock ./backend/
RUN cd backend && uv sync --frozen --no-dev

# Copy backend source
COPY backend/ ./backend/

# Copy built frontend
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Create required directories
RUN mkdir -p backend/uploads backend/logs && \
    chown -R mirofish:mirofish /app

# Switch to non-root user
USER mirofish

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5001/health')" || exit 1

EXPOSE 5001

# Production command with gunicorn
CMD ["uv", "run", "--directory", "backend", "gunicorn", "--config", "gunicorn.conf.py", "app:create_app()"]
