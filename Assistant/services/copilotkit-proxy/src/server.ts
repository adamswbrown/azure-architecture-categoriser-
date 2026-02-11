import express, { Request, Response } from 'express';
import cors from 'cors';
import {
  CopilotRuntime,
  ExperimentalEmptyAdapter,
  copilotRuntimeNodeHttpEndpoint,
} from '@copilotkit/runtime';
import { HttpAgent } from '@ag-ui/client';
import {
  config,
  port as PORT,
  pythonBackendUrl as PYTHON_BACKEND_URL,
  corsOrigin as CORS_ORIGIN,
  nodeEnv as NODE_ENV,
  logLevel as LOG_LEVEL,
  copilotObsEnabled as COPILOT_OBS_ENABLED,
  copilotObsProgressive as COPILOT_OBS_PROGRESSIVE,
} from './config';

// Minimal logger with levels
type Level = 'debug' | 'info' | 'warn' | 'error';
const levelOrder: Record<Level, number> = { debug: 10, info: 20, warn: 30, error: 40 };
const currentLevel = levelOrder[LOG_LEVEL];

function log(level: Level, msg: string, extra?: Record<string, unknown>) {
  if (levelOrder[level] < currentLevel) return;
  const line = {
    ts: new Date().toISOString(),
    level,
    msg,
    ...extra,
  };
  // eslint-disable-next-line no-console
  console[level === 'warn' ? 'warn' : level === 'error' ? 'error' : 'log'](JSON.stringify(line));
}

function safeJson(data: unknown) {
  try {
    return JSON.stringify(data);
  } catch {
    return '[unserializable]';
  }
}

function newRequestId() {
  try {
    const { randomUUID } = require('crypto');
    return randomUUID();
  } catch {
    return 'req_' + Math.random().toString(36).slice(2, 10);
  }
}

// Initialize Express app
const app = express();

// CORS configuration
const corsOptions = {
  origin: (origin: string | undefined, callback: (err: Error | null, allow?: boolean) => void) => {
    if (!origin) return callback(null, true);
    if (CORS_ORIGIN === '*') return callback(null, true);

    if (CORS_ORIGIN.startsWith('*.')) {
      const domain = CORS_ORIGIN.slice(2);
      const originUrl = new URL(origin);
      if (originUrl.hostname.endsWith(domain) || originUrl.hostname === domain) {
        return callback(null, true);
      }
    }

    if (
      origin === CORS_ORIGIN ||
      origin === `https://${CORS_ORIGIN}` ||
      origin === `http://${CORS_ORIGIN}`
    ) {
      return callback(null, true);
    }

    callback(new Error('Not allowed by CORS'));
  },
  methods: ['GET', 'POST', 'OPTIONS', 'PUT', 'PATCH', 'DELETE'],
  allowedHeaders: '*',
  exposedHeaders: '*',
  credentials: false,
  preflightContinue: false,
  optionsSuccessStatus: 204,
};

app.use(cors(corsOptions));
app.use(express.json());

// Initialize CopilotKit Runtime
const serviceAdapter = new ExperimentalEmptyAdapter();

const runtime = new CopilotRuntime({
  agents: {
    dr_migrate_agent: new HttpAgent({ url: PYTHON_BACKEND_URL }),
  },

  // ✅ correct field is observability_c
  observability_c: {
    enabled: COPILOT_OBS_ENABLED,
    progressive: COPILOT_OBS_PROGRESSIVE,
    hooks: {
      handleRequest: async (data: any) => {
        log('debug', '[CopilotKit] handleRequest', {
          threadId: data?.threadId,
          runId: data?.runId,
          model: data?.model,
          provider: data?.provider,
        });
      },
      handleResponse: async (data: any) => {
        log('info', '[CopilotKit] handleResponse', {
          threadId: data?.threadId,
          runId: data?.runId,
          latency: data?.latency,
          provider: data?.provider,
          isFinal: data?.isFinalResponse,
        });
      },
      handleError: async (data: any) => {
        log('error', '[CopilotKit] handleError', {
          threadId: data?.threadId,
          runId: data?.runId,
          provider: data?.provider,
          error:
            data?.error instanceof Error
              ? data.error.message
              : typeof data?.error === 'string'
              ? data.error
              : safeJson(data?.error),
        });
      },
    },
  },
});

// CopilotKit endpoint
const copilotKitEndpoint = copilotRuntimeNodeHttpEndpoint({
  runtime,
  serviceAdapter,
  endpoint: '/copilotkit',
});

// Health check endpoint
app.get('/health', (req: Request, res: Response) => {
  res.json({
    status: 'healthy',
    service: 'copilotkit-proxy',
    environment: NODE_ENV,
    pythonBackend: PYTHON_BACKEND_URL,
    observability: {
      enabled: COPILOT_OBS_ENABLED,
      progressive: COPILOT_OBS_PROGRESSIVE,
    },
    timestamp: new Date().toISOString(),
  });
});

