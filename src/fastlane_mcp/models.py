"""Typed models used by the MCP server."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ArtifactsConfig(BaseModel):
    """Artifact discovery configuration."""

    aab_glob: str = "android/app/build/outputs/bundle/**/*.aab"
    apk_glob: str = "android/app/build/outputs/apk/**/*.apk"
    ipa_glob: str = "ios/build/**/*.ipa"


class PlayConfig(BaseModel):
    """Google Play / supply configuration."""

    json_key_file: str | None = None
    json_key_content: str | None = None
    metadata_dir: str | None = "fastlane/metadata/android"
    images_dir: str | None = None
    changelogs_dir: str | None = None
    default_language: str = "en-US"


class GradleConfig(BaseModel):
    """Gradle defaults for Android builds."""

    build_aab_task: str = "bundleRelease"
    build_apk_task: str = "assembleRelease"
    clean_task: str = "clean"


class DefaultsConfig(BaseModel):
    """Default behavior for uploads."""

    changes_not_sent_for_review: bool = True
    skip_upload_metadata: bool = False
    skip_upload_images: bool = False
    skip_upload_changelogs: bool = False


class AppleConfig(BaseModel):
    """App Store Connect / fastlane Apple configuration."""

    api_key_path: str | None = None
    api_key_content: str | None = None
    username: str | None = None
    metadata_dir: str | None = "fastlane/metadata/ios"
    screenshots_dir: str | None = "fastlane/screenshots"
    privacy_details_path: str | None = "fastlane/app_privacy_details.json"
    team_id: str | None = None
    team_name: str | None = None
    itc_team_id: str | None = None
    itc_team_name: str | None = None
    default_platform: str = "ios"


class AppConfig(BaseModel):
    """Resolved app configuration used by all tools."""

    app_name: str | None = None
    platform: Literal["android", "ios", "react-native"] = "android"
    project_root: str
    android_dir: str = "android"
    ios_dir: str = "ios"
    package_name: str | None = None
    bundle_identifier: str | None = None
    default_track: str = "internal"
    artifacts: ArtifactsConfig = Field(default_factory=ArtifactsConfig)
    play: PlayConfig = Field(default_factory=PlayConfig)
    apple: AppleConfig = Field(default_factory=AppleConfig)
    gradle: GradleConfig = Field(default_factory=GradleConfig)
    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)
    config_path: str | None = None


class HealthCheckItem(BaseModel):
    """Single dependency check result."""

    name: str
    command: list[str]
    available: bool
    version: str | None = None
    detail: str | None = None


class DoctorCheck(BaseModel):
    """Single doctor check result."""

    name: str
    ok: bool
    severity: Literal["error", "warning", "info"] = "info"
    detail: str


class SupportedAction(BaseModel):
    """Supported MCP action metadata."""

    tool_name: str
    category: str
    description: str
    underlying_capability: str


class CommandResult(BaseModel):
    """Normalized command execution response returned by tools."""

    success: bool
    tool: str
    message: str
    command: list[str] = Field(default_factory=list)
    command_display: str | None = None
    cwd: str | None = None
    return_code: int | None = None
    stdout_excerpt: str | None = None
    stderr_excerpt: str | None = None
    artifact_paths: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)
