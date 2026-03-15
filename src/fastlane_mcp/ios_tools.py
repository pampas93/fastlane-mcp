"""Tool implementations for iOS App Store and TestFlight workflows."""

from __future__ import annotations

import json
import re
import tempfile
from contextlib import ExitStack
from pathlib import Path
from typing import Any, Literal

from .android_tools import (
    _base_success,
    _build_fastlane_command,
    _find_artifact,
    _resolve_config,
    _timeout_seconds,
    _tool_error,
)
from .exceptions import ConfigError, FastlaneMCPError, ValidationError
from .fastlane_runner import find_bundle_context, run_command
from .models import AppConfig
from .validators import normalize_path, redact_value, require_directory, require_file


def _resolve_apple_metadata_root(config: AppConfig, override: str | None, kind: Literal["metadata", "screenshots"]) -> Path:
    if override:
        return require_directory(normalize_path(override, config.project_root), f"{kind}_dir")
    configured = config.apple.metadata_dir if kind == "metadata" else config.apple.screenshots_dir
    if not configured:
        raise ConfigError(f"No Apple {kind} directory configured.")
    return require_directory(normalize_path(configured, config.project_root), f"{kind}_dir")


def _resolve_apple_api_key(config: AppConfig, stack: ExitStack) -> tuple[Path, list[str]]:
    sensitive_values: list[str] = []
    if config.apple.api_key_path:
        key_path = require_file(normalize_path(config.apple.api_key_path, config.project_root), "api_key_path")
        sensitive_values.append(str(key_path))
        return key_path, sensitive_values
    if config.apple.api_key_content:
        temp_dir = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="fastlane-mcp-apple-key-")))
        key_path = temp_dir / "app-store-connect-api-key.json"
        key_path.write_text(config.apple.api_key_content, encoding="utf-8")
        sensitive_values.append(str(key_path))
        return key_path, sensitive_values
    raise ConfigError(
        "App Store Connect API credentials are missing. Set apple.api_key_path, apple.api_key_content, "
        "FASTLANE_MCP_APPLE_API_KEY_PATH, or FASTLANE_MCP_APPLE_API_KEY_CONTENT."
    )


def _require_bundle_identifier(config: AppConfig, bundle_identifier: str | None = None) -> str:
    identifier = (bundle_identifier or config.bundle_identifier or "").strip()
    if not identifier:
        raise ConfigError("bundle_identifier is required for iOS App Store operations.")
    return identifier


def _require_apple_username(config: AppConfig, username: str | None = None) -> str:
    value = (username or config.apple.username or "").strip()
    if not value:
        raise ConfigError(
            "An Apple username is required for this operation. Set apple.username or FASTLANE_MCP_APPLE_USERNAME."
        )
    return value


def _extract_build_number(output: str) -> int | None:
    matches = re.findall(r"(?<!\d)(\d+)(?!\d)", output)
    if not matches:
        return None
    return int(matches[-1])


def _apple_common_params(config: AppConfig, bundle_identifier: str) -> dict[str, Any]:
    params: dict[str, Any] = {
        "app_identifier": bundle_identifier,
        "platform": config.apple.default_platform,
        "team_id": config.apple.team_id,
        "team_name": config.apple.team_name,
        "itc_team_id": config.apple.itc_team_id,
        "itc_team_name": config.apple.itc_team_name,
    }
    return params


def _build_pilot_command(
    config: AppConfig,
    *,
    subcommand: str,
    arguments: list[str],
    working_dir: str | None = None,
) -> tuple[list[str], Path]:
    base_command, cwd = find_bundle_context(config.project_root, working_dir or config.ios_dir)
    return [*base_command, "pilot", subcommand, *arguments], cwd


