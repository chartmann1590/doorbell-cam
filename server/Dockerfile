# DoorbellCam hub — multi-stage: builds the web dashboard, then runs the FastAPI app.
FROM node:22-alpine AS webui
WORKDIR /build
COPY webui/package.json webui/package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund
COPY webui/ .
RUN npm run build

FROM python:3.12-slim
WORKDIR /hub
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server/ ./server/
COPY --from=webui /build/dist ./webui/dist
ENV HUB_PORT=8765
EXPOSE 8765
# host networking (set in compose) is required for mDNS camera discovery
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8765", "--app-dir", "server"]
