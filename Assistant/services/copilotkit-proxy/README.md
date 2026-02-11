# CopilotKit Proxy Server

Standalone Node.js server that acts as a proxy between the CopilotKit frontend and the Python AG-UI backend.

## Overview

This server provides protocol translation between CopilotKit's client-side SDK and the Python backend's AG-UI protocol. It runs as an independent service, enabling the frontend to be deployed as static files while maintaining full CopilotKit functionality.

## Architecture

```
┌──────────────────┐
│  Static Frontend │
│   (Next.js SPA)  │
└────────┬─────────┘
         │ HTTP/WebSocket
         ▼
┌────────────────────────────┐
│  CopilotKit Proxy Server   │
│  (This Service - Port 8001)│
│                            │
│  • Protocol Translation    │
│  • CORS Handling           │
│  • Request Proxying        │
└────────┬───────────────────┘
         │ HTTP
         ▼
┌────────────────────────────┐
│   Python Backend           │
│   (AG-UI - Port 8000)      │
│                            │
│  • Pydantic AI Agents      │
│  • Multi-Persona System    │
│  • Database Integration    │
└────────────────────────────┘
```

## Features

- **Protocol Translation**: Converts CopilotKit protocol to AG-UI protocol
- **CORS Support**: Configurable CORS for cross-origin requests
- **Health Monitoring**: `/health` endpoint for monitoring
- **Observability Hooks**: Built-in request/response tracking and error monitoring
- **Structured Logging**: JSON-formatted logs with request correlation
- **Request Tracking**: X-Request-Id headers for distributed tracing
- **Environment-Based Configuration**: Easy deployment across environments
- **Lightweight**: Minimal dependencies, fast startup
- **Production-Ready**: Includes error handling, logging, and graceful shutdown

## Observability

The server includes built-in observability features for monitoring request flow and performance:

### Features

- **Request Hooks**: Tracks incoming requests with thread/run IDs
- **Response Hooks**: Monitors response latency and completion status
- **Error Hooks**: Captures and logs errors with full context
- **Progressive Mode**: Gradual enablement of observability features
- **Structured Logging**: JSON-formatted logs for easy parsing

### Configuration

Enable observability via environment variables:

```bash
# Enable observability (default: true in dev, false in prod)
COPILOT_OBS_ENABLED=true

# Progressive observability mode (default: true)
COPILOT_OBS_PROGRESSIVE=true

# Logging level: debug, info, warn, error (default: info)
LOG_LEVEL=info
```

### Example Log Output

```json
{
  "ts": "2025-11-18T14:32:31.123Z",
  "level": "info",
  "msg": "[HTTP] /copilotkit request",
  "requestId": "req_abc123",
  "origin": "http://localhost:3000",
  "contentType": "application/json"
}

{
  "ts": "2025-11-18T14:32:31.456Z",
  "level": "info",
  "msg": "[CopilotKit] handleResponse",
  "threadId": "thread_xyz789",
  "runId": "run_def456",
  "latency": 1234,
  "provider": "azure-openai",
  "isFinal": true
}
```

## Installation

```bash
cd copilotkit-server
pnpm install
```

## Configuration

### Environment Variables

Create a `.env` file or use `.env.development` / `.env.production`:

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `PORT` | Server port | `8001` | No |
| `PYTHON_BACKEND_URL` | Python AG-UI endpoint URL | `http://localhost:8002/api` | No |
| `CORS_ORIGIN` | Allowed CORS origin(s) | `*` (dev) | No |
| `NODE_ENV` | Environment | `development` | No |
| `COPILOT_OBS_ENABLED` | Enable observability hooks | `true` (dev), `false` (prod) | No |
| `COPILOT_OBS_PROGRESSIVE` | Progressive observability mode | `true` | No |
| `LOG_LEVEL` | Logging level: `debug`, `info`, `warn`, `error` | `info` | No |

### Example Configurations

**Development (`.env.development`)**:
```bash
PORT=8001
NODE_ENV=development
PYTHON_BACKEND_URL=http://localhost:8002/api
CORS_ORIGIN=*
COPILOT_OBS_ENABLED=true
COPILOT_OBS_PROGRESSIVE=true
LOG_LEVEL=debug
```

**Production (`.env.production`)**:
```bash
PORT=8001
NODE_ENV=production
PYTHON_BACKEND_URL=http://python-backend:8002/api
CORS_ORIGIN=https://yourapp.com
COPILOT_OBS_ENABLED=false
COPILOT_OBS_PROGRESSIVE=false
LOG_LEVEL=info
```

## Running

### Development

```bash
# Using pnpm scripts
pnpm run dev

# Or using tsx directly
pnpm exec tsx watch src/server.ts
```

The server will start on `http://localhost:8001` with hot-reload enabled.

### Production

```bash
# Build TypeScript
pnpm run build

# Start production server
pnpm start

# Or using Node.js directly
node dist/server.js
```

### Using PM2 (Recommended for Production)

```bash
# Install PM2 globally
pnpm add -g pm2

# Start with PM2
pm2 start dist/server.ts --name copilotkit-proxy

# Start with environment file
pm2 start dist/server.ts --name copilotkit-proxy --env production

# View logs
pm2 logs copilotkit-proxy

# Restart
pm2 restart copilotkit-proxy

# Stop
pm2 stop copilotkit-proxy

# Remove from PM2
pm2 delete copilotkit-proxy
```

