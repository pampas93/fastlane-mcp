from pathlib import Path

from fastlane_mcp.config import load_app_config


def test_load_app_config_from_file_and_env(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / "example-app"
    project_root.mkdir()
    config_path = project_root / "fastlane-mcp.yaml"
    config_path.write_text(
        """
project_root: /should/be/overridden
android_dir: android
package_name: com.example.file
play:
  metadata_dir: fastlane/metadata/android
""".strip(),
        encoding="utf-8",
    )

    monkeypatch.setenv("FASTLANE_MCP_PACKAGE_NAME", "com.example.env")

    config = load_app_config(project_root=str(project_root))

    assert config.project_root == str(project_root.resolve())
    assert config.package_name == "com.example.env"
    assert config.config_path == str(config_path.resolve())


def test_load_app_config_requires_project_root(tmp_path: Path) -> None:
    try:
        load_app_config()
    except Exception as exc:  # noqa: BLE001
        assert "project_root" in str(exc)
    else:
        raise AssertionError("load_app_config should require project_root when nothing else provides it")
