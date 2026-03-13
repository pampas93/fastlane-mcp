"""Custom exceptions for fastlane-mcp."""


class FastlaneMCPError(Exception):
    """Base exception for all fastlane-mcp failures."""


class ConfigError(FastlaneMCPError):
    """Raised when configuration cannot be loaded or is incomplete."""


class ValidationError(FastlaneMCPError):
    """Raised when tool input or derived values are invalid."""


class ExecutionError(FastlaneMCPError):
    """Raised when an external command fails."""
