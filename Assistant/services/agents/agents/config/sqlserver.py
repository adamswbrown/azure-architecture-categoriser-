from __future__ import annotations

from pathlib import Path
import tomllib
import os

import sqlalchemy as sa

from .vault import get_vault_client
from ..app_logging import get_logger

logger = get_logger("config.sqlserver")

CONFIG_PATH = (Path(".") / "config.toml").resolve()


class db:
    """Configuration for SQL Server connection with Vault-first credential loading."""

    with open(CONFIG_PATH, "rb") as f:
        config: dict[str, dict] = tomllib.load(f)

    _vault_secrets = None

    _mode = config.get("agents", {}).get("MODE", "dev")
    _vault_client = get_vault_client(_mode)
    if _vault_client:
        try:
            import hvac as _hvac

            _response = _vault_client.secrets.kv.v2.read_secret_version(
                path="credentials/assistant/database",
                mount_point="secret",
            )

            _vault_cred = _response["data"]["data"]
            if _vault_cred and _vault_cred.get("username") and _vault_cred.get("password"):
                _vault_secrets = {
                    "DB_USERNAME": _vault_cred["username"],
                    "DB_PASSWORD": _vault_cred["password"],
                }
                logger.info(f"[DB Config] ✓ Loaded database credentials from Vault: username={_vault_cred['username']}, password_len={len(_vault_cred['password'])}")

        except _hvac.exceptions.InvalidPath:
            logger.info("[DB Config] Database credential 'credentials/assistant/database' not found in Vault - using fallback")
        except Exception as e:
            logger.warning(f"[DB Config] Failed to load DB secrets from Vault: {type(e).__name__}: {e}")

    DB_HOST: str = config["db"]["DB_HOST"]
    DB_PORT: int = int(config["db"].get("DB_PORT", 1433))
    DB_NAME: str = config["db"]["DB_NAME"]
    DB_TRUST_SERVER_CERTIFICATE: bool = config["db"].get("DB_TRUST_SERVER_CERTIFICATE", True)

    DB_USER: str = (
        (_vault_secrets and _vault_secrets.get("DB_USERNAME"))
        or os.getenv("DB_USERNAME")
        or os.getenv("DB_USER")
        or config["db"].get("DB_USER", "")
    )
    DB_PASSWORD: str = (
        (_vault_secrets and _vault_secrets.get("DB_PASSWORD"))
        or os.getenv("DB_PASSWORD")
        or config["db"].get("DB_PASSWORD", "")
    )

    logger.info("[DB Config] Credential fallback chain evaluation:")
    logger.info(f"  - Vault: {bool(_vault_secrets and _vault_secrets.get('DB_USERNAME'))}")
    logger.info(f"  - Env DB_USERNAME: {bool(os.getenv('DB_USERNAME'))}")
    logger.info(f"  - Env DB_USER: {bool(os.getenv('DB_USER'))}")
    logger.info(f"  - Config DB_USER: {bool(config['db'].get('DB_USER'))}")

    if _vault_secrets and _vault_secrets.get("DB_USERNAME"):
        logger.info(f"[DB Config] ✓ Database credentials loaded from Vault (username={DB_USER})")
    elif os.getenv("DB_USERNAME") or os.getenv("DB_USER"):
        logger.info(f"[DB Config] Database credentials loaded from environment variables (username={DB_USER})")
    elif config["db"].get("DB_USER"):
        logger.info(f"[DB Config] Database credentials loaded from config.toml (username={DB_USER})")
    else:
        logger.warning("[DB Config] ⚠ No database credentials found in Vault, env vars, or config.toml!")

    logger.info(
        f"[DB Config] Final configuration: host={DB_HOST}, port={DB_PORT}, database={DB_NAME}, "
        f"user={DB_USER[:3] if DB_USER else '(empty)'}***, password={'SET' if DB_PASSWORD else 'EMPTY'} ({len(DB_PASSWORD)} chars), "
        f"trust_cert={DB_TRUST_SERVER_CERTIFICATE}"
    )

    @classmethod
    def _pick_driver(cls) -> str:
        """Prefer ODBC 18, then 17, else last installed."""
        import pyodbc

        preferred = ["ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server"]
        installed = list(pyodbc.drivers())
        for d in preferred:
            if d in installed:
                return d
        if installed:
            return installed[-1]
        raise RuntimeError(
            "No ODBC SQL Server driver found. Install 'ODBC Driver 18 for SQL Server' or '17'."
        )

    @classmethod
    def _build_server_part(cls) -> str:
        """
        Build the SERVER=... fragment:
          - If DB_HOST contains a backslash (named instance), use it verbatim (no tcp: prefix, no port).
          - Else if DB_HOST already has ',', assume host,port.
          - Else if DB_PORT is set, append ,PORT.
          - Else just host.
        """
        host = cls.DB_HOST.strip()
        if "\\" in host:
            return f"SERVER={host};"
        if "," in host:
            return f"SERVER={host};"
        if cls.DB_PORT:
            return f"SERVER={host},{cls.DB_PORT};"
        return f"SERVER={host};"

    @classmethod
    def create_connection_string(cls) -> str:
        """Create a robust pyodbc connection string that works for SQL Express or Azure SQL."""
        driver = cls._pick_driver()
        encrypt = "yes"
        trust = "yes" if cls.DB_TRUST_SERVER_CERTIFICATE else "no"

        odbc = (
            f"DRIVER={{{driver}}};"
            f"{cls._build_server_part()}"
            f"DATABASE={cls.DB_NAME};"
            f"UID={cls.DB_USER};"
            f"PWD={cls.DB_PASSWORD};"
            f"Encrypt={encrypt};"
            f"TrustServerCertificate={trust};"
            "MARS_Connection=yes;"
            "Connection Timeout=30;"
        )
        return odbc

    @classmethod
    def create_sqlalchemy_engine(cls):
        """
        Create a SQLAlchemy engine using a custom creator (pyodbc.connect),
        so we don't fight URL-encoding of special characters.
        """
        import pyodbc

        def creator():
            return pyodbc.connect(cls.create_connection_string(), timeout=15)

        return sa.create_engine(
            "mssql+pyodbc://",
            creator=creator,
            pool_pre_ping=True,
        )

    @classmethod
    def verify_connection(cls, startup: bool = False):
        """
        Perform a lightweight connectivity check (SELECT 1).
        Logs warning on failure but does not raise to avoid crashing startup.
        """
        try:
            import pyodbc

            with pyodbc.connect(cls.create_connection_string(), timeout=5) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
                    cur.fetchone()
            logger.info(f"[DB Config] ✓ Connection test succeeded{' at startup' if startup else ''}")
        except Exception as e:
            logger.warning(f"[DB Config] ⚠ Connection test failed{' at startup' if startup else ''}: {type(e).__name__}: {e}")


# Run a startup connectivity check in production mode (best-effort)
if db._mode == "prod":
    db.verify_connection(startup=True)
