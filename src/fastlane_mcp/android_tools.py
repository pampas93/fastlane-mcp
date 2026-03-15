"""Tool implementations for Android build and release flows."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from contextlib import ExitStack
from pathlib import Path
from typing import Any, Literal

from .config import load_app_config
from .exceptions import ConfigError, ExecutionError, FastlaneMCPError, ValidationError
from .fastlane_runner import detect_version, find_bundle_context, run_command, which
from .models import AppConfig, CommandResult, DoctorCheck, HealthCheckItem, SupportedAction
from .validators import (
    build_gradle_task,
    find_latest_match,
    normalize_path,
    parse_bracketed_list,
    redact_value,
    require_directory,
    require_file,
    safe_excerpt,
    validate_rollout,
    validate_track_name,
)

DEFAULT_TIMEOUT_SECONDS = 1800


def _timeout_seconds() -> int:
    return int(os.environ.get("FASTLANE_MCP_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))


def _tool_error(tool_name: str, exc: Exception, *, next_steps: list[str] | None = None) -> dict[str, Any]:
    result = CommandResult(
        success=False,
        tool=tool_name,
        message=str(exc),
        next_steps=next_steps or [],
    )
    return result.model_dump()


def _base_success(tool_name: str, message: str, *, data: dict[str, Any] | None = None) -> dict[str, Any]:
    return CommandResult(success=True, tool=tool_name, message=message, data=data or {}).model_dump()


def _resolve_config(project_root: str | None, app_config_path: str | None) -> AppConfig:
    config = load_app_config(project_root=project_root, app_config_path=app_config_path)
    require_directory(config.project_root, "project_root")
    return config


def _resolve_android_dir(config: AppConfig) -> Path:
    return require_directory(normalize_path(config.android_dir, config.project_root), "android_dir")


def _resolve_metadata_root(
    config: AppConfig,
    override: str | None,
    kind: Literal["metadata", "images", "changelogs"],
) -> Path:
    if override:
        return require_directory(normalize_path(override, config.project_root), f"{kind}_dir")

    base_value = {
        "metadata": config.play.metadata_dir,
        "images": config.play.images_dir or config.play.metadata_dir,
        "changelogs": config.play.changelogs_dir or config.play.metadata_dir,
    }[kind]
    if not base_value:
        raise ConfigError(f"No {kind} directory configured.")
    return require_directory(normalize_path(base_value, config.project_root), f"{kind}_dir")


def _resolve_auth(config: AppConfig, stack: ExitStack) -> tuple[Path, list[str]]:
    sensitive_values: list[str] = []
    if config.play.json_key_file:
        json_key_file = require_file(
            normalize_path(config.play.json_key_file, config.project_root), "json_key_file"
        )
        sensitive_values.append(str(json_key_file))
        return json_key_file, sensitive_values

    if config.play.json_key_content:
        temp_dir = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="fastlane-mcp-play-key-")))
        json_key_path = temp_dir / "service-account.json"
        json_key_path.write_text(config.play.json_key_content, encoding="utf-8")
        sensitive_values.append(str(json_key_path))
        return json_key_path, sensitive_values

    raise ConfigError(
        "Google Play credentials are missing. Set play.json_key_file, play.json_key_content, GOOGLE_PLAY_JSON_KEY_FILE, or GOOGLE_PLAY_JSON_KEY_CONTENT."
    )


def _serialize_fastlane_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    if isinstance(value, (list, tuple, set)):
        return ",".join(str(item) for item in value)
    return str(value)


def _build_fastlane_command(
    config: AppConfig,
    *,
    action: str,
    params: dict[str, Any],
    sensitive_values: list[str] | None = None,
    working_dir: str | None = None,
) -> tuple[list[str], Path, list[str]]:
    base_command, cwd = find_bundle_context(config.project_root, working_dir or config.android_dir)
    command = [*base_command, "run", action]
    collected_sensitive_values = list(sensitive_values or [])
    for key, value in params.items():
        if value is None:
            continue
        command.append(f"{key}:{_serialize_fastlane_value(value)}")
    return command, cwd, collected_sensitive_values


def _gradle_command(android_dir: Path, task: str, clean: bool) -> list[str]:
    wrapper = android_dir / ("gradlew.bat" if os.name == "nt" else "gradlew")
    if wrapper.is_file():
        command = [str(wrapper)]
    elif which("gradle"):
        command = ["gradle"]
    else:
        raise ValidationError(
            f"No Gradle wrapper found at {wrapper} and `gradle` is not available on PATH."
        )

    if clean:
        command.append("clean")
    command.append(task)
    return command


def _find_artifact(config: AppConfig, kind: Literal["aab", "apk", "ipa"], override: str | None = None) -> Path:
    if override:
        return require_file(normalize_path(override, config.project_root), kind)
    pattern = {
        "aab": config.artifacts.aab_glob,
        "apk": config.artifacts.apk_glob,
        "ipa": config.artifacts.ipa_glob,
    }[kind]
    found = find_latest_match(config.project_root, pattern)
    if not found:
        raise ValidationError(
            f"Could not find a {kind.upper()} using glob {pattern!r}. Build first or pass an explicit path."
        )
    return found.resolve()


def _prepare_release_notes_overlay(
    *,
    stack: ExitStack,
    config: AppConfig,
    release_notes: str,
    base_metadata_root: str | None,
) -> Path:
    source: Path | None = None
    if base_metadata_root:
        source = _resolve_metadata_root(config, base_metadata_root, "metadata")
    elif config.play.metadata_dir:
        source = normalize_path(config.play.metadata_dir, config.project_root)

    temp_dir = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="fastlane-mcp-metadata-")))
    if source and source.is_dir():
        shutil.copytree(source, temp_dir, dirs_exist_ok=True)

    locale_dir = temp_dir / config.play.default_language / "changelogs"
    locale_dir.mkdir(parents=True, exist_ok=True)
    (locale_dir / "default.txt").write_text(release_notes.strip() + "\n", encoding="utf-8")
    return temp_dir


def _play_upload(
    *,
    tool_name: str,
    config: AppConfig,
    track: str,
    aab_path: str | None = None,
    apk_path: str | None = None,
    release_notes: str | None = None,
    changes_not_sent_for_review: bool | None = None,
    rollout: float | None = None,
    upload_metadata: bool = False,
    upload_images: bool = False,
    upload_changelogs: bool = False,
    metadata_root_override: str | None = None,
) -> dict[str, Any]:
    validate_track_name(track)
    validate_rollout(rollout)
    if not config.package_name:
        raise ConfigError("package_name is required for Google Play operations.")

    with ExitStack() as stack:
        json_key_path, sensitive_values = _resolve_auth(config, stack)
        effective_metadata_root: Path | None = None
        artifact_paths: list[Path] = []
        if aab_path:
            artifact_paths.append(_find_artifact(config, "aab", aab_path))
        if apk_path:
            artifact_paths.append(_find_artifact(config, "apk", apk_path))
        if not artifact_paths and not any([upload_metadata, upload_images, upload_changelogs]):
            artifact_paths.append(_find_artifact(config, "aab"))

        if release_notes:
            effective_metadata_root = _prepare_release_notes_overlay(
                stack=stack,
                config=config,
                release_notes=release_notes,
                base_metadata_root=metadata_root_override,
            )
            upload_changelogs = True

        if any([upload_metadata, upload_images, upload_changelogs]) and not effective_metadata_root:
            metadata_kind: Literal["metadata", "images", "changelogs"] = "metadata"
            if upload_images and not upload_metadata and not upload_changelogs:
                metadata_kind = "images"
            elif upload_changelogs and not upload_metadata and not upload_images:
                metadata_kind = "changelogs"
            effective_metadata_root = _resolve_metadata_root(config, metadata_root_override, metadata_kind)

        params: dict[str, Any] = {
            "package_name": config.package_name,
            "json_key": str(json_key_path),
            "track": track,
            "skip_upload_apk": not any(path.suffix == ".apk" for path in artifact_paths),
            "skip_upload_aab": not any(path.suffix == ".aab" for path in artifact_paths),
            "skip_upload_metadata": not upload_metadata,
            "skip_upload_images": not upload_images,
            "skip_upload_changelogs": not upload_changelogs,
            "changes_not_sent_for_review": (
                config.defaults.changes_not_sent_for_review
                if changes_not_sent_for_review is None
                else changes_not_sent_for_review
            ),
        }
        if effective_metadata_root:
            params["metadata_path"] = str(effective_metadata_root)
            sensitive_values.append(str(effective_metadata_root))
        if rollout is not None:
            params["rollout"] = rollout
        for artifact in artifact_paths:
            params["aab" if artifact.suffix == ".aab" else "apk"] = str(artifact)
            sensitive_values.append(str(artifact))

        command, cwd, sensitive_values = _build_fastlane_command(
            config,
            action="upload_to_play_store",
            params=params,
            sensitive_values=sensitive_values,
        )
        result = run_command(
            tool_name=tool_name,
            command=command,
            cwd=cwd,
            timeout=_timeout_seconds(),
            sensitive_values=sensitive_values,
        )
        result.message = f"Uploaded Android release assets to the {track} track."
        result.next_steps = [
            f"Check the {track} track in Play Console for review or rollout status.",
            "Run android_get_latest_build_info to confirm the published version codes.",
        ]
        result.artifact_paths = [str(path) for path in artifact_paths]
        return result.model_dump()


def healthcheck() -> dict[str, Any]:
    """Return local dependency availability and versions."""
    checks = [
        ("python", [sys.executable, "--version"]),
        ("ruby", ["ruby", "--version"]),
        ("bundle", ["bundle", "--version"]),
        ("fastlane", ["fastlane", "--version"]),
        ("java", ["java", "-version"]),
    ]
    items: list[HealthCheckItem] = []
    for name, command in checks:
        available, version, detail = detect_version(command)
        items.append(
            HealthCheckItem(
                name=name,
                command=command,
                available=available,
                version=safe_excerpt(version, limit=300),
                detail=detail,
            )
        )
    return _base_success(
        "healthcheck",
        "Local dependency check completed.",
        data={"checks": [item.model_dump() for item in items]},
    )


def doctor(project_root: str, app_config_path: str | None = None) -> dict[str, Any]:
    """Validate project layout, config, and likely prerequisites."""
    checks: list[DoctorCheck] = []
    try:
        config = _resolve_config(project_root, app_config_path)
        checks.append(
            DoctorCheck(
                name="config",
                ok=True,
                severity="info",
                detail=f"Resolved config for project_root={config.project_root}",
            )
        )
    except FastlaneMCPError as exc:
        return _tool_error(
            "doctor",
            exc,
            next_steps=["Add fastlane-mcp.yaml or set FASTLANE_MCP_PROJECT_ROOT and related env vars."],
        )

    android_dir = normalize_path(config.android_dir, config.project_root)
    ios_dir = normalize_path(config.ios_dir, config.project_root)
    checks.append(
        DoctorCheck(
            name="android_dir",
            ok=android_dir.is_dir(),
            severity="error" if not android_dir.is_dir() else "info",
            detail=f"Android directory {'found' if android_dir.is_dir() else 'missing'} at {android_dir}",
        )
    )
    checks.append(
        DoctorCheck(
            name="ios_dir",
            ok=ios_dir.is_dir(),
            severity="warning" if not ios_dir.is_dir() else "info",
            detail=f"iOS directory {'found' if ios_dir.is_dir() else 'missing'} at {ios_dir}",
        )
    )

    gradle_candidates = [android_dir / "gradlew", android_dir / "gradlew.bat"]
    has_gradle_wrapper = any(path.is_file() for path in gradle_candidates)
    checks.append(
        DoctorCheck(
            name="gradle_wrapper",
            ok=has_gradle_wrapper or which("gradle") is not None,
            severity="warning" if not has_gradle_wrapper else "info",
            detail="Using project Gradle wrapper."
            if has_gradle_wrapper
            else "No Gradle wrapper found. Will fall back to `gradle` if installed.",
        )
    )

    fastlane_available = which("fastlane") is not None
    checks.append(
        DoctorCheck(
            name="fastlane",
            ok=fastlane_available,
            severity="error" if not fastlane_available else "info",
            detail="fastlane is available on PATH." if fastlane_available else "fastlane not found on PATH.",
        )
    )

    gemfile_found = (Path(config.project_root) / "Gemfile").is_file() or (android_dir / "Gemfile").is_file()
    checks.append(
        DoctorCheck(
            name="bundler",
            ok=(not gemfile_found) or (which("bundle") is not None),
            severity="warning" if gemfile_found and which("bundle") is None else "info",
            detail="Gemfile present and bundle is available."
            if gemfile_found and which("bundle")
            else "No Gemfile found; fastlane will run directly."
            if not gemfile_found
            else "Gemfile found but `bundle` is missing.",
        )
    )

    checks.append(
        DoctorCheck(
            name="package_name",
            ok=bool(config.package_name),
            severity="warning" if not config.package_name else "info",
            detail="package_name configured." if config.package_name else "package_name is missing; Play uploads will fail.",
        )
    )
    checks.append(
        DoctorCheck(
            name="bundle_identifier",
            ok=bool(config.bundle_identifier),
            severity="warning" if not config.bundle_identifier else "info",
            detail="bundle_identifier configured."
            if config.bundle_identifier
            else "bundle_identifier is missing; App Store and TestFlight uploads will fail.",
        )
    )

    for label, value in {
        "metadata_dir": config.play.metadata_dir,
        "images_dir": config.play.images_dir,
        "changelogs_dir": config.play.changelogs_dir,
    }.items():
        if not value:
            continue
        path = normalize_path(value, config.project_root)
        checks.append(
            DoctorCheck(
                name=label,
                ok=path.is_dir(),
                severity="warning" if not path.is_dir() else "info",
                detail=f"{label} {'found' if path.is_dir() else 'missing'} at {path}",
            )
        )

    has_auth = bool(config.play.json_key_file or config.play.json_key_content)
    checks.append(
        DoctorCheck(
            name="play_auth",
            ok=has_auth,
            severity="warning" if not has_auth else "info",
            detail="Google Play credentials configured." if has_auth else "No Play auth configured.",
        )
    )
    has_apple_auth = bool(config.apple.api_key_path or config.apple.api_key_content or config.apple.username)
    checks.append(
        DoctorCheck(
            name="apple_auth",
            ok=has_apple_auth,
            severity="warning" if not has_apple_auth else "info",
            detail="Apple auth configured." if has_apple_auth else "No Apple auth configured.",
        )
    )
    for label, value in {
        "apple_metadata_dir": config.apple.metadata_dir,
        "apple_screenshots_dir": config.apple.screenshots_dir,
        "apple_privacy_details_path": config.apple.privacy_details_path,
    }.items():
        if not value:
            continue
        path = normalize_path(value, config.project_root)
        is_ok = path.exists()
        checks.append(
            DoctorCheck(
                name=label,
                ok=is_ok,
                severity="warning" if not is_ok else "info",
                detail=f"{label} {'found' if is_ok else 'missing'} at {path}",
            )
        )

    success = not any(check.severity == "error" and not check.ok for check in checks)
    return _base_success(
        "doctor",
        "Doctor completed." if success else "Doctor found blocking issues.",
        data={"ok": success, "checks": [check.model_dump() for check in checks]},
    )


def list_supported_actions() -> dict[str, Any]:
    """Return the MCP tool surface and the underlying fastlane/Gradle capabilities."""
    actions = [
        SupportedAction("healthcheck", "diagnostics", "Check local tool availability.", "python --version, ruby --version, bundle --version, fastlane --version"),
        SupportedAction("doctor", "diagnostics", "Validate project config and prerequisites.", "Local filesystem and PATH checks"),
        SupportedAction("list_supported_actions", "diagnostics", "List available MCP tools.", "Static metadata"),
        SupportedAction("android_build_aab", "build", "Build an Android App Bundle.", "Gradle bundle task"),
        SupportedAction("android_build_apk", "build", "Build an Android APK.", "Gradle assemble task"),
        SupportedAction("android_upload_to_internal", "release", "Upload a build to the internal track.", "fastlane upload_to_play_store"),
        SupportedAction("android_upload_to_beta", "release", "Upload a build to the beta track.", "fastlane upload_to_play_store"),
        SupportedAction("android_upload_to_production", "release", "Upload a build to the production track.", "fastlane upload_to_play_store"),
        SupportedAction("android_promote_track", "release", "Promote an existing release between tracks.", "fastlane upload_to_play_store track_promote_to"),
        SupportedAction("android_validate_play_auth", "release", "Validate Play JSON key and app access.", "fastlane validate_play_store_json_key + google_play_track_version_codes"),
        SupportedAction("android_upload_metadata", "metadata", "Upload store listing text metadata.", "fastlane upload_to_play_store"),
        SupportedAction("android_upload_images", "metadata", "Upload icons and screenshots.", "fastlane upload_to_play_store"),
        SupportedAction("android_upload_changelogs", "metadata", "Upload changelog files.", "fastlane upload_to_play_store"),
        SupportedAction("android_upload_everything", "metadata", "Upload binary plus metadata assets.", "fastlane upload_to_play_store"),
        SupportedAction("android_get_latest_build_info", "introspection", "Read latest release info for a track.", "fastlane google_play_track_version_codes + google_play_track_release_names"),
        SupportedAction("android_show_effective_config", "introspection", "Show merged config with secrets redacted.", "Config loader"),
        SupportedAction("ios_upload_to_testflight", "release", "Upload an iOS build to TestFlight.", "fastlane upload_to_testflight"),
        SupportedAction("ios_distribute_testflight_build", "release", "Distribute an existing TestFlight build to tester groups.", "fastlane upload_to_testflight distribute_only"),
        SupportedAction("ios_manage_testflight_testers", "release", "Manage TestFlight testers and groups.", "fastlane pilot"),
        SupportedAction("ios_upload_to_app_store", "release", "Upload an iOS build plus App Store assets.", "fastlane upload_to_app_store"),
        SupportedAction("ios_create_app", "release", "Create a new app in App Store Connect.", "fastlane produce"),
        SupportedAction("ios_upload_metadata", "metadata", "Upload App Store text metadata.", "fastlane upload_to_app_store"),
        SupportedAction("ios_upload_screenshots", "metadata", "Upload App Store screenshots.", "fastlane upload_to_app_store"),
        SupportedAction("ios_upload_app_privacy_details", "metadata", "Upload App Privacy Details.", "fastlane upload_app_privacy_details_to_app_store"),
        SupportedAction("ios_precheck", "metadata", "Validate App Store metadata before submission.", "fastlane precheck"),
        SupportedAction("ios_get_latest_build_info", "introspection", "Read latest TestFlight and App Store build numbers.", "fastlane latest_testflight_build_number + app_store_build_number"),
        SupportedAction("ios_show_effective_config", "introspection", "Show merged config with Apple and Play secrets redacted.", "Config loader"),
        SupportedAction("ios_sync_code_signing", "signing", "Sync certificates and profiles with match.", "fastlane match"),
    ]
    return _base_success(
        "list_supported_actions",
        "Supported actions listed.",
        data={"actions": [action.model_dump() for action in actions]},
    )


def _build_android_artifact(
    *,
    tool_name: str,
    project_root: str,
    app_config_path: str | None,
    kind: Literal["aab", "apk"],
    flavor: str | None,
    build_type: str | None,
    gradle_task: str | None,
    clean: bool,
) -> dict[str, Any]:
    try:
        config = _resolve_config(project_root, app_config_path)
        android_dir = _resolve_android_dir(config)
        derived_task = build_gradle_task(kind, flavor, build_type)
        task = gradle_task or derived_task or (
            config.gradle.build_aab_task if kind == "aab" else config.gradle.build_apk_task
        )
        command = _gradle_command(android_dir, task, clean)
        result = run_command(
            tool_name=tool_name,
            command=command,
            cwd=android_dir,
            timeout=_timeout_seconds(),
        )
        artifact = _find_artifact(config, kind)
        result.message = f"Built Android {kind.upper()} successfully."
        result.artifact_paths = [str(artifact)]
        result.next_steps = [
            "Upload the artifact with one of the android_upload_* tools.",
        ]
        return result.model_dump()
    except FastlaneMCPError as exc:
        return _tool_error(
            tool_name,
            exc,
            next_steps=["Run doctor to validate the project layout and fastlane prerequisites."],
        )


def android_build_aab(
    project_root: str,
    app_config_path: str | None = None,
    flavor: str | None = None,
    build_type: str | None = None,
    gradle_task: str | None = None,
    clean: bool = False,
) -> dict[str, Any]:
    """Build an Android App Bundle via Gradle."""
    return _build_android_artifact(
        tool_name="android_build_aab",
        project_root=project_root,
        app_config_path=app_config_path,
        kind="aab",
        flavor=flavor,
        build_type=build_type,
        gradle_task=gradle_task,
        clean=clean,
    )


def android_build_apk(
    project_root: str,
    app_config_path: str | None = None,
    flavor: str | None = None,
    build_type: str | None = None,
    gradle_task: str | None = None,
    clean: bool = False,
) -> dict[str, Any]:
    """Build an Android APK via Gradle."""
    return _build_android_artifact(
        tool_name="android_build_apk",
        project_root=project_root,
        app_config_path=app_config_path,
        kind="apk",
        flavor=flavor,
        build_type=build_type,
        gradle_task=gradle_task,
        clean=clean,
    )


def _upload_to_track(
    tool_name: str,
    project_root: str,
    app_config_path: str | None,
    track: str,
    aab_path: str | None,
    apk_path: str | None,
    release_notes: str | None,
    changes_not_sent_for_review: bool | None,
    rollout: float | None,
) -> dict[str, Any]:
    try:
        config = _resolve_config(project_root, app_config_path)
        return _play_upload(
            tool_name=tool_name,
            config=config,
            track=track,
            aab_path=aab_path,
            apk_path=apk_path,
            release_notes=release_notes,
            changes_not_sent_for_review=changes_not_sent_for_review,
            rollout=rollout,
        )
    except FastlaneMCPError as exc:
        return _tool_error(
            tool_name,
            exc,
            next_steps=["Confirm the package exists in Play Console and the service account has API access."],
        )


def android_upload_to_internal(
    project_root: str,
    app_config_path: str | None = None,
    aab_path: str | None = None,
    apk_path: str | None = None,
    release_notes: str | None = None,
    changes_not_sent_for_review: bool | None = None,
    rollout: float | None = None,
) -> dict[str, Any]:
    """Upload an Android build to the internal track."""
    return _upload_to_track(
        "android_upload_to_internal",
        project_root,
        app_config_path,
        "internal",
        aab_path,
        apk_path,
        release_notes,
        changes_not_sent_for_review,
        rollout,
    )


def android_upload_to_beta(
    project_root: str,
    app_config_path: str | None = None,
    aab_path: str | None = None,
    apk_path: str | None = None,
    release_notes: str | None = None,
    changes_not_sent_for_review: bool | None = None,
    rollout: float | None = None,
) -> dict[str, Any]:
    """Upload an Android build to the beta track."""
    return _upload_to_track(
        "android_upload_to_beta",
        project_root,
        app_config_path,
        "beta",
        aab_path,
        apk_path,
        release_notes,
        changes_not_sent_for_review,
        rollout,
    )


def android_upload_to_production(
    project_root: str,
    app_config_path: str | None = None,
    aab_path: str | None = None,
    apk_path: str | None = None,
    release_notes: str | None = None,
    changes_not_sent_for_review: bool | None = None,
    rollout: float | None = None,
) -> dict[str, Any]:
    """Upload an Android build to the production track."""
    return _upload_to_track(
        "android_upload_to_production",
        project_root,
        app_config_path,
        "production",
        aab_path,
        apk_path,
        release_notes,
        changes_not_sent_for_review,
        rollout,
    )


def android_promote_track(
    project_root: str,
    app_config_path: str | None = None,
    from_track: str = "internal",
    to_track: str = "production",
    rollout: float | None = None,
) -> dict[str, Any]:
    """Promote an existing Play release from one track to another."""
    try:
        config = _resolve_config(project_root, app_config_path)
        if not config.package_name:
            raise ConfigError("package_name is required for track promotion.")
        validate_track_name(from_track)
        validate_track_name(to_track)
        validate_rollout(rollout)
        with ExitStack() as stack:
            json_key_path, sensitive_values = _resolve_auth(config, stack)
            params = {
                "package_name": config.package_name,
                "json_key": str(json_key_path),
                "track": from_track,
                "track_promote_to": to_track,
                "skip_upload_apk": True,
                "skip_upload_aab": True,
                "skip_upload_metadata": True,
                "skip_upload_images": True,
                "skip_upload_changelogs": True,
            }
            if rollout is not None:
                params["rollout"] = rollout
            command, cwd, sensitive_values = _build_fastlane_command(
                config,
                action="upload_to_play_store",
                params=params,
                sensitive_values=sensitive_values,
            )
            result = run_command(
                tool_name="android_promote_track",
                command=command,
                cwd=cwd,
                timeout=_timeout_seconds(),
                sensitive_values=sensitive_values,
            )
            result.message = f"Promoted releases from {from_track} to {to_track}."
            result.next_steps = [f"Check the {to_track} track in Play Console for release status."]
            return result.model_dump()
    except FastlaneMCPError as exc:
        return _tool_error("android_promote_track", exc)


def android_validate_play_auth(
    project_root: str | None = None,
    app_config_path: str | None = None,
) -> dict[str, Any]:
    """Validate Google Play auth and optionally confirm app-level access."""
    try:
        config = _resolve_config(project_root, app_config_path)
        with ExitStack() as stack:
            json_key_path, sensitive_values = _resolve_auth(config, stack)
            validate_cmd, cwd, sensitive_values = _build_fastlane_command(
                config,
                action="validate_play_store_json_key",
                params={"json_key": str(json_key_path)},
                sensitive_values=sensitive_values,
            )
            validate_result = run_command(
                tool_name="android_validate_play_auth",
                command=validate_cmd,
                cwd=cwd,
                timeout=300,
                sensitive_values=sensitive_values,
            )

            package_access: dict[str, Any] | None = None
            warnings: list[str] = []
            if config.package_name:
                info_cmd, info_cwd, info_sensitive = _build_fastlane_command(
                    config,
                    action="google_play_track_version_codes",
                    params={
                        "package_name": config.package_name,
                        "track": validate_track_name(config.default_track),
                        "json_key": str(json_key_path),
                    },
                    sensitive_values=sensitive_values,
                )
                try:
                    info_result = run_command(
                        tool_name="android_validate_play_auth",
                        command=info_cmd,
                        cwd=info_cwd,
                        timeout=300,
                        sensitive_values=info_sensitive,
                    )
                    package_access = {
                        "track_checked": config.default_track,
                        "version_codes": parse_bracketed_list(
                            f"{info_result.stdout_excerpt or ''}\n{info_result.stderr_excerpt or ''}"
                        )
                        or [],
                    }
                except ExecutionError as exc:
                    warnings.append(
                        "The JSON key validated, but package-level Play API access check failed. "
                        "Confirm Play Console API access and app permissions."
                    )
                    package_access = {"package_access_error": str(exc)}
            else:
                warnings.append("package_name is missing, so only the JSON key itself was validated.")

            validate_result.warnings = warnings
            validate_result.message = "Google Play auth validation completed."
            validate_result.data = {
                "json_key_validation": "ok",
                "package_access": package_access,
            }
            return validate_result.model_dump()
    except FastlaneMCPError as exc:
        return _tool_error("android_validate_play_auth", exc)


def android_upload_metadata(
    project_root: str,
    app_config_path: str | None = None,
    metadata_dir: str | None = None,
) -> dict[str, Any]:
    """Upload Play Store text metadata only."""
    try:
        config = _resolve_config(project_root, app_config_path)
        return _play_upload(
            tool_name="android_upload_metadata",
            config=config,
            track=validate_track_name(config.default_track),
            upload_metadata=True,
            metadata_root_override=metadata_dir,
        )
    except FastlaneMCPError as exc:
        return _tool_error("android_upload_metadata", exc)


def android_upload_images(
    project_root: str,
    app_config_path: str | None = None,
    images_dir: str | None = None,
) -> dict[str, Any]:
    """Upload Play Store images and screenshots only."""
    try:
        config = _resolve_config(project_root, app_config_path)
        return _play_upload(
            tool_name="android_upload_images",
            config=config,
            track=validate_track_name(config.default_track),
            upload_images=True,
            metadata_root_override=images_dir,
        )
    except FastlaneMCPError as exc:
        return _tool_error("android_upload_images", exc)


def android_upload_changelogs(
    project_root: str,
    app_config_path: str | None = None,
    changelogs_dir: str | None = None,
) -> dict[str, Any]:
    """Upload Play Store changelog files only."""
    try:
        config = _resolve_config(project_root, app_config_path)
        return _play_upload(
            tool_name="android_upload_changelogs",
            config=config,
            track=validate_track_name(config.default_track),
            upload_changelogs=True,
            metadata_root_override=changelogs_dir,
        )
    except FastlaneMCPError as exc:
        return _tool_error("android_upload_changelogs", exc)


def android_upload_everything(
    project_root: str,
    app_config_path: str | None = None,
    aab_path: str | None = None,
    release_notes: str | None = None,
    track: str | None = None,
) -> dict[str, Any]:
    """Upload binary, metadata, images, and changelogs in one call."""
    try:
        config = _resolve_config(project_root, app_config_path)
        return _play_upload(
            tool_name="android_upload_everything",
            config=config,
            track=validate_track_name(track or config.default_track),
            aab_path=aab_path,
            release_notes=release_notes,
            upload_metadata=not config.defaults.skip_upload_metadata,
            upload_images=not config.defaults.skip_upload_images,
            upload_changelogs=not config.defaults.skip_upload_changelogs,
        )
    except FastlaneMCPError as exc:
        return _tool_error("android_upload_everything", exc)


def android_get_latest_build_info(
    project_root: str,
    app_config_path: str | None = None,
    track: str | None = None,
) -> dict[str, Any]:
    """Read current version codes and release names from a Play track."""
    try:
        config = _resolve_config(project_root, app_config_path)
        if not config.package_name:
            raise ConfigError("package_name is required to read Play track information.")
        selected_track = validate_track_name(track or config.default_track)
        with ExitStack() as stack:
            json_key_path, sensitive_values = _resolve_auth(config, stack)
            version_cmd, cwd, sensitive_values = _build_fastlane_command(
                config,
                action="google_play_track_version_codes",
                params={
                    "package_name": config.package_name,
                    "track": selected_track,
                    "json_key": str(json_key_path),
                },
                sensitive_values=sensitive_values,
            )
            version_result = run_command(
                tool_name="android_get_latest_build_info",
                command=version_cmd,
                cwd=cwd,
                timeout=300,
                sensitive_values=sensitive_values,
            )

            release_cmd, release_cwd, release_sensitive = _build_fastlane_command(
                config,
                action="google_play_track_release_names",
                params={
                    "package_name": config.package_name,
                    "track": selected_track,
                    "json_key": str(json_key_path),
                },
                sensitive_values=sensitive_values,
            )
            release_result = run_command(
                tool_name="android_get_latest_build_info",
                command=release_cmd,
                cwd=release_cwd,
                timeout=300,
                sensitive_values=release_sensitive,
            )

            version_codes = parse_bracketed_list(
                f"{version_result.stdout_excerpt or ''}\n{version_result.stderr_excerpt or ''}"
            ) or []
            release_names = parse_bracketed_list(
                f"{release_result.stdout_excerpt or ''}\n{release_result.stderr_excerpt or ''}"
            ) or []

            version_result.message = f"Fetched Play build information for track {selected_track}."
            version_result.data = {
                "track": selected_track,
                "version_codes": version_codes,
                "release_names": release_names,
                "latest_version_code": max(version_codes) if version_codes else None,
                "latest_release_name": release_names[-1] if release_names else None,
            }
            return version_result.model_dump()
    except FastlaneMCPError as exc:
        return _tool_error("android_get_latest_build_info", exc)


def android_show_effective_config(
    project_root: str | None = None,
    app_config_path: str | None = None,
) -> dict[str, Any]:
    """Return the merged config with secrets redacted."""
    try:
        config = _resolve_config(project_root, app_config_path)
        dumped = config.model_dump()
        if dumped["play"].get("json_key_file"):
            dumped["play"]["json_key_file"] = redact_value(dumped["play"]["json_key_file"])
        if dumped["play"].get("json_key_content"):
            dumped["play"]["json_key_content"] = "[REDACTED_JSON_KEY_CONTENT]"
        return _base_success(
            "android_show_effective_config",
            "Resolved config.",
            data={"config": dumped},
        )
    except FastlaneMCPError as exc:
        return _tool_error("android_show_effective_config", exc)
