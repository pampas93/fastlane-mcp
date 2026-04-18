from fastlane_mcp.android_tools import list_supported_actions
from fastlane_mcp.store_listing_tools import store_listing_requirements


def test_store_listing_requirements_returns_both_platforms_by_default() -> None:
    result = store_listing_requirements()

    assert result["success"] is True
    assert result["tool"] == "store_listing_requirements"
    assert "google_play" in result["data"]["platforms"]
    assert "app_store" in result["data"]["platforms"]


def test_store_listing_requirements_can_filter_to_single_platform() -> None:
    result = store_listing_requirements(platform="google_play")

    assert result["success"] is True
    assert "google_play" in result["data"]["platforms"]
    assert "app_store" not in result["data"]["platforms"]


def test_list_supported_actions_includes_store_listing_requirements() -> None:
    result = list_supported_actions()
    actions = result["data"]["actions"]

    assert any(action["tool_name"] == "store_listing_requirements" for action in actions)
