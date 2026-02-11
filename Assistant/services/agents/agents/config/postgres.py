from __future__ import annotations

from pathlib import Path
import tomllib
import os

import sqlalchemy as sa

from .vault import get_vault_client
from ..app_logging import get_logger

logger = get_logger("config.postgres")

CONFIG_PATH = (Path(".") / "config.toml").resolve()


class postgres:
    """Configuration for Postgres connection with Vault-first credential loading."""

    with open(CONFIG_PATH, "rb") as f:
        config: dict[str, dict] = tomllib.load(f)

    _mode = config.get("agents", {}).get("MODE", "dev")
    _vault_client = get_vault_client(_mode)
    _vault_secrets = {}
    if _vault_client:
        from hvac.exceptions import InvalidPath
        try:
            _response = _vault_client.secrets.kv.v2.read_secret_version(
                path="credentials/assistant/postgresql",
                mount_point="secret",
            )
            _vault_cred = _response["data"]["data"]
            if _vault_cred and _vault_cred.get("username") and _vault_cred.get("password"):
                _vault_secrets = {
                    "PG_USER": _vault_cred["username"],
                    "PG_PASSWORD": _vault_cred["password"],
                }
                logger.info(f"[Postgres Config] ✓ Loaded database credentials from Vault: username={_vault_cred['username']}, password_len={len(_vault_cred['password'])}")
        except InvalidPath:
            logger.info("[Postgres Config] Secret 'credentials/postgres' not found in Vault - using fallback")
        except Exception as e:
            logger.warning(f"[Postgres Config] Failed to load Postgres secrets from Vault: {type(e).__name__}: {e}")

    PG_HOST: str = config["postgres"]["PG_HOST"]
    PG_PORT: int = int(config["postgres"].get("PG_PORT", 5432))
    PG_DATABASE: str = config["postgres"]["PG_DATABASE"]
    PG_SSL_MODE: str = config["postgres"].get("PG_SSL_MODE", "prefer")

    PG_USER: str = (
        (_vault_secrets.get("PG_USER") if _vault_secrets else None)
        or os.getenv("PGUSER")
        or os.getenv("POSTGRES_USER")
        or config["postgres"].get("PG_USER", "")
    )
    PG_PASSWORD: str = (
        (_vault_secrets.get("PG_PASSWORD") if _vault_secrets else None)
        or os.getenv("PGPASSWORD")
        or os.getenv("POSTGRES_PASSWORD")
        or config["postgres"].get("PG_PASSWORD", "")
    )

    logger.info("[Postgres Config] Credential fallback chain evaluation:")
    logger.info(f"  - Vault: {bool(_vault_secrets and _vault_secrets.get('PG_USER'))}")
    logger.info(f"  - Env PGUSER/POSTGRES_USER: {bool(os.getenv('PGUSER') or os.getenv('POSTGRES_USER'))}")
    logger.info(f"  - Config PG_USER: {bool(config['postgres'].get('PG_USER'))}")

    if _vault_secrets and _vault_secrets.get("PG_USER"):
        logger.info(f"[Postgres Config] ✓ Database credentials loaded from Vault (username={PG_USER})")
    elif os.getenv("PGUSER") or os.getenv("POSTGRES_USER"):
        logger.info(f"[Postgres Config] Database credentials loaded from environment variables (username={PG_USER})")
    elif config["postgres"].get("PG_USER"):
        logger.info(f"[Postgres Config] Database credentials loaded from config.toml (username={PG_USER})")
    else:
        logger.warning("[Postgres Config] ⚠ No database credentials found in Vault, env vars, or config.toml!")

    logger.info(
        f"[Postgres Config] Final configuration: host={PG_HOST}, port={PG_PORT}, database={PG_DATABASE}, "
        f"user={PG_USER[:3] if PG_USER else '(empty)'}***, password={'SET' if PG_PASSWORD else 'EMPTY'} ({len(PG_PASSWORD)} chars), "
        f"sslmode={PG_SSL_MODE}"
    )

    @classmethod
    def create_conninfo(cls) -> str:
        """psycopg conninfo string for direct connections."""
        return (
            f"host={cls.PG_HOST} "
            f"port={cls.PG_PORT} "
            f"dbname={cls.PG_DATABASE} "
            f"user={cls.PG_USER} "
            f"password={cls.PG_PASSWORD} "
            f"sslmode={cls.PG_SSL_MODE}"
        )

    @classmethod
    def create_client(cls):
        """Create a psycopg connection for use in agents/LLM tooling."""
        import psycopg

        return psycopg.connect(cls.create_conninfo())

    @classmethod
    def create_sqlalchemy_engine(cls):
        """Create a SQLAlchemy engine backed by psycopg."""
        from sqlalchemy.engine import URL

        url = URL.create(
            "postgresql+psycopg",
            username=cls.PG_USER,
            password=cls.PG_PASSWORD,
            host=cls.PG_HOST,
            port=cls.PG_PORT,
            database=cls.PG_DATABASE,
        )

        return sa.create_engine(
            url,
            connect_args={"sslmode": cls.PG_SSL_MODE},
            pool_pre_ping=True,
        )

    @classmethod
    def verify_connection(cls, startup: bool = False):
        """
        Perform a lightweight connectivity check (SELECT 1).
        Logs warning on failure but does not raise to avoid crashing startup.
        """
        try:
            with cls.create_client() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
                    cur.fetchone()
            logger.info(f"[Postgres Config] ✓ Connection test succeeded{' at startup' if startup else ''}")
        except Exception as e:
            logger.warning(f"[Postgres Config] ⚠ Connection test failed{' at startup' if startup else ''}: {type(e).__name__}: {e}")


# Run a startup connectivity check in production mode (best-effort)
if postgres._mode == "prod":
    postgres.verify_connection(startup=True)
