from pathlib import Path

from fastlane_mcp.android_tools import _build_fastlane_command, _prepare_release_notes_overlay
from fastlane_mcp.models import AppConfig


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
