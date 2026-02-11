"""
Custom exceptions for the application.
"""
class BaseDrMException(Exception):
    """Base exception for DrM application."""
    pass

class DatabaseConnectionError(BaseDrMException):
    """Exception raised for errors in the database connection."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)