def ios_upload_to_testflight(
    project_root: str,
    app_config_path: str | None = None,
    ipa_path: str | None = None,
    changelog: str | None = None,
    groups: list[str] | None = None,
    distribute_external: bool = False,
    notify_external_testers: bool = False,
    expire_previous_builds: bool = False,
) -> dict[str, Any]:
    """Upload an iOS build to TestFlight and optionally distribute it."""
    try:
        config = _resolve_config(project_root, app_config_path)
        bundle_identifier = _require_bundle_identifier(config)
        with ExitStack() as stack:
            api_key_path, sensitive_values = _resolve_apple_api_key(config, stack)
            ipa = _find_artifact(config, "ipa", ipa_path)
            params = {
                "api_key_path": str(api_key_path),
                "ipa": str(ipa),
                "skip_waiting_for_build_processing": False,
                "changelog": changelog,
                "groups": groups,
                "distribute_external": distribute_external,
                "notify_external_testers": notify_external_testers,
                "expire_previous_builds": expire_previous_builds,
                **_apple_common_params(config, bundle_identifier),
            }
            sensitive_values.append(str(ipa))
            command, cwd, sensitive_values = _build_fastlane_command(
                config,
                action="upload_to_testflight",
                params=params,
                sensitive_values=sensitive_values,
                working_dir=config.ios_dir,
            )
            result = run_command(
                tool_name="ios_upload_to_testflight",
                command=command,
                cwd=cwd,
                timeout=_timeout_seconds(),
                sensitive_values=sensitive_values,
            )
            result.message = "Uploaded iOS build to TestFlight."
            result.artifact_paths = [str(ipa)]
            result.next_steps = [
                "Check TestFlight processing and tester visibility in App Store Connect.",
                "Run ios_get_latest_build_info to confirm the latest TestFlight build number.",
            ]
            return result.model_dump()
    except FastlaneMCPError as exc:
        return _tool_error("ios_upload_to_testflight", exc)


def ios_distribute_testflight_build(
    project_root: str,
    app_config_path: str | None = None,
    groups: list[str] | None = None,
    notify_external_testers: bool = False,
    app_version: str | None = None,
    build_number: str | None = None,
) -> dict[str, Any]:
    """Distribute an existing TestFlight build to tester groups."""
    try:
        if not groups:
            raise ValidationError("At least one TestFlight group is required.")
        config = _resolve_config(project_root, app_config_path)
        bundle_identifier = _require_bundle_identifier(config)
        with ExitStack() as stack:
            api_key_path, sensitive_values = _resolve_apple_api_key(config, stack)
            params = {
                "api_key_path": str(api_key_path),
                "app_identifier": bundle_identifier,
                "distribute_only": True,
                "distribute_external": True,
                "groups": groups,
                "notify_external_testers": notify_external_testers,
                "app_version": app_version,
                "build_number": build_number,
                **_apple_common_params(config, bundle_identifier),
            }
            command, cwd, sensitive_values = _build_fastlane_command(
                config,
                action="upload_to_testflight",
                params=params,
                sensitive_values=sensitive_values,
                working_dir=config.ios_dir,
            )
            result = run_command(
                tool_name="ios_distribute_testflight_build",
                command=command,
                cwd=cwd,
                timeout=_timeout_seconds(),
                sensitive_values=sensitive_values,
            )
            result.message = "Distributed existing TestFlight build."
            result.next_steps = ["Verify tester group assignment and external distribution in App Store Connect."]
            return result.model_dump()
    except FastlaneMCPError as exc:
        return _tool_error("ios_distribute_testflight_build", exc)


def ios_manage_testflight_testers(
    project_root: str,
    app_config_path: str | None = None,
    operation: Literal["add", "remove", "list", "import", "export"] = "list",
    emails: list[str] | None = None,
    groups: list[str] | None = None,
    file_path: str | None = None,
) -> dict[str, Any]:
    """Manage TestFlight testers and groups via fastlane pilot."""
    try:
        config = _resolve_config(project_root, app_config_path)
        bundle_identifier = _require_bundle_identifier(config)
        username = _require_apple_username(config)
        arguments = ["-a", bundle_identifier, "-u", username]
        sensitive_values = [username]
        for group in groups or []:
            arguments.extend(["-g", group])
        if operation in {"add", "remove"}:
            if not emails:
                raise ValidationError(f"emails are required for the {operation} operation.")
            arguments.extend(emails)
        if operation in {"import", "export"}:
            if not file_path:
                raise ValidationError(f"file_path is required for the {operation} operation.")
            resolved = normalize_path(file_path, config.project_root)
            if operation == "import":
                require_file(resolved, "file_path")
            else:
                resolved.parent.mkdir(parents=True, exist_ok=True)
            arguments.extend(["-f", str(resolved)])
            sensitive_values.append(str(resolved))

        command, cwd = _build_pilot_command(
            config,
            subcommand=operation,
            arguments=arguments,
            working_dir=config.ios_dir,
        )
        result = run_command(
            tool_name="ios_manage_testflight_testers",
            command=command,
            cwd=cwd,
            timeout=_timeout_seconds(),
            sensitive_values=sensitive_values,
        )
        result.message = f"TestFlight tester operation `{operation}` completed."
        if file_path and operation == "export":
            result.artifact_paths = [str(normalize_path(file_path, config.project_root))]
        return result.model_dump()
    except FastlaneMCPError as exc:
        return _tool_error("ios_manage_testflight_testers", exc)


