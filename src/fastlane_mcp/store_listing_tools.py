"""Static store listing requirements sourced from official Apple and Google docs."""

from __future__ import annotations

from typing import Any, Literal

from .models import CommandResult

PlatformSelector = Literal["all", "google_play", "app_store"]

VERIFIED_ON = "2026-03-15"

GOOGLE_PLAY_REQUIREMENTS: dict[str, Any] = {
    "store": "google_play",
    "verified_on": VERIFIED_ON,
    "sources": [
        {
            "label": "Create and set up your app",
            "url": "https://support.google.com/googleplay/android-developer/answer/9859152?hl=en",
        },
        {
            "label": "Add preview assets to showcase your app",
            "url": "https://support.google.com/googleplay/android-developer/answer/9866151?hl=en",
        },
        {
            "label": "User Data policy",
            "url": "https://support.google.com/googleplay/android-developer/answer/9888076?hl=en",
        },
        {
            "label": "Metadata policy",
            "url": "https://support.google.com/googleplay/android-developer/answer/9898842?hl=en",
        },
    ],
    "required_metadata": [
        {"field": "app_name", "limit": "30 characters", "required": True},
        {"field": "short_description", "limit": "80 characters", "required": True},
        {"field": "full_description", "limit": "4000 characters", "required": True},
        {"field": "support_email", "required": True},
        {"field": "privacy_policy_url", "required": True},
    ],
    "recommended_metadata": [
        {"field": "support_phone", "required": False},
        {"field": "support_website", "required": False},
        {"field": "localized_store_listing", "required": False},
    ],
    "required_assets": [
        {
            "asset": "app_icon",
            "required": True,
            "format": ["PNG"],
            "details": {
                "color_depth": "32-bit",
                "alpha": True,
                "dimensions": ["512x512"],
                "max_file_size_kb": 1024,
            },
        },
        {
            "asset": "feature_graphic",
            "required": True,
            "format": ["JPEG", "PNG"],
            "details": {
                "color_depth": "24-bit",
                "alpha": False,
                "dimensions": ["1024x500"],
            },
        },
        {
            "asset": "screenshots",
            "required": True,
            "format": ["JPEG", "PNG"],
            "details": {
                "color_depth": "24-bit",
                "alpha": False,
                "minimum_total": 2,
                "maximum_per_device_type": 8,
                "min_dimension_px": 320,
                "max_dimension_px": 3840,
                "max_long_side_ratio_to_short_side": 2,
            },
        },
    ],
    "screenshot_requirements": {
        "global": {
            "minimum_total_screenshots": 2,
            "maximum_per_device_type": 8,
            "formats": ["JPEG", "PNG"],
            "color_depth": "24-bit",
            "alpha": False,
            "min_dimension_px": 320,
            "max_dimension_px": 3840,
            "long_side_limit": "long side cannot exceed 2x the short side",
        },
        "eligible_for_large_format_app_promotion": {
            "minimum_screenshots": 4,
            "minimum_resolution_px": 1080,
            "portrait": "9:16, minimum 1080x1920",
            "landscape": "16:9, minimum 1920x1080",
        },
        "large_screens": {
            "device_types": ["Chromebook", "7-inch tablet", "10-inch tablet"],
            "minimum_screenshots": 4,
            "dimension_range_px": "1080 to 7680",
            "portrait_aspect_ratio": "9:16",
            "landscape_aspect_ratio": "16:9",
        },
        "wear_os": {
            "minimum_screenshots": 1,
            "aspect_ratio": "1:1",
            "minimum_size_px": "384x384",
            "notes": [
                "Must show only the app interface",
                "No device frames, extra text, extra graphics, or masking",
            ],
        },
        "android_tv": {
            "minimum_screenshots": 1,
            "extra_required_asset": "android_tv_banner",
        },
        "android_automotive_os": {
            "minimum_portrait_screenshots": 2,
            "portrait_size_px": "800x1280",
            "minimum_landscape_screenshots": 2,
            "landscape_size_px": "1024x768",
            "notes": ["Required for apps outside parked app categories"],
        },
        "android_xr": {
            "minimum_screenshots": 4,
            "maximum_screenshots": 8,
            "format": ["PNG", "JPEG"],
            "max_file_size_mb": 8,
            "aspect_ratio": "8:5",
            "recommended_resolution_px": "3840x2400",
            "minimum_resolution_px": "1920x1200",
        },
    },
    "policy_notes": [
        "Screenshots must reflect the current in-app experience.",
        "Do not include misleading ranking, awards, pricing, or promotional claims in metadata or graphics.",
        "Privacy policy must be public, active, non-geofenced, and not a PDF.",
        "The entity named in the store listing should appear in the privacy policy or the app should be named there.",
        "Google recommends alt text for each graphic asset and screenshot, using 140 characters or less.",
    ],
}

