"""
ASGI Server for DrMChat

This module provides the main entry point for running the DrMChat backend server.
It configures and launches a Starlette/Uvicorn server with:
- DrMChatApp for AG-UI endpoints
- CORS middleware for frontend communication
- Static file serving for built frontend (if available)
- Health check endpoint
- Structured logging configuration

Usage:
    uv run agents                           # Start with default settings
    uv run agents --port 8080               # Custom port
    uv run agents --persona "core"          # Force specific persona

CLI Options:
    --port: Server port (default: from config.toml)
    --persona: Force a specific persona, bypassing auto-delegation
"""
from pathlib import Path

import click
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles
import uvicorn

from . import config
from .ag_ui import DrMChatApp
from .telemetry import get_logfire
from .personas import Persona

logger = config.get_logger('server')

# Uvicorn logging configuration to match our structured logging format
UVICORN_LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "access": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
        "access": {
            "formatter": "access",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "uvicorn": {"handlers": ["default"], "level": "INFO"},
        "uvicorn.error": {"level": "INFO"},
        "uvicorn.access": {"handlers": ["access"], "level": "INFO", "propagate": False},
    },
}

async def frontend_not_built(_: Request) -> JSONResponse:
    return JSONResponse(
        {
            "detail": "Frontend build not found. Run `pnpm run build:static` inside the frontend directory.",
        },
        status_code=404,
    )


async def options_ok(_: Request) -> JSONResponse:
    return JSONResponse({})


async def health_check(_: Request) -> JSONResponse:
    logger.debug("Health check requested")
    return JSONResponse({"status": "ok"})


frontend_build_dir = Path(__file__).parent / 'frontend' / 'out'

# Simple click server
@click.group(invoke_without_command=True)
@click.version_option(prog_name="agents x starlette ASGI server")
@click.option('--port', default=config.server.PORT, help="Port to run the server on.")
@click.option('--persona', default=None, help=f"Only use the specified persona agent {tuple([p.value for p in Persona])}.")
@click.option('--no-templates', is_flag=True, default=False, help="Disable template agent for response formatting.")
@click.option('--turbo', is_flag=True, default=False, help="Enable turbo mode for faster processing.")
def main(port: int, persona: str | None, no_templates: bool, turbo: bool):
    """
    Run the DrMChat ASGI server.

    This function:
    1. Initializes DrMChatApp with optional forced persona
    2. Adds CORS middleware for frontend communication
    3. Mounts static frontend if built, otherwise shows "not built" message
    4. Configures Logfire instrumentation
    5. Starts Uvicorn server with structured logging

    Args:
        port: Port to run the server on
        persona: Optional persona to force (bypasses delegation if set)

    Note:
        If port differs from config.toml, a warning is logged as this may
        cause frontend connection issues.
    """
    logger.info(f"Starting server on port {port}")

    app = DrMChatApp(
        force_persona=Persona(persona) if persona else None,
        apply_templates=not no_templates,
        turbo=turbo,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True, 
    )

    # Add some extra server related endpoints
    ## Health check
    app.add_route('/health', health_check, methods=['GET'])

    if frontend_build_dir.exists():
        app.mount('/', StaticFiles(directory=frontend_build_dir, html=True), name='frontend')
    else:
        app.add_route('/', frontend_not_built, methods=['GET'])

    # Instrument logfire with Starlette
    get_logfire().instrument_starlette(app)

    if port != config.server.PORT:
        logger.warning(f"Warning: Overriding configured port {config.server.PORT} with command line port {port} may cause issues connecting to the frontend. Set the port in config.toml to avoid this warning.")

    # Clear any existing uvicorn logger handlers to prevent duplicates
    import logging
    for logger_name in ['uvicorn', 'uvicorn.error', 'uvicorn.access']:
        uvicorn_logger = logging.getLogger(logger_name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = False

    uvicorn.run(app, host='0.0.0.0', port=port, log_config=UVICORN_LOG_CONFIG)

if __name__ == '__main__':
    main()