def _upload_to_app_store(
    *,
    tool_name: str,
    config: AppConfig,
    ipa_path: str | None = None,
    metadata_dir: str | None = None,
    screenshots_dir: str | None = None,
    submit_for_review: bool = False,
    release_notes: str | None = None,
    skip_binary_upload: bool = False,
    skip_metadata: bool = False,
    skip_screenshots: bool = False,
) -> dict[str, Any]:
    bundle_identifier = _require_bundle_identifier(config)
    with ExitStack() as stack:
        api_key_path, sensitive_values = _resolve_apple_api_key(config, stack)
        ipa: Path | None = None
        params = {
            "api_key_path": str(api_key_path),
            "app_identifier": bundle_identifier,
            "metadata_path": str(_resolve_apple_metadata_root(config, metadata_dir, "metadata")) if not skip_metadata else None,
            "screenshots_path": str(_resolve_apple_metadata_root(config, screenshots_dir, "screenshots")) if not skip_screenshots else None,
            "submit_for_review": submit_for_review,
            "release_notes": release_notes,
            "skip_binary_upload": skip_binary_upload,
            "skip_metadata": skip_metadata,
            "skip_screenshots": skip_screenshots,
            **_apple_common_params(config, bundle_identifier),
        }
        if not skip_binary_upload:
            ipa = _find_artifact(config, "ipa", ipa_path)
            params["ipa"] = str(ipa)
            sensitive_values.append(str(ipa))
        command, cwd, sensitive_values = _build_fastlane_command(
            config,
            action="upload_to_app_store",
            params=params,
            sensitive_values=sensitive_values,
            working_dir=config.ios_dir,
        )
        result = run_command(
            tool_name=tool_name,
            command=command,
            cwd=cwd,
            timeout=_timeout_seconds(),
            sensitive_values=sensitive_values,
        )
        result.message = "Uploaded App Store Connect assets." if skip_binary_upload else "Uploaded iOS release to App Store Connect."
        if ipa:
            result.artifact_paths = [str(ipa)]
        result.next_steps = ["Check App Store Connect for processing, metadata validation, and review state."]
        return result.model_dump()


def ios_upload_to_app_store(
    project_root: str,
    app_config_path: str | None = None,
    ipa_path: str | None = None,
    submit_for_review: bool = False,
    release_notes: str | None = None,
) -> dict[str, Any]:
    """Upload an iOS build, metadata, and screenshots to App Store Connect."""
    try:
        config = _resolve_config(project_root, app_config_path)
        return _upload_to_app_store(
            tool_name="ios_upload_to_app_store",
            config=config,
            ipa_path=ipa_path,
            submit_for_review=submit_for_review,
            release_notes=release_notes,
        )
    except FastlaneMCPError as exc:
        return _tool_error("ios_upload_to_app_store", exc)


def ios_upload_metadata(
    project_root: str,
    app_config_path: str | None = None,
    metadata_dir: str | None = None,
) -> dict[str, Any]:
    """Upload App Store text metadata only."""
    try:
        config = _resolve_config(project_root, app_config_path)
        return _upload_to_app_store(
            tool_name="ios_upload_metadata",
            config=config,
            metadata_dir=metadata_dir,
            skip_binary_upload=True,
            skip_screenshots=True,
        )
    except FastlaneMCPError as exc:
        return _tool_error("ios_upload_metadata", exc)


def ios_upload_screenshots(
    project_root: str,
    app_config_path: str | None = None,
    screenshots_dir: str | None = None,
) -> dict[str, Any]:
    """Upload App Store screenshots only."""
    try:
        config = _resolve_config(project_root, app_config_path)
        return _upload_to_app_store(
            tool_name="ios_upload_screenshots",
            config=config,
            screenshots_dir=screenshots_dir,
            skip_binary_upload=True,
            skip_metadata=True,
        )
    except FastlaneMCPError as exc:
        return _tool_error("ios_upload_screenshots", exc)


