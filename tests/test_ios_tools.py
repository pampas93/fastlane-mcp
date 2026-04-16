from pathlib import Path

from fastlane_mcp.android_tools import _build_fastlane_command
from fastlane_mcp.ios_tools import (
    _build_pilot_command,
    _apple_testflight_params,
    _extract_build_number,
    ios_upload_to_testflight,
    ios_show_effective_config,
    ios_upload_metadata,
    ios_upload_to_app_store,
)
from fastlane_mcp.models import AppConfig, CommandResult


def test_build_fastlane_command_supports_ios_working_dir_and_lists() -> None:
    config = AppConfig(project_root=str(Path.cwd()), ios_dir="ios")
    command, cwd, sensitive = _build_fastlane_command(
        config,
        action="upload_to_testflight",
        params={
            "groups": ["External", "Internal"],
            "notify_external_testers": True,
        },
        sensitive_values=["secret"],
        working_dir=config.ios_dir,
    )

    assert command[-2:] == [
        "groups:External,Internal",
        "notify_external_testers:true",
    ]
    assert cwd == Path.cwd()
    assert sensitive == ["secret"]


def test_build_pilot_command_uses_bundler_context() -> None:
    config = AppConfig(project_root=str(Path.cwd()), ios_dir="ios")
    command, cwd = _build_pilot_command(
        config,
        subcommand="list",
        arguments=["-a", "com.example.app", "-u", "ios@example.com"],
        working_dir=config.ios_dir,
    )

    assert command[:2] == ["fastlane", "pilot"]
    assert command[-4:] == ["-a", "com.example.app", "-u", "ios@example.com"]
    assert cwd == Path.cwd()


def test_apple_testflight_params_use_app_platform() -> None:
    config = AppConfig(project_root=str(Path.cwd()))

    params = _apple_testflight_params(config, "com.example.app")

    assert params["app_platform"] == "ios"
    assert "platform" not in params


def test_extract_build_number_returns_last_integer() -> None:
    output = "Latest build numbers:\n42\nApp Store build number: 41"

    assert _extract_build_number(output) == 41


