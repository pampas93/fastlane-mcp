"""Configuration loading for fastlane-mcp."""

from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from .exceptions import ConfigError
from .models import AppConfig
from .validators import bool_from_env, normalize_path

DEFAULT_CONFIG_FILES = (
    "fastlane-mcp.yaml",
    "fastlane-mcp.yml",
    ".fastlane-mcp/app.yaml",
    ".fastlane-mcp/app.yml",
)


def discover_app_config(project_root: str | None) -> Path | None:
    """Find a default app config file inside a project root."""
    if not project_root:
        return None
    root = Path(project_root).resolve()
    for candidate in DEFAULT_CONFIG_FILES:
        path = root / candidate
        if path.is_file():
            return path
    return None


def _load_yaml_config(path: Path) -> dict[str, Any]:
    """Load YAML config and expand env vars in string values."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Failed to parse YAML config {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"Config file must contain a top-level mapping: {path}")
    return _expand_env_vars(raw)


def _expand_env_vars(value: Any) -> Any:
    """Recursively expand environment variables in a config structure."""
    if isinstance(value, str):
        return os.path.expandvars(value)
    if isinstance(value, list):
        return [_expand_env_vars(item) for item in value]
    if isinstance(value, dict):
        return {key: _expand_env_vars(item) for key, item in value.items()}
    return value


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge dictionaries without mutating the inputs."""
    result = deepcopy(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _strip_none_values(value: Any) -> Any:
    """Remove empty values so defaults can still apply."""
    if isinstance(value, dict):
        return {
            key: cleaned
            for key, item in value.items()
            if (cleaned := _strip_none_values(item)) is not None
        }
    return value


def env_config() -> dict[str, Any]:
    """Build config overrides from environment variables."""
    env = os.environ
    play_json_key_file = env.get("FASTLANE_MCP_PLAY_JSON_KEY_FILE") or env.get(
        "GOOGLE_PLAY_JSON_KEY_FILE"
    )
    play_json_key_content = env.get("FASTLANE_MCP_PLAY_JSON_KEY_CONTENT") or env.get(
        "GOOGLE_PLAY_JSON_KEY_CONTENT"
    )
    return {
        "app_name": env.get("FASTLANE_MCP_APP_NAME"),
        "platform": env.get("FASTLANE_MCP_PLATFORM"),
        "project_root": env.get("FASTLANE_MCP_PROJECT_ROOT"),
        "android_dir": env.get("FASTLANE_MCP_ANDROID_DIR"),
        "ios_dir": env.get("FASTLANE_MCP_IOS_DIR"),
        "package_name": env.get("FASTLANE_MCP_PACKAGE_NAME"),
        "bundle_identifier": env.get("FASTLANE_MCP_BUNDLE_IDENTIFIER"),
        "default_track": env.get("FASTLANE_MCP_DEFAULT_TRACK"),
        "artifacts": {
            "aab_glob": env.get("FASTLANE_MCP_AAB_GLOB"),
            "apk_glob": env.get("FASTLANE_MCP_APK_GLOB"),
            "ipa_glob": env.get("FASTLANE_MCP_IPA_GLOB"),
        },
        "play": {
            "json_key_file": play_json_key_file,
            "json_key_content": play_json_key_content,
            "metadata_dir": env.get("FASTLANE_MCP_PLAY_METADATA_DIR"),
            "images_dir": env.get("FASTLANE_MCP_PLAY_IMAGES_DIR"),
            "changelogs_dir": env.get("FASTLANE_MCP_PLAY_CHANGELOGS_DIR"),
            "default_language": env.get("FASTLANE_MCP_PLAY_DEFAULT_LANGUAGE"),
        },
        "apple": {
            "api_key_path": env.get("FASTLANE_MCP_APPLE_API_KEY_PATH"),
            "api_key_content": env.get("FASTLANE_MCP_APPLE_API_KEY_CONTENT"),
            "username": env.get("FASTLANE_MCP_APPLE_USERNAME"),
            "metadata_dir": env.get("FASTLANE_MCP_APPLE_METADATA_DIR"),
            "screenshots_dir": env.get("FASTLANE_MCP_APPLE_SCREENSHOTS_DIR"),
            "privacy_details_path": env.get("FASTLANE_MCP_APPLE_PRIVACY_DETAILS_PATH"),
            "age_rating_config_path": env.get("FASTLANE_MCP_APPLE_AGE_RATING_CONFIG_PATH"),
            "team_id": env.get("FASTLANE_MCP_APPLE_TEAM_ID"),
            "team_name": env.get("FASTLANE_MCP_APPLE_TEAM_NAME"),
            "itc_team_id": env.get("FASTLANE_MCP_APPLE_ITC_TEAM_ID"),
            "itc_team_name": env.get("FASTLANE_MCP_APPLE_ITC_TEAM_NAME"),
            "default_platform": env.get("FASTLANE_MCP_APPLE_DEFAULT_PLATFORM"),
        },
        "gradle": {
            "build_aab_task": env.get("FASTLANE_MCP_GRADLE_BUILD_AAB_TASK"),
            "build_apk_task": env.get("FASTLANE_MCP_GRADLE_BUILD_APK_TASK"),
        },
        "defaults": {
            "changes_not_sent_for_review": bool_from_env(
                env.get("FASTLANE_MCP_DEFAULT_CHANGES_NOT_SENT_FOR_REVIEW"),
                True,
            ),
            "skip_upload_metadata": bool_from_env(
                env.get("FASTLANE_MCP_DEFAULT_SKIP_UPLOAD_METADATA"),
                False,
            ),
            "skip_upload_images": bool_from_env(
                env.get("FASTLANE_MCP_DEFAULT_SKIP_UPLOAD_IMAGES"),
                False,
            ),
            "skip_upload_screenshots": bool_from_env(
                env.get("FASTLANE_MCP_DEFAULT_SKIP_UPLOAD_SCREENSHOTS"),
                False,
            ),
            "skip_upload_changelogs": bool_from_env(
                env.get("FASTLANE_MCP_DEFAULT_SKIP_UPLOAD_CHANGELOGS"),
                False,
            ),
        },
    }


def load_app_config(
    project_root: str | None = None,
    app_config_path: str | None = None,
) -> AppConfig:
    """Resolve effective config from file, env vars, and explicit arguments."""
    file_path: Path | None = None
    if app_config_path:
        file_path = normalize_path(app_config_path, base_dir=project_root or os.getcwd())
    elif project_root:
        file_path = discover_app_config(project_root)
    elif os.environ.get("FASTLANE_MCP_PROJECT_ROOT"):
        file_path = discover_app_config(os.environ["FASTLANE_MCP_PROJECT_ROOT"])

    merged: dict[str, Any] = {}
    if file_path:
        merged = _deep_merge(merged, _load_yaml_config(file_path))

    merged = _deep_merge(merged, _strip_none_values(env_config()))

    if project_root:
        merged["project_root"] = str(normalize_path(project_root))
    elif merged.get("project_root"):
        merged["project_root"] = str(normalize_path(str(merged["project_root"])))
    else:
        raise ConfigError(
            "project_root is required. Pass it to the tool, set FASTLANE_MCP_PROJECT_ROOT, or configure it in app config."
        )

    merged.setdefault("android_dir", "android")
    merged.setdefault("ios_dir", "ios")
    merged.setdefault("default_track", "internal")
    merged["config_path"] = str(file_path) if file_path else None
    return AppConfig.model_validate(merged)