APP_STORE_REQUIREMENTS: dict[str, Any] = {
    "store": "app_store",
    "verified_on": VERIFIED_ON,
    "sources": [
        {
            "label": "App information",
            "url": "https://developer.apple.com/help/app-store-connect/reference/app-information/app-information",
        },
        {
            "label": "Platform version information",
            "url": "https://developer.apple.com/help/app-store-connect/reference/app-information/platform-version-information",
        },
        {
            "label": "Screenshot specifications",
            "url": "https://developer.apple.com/help/app-store-connect/reference/app-information/screenshot-specifications",
        },
        {
            "label": "Upload app previews and screenshots",
            "url": "https://developer.apple.com/help/app-store-connect/manage-app-information/upload-app-previews-and-screenshots/",
        },
    ],
    "required_metadata": [
        {"field": "name", "limit": "2 to 30 characters", "required": True},
        {"field": "subtitle", "limit": "30 characters", "required": False},
        {"field": "privacy_policy_url", "required": True},
        {"field": "description", "limit": "4000 characters", "required": True},
        {"field": "keywords", "limit": "100 bytes", "required": True},
        {"field": "support_url", "required": True},
        {"field": "copyright", "required": True},
        {"field": "primary_category", "required": True},
        {"field": "age_rating", "required": True},
    ],
    "recommended_metadata": [
        {"field": "promotional_text", "limit": "170 characters", "required": False},
        {"field": "marketing_url", "required": False},
        {"field": "app_preview_video", "required": False, "maximum": 3},
    ],
    "required_assets": [
        {
            "asset": "screenshots",
            "required": True,
            "format": ["JPEG", "JPG", "PNG"],
            "details": {
                "minimum_per_device_size": 1,
                "maximum_per_device_size": 10,
            },
        }
    ],
    "screenshot_requirements": {
        "global": {
            "minimum_per_device_size": 1,
            "maximum_per_device_size": 10,
            "formats": ["JPEG", "JPG", "PNG"],
            "scaling_behavior": "Provide the highest required resolution when Apple allows scaling down to smaller sizes.",
        },
        "iphone": {
            "required_rule": "6.9-inch screenshots satisfy the iPhone requirement. If absent, 6.5-inch screenshots are required.",
            "device_sizes": [
                {
                    "display": "6.9-inch",
                    "portrait_px": ["1260x2736", "1290x2796", "1320x2868"],
                    "landscape_px": ["2736x1260", "2796x1290", "2868x1320"],
                    "required": False,
                    "note": "Preferred newest iPhone size.",
                },
                {
                    "display": "6.5-inch",
                    "portrait_px": ["1284x2778", "1242x2688"],
                    "landscape_px": ["2778x1284", "2688x1242"],
                    "required": True,
                    "note": "Required when 6.9-inch screenshots are not provided.",
                },
                {
                    "display": "6.3-inch",
                    "portrait_px": ["1179x2556", "1206x2622"],
                    "landscape_px": ["2556x1179", "2622x1206"],
                    "required": False,
                    "note": "Can scale from 6.5-inch.",
                },
                {
                    "display": "6.1-inch",
                    "portrait_px": ["1170x2532", "1125x2436", "1080x2340"],
                    "landscape_px": ["2532x1170", "2436x1125", "2340x1080"],
                    "required": False,
                    "note": "Can scale from 6.5-inch.",
                },
            ],
        },
        "ipad": {
            "required_rule": "13-inch screenshots are required if the app runs on iPad.",
            "device_sizes": [
                {
                    "display": "13-inch",
                    "portrait_px": ["2064x2752", "2048x2732"],
                    "landscape_px": ["2752x2064", "2732x2048"],
                    "required": True,
                },
                {
                    "display": "12.9-inch",
                    "portrait_px": ["2048x2732"],
                    "landscape_px": ["2732x2048"],
                    "required": False,
                    "note": "Apple can scale from 13-inch.",
                },
                {
                    "display": "11-inch",
                    "portrait_px": ["1488x2266", "1668x2420", "1668x2388", "1640x2360"],
                    "landscape_px": ["2266x1488", "2420x1668", "2388x1668", "2360x1640"],
                    "required": False,
                    "note": "Apple can scale from 13-inch.",
                },
            ],
        },
        "apple_watch": {
            "required": False,
            "required_rule": "Required for Apple Watch apps.",
            "portrait_px": ["422x514", "410x502", "416x496", "396x484", "368x448", "312x390"],
        },
        "apple_tv": {
            "required": False,
            "required_rule": "Required for Apple TV apps.",
            "landscape_px": ["1920x1080", "3840x2160"],
        },
        "apple_vision_pro": {
            "required": False,
            "required_rule": "Required for Apple Vision Pro apps.",
            "landscape_px": ["3840x2160"],
        },
        "mac": {
            "required": False,
            "required_rule": "Required for Mac apps.",
            "aspect_ratio": "16:10",
            "sizes_px": ["1280x800", "1440x900", "2560x1600", "2880x1800"],
        },
    },
    "policy_notes": [
        "Description, keywords, support URL, and screenshots are localized per platform version.",
        "Support URL must point to actual contact information.",
        "Keywords should not duplicate the app or company name and cannot include other app or company names.",
        "App previews are optional and limited to three per localization per device size.",
    ],
}


def _success(message: str, *, data: dict[str, Any]) -> dict[str, Any]:
    return CommandResult(success=True, tool="store_listing_requirements", message=message, data=data).model_dump()


def store_listing_requirements(platform: PlatformSelector = "all") -> dict[str, Any]:
    """Return current Google Play and App Store metadata and screenshot requirements."""
    data: dict[str, Any] = {
        "verified_on": VERIFIED_ON,
        "platforms": {},
    }
    if platform in {"all", "google_play"}:
        data["platforms"]["google_play"] = GOOGLE_PLAY_REQUIREMENTS
    if platform in {"all", "app_store"}:
        data["platforms"]["app_store"] = APP_STORE_REQUIREMENTS
    return _success("Store listing requirements loaded.", data=data)
