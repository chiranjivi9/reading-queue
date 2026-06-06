# ── Stage 1: Build the React frontend ────────────────────────────────────────
FROM node:20-alpine AS frontend-build

WORKDIR /app/frontend

# Install dependencies first (cached layer — only re-runs if package.json changes)
COPY frontend/package*.json ./
RUN npm ci

# Copy source and build
COPY frontend/ ./
# VITE_API_KEY must be known at build time so Vite can embed it in the JS bundle.
# Pass it with: docker compose build --build-arg VITE_API_KEY=<your-key>
ARG VITE_API_KEY
ENV VITE_API_KEY=$VITE_API_KEY
RUN npm run build
# Output: /app/frontend/dist/

# ── Stage 2: Python backend ───────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app/backend

# Install Python dependencies (cached layer)
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY backend/src/ ./src/

# Copy the built React app from Stage 1
# FastAPI detects this directory at startup and serves it as static files.
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist

# Create data directory for the SQLite database volume mount
RUN mkdir -p /app/data

EXPOSE 8000

# Run uvicorn from /app/backend so "from src.xxx import" works correctly
CMD ["python", "-m", "uvicorn", "src.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips=*"]
