"""FastMCP server entrypoint."""

from __future__ import annotations

import logging
import os

from fastmcp import FastMCP

from .android_tools import (
    android_build_aab,
    android_build_apk,
    android_get_latest_build_info,
    android_promote_track,
    android_show_effective_config,
    android_upload_changelogs,
    android_upload_everything,
    android_upload_images,
    android_upload_metadata,
    android_upload_to_beta,
    android_upload_to_internal,
    android_upload_to_production,
    android_validate_play_auth,
    doctor,
    healthcheck,
    list_supported_actions,
)
from .ios_tools import (
    ios_create_app,
    ios_distribute_testflight_build,
    ios_get_latest_build_info,
    ios_manage_testflight_testers,
    ios_precheck,
    ios_show_effective_config,
    ios_sync_code_signing,
    ios_upload_app_privacy_details,
    ios_upload_metadata,
    ios_upload_screenshots,
    ios_upload_to_app_store,
    ios_upload_to_testflight,
)
from .store_listing_tools import store_listing_requirements


def configure_logging() -> None:
    """Initialize stderr logging for local debugging."""
    level_name = os.environ.get("FASTLANE_MCP_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


configure_logging()

mcp = FastMCP(
    name="fastlane-mcp",
    instructions=(
        "Thin MCP server over Gradle and fastlane for Android, iOS, and React Native release workflows. "
        "Prefer doctor before build or upload commands when project setup is unknown."
    ),
)

mcp.tool(healthcheck)
mcp.tool(doctor)
mcp.tool(list_supported_actions)
mcp.tool(store_listing_requirements)
mcp.tool(android_build_aab)
mcp.tool(android_build_apk)
mcp.tool(android_upload_to_internal)
mcp.tool(android_upload_to_beta)
mcp.tool(android_upload_to_production)
mcp.tool(android_promote_track)
mcp.tool(android_validate_play_auth)
mcp.tool(android_upload_metadata)
mcp.tool(android_upload_images)
mcp.tool(android_upload_changelogs)
mcp.tool(android_upload_everything)
mcp.tool(android_get_latest_build_info)
mcp.tool(android_show_effective_config)
mcp.tool(ios_upload_to_testflight)
mcp.tool(ios_distribute_testflight_build)
mcp.tool(ios_manage_testflight_testers)
mcp.tool(ios_upload_to_app_store)
mcp.tool(ios_create_app)
mcp.tool(ios_upload_metadata)
mcp.tool(ios_upload_screenshots)
mcp.tool(ios_upload_app_privacy_details)
mcp.tool(ios_precheck)
mcp.tool(ios_get_latest_build_info)
mcp.tool(ios_show_effective_config)
mcp.tool(ios_sync_code_signing)


def main() -> None:
    """Run the server using STDIO transport."""
    mcp.run()


if __name__ == "__main__":
    main()
