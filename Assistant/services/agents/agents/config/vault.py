from __future__ import annotations

from pathlib import Path
import base64

from ..app_logging import get_logger

logger = get_logger("config.vault")

_VAULT_CLIENT = None


def get_vault_client(mode: str):
    """Authenticate to Vault using the SYSTEM account (WinSW service user)."""
    global _VAULT_CLIENT

    if mode != "prod":
        logger.info(f"[Vault] Development mode (MODE={mode}) - skipping Vault authentication")
        return None

    if _VAULT_CLIENT is not None:
        return _VAULT_CLIENT

    try:
        import hvac
    except ImportError as e:
        logger.info(f"[Vault] {e}, using env vars/config fallback")
        return None

    try:
        logger.info("[Vault] Production mode - authenticating to Vault with service account (SYSTEM)...")

        try:
            import win32crypt
        except ImportError:
            raise ImportError("pywin32 required for DPAPI decryption. Install with: pip install pywin32")

        cert_path = Path("C:/Vault/tls/vault-cert.pem")
        verify_setting = cert_path if cert_path.exists() else False
        if verify_setting:
            logger.info(f"[Vault] Using Vault TLS certificate for verification: {cert_path}")
        else:
            logger.warning("[Vault] Vault TLS cert not found at C:/Vault/tls/vault-cert.pem, falling back to verify=False")

        client = hvac.Client(
            url="https://localhost:8200",
            verify=verify_setting,
        )

        # Wait for Vault to be unsealed (by VaultService)
        import time
        max_wait_seconds = 120  # 2 minutes
        check_interval = 5  # Check every 5 seconds
        elapsed = 0

        logger.info("[Vault] Waiting for Vault to be unsealed...")
        while elapsed < max_wait_seconds:
            try:
                seal_status = client.sys.read_seal_status()
                is_sealed = seal_status.get('sealed', True)

                if not is_sealed:
                    logger.info(f"[Vault] Vault is unsealed (waited {elapsed}s)")
                    break

                logger.info(f"[Vault] Vault is sealed, waiting... ({elapsed}/{max_wait_seconds}s)")
                time.sleep(check_interval)
                elapsed += check_interval

            except Exception as e:
                logger.warning(f"[Vault] Error checking seal status: {e}, retrying...")
                time.sleep(check_interval)
                elapsed += check_interval

        # Final check after wait loop
        try:
            final_seal_status = client.sys.read_seal_status()
            if final_seal_status.get('sealed', True):
                raise Exception(f"Vault is still sealed after waiting {max_wait_seconds}s. VaultService may have failed to unseal.")
        except Exception as e:
            logger.error(f"[Vault] Failed to connect to unsealed Vault: {e}")
            raise

        # Authenticate with SYSTEM account
        password_file = Path("C:/Vault/Secrets/SYSTEM-password.txt")
        if not password_file.exists():
            raise FileNotFoundError(f"Password file not found: {password_file}")

        encrypted_password = password_file.read_text().strip()
        encrypted_bytes = base64.b64decode(encrypted_password)
        decrypted_bytes = win32crypt.CryptUnprotectData(
            encrypted_bytes, None, None, None, 0
        )[1]
        password = decrypted_bytes.decode("utf-8")

        client.auth.userpass.login(username="SYSTEM", password=password)
        logger.info("[Vault] ✓ Authenticated to Vault as SYSTEM")
        _VAULT_CLIENT = client
        return client
    except FileNotFoundError as e:
        logger.warning(f"[Vault] Password file not found: {e}, using env vars/config fallback")
    except ImportError as e:
        logger.info(f"[Vault] {e}, using env vars/config fallback")
    except Exception as e:
        logger.warning(f"[Vault] Failed to authenticate to Vault: {type(e).__name__}: {e}")

    return None