def ios_precheck(
    project_root: str,
    app_config_path: str | None = None,
    include_in_app_purchases: bool = False,
) -> dict[str, Any]:
    """Run fastlane precheck against App Store metadata."""
    try:
        config = _resolve_config(project_root, app_config_path)
        bundle_identifier = _require_bundle_identifier(config)
        with ExitStack() as stack:
            api_key_path, sensitive_values = _resolve_apple_api_key(config, stack)
            params = {
                "api_key_path": str(api_key_path),
                "app_identifier": bundle_identifier,
                "include_in_app_purchases": include_in_app_purchases,
                **_apple_common_params(config, bundle_identifier),
            }
            command, cwd, sensitive_values = _build_fastlane_command(
                config,
                action="precheck",
                params=params,
                sensitive_values=sensitive_values,
                working_dir=config.ios_dir,
            )
            result = run_command(
                tool_name="ios_precheck",
                command=command,
                cwd=cwd,
                timeout=_timeout_seconds(),
                sensitive_values=sensitive_values,
            )
            result.message = "App Store precheck completed."
            return result.model_dump()
    except FastlaneMCPError as exc:
        return _tool_error("ios_precheck", exc)


def ios_get_latest_build_info(
    project_root: str,
    app_config_path: str | None = None,
    live: bool = False,
    initial_build_number: int | None = None,
) -> dict[str, Any]:
    """Read latest TestFlight and App Store build numbers."""
    try:
        config = _resolve_config(project_root, app_config_path)
        bundle_identifier = _require_bundle_identifier(config)
        with ExitStack() as stack:
            api_key_path, sensitive_values = _resolve_apple_api_key(config, stack)
            tf_cmd, cwd, tf_sensitive = _build_fastlane_command(
                config,
                action="latest_testflight_build_number",
                params={
                    "api_key_path": str(api_key_path),
                    "app_identifier": bundle_identifier,
                    "initial_build_number": initial_build_number,
                    **_apple_common_params(config, bundle_identifier),
                },
                sensitive_values=sensitive_values,
                working_dir=config.ios_dir,
            )
            tf_result = run_command(
                tool_name="ios_get_latest_build_info",
                command=tf_cmd,
                cwd=cwd,
                timeout=300,
                sensitive_values=tf_sensitive,
            )
            app_store_cmd, app_store_cwd, app_store_sensitive = _build_fastlane_command(
                config,
                action="app_store_build_number",
                params={
                    "api_key_path": str(api_key_path),
                    "app_identifier": bundle_identifier,
                    "live": live,
                    "initial_build_number": initial_build_number,
                    **_apple_common_params(config, bundle_identifier),
                },
                sensitive_values=sensitive_values,
                working_dir=config.ios_dir,
            )
            app_store_result = run_command(
                tool_name="ios_get_latest_build_info",
                command=app_store_cmd,
                cwd=app_store_cwd,
                timeout=300,
                sensitive_values=app_store_sensitive,
            )
            tf_output = f"{tf_result.stdout_excerpt or ''}\n{tf_result.stderr_excerpt or ''}"
            app_store_output = f"{app_store_result.stdout_excerpt or ''}\n{app_store_result.stderr_excerpt or ''}"
            tf_result.message = "Fetched iOS build information."
            tf_result.data = {
                "bundle_identifier": bundle_identifier,
                "latest_testflight_build_number": _extract_build_number(tf_output),
                "app_store_build_number": _extract_build_number(app_store_output),
                "app_store_live": live,
            }
            return tf_result.model_dump()
    except FastlaneMCPError as exc:
        return _tool_error("ios_get_latest_build_info", exc)


def ios_sync_code_signing(
    project_root: str,
    app_config_path: str | None = None,
    type: Literal["appstore", "adhoc", "development", "enterprise"] = "appstore",
    readonly: bool = True,
    app_identifiers: list[str] | None = None,
) -> dict[str, Any]:
    """Sync iOS certificates and provisioning profiles with fastlane match."""
    try:
        config = _resolve_config(project_root, app_config_path)
        identifiers = app_identifiers or [_require_bundle_identifier(config)]
        with ExitStack() as stack:
            api_key_path, sensitive_values = _resolve_apple_api_key(config, stack)
            params = {
                "api_key_path": str(api_key_path),
                "type": type,
                "readonly": readonly,
                "app_identifier": identifiers,
                "platform": config.apple.default_platform,
                "team_id": config.apple.team_id,
                "team_name": config.apple.team_name,
            }
            command, cwd, sensitive_values = _build_fastlane_command(
                config,
                action="match",
                params=params,
                sensitive_values=sensitive_values,
                working_dir=config.ios_dir,
            )
            result = run_command(
                tool_name="ios_sync_code_signing",
                command=command,
                cwd=cwd,
                timeout=_timeout_seconds(),
                sensitive_values=sensitive_values,
            )
            result.message = "Code signing sync completed."
            result.data = {"app_identifiers": identifiers, "type": type, "readonly": readonly}
            return result.model_dump()
    except FastlaneMCPError as exc:
        return _tool_error("ios_sync_code_signing", exc)