### Using systemd

Create `/etc/systemd/system/copilotkit-proxy.service`:

```ini
[Unit]
Description=CopilotKit Proxy Server
After=network.target

[Service]
Type=simple
User=nodejs
WorkingDirectory=/opt/copilotkit-server
Environment=NODE_ENV=production
ExecStart=/usr/bin/node /opt/copilotkit-server/dist/server.js
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable copilotkit-proxy
sudo systemctl start copilotkit-proxy
sudo systemctl status copilotkit-proxy
```

## API Endpoints

### POST `/copilotkit`

Main CopilotKit endpoint. Proxies requests to Python backend.

**Request**: CopilotKit protocol (auto-handled by SDK)
**Response**: CopilotKit protocol (auto-handled by SDK)

### GET `/health`

Health check endpoint with observability status.

**Response**:
```json
{
  "status": "healthy",
  "service": "copilotkit-proxy",
  "environment": "production",
  "pythonBackend": "http://localhost:8002/api",
  "observability": {
    "enabled": false,
    "progressive": false
  },
  "timestamp": "2025-11-18T14:32:31.000Z"
}
```

### GET `/`

Service information endpoint.

**Response**:
```json
{
  "service": "Dr. Migrate Chat - CopilotKit Proxy Server",
  "version": "1.0.0",
  "endpoints": {
    "health": "/health",
    "copilotkit": "/copilotkit (POST)"
  },
  "pythonBackend": "http://localhost:8002/api",
  "observability": {
    "enabled": true,
    "progressive": true
  }
}
```

## Docker Deployment

### Dockerfile

```dockerfile
FROM node:20-alpine AS builder

WORKDIR /app

# Enable corepack for pnpm
RUN corepack enable pnpm

COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .
RUN pnpm run build

FROM node:20-alpine

WORKDIR /app

# Enable corepack for pnpm
RUN corepack enable pnpm

COPY package.json pnpm-lock.yaml ./
RUN pnpm install --prod --frozen-lockfile

COPY --from=builder /app/dist ./dist

EXPOSE 8001

ENV NODE_ENV=production

CMD ["node", "dist/server.js"]
```

### Build and Run

```bash
# Build image
docker build -t copilotkit-proxy:latest .

# Run container
docker run -d \
  --name copilotkit-proxy \
  -p 8001:8001 \
  -e PYTHON_BACKEND_URL=http://python-backend:8002/api \
  -e CORS_ORIGIN=https://yourapp.com \
  copilotkit-proxy:latest

# View logs
docker logs -f copilotkit-proxy
```

### Docker Compose

```yaml
version: '3.8'

services:
  copilotkit-proxy:
    build: .
    ports:
      - "8001:8001"
    environment:
      - NODE_ENV=production
      - PYTHON_BACKEND_URL=http://python-backend:8002/api
      - CORS_ORIGIN=https://yourapp.com
    depends_on:
      - python-backend
    restart: unless-stopped
```

## Troubleshooting

### Server won't start

1. Check port 8001 is not in use:
   ```bash
   lsof -i :8001
   # Or on Windows: netstat -ano | findstr :8001
   ```

2. Check environment variables are set correctly:
   ```bash
   cat .env.development
   ```

3. Check Python backend is running:
   ```bash
   curl http://localhost:8002/health
   ```

### CORS errors

Ensure `CORS_ORIGIN` matches your frontend URL:
```bash
# Development (allow all)
CORS_ORIGIN=*

# Production (specific origin)
CORS_ORIGIN=https://yourapp.com

# Multiple origins (comma-separated)
CORS_ORIGIN=https://yourapp.com,https://www.yourapp.com
```

### Connection refused to Python backend

1. Verify Python backend URL:
   ```bash
   curl http://localhost:8002/api
   ```

2. Check network connectivity (Docker networks, firewalls, etc.)

3. Update `PYTHON_BACKEND_URL` in environment file

### High memory usage

The server is designed to be lightweight. If experiencing high memory:
1. Check for memory leaks in error logs
2. Ensure you're running production build (`pnpm run build && pnpm start`)
3. Monitor with: `pm2 monit` or `docker stats`

## Development

### Type Checking

```bash
pnpm run type-check
```

### Building

```bash
pnpm run build
```

### Project Structure

```
copilotkit-server/
├── src/
│   └── server.ts         # Main server implementation
├── dist/                 # Compiled JavaScript (gitignored)
├── node_modules/         # Dependencies (gitignored)
├── .env.development      # Development config
├── .env.production       # Production config
├── .env.local.example    # Local override template
├── .gitignore            # Git ignore rules
├── package.json          # Dependencies and scripts
├── tsconfig.json         # TypeScript configuration
└── README.md             # This file
```

## Security Considerations

1. **CORS Configuration**: Always set `CORS_ORIGIN` to specific origins in production
2. **Environment Variables**: Never commit `.env.local` or `.env` files with secrets
3. **Network Security**: Run behind reverse proxy (nginx, IIS) in production
4. **HTTPS**: Always use HTTPS in production for encrypted communication
5. **Rate Limiting**: Consider adding rate limiting for production deployments

## License

ISC

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review logs: `pnpm run dev` (development) or `pm2 logs` (production)
3. Verify Python backend connectivity
4. Open an issue in the main repository
