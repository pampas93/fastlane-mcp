"""Subprocess helpers for fastlane and Gradle commands."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from .exceptions import ExecutionError
from .models import CommandResult
from .validators import redact_command, safe_excerpt

logger = logging.getLogger(__name__)


def which(command: str) -> str | None:
    """Return an executable path if available on PATH."""
    return shutil.which(command)


def detect_version(command: list[str], timeout: int = 15) -> tuple[bool, str | None, str | None]:
    """Run a lightweight version command."""
    executable = which(command[0])
    if not executable:
        return False, None, f"{command[0]} not found on PATH"
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, None, str(exc)
    output = completed.stdout.strip() or completed.stderr.strip()
    return completed.returncode == 0, output or None, None if completed.returncode == 0 else output


def find_bundle_context(project_root: str, platform_dir: str) -> tuple[list[str], Path]:
    """Prefer bundle exec fastlane when a Gemfile exists."""
    candidates = [
        Path(project_root).resolve(),
        Path(project_root, platform_dir).resolve(),
    ]
    if which("bundle"):
        for candidate in candidates:
            if (candidate / "Gemfile").is_file():
                return ["bundle", "exec", "fastlane"], candidate
    return ["fastlane"], Path(project_root).resolve()


def command_display(command: list[str], sensitive_values: list[str | None] | None = None) -> str:
    """Render a safe, readable command string."""
    pieces = redact_command(command, sensitive_values or [])
    return subprocess.list2cmdline(pieces)


def run_command(
    *,
    tool_name: str,
    command: list[str],
    cwd: str | Path,
    timeout: int,
    sensitive_values: list[str | None] | None = None,
) -> CommandResult:
    """Execute a subprocess and normalize the response."""
    logger.info("Running command for %s: %s", tool_name, command_display(command, sensitive_values))
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise ExecutionError(
            f"Command timed out after {timeout} seconds for {tool_name}: {command[0]}"
        ) from exc
    except OSError as exc:
        raise ExecutionError(f"Failed to start command for {tool_name}: {exc}") from exc

    result = CommandResult(
        success=completed.returncode == 0,
        tool=tool_name,
        message="Command completed successfully." if completed.returncode == 0 else "Command failed.",
        command=command,
        command_display=command_display(command, sensitive_values),
        cwd=str(Path(cwd).resolve()),
        return_code=completed.returncode,
        stdout_excerpt=safe_excerpt(completed.stdout),
        stderr_excerpt=safe_excerpt(completed.stderr),
    )
    if completed.returncode != 0:
        raise ExecutionError(
            f"{tool_name} failed with exit code {completed.returncode}. "
            f"stderr: {result.stderr_excerpt or '[no stderr]'}"
        )
    return result
