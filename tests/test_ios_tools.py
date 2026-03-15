from pathlib import Path

from fastlane_mcp.android_tools import _build_fastlane_command
from fastlane_mcp.ios_tools import _build_pilot_command, _extract_build_number
from fastlane_mcp.models import AppConfig


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


def test_extract_build_number_returns_last_integer() -> None:
    output = "Latest build numbers:\n42\nApp Store build number: 41"

    assert _extract_build_number(output) == 41