def test_ios_upload_to_testflight_uses_app_platform(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FASTLANE_MCP_BUNDLE_IDENTIFIER", "com.example.app")
    monkeypatch.setenv("FASTLANE_MCP_APPLE_API_KEY_CONTENT", "{}")
    project_root = tmp_path / "ios-app"
    project_root.mkdir()
    (project_root / "ios").mkdir()
    ipa_path = project_root / "ios" / "build.ipa"
    ipa_path.write_text("ipa", encoding="utf-8")
    captured: dict[str, object] = {}
    _stub_run_command(monkeypatch, captured)

    result = ios_upload_to_testflight(
        project_root=str(project_root),
        ipa_path=str(ipa_path),
    )

    assert result["success"] is True
    command = captured["command"]
    assert isinstance(command, list)
    assert any(item == "app_platform:ios" for item in command)
    assert not any(item == "platform:ios" for item in command)


def _write_ios_upload_fixture(project_root: Path) -> tuple[Path, Path, Path]:
    (project_root / "ios").mkdir()
    metadata_dir = project_root / "fastlane" / "metadata" / "ios"
    metadata_dir.mkdir(parents=True)
    screenshots_dir = project_root / "fastlane" / "screenshots"
    screenshots_dir.mkdir(parents=True)
    age_rating_config = project_root / "fastlane" / "age_rating_config.json"
    age_rating_config.write_text('{"CARTOON_OR_FANTASY_VIOLENCE": "NONE"}', encoding="utf-8")
    ipa_path = project_root / "ios" / "build.ipa"
    ipa_path.write_text("ipa", encoding="utf-8")
    return metadata_dir, screenshots_dir, ipa_path


def _stub_run_command(monkeypatch, captured: dict[str, object]) -> None:
    def _run_command(*, tool_name: str, command: list[str], cwd, timeout: int, sensitive_values=None) -> CommandResult:
        captured["tool_name"] = tool_name
        captured["command"] = command
        captured["cwd"] = str(cwd)
        captured["timeout"] = timeout
        captured["sensitive_values"] = sensitive_values or []
        return CommandResult(success=True, tool=tool_name, message="ok", command=command, cwd=str(cwd))

    monkeypatch.setattr("fastlane_mcp.ios_tools.run_command", _run_command)


def _set_ios_upload_env(monkeypatch) -> None:
    monkeypatch.setenv("FASTLANE_MCP_BUNDLE_IDENTIFIER", "com.example.app")
    monkeypatch.setenv("FASTLANE_MCP_APPLE_API_KEY_CONTENT", "{}")


def test_ios_upload_metadata_uses_configured_age_rating_path_when_present(monkeypatch, tmp_path: Path) -> None:
    _set_ios_upload_env(monkeypatch)
    project_root = tmp_path / "ios-app"
    project_root.mkdir()
    metadata_dir, _, _ = _write_ios_upload_fixture(project_root)
    captured: dict[str, object] = {}
    _stub_run_command(monkeypatch, captured)

    result = ios_upload_metadata(
        project_root=str(project_root),
        metadata_dir=str(metadata_dir),
    )

    assert result["success"] is True
    command = captured["command"]
    assert isinstance(command, list)
    assert any(
        item == f"app_rating_config_path:{(project_root / 'fastlane' / 'age_rating_config.json').resolve()}"
        for item in command
    )


def test_ios_upload_metadata_uses_override_age_rating_path_when_passed(monkeypatch, tmp_path: Path) -> None:
    _set_ios_upload_env(monkeypatch)
    project_root = tmp_path / "ios-app"
    project_root.mkdir()
    metadata_dir, _, _ = _write_ios_upload_fixture(project_root)
    override_path = project_root / "config" / "custom_age_rating.json"
    override_path.parent.mkdir(parents=True)
    override_path.write_text('{"UNRESTRICTED_WEB_ACCESS": "NO"}', encoding="utf-8")
    captured: dict[str, object] = {}
    _stub_run_command(monkeypatch, captured)

    result = ios_upload_metadata(
        project_root=str(project_root),
        metadata_dir=str(metadata_dir),
        age_rating_config_path=str(override_path),
    )

    assert result["success"] is True
    command = captured["command"]
    assert isinstance(command, list)
    assert any(item == f"app_rating_config_path:{override_path.resolve()}" for item in command)


def test_ios_upload_metadata_ignores_missing_configured_age_rating_file(monkeypatch, tmp_path: Path) -> None:
    _set_ios_upload_env(monkeypatch)
    project_root = tmp_path / "ios-app"
    project_root.mkdir()
    metadata_dir = project_root / "fastlane" / "metadata" / "ios"
    metadata_dir.mkdir(parents=True)
    captured: dict[str, object] = {}
    _stub_run_command(monkeypatch, captured)

    result = ios_upload_metadata(
        project_root=str(project_root),
        metadata_dir=str(metadata_dir),
    )

    assert result["success"] is True
    command = captured["command"]
    assert isinstance(command, list)
    assert not any(item.startswith("app_rating_config_path:") for item in command)


def test_ios_upload_metadata_returns_validation_error_for_missing_override(monkeypatch, tmp_path: Path) -> None:
    _set_ios_upload_env(monkeypatch)
    project_root = tmp_path / "ios-app"
    project_root.mkdir()
    metadata_dir = project_root / "fastlane" / "metadata" / "ios"
    metadata_dir.mkdir(parents=True)
    captured: dict[str, object] = {}
    _stub_run_command(monkeypatch, captured)
    missing_override = project_root / "config" / "missing_age_rating.json"

    result = ios_upload_metadata(
        project_root=str(project_root),
        metadata_dir=str(metadata_dir),
        age_rating_config_path=str(missing_override),
    )

    assert result["success"] is False
    assert result["message"] == f"age_rating_config_path does not exist: {missing_override.resolve()}"


def test_ios_upload_to_app_store_command_includes_age_rating_config_path(monkeypatch, tmp_path: Path) -> None:
    _set_ios_upload_env(monkeypatch)
    project_root = tmp_path / "ios-app"
    project_root.mkdir()
    metadata_dir, screenshots_dir, ipa_path = _write_ios_upload_fixture(project_root)
    captured: dict[str, object] = {}
    _stub_run_command(monkeypatch, captured)

    result = ios_upload_to_app_store(
        project_root=str(project_root),
        ipa_path=str(ipa_path),
        age_rating_config_path=str(project_root / "fastlane" / "age_rating_config.json"),
    )

    assert result["success"] is True
    command = captured["command"]
    assert isinstance(command, list)
    assert any(item == f"metadata_path:{metadata_dir.resolve()}" for item in command)
    assert any(item == f"screenshots_path:{screenshots_dir.resolve()}" for item in command)
    assert any(
        item == f"app_rating_config_path:{(project_root / 'fastlane' / 'age_rating_config.json').resolve()}"
        for item in command
    )


def test_ios_show_effective_config_includes_age_rating_config_path(tmp_path: Path) -> None:
    project_root = tmp_path / "ios-app"
    project_root.mkdir()

    result = ios_show_effective_config(project_root=str(project_root))

    assert result["success"] is True
    assert result["data"]["config"]["apple"]["age_rating_config_path"] == "fastlane/age_rating_config.json"
