"""
Base authenticator interface for cloud providers.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseAuthenticator(ABC):
    """Abstract base class for cloud authenticators."""

    @abstractmethod
    def authenticate(self) -> Dict[str, Any]:
        """
        Perform authentication and return credentials.

        Returns:
            Dictionary containing authentication credentials/configuration
        """
        pass

    @abstractmethod
    def get_token(self) -> str:
        """
        Get or refresh access token.

        Returns:
            Access token string
        """
        pass