def ios_create_app(
    project_root: str,
    app_name: str,
    sku: str,
    bundle_identifier: str,
    primary_language: str = "English",
    app_config_path: str | None = None,
    username: str | None = None,
) -> dict[str, Any]:
    """Create a new app in App Store Connect and the Apple Developer Portal."""
    try:
        config = _resolve_config(project_root, app_config_path)
        apple_username = _require_apple_username(config, username)
        base_command, cwd = find_bundle_context(config.project_root, config.ios_dir)
        command = [
            *base_command,
            "produce",
            "-u",
            apple_username,
            "-a",
            bundle_identifier,
            "--app_name",
            app_name,
            "--sku",
            sku,
            "--language",
            primary_language,
        ]
        sensitive_values = [apple_username]
        result = run_command(
            tool_name="ios_create_app",
            command=command,
            cwd=cwd,
            timeout=_timeout_seconds(),
            sensitive_values=sensitive_values,
        )
        result.message = f"Created App Store Connect app `{app_name}`."
        result.data = {"bundle_identifier": bundle_identifier, "sku": sku, "primary_language": primary_language}
        result.next_steps = [
            "Confirm the app record, capabilities, and agreements in App Store Connect.",
            "Upload App Privacy Details and metadata before the first submission.",
        ]
        return result.model_dump()
    except FastlaneMCPError as exc:
        return _tool_error("ios_create_app", exc)


def ios_upload_app_privacy_details(
    project_root: str,
    app_config_path: str | None = None,
    json_path: str | None = None,
    username: str | None = None,
) -> dict[str, Any]:
    """Upload App Privacy Details to App Store Connect."""
    try:
        config = _resolve_config(project_root, app_config_path)
        apple_username = _require_apple_username(config, username)
        privacy_path_value = json_path or config.apple.privacy_details_path
        if not privacy_path_value:
            raise ConfigError("No privacy details file configured.")
        privacy_path = require_file(
            normalize_path(privacy_path_value, config.project_root),
            "privacy_details_path",
        )
        require_bundle_identifier(config)
        command, cwd, sensitive_values = _build_fastlane_command(
            config,
            action="upload_app_privacy_details_to_app_store",
            params={
                "username": apple_username,
                "json_path": str(privacy_path),
            },
            sensitive_values=[apple_username, str(privacy_path)],
            working_dir=config.ios_dir,
        )
        result = run_command(
            tool_name="ios_upload_app_privacy_details",
            command=command,
            cwd=cwd,
            timeout=_timeout_seconds(),
            sensitive_values=sensitive_values,
        )
        result.message = "Uploaded App Privacy Details to App Store Connect."
        return result.model_dump()
    except FastlaneMCPError as exc:
        return _tool_error("ios_upload_app_privacy_details", exc)


def ios_show_effective_config(
    project_root: str | None = None,
    app_config_path: str | None = None,
) -> dict[str, Any]:
    """Return the merged config with Apple and Play secrets redacted."""
    try:
        config = _resolve_config(project_root, app_config_path)
        dumped = config.model_dump()
        if dumped["play"].get("json_key_file"):
            dumped["play"]["json_key_file"] = redact_value(dumped["play"]["json_key_file"])
        if dumped["play"].get("json_key_content"):
            dumped["play"]["json_key_content"] = "[REDACTED_JSON_KEY_CONTENT]"
        if dumped["apple"].get("api_key_path"):
            dumped["apple"]["api_key_path"] = redact_value(dumped["apple"]["api_key_path"])
        if dumped["apple"].get("api_key_content"):
            try:
                json.loads(dumped["apple"]["api_key_content"])
            except json.JSONDecodeError:
                pass
            dumped["apple"]["api_key_content"] = "[REDACTED_APP_STORE_CONNECT_API_KEY]"
        return _base_success(
            "ios_show_effective_config",
            "Resolved config.",
            data={"config": dumped},
        )
    except FastlaneMCPError as exc:
        return _tool_error("ios_show_effective_config", exc)
