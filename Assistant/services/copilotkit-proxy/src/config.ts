/**
 * CopilotKit Proxy Server Configuration
 *
 * Centralized, type-safe configuration management.
 *
 * Configuration Sources (in order of precedence):
 * 1. Environment variables (set by WinSW XML in production)
 * 2. .env files (development only)
 * 3. Default values (fallback)
 *
 * Security Note:
 * - NO SECRETS in this file
 * - Secrets (DB credentials) loaded from Vault → Machine environment
 * - Configuration (ports, URLs, etc.) set via environment/XML
 */

import { config as dotenvConfig } from 'dotenv';

/**
 * Configuration interface
 */
export interface Config {
  /** Node environment */
  nodeEnv: 'development' | 'production' | 'test';

  /** Server port */
  port: number;

  /** Python backend API URL */
  pythonBackendUrl: string;

  /** CORS allowed origin(s) */
  corsOrigin: string;

  /** Logging level */
  logLevel: 'debug' | 'info' | 'warn' | 'error';

  /** Enable CopilotKit observability hooks */
  copilotObsEnabled: boolean;

  /** Progressive observability mode */
  copilotObsProgressive: boolean;
}

/**
 * Load environment variables from .env files (development only)
 */
function loadEnvFiles(): void {
  const nodeEnv = process.env.NODE_ENV || 'development';

  // Only load .env files in development
  // Production uses WinSW XML environment variables
  if (nodeEnv !== 'production') {
    dotenvConfig();
  }
}

/**
 * Parse boolean from string environment variable
 */
function parseBoolean(value: string | undefined, defaultValue: boolean): boolean {
  if (!value) return defaultValue;
  return value.toLowerCase() === 'true';
}

/**
 * Parse log level from environment variable
 */
function parseLogLevel(value: string | undefined): 'debug' | 'info' | 'warn' | 'error' {
  const level = (value || 'info').toLowerCase();
  if (['debug', 'info', 'warn', 'error'].includes(level)) {
    return level as 'debug' | 'info' | 'warn' | 'error';
  }
  return 'info';
}

/**
 * Parse node environment
 */
function parseNodeEnv(value: string | undefined): 'development' | 'production' | 'test' {
  const env = (value || 'development').toLowerCase();
  if (['development', 'production', 'test'].includes(env)) {
    return env as 'development' | 'production' | 'test';
  }
  return 'development';
}

/**
 * Validate configuration
 */
function validateConfig(config: Config): void {
  const errors: string[] = [];

  if (!config.port || config.port < 1 || config.port > 65535) {
    errors.push(`Invalid port: ${config.port}. Must be between 1 and 65535.`);
  }

  if (!config.pythonBackendUrl) {
    errors.push('PYTHON_BACKEND_URL is required');
  }

  try {
    new URL(config.pythonBackendUrl);
  } catch {
    errors.push(`Invalid PYTHON_BACKEND_URL: ${config.pythonBackendUrl}`);
  }

  if (errors.length > 0) {
    throw new Error(`Configuration validation failed:\n${errors.join('\n')}`);
  }
}

/**
 * Load and validate configuration
 */
function loadConfig(): Config {
  // Load .env files (development only)
  loadEnvFiles();

  const nodeEnv = parseNodeEnv(process.env.NODE_ENV);

  // Build configuration
  const config: Config = {
    nodeEnv,
    port: parseInt(process.env.PORT || '8001', 10),
    pythonBackendUrl: process.env.PYTHON_BACKEND_URL || 'http://localhost:8002/api',
    corsOrigin: process.env.CORS_ORIGIN || (nodeEnv === 'development' ? '*' : '*.drmigrate.com'),
    logLevel: parseLogLevel(process.env.LOG_LEVEL),
    copilotObsEnabled: parseBoolean(
      process.env.COPILOT_OBS_ENABLED,
      nodeEnv === 'development' // default: true in dev, false in prod
    ),
    copilotObsProgressive: parseBoolean(process.env.COPILOT_OBS_PROGRESSIVE, true),
  };

  // Validate configuration
  validateConfig(config);

  return config;
}

/**
 * Singleton configuration instance
 */
export const config = loadConfig();

/**
 * Export individual config values for convenience
 */
export const {
  nodeEnv,
  port,
  pythonBackendUrl,
  corsOrigin,
  logLevel,
  copilotObsEnabled,
  copilotObsProgressive,
} = config;
