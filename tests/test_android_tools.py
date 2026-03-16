from pathlib import Path

from fastlane_mcp.android_tools import (
    _build_fastlane_command,
    _prepare_release_notes_overlay,
    android_upload_to_internal,
)
from fastlane_mcp.models import AppConfig, CommandResult


def test_build_fastlane_command_serializes_values() -> None:
    config = AppConfig(project_root=str(Path.cwd()))
    command, cwd, sensitive = _build_fastlane_command(
        config,
        action="upload_to_play_store",
        params={
            "track": "internal",
            "changes_not_sent_for_review": True,
            "rollout": 0.5,
        },
        sensitive_values=["secret"],
    )

    assert command[-3:] == [
        "track:internal",
        "changes_not_sent_for_review:true",
        "rollout:0.5",
    ]
    assert cwd == Path.cwd()
    assert sensitive == ["secret"]


def test_prepare_release_notes_overlay_creates_default_changelog(tmp_path: Path) -> None:
    metadata_root = tmp_path / "fastlane" / "metadata" / "android"
    metadata_root.mkdir(parents=True)
    config = AppConfig(project_root=str(tmp_path), play={"metadata_dir": "fastlane/metadata/android"})

    from contextlib import ExitStack

    with ExitStack() as stack:
        overlay = _prepare_release_notes_overlay(
            stack=stack,
            config=config,
            release_notes="Ship it",
            base_metadata_root=None,
        )
        changelog = overlay / "en-US" / "changelogs" / "default.txt"
        assert changelog.read_text(encoding="utf-8").strip() == "Ship it"


def _write_android_upload_fixture(project_root: Path) -> Path:
    (project_root / "android").mkdir()
    metadata_dir = project_root / "fastlane" / "metadata" / "android"
    metadata_dir.mkdir(parents=True)
    aab_path = project_root / "android" / "app-release.aab"
    aab_path.write_text("aab", encoding="utf-8")
    return aab_path


def _stub_android_run_command(monkeypatch, captured: dict[str, object]) -> None:
    def _run_command(*, tool_name: str, command: list[str], cwd, timeout: int, sensitive_values=None) -> CommandResult:
        captured["tool_name"] = tool_name
        captured["command"] = command
        captured["cwd"] = str(cwd)
        captured["timeout"] = timeout
        captured["sensitive_values"] = sensitive_values or []
        return CommandResult(success=True, tool=tool_name, message="ok", command=command, cwd=str(cwd))

    monkeypatch.setattr("fastlane_mcp.android_tools.run_command", _run_command)


def _set_android_upload_env(monkeypatch, project_root: Path) -> None:
    monkeypatch.setenv("FASTLANE_MCP_PACKAGE_NAME", "com.example.app")
    monkeypatch.setenv("FASTLANE_MCP_PLAY_JSON_KEY_CONTENT", "{}")
    monkeypatch.setenv("FASTLANE_MCP_PLAY_METADATA_DIR", str(project_root / "fastlane" / "metadata" / "android"))


def test_android_upload_to_internal_supports_release_status_and_skip_flags(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / "android-app"
    project_root.mkdir()
    aab_path = _write_android_upload_fixture(project_root)
    _set_android_upload_env(monkeypatch, project_root)
    captured: dict[str, object] = {}
    _stub_android_run_command(monkeypatch, captured)

    result = android_upload_to_internal(
        project_root=str(project_root),
        aab_path=str(aab_path),
        release_status="draft",
        skip_upload_metadata=True,
        skip_upload_images=True,
        skip_upload_screenshots=True,
        skip_upload_changelogs=True,
    )

    assert result["success"] is True
    command = captured["command"]
    assert isinstance(command, list)
    assert any(item == "release_status:draft" for item in command)
    assert any(item == "skip_upload_metadata:true" for item in command)
    assert any(item == "skip_upload_images:true" for item in command)
    assert any(item == "skip_upload_screenshots:true" for item in command)
    assert any(item == "skip_upload_changelogs:true" for item in command)


def test_android_upload_to_internal_normalizes_in_progress_release_status(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / "android-app"
    project_root.mkdir()
    aab_path = _write_android_upload_fixture(project_root)
    _set_android_upload_env(monkeypatch, project_root)
    captured: dict[str, object] = {}
    _stub_android_run_command(monkeypatch, captured)

    result = android_upload_to_internal(
        project_root=str(project_root),
        aab_path=str(aab_path),
        release_status="in_progress",
    )

    assert result["success"] is True
    command = captured["command"]
    assert isinstance(command, list)
    assert any(item == "release_status:inProgress" for item in command)


def test_android_upload_to_internal_rejects_invalid_release_status(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / "android-app"
    project_root.mkdir()
    aab_path = _write_android_upload_fixture(project_root)
    _set_android_upload_env(monkeypatch, project_root)
    captured: dict[str, object] = {}
    _stub_android_run_command(monkeypatch, captured)

    result = android_upload_to_internal(
        project_root=str(project_root),
        aab_path=str(aab_path),
        release_status="pending",
    )

    assert result["success"] is False
    assert "release_status must be one of" in result["message"]
