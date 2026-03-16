"""Validation and normalization helpers."""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from typing import Iterable

from .exceptions import ValidationError

TRACK_RE = re.compile(r"^[A-Za-z0-9._-]+$")
PLAY_RELEASE_STATUS_MAP = {
    "completed": "completed",
    "draft": "draft",
    "halted": "halted",
    "inprogress": "inProgress",
    "in_progress": "inProgress",
}


def bool_from_env(value: str | None, default: bool) -> bool:
    """Parse a boolean-like environment value."""
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValidationError(f"Invalid boolean value: {value!r}")


def normalize_path(path_value: str, base_dir: str | Path | None = None) -> Path:
    """Expand environment variables and resolve a path."""
    expanded = Path(os.path.expandvars(path_value)).expanduser()
    if expanded.is_absolute():
        return expanded.resolve()
    if base_dir is None:
        return expanded.resolve()
    return Path(base_dir, expanded).resolve()


def require_directory(path_value: str | Path, label: str) -> Path:
    """Validate that a directory exists."""
    path = Path(path_value)
    if not path.is_dir():
        raise ValidationError(f"{label} does not exist: {path}")
    return path


def require_file(path_value: str | Path, label: str) -> Path:
    """Validate that a file exists."""
    path = Path(path_value)
    if not path.is_file():
        raise ValidationError(f"{label} does not exist: {path}")
    return path


def validate_track_name(track: str) -> str:
    """Validate a Google Play track name."""
    normalized = track.strip()
    if not normalized:
        raise ValidationError("Track name must not be empty.")
    if not TRACK_RE.match(normalized):
        raise ValidationError(
            "Track names may only contain letters, numbers, dots, underscores, and hyphens."
        )
    return normalized


def validate_rollout(rollout: float | None) -> float | None:
    """Validate a rollout fraction."""
    if rollout is None:
        return None
    if rollout <= 0 or rollout > 1:
        raise ValidationError("rollout must be greater than 0 and less than or equal to 1.")
    return rollout


def validate_play_release_status(release_status: str | None) -> str | None:
    """Validate and normalize a Google Play release status."""
    if release_status is None:
        return None
    normalized = release_status.strip()
    if not normalized:
        raise ValidationError("release_status must not be empty.")
    canonical = PLAY_RELEASE_STATUS_MAP.get(normalized.lower(), PLAY_RELEASE_STATUS_MAP.get(normalized))
    if canonical is None:
        raise ValidationError("release_status must be one of: completed, draft, halted, inProgress.")
    return canonical


def build_gradle_task(kind: str, flavor: str | None, build_type: str | None) -> str | None:
    """Compute a Gradle task when the user overrides flavor/build type."""
    if not flavor and not build_type:
        return None

    def title_case(value: str | None) -> str:
        if not value:
            return ""
        parts = re.split(r"[-_ ]+", value)
        return "".join(part[:1].upper() + part[1:] for part in parts if part)

    prefix = "bundle" if kind == "aab" else "assemble"
    return f"{prefix}{title_case(flavor)}{title_case(build_type or 'release')}"


def find_latest_match(base_dir: str | Path, pattern: str) -> Path | None:
    """Return the newest file matching a glob pattern."""
    base = Path(base_dir)
    matches = [path for path in base.glob(pattern) if path.is_file()]
    if not matches:
        return None
    return max(matches, key=lambda item: item.stat().st_mtime)


def redact_value(value: str | None) -> str | None:
    """Redact potentially sensitive values for logs and tool output."""
    if value is None:
        return None
    path = Path(value)
    if path.suffix == ".json":
        return "[REDACTED_JSON_KEY_PATH]"
    return "[REDACTED]"


def redact_command(command: Iterable[str], sensitive_values: Iterable[str | None]) -> list[str]:
    """Redact sensitive values from a command list."""
    redacted = list(command)
    replacements = {value: redact_value(value) for value in sensitive_values if value}
    for index, item in enumerate(redacted):
        for raw, mask in replacements.items():
            if raw and raw in item:
                redacted[index] = item.replace(raw, mask or "[REDACTED]")
    return redacted


def safe_excerpt(text: str | None, limit: int = 1200) -> str | None:
    """Collapse and trim command output for concise tool responses."""
    if not text:
        return None
    cleaned = text.strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit].rstrip() + "\n...[truncated]..."


def parse_bracketed_list(output: str) -> list[int] | list[str] | None:
    """Best-effort parser for fastlane array output."""
    candidates = re.findall(r"\[[^\]]*\]", output, flags=re.MULTILINE)
    for candidate in reversed(candidates):
        try:
            parsed = ast.literal_eval(candidate)
        except (SyntaxError, ValueError):
            continue
        if isinstance(parsed, list):
            return parsed
    return None