function getAllowedOrigin(requestOrigin: string | undefined): string {
  if (!requestOrigin) return '*';
  if (CORS_ORIGIN === '*') return '*';

  if (CORS_ORIGIN.startsWith('*.')) {
    const domain = CORS_ORIGIN.slice(2);
    try {
      const originUrl = new URL(requestOrigin);
      if (originUrl.hostname.endsWith(domain) || originUrl.hostname === domain) {
        return requestOrigin;
      }
    } catch {
      return '*';
    }
  }

  if (
    requestOrigin === CORS_ORIGIN ||
    requestOrigin === `https://${CORS_ORIGIN}` ||
    requestOrigin === `http://${CORS_ORIGIN}`
  ) {
    return requestOrigin;
  }

  return '*';
}

// CopilotKit proxy endpoint with request logging
app.post('/copilotkit', async (req: Request, res: Response) => {
  const reqId = req.headers['x-request-id']?.toString() || newRequestId();
  const start = Date.now();

  try {
    const allowedOrigin = getAllowedOrigin(req.headers.origin);
    res.header('Access-Control-Allow-Origin', allowedOrigin);
    res.header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, PUT, PATCH, DELETE');
    res.header('Access-Control-Allow-Headers', '*');
    res.header('Access-Control-Expose-Headers', '*');
    res.header('X-Request-Id', reqId);

    log('info', '[HTTP] /copilotkit request', {
      requestId: reqId,
      origin: req.headers.origin,
      contentType: req.headers['content-type'],
      contentLength: req.headers['content-length'],
    });

    await copilotKitEndpoint(req, res);

    const ms = Date.now() - start;
    log('info', '[HTTP] /copilotkit response', { requestId: reqId, durationMs: ms });
  } catch (error) {
    const ms = Date.now() - start;
    log('error', '[CopilotKit] Error handling request', {
      requestId: reqId,
      durationMs: ms,
      error: error instanceof Error ? error.message : 'Unknown error',
    });
    res.status(500).json({
      error: 'Internal server error',
      message: error instanceof Error ? error.message : 'Unknown error',
      requestId: reqId,
    });
  }
});

// OPTIONS for preflight
app.options('/copilotkit', (req: Request, res: Response) => {
  const allowedOrigin = getAllowedOrigin(req.headers.origin);
  res.header('Access-Control-Allow-Origin', allowedOrigin);
  res.header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, PUT, PATCH, DELETE');
  res.header('Access-Control-Allow-Headers', '*');
  res.header('Access-Control-Expose-Headers', '*');
  res.header('Access-Control-Max-Age', '86400');
  res.status(204).end();
});

// Root endpoint
app.get('/', (req: Request, res: Response) => {
  res.json({
    service: 'Dr. Migrate Chat - CopilotKit Proxy Server',
    version: '1.0.0',
    endpoints: { health: '/health', copilotkit: '/copilotkit (POST)' },
    pythonBackend: PYTHON_BACKEND_URL,
    observability: {
      enabled: COPILOT_OBS_ENABLED,
      progressive: COPILOT_OBS_PROGRESSIVE,
    },
  });
});

// Error handling
app.use((err: Error, req: Request, res: Response, next: express.NextFunction) => {
  log('error', '[Server] Unhandled error', { error: err.message });
  res.status(500).json({
    error: 'Internal server error',
    message: NODE_ENV === 'development' ? err.message : 'An error occurred',
  });
});

// Start server
app.listen(PORT, () => {
  console.log('');
  console.log('═════════════════════════════════════════════════════════════');
  console.log('  Dr. Migrate Chat - CopilotKit Proxy Server');
  console.log('═════════════════════════════════════════════════════════════');
  console.log(`  Environment: ${NODE_ENV}`);
  console.log(`  Server URL:  http://localhost:${PORT}`);
  console.log(`  Endpoint:    http://localhost:${PORT}/copilotkit`);
  console.log(`  Health:      http://localhost:${PORT}/health`);
  console.log(`  Backend:     ${PYTHON_BACKEND_URL}`);
  console.log(`  CORS Origin: ${CORS_ORIGIN}`);
  console.log(`  Obs Enabled: ${COPILOT_OBS_ENABLED} | Progressive: ${COPILOT_OBS_PROGRESSIVE}`);
  console.log(`  Log Level:   ${LOG_LEVEL}`);
  console.log('═════════════════════════════════════════════════════════════');
  console.log('');
});

// Graceful shutdown
process.on('SIGTERM', () => {
  log('warn', 'SIGTERM signal received: closing HTTP server');
  process.exit(0);
});

process.on('SIGINT', () => {
  log('warn', 'SIGINT signal received: closing HTTP server');
  process.exit(0);
});

