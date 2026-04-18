# fastlane-mcp

`fastlane-mcp` is a local MCP server that wraps Gradle and fastlane so coding agents can publish Android and iOS apps through Google Play and App Store Connect with a stable tool surface.

This repo is meant to be reused across many app repos. The app-specific state lives in a small `fastlane-mcp.yaml` file inside each target app.

## What It Is Good At Today

`P0`: publishing release binaries

- Android: build AAB or APK with Gradle, then upload to Google Play
- iOS: upload an existing IPA to TestFlight or App Store Connect
- Both: inspect latest store build numbers, validate auth, and expose the effective config an agent will use

`P1`: listing assets and metadata

- Android metadata, screenshots, images, changelogs
- iOS metadata, screenshots, privacy details, age rating config

## Is It Generic Enough Yet

Short answer: `yes` for the core publish flow, with one important caveat.

What is already generic:

- The server is app-agnostic. It only needs a `project_root` plus a small per-app config file.
- Argus and LunaCradle both use the same config contract:
  - Argus: [mobile/fastlane-mcp.yaml](/Users/abhi/Projects/argus/mobile/fastlane-mcp.yaml)
  - LunaCradle: [app/fastlane-mcp.yaml](/Users/abhi/Projects/lunacradle/app/fastlane-mcp.yaml)
- The Android and iOS publish tools are parameterized by package ID, bundle ID, artifact globs, metadata paths, and credentials.
- The tool surface is already stable enough for an agent to:
  - read latest build numbers
  - validate store auth
  - upload an Android AAB to Play
  - upload an IPA to TestFlight

Important current caveat:

- Android build and upload are both genericized inside MCP.
- iOS upload is genericized, but iOS archive and IPA export are not wrapped as MCP tools yet.
- In practice, the generic flow today is:
  - build Android AAB inside `fastlane-mcp`
  - produce iOS IPA with `xcodebuild`, Xcode, EAS, or another app-local workflow
  - upload the IPA through `fastlane-mcp`

That means this repo is ready as a generic publish server for Android and for iOS upload. It is not yet a fully generic end-to-end iOS build server.

## How The Server Works

The server is intentionally thin:

- [src/fastlane_mcp/server.py](src/fastlane_mcp/server.py): MCP entrypoint and tool registration
- [src/fastlane_mcp/config.py](src/fastlane_mcp/config.py): config discovery and environment expansion
- [src/fastlane_mcp/android_tools.py](src/fastlane_mcp/android_tools.py): Android build and Play publishing
- [src/fastlane_mcp/ios_tools.py](src/fastlane_mcp/ios_tools.py): TestFlight and App Store publishing
- [src/fastlane_mcp/fastlane_runner.py](src/fastlane_mcp/fastlane_runner.py): subprocess execution and Bundler detection
- [examples/fastlane-mcp.yaml](examples/fastlane-mcp.yaml): app-level config example

The design is:

- use Gradle directly for Android builds
- use fastlane directly for store upload and store-management operations
- prefer `bundle exec fastlane ...` when the target app repo has a `Gemfile`
- keep app repos small by avoiding custom fastlane lane code unless the app already needs it

## Tool Surface

The current server registers these publish-relevant tools:

- Android:
  - `doctor`
  - `android_build_aab`
  - `android_build_apk`
  - `android_validate_play_auth`
  - `android_get_latest_build_info`
  - `android_upload_to_internal`
  - `android_upload_to_beta`
  - `android_upload_to_production`
  - `android_promote_track`
  - `android_upload_metadata`
  - `android_upload_images`
  - `android_upload_changelogs`
  - `android_upload_everything`
  - `android_show_effective_config`
- iOS:
  - `ios_get_latest_build_info`
  - `ios_upload_to_testflight`
  - `ios_distribute_testflight_build`
  - `ios_upload_to_app_store`
  - `ios_upload_metadata`
  - `ios_upload_screenshots`
  - `ios_upload_app_privacy_details`
  - `ios_precheck`
  - `ios_sync_code_signing`
  - `ios_create_app`
  - `ios_show_effective_config`

## What Other App Repos Need

Every target app needs two classes of setup:

1. App-repo configuration
2. Store-console credentials and permissions

### App-repo requirements

Minimum:

- the app already builds locally
- the app has a `fastlane-mcp.yaml` file
- Android apps have a working Gradle wrapper or `gradle` on PATH
- iOS apps can already produce an `.ipa` through Xcode, `xcodebuild`, or another existing flow
- the app repo has fastlane installed globally or via Bundler

Recommended:

- keep fastlane in the app repo `Gemfile`
- keep Android metadata under `fastlane/metadata/android`
- keep iOS metadata under `fastlane/metadata/ios`
- keep iOS screenshots under `fastlane/screenshots`

### Google Play requirements

Before `fastlane-mcp` can upload an AAB:

1. Create the app in Play Console manually.
2. Create a Google Cloud service account.
3. Enable the Android Publisher API in the Google Cloud project.
4. Download the service-account JSON key.
5. In Play Console:
   - open `Users and permissions`
   - invite that service account
   - grant the app-level permissions needed for releases
6. Put the JSON key somewhere on disk and point `play.json_key_file` to it, or provide the JSON content via environment variable.

Important:

- `fastlane-mcp` does not create the Play app listing for you.
- version codes must always increase.
- draft/internal-track behavior still depends on Play Console state; for first uploads, `release_status:draft` is often the safest choice.

### Apple / App Store Connect requirements

Before `fastlane-mcp` can upload an IPA:

1. Create the app in App Store Connect manually, or use `ios_create_app`.
2. Create an App Store Connect API key.
3. Store the API key as either:
   - a JSON descriptor file, then point `apple.api_key_path` at it
   - raw JSON content via `FASTLANE_MCP_APPLE_API_KEY_CONTENT`
4. Make sure the app can already archive and export a valid `.ipa`.
5. Make sure the build number always increases.

Important:

- `ios_upload_to_testflight` uploads an IPA. It does not produce that IPA.
- App Store Connect rejects re-uploads of a build number that already exists.
- If a client times out while Apple is uploading, App Store Connect may still accept the build. Always confirm with `ios_get_latest_build_info`.

## Per-App Config

Each app should carry a small file named `fastlane-mcp.yaml`.

Supported discovery paths:

- `fastlane-mcp.yaml`
- `fastlane-mcp.yml`
- `.fastlane-mcp/app.yaml`
- `.fastlane-mcp/app.yml`

### Generic example

See [examples/fastlane-mcp.yaml](examples/fastlane-mcp.yaml).

```yaml
app_name: Example App
platform: react-native
project_root: /absolute/path/to/app
android_dir: android
ios_dir: ios
package_name: com.example.app
bundle_identifier: com.example.app
default_track: internal

artifacts:
  aab_glob: android/app/build/outputs/bundle/**/*.aab
  apk_glob: android/app/build/outputs/apk/**/*.apk
  ipa_glob: ios/build/**/*.ipa

play:
  json_key_file: ${GOOGLE_PLAY_JSON_KEY_FILE}
  metadata_dir: fastlane/metadata/android
  images_dir: fastlane/metadata/android
  changelogs_dir: fastlane/metadata/android
  default_language: en-US

apple:
  api_key_path: ${APP_STORE_CONNECT_API_KEY_PATH}
  username: ${FASTLANE_USER}
  metadata_dir: fastlane/metadata/ios
  screenshots_dir: fastlane/screenshots
  privacy_details_path: fastlane/app_privacy_details.json
  age_rating_config_path: fastlane/age_rating_config.json
  default_platform: ios

gradle:
  build_aab_task: bundleRelease
  build_apk_task: assembleRelease

defaults:
  changes_not_sent_for_review: true
  skip_upload_metadata: false
  skip_upload_images: false
  skip_upload_screenshots: false
  skip_upload_changelogs: false
```

### Real app examples

Argus:

- uses an absolute `project_root`
- stores the exported IPA under `/tmp/argus-ios/export/**/*.ipa`
- points `apple.api_key_path` at a checked-in local JSON descriptor file

LunaCradle:

- uses the same structure
- keeps the IPA glob under `ios/build/**/*.ipa`
- resolves the App Store Connect key path through an environment variable

Those two examples are a useful proof that the config model is already reusable across different apps without changing the server code.

## Environment Variables

The server supports both config-file values and env-based overrides.

Common ones:

- `FASTLANE_MCP_PROJECT_ROOT`
- `GOOGLE_PLAY_JSON_KEY_FILE`
- `GOOGLE_PLAY_JSON_KEY_CONTENT`
- `FASTLANE_MCP_APPLE_API_KEY_PATH`
- `FASTLANE_MCP_APPLE_API_KEY_CONTENT`
- `FASTLANE_MCP_APPLE_USERNAME`
- `FASTLANE_MCP_LOG_LEVEL`
- `FASTLANE_MCP_TIMEOUT_SECONDS`

Merge precedence is:

1. explicit tool arguments
2. environment variables
3. app config file
4. built-in defaults

## Installation

### 1. Clone the MCP server repo

```bash
git clone /path/to/fastlane-mcp
cd fastlane-mcp
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Make sure fastlane is available

Preferred:

- install fastlane in each target app repo with Bundler

Also supported:

- global `fastlane` install on PATH

### 3. Make sure the app repo is ready

For Android:

- Gradle wrapper works
- package name is final
- signing/build config is already valid

For iOS:

- app archives locally
- IPA export flow already works
- bundle identifier matches App Store Connect app

## Running The MCP Server

```bash
source /absolute/path/to/fastlane-mcp/.venv/bin/activate
fastlane-mcp
```

or:

```bash
python -m fastlane_mcp
```

## MCP Client Setup

Any MCP client that can launch a local stdio server can use this repo.

Generic config shape:

```json
{
  "mcpServers": {
    "fastlane-mcp": {
      "command": "/absolute/path/to/fastlane-mcp/.venv/bin/fastlane-mcp",
      "args": [],
      "env": {
        "FASTLANE_MCP_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

If the client prefers `python -m`:

```json
{
  "mcpServers": {
    "fastlane-mcp": {
      "command": "/absolute/path/to/fastlane-mcp/.venv/bin/python",
      "args": ["-m", "fastlane_mcp"]
    }
  }
}
```

Use the same idea in Codex, Claude Code, Cursor, or any other MCP-capable client: register this repo as a local stdio MCP server.

## Recommended Publish Flow

### Android release flow

This is the most complete generic flow today.

1. Validate setup:

```text
Run `doctor` for /path/to/app
Run `android_validate_play_auth` for /path/to/app
Run `android_get_latest_build_info` for the internal track
```

2. Build:

```text
Run `android_build_aab` for /path/to/app
```

3. Upload:

```text
Run `android_upload_to_internal` using the latest AAB
```

4. Verify:

```text
Run `android_get_latest_build_info` for the internal track
```

### iOS release flow

This is the correct generic flow today.

1. Confirm latest build number:

```text
Run `ios_get_latest_build_info` for /path/to/app
```

2. Bump build number in the app repo.

3. Produce a fresh `.ipa` using Xcode, `xcodebuild`, EAS, or the app’s existing build pipeline.

4. Upload:

```text
Run `ios_upload_to_testflight` using the fresh IPA
```

5. Verify:

```text
Run `ios_get_latest_build_info`
```

## Example Agent Prompts

These are the kinds of prompts a developer can use in Codex, Claude Code, or Cursor once the server is connected.

### Android

```text
Use fastlane-mcp to run doctor for /Users/me/Projects/MyApp.
```

```text
Use fastlane-mcp to show the effective config for /Users/me/Projects/MyApp.
```

```text
Use fastlane-mcp to build the Android AAB for /Users/me/Projects/MyApp.
```

```text
Use fastlane-mcp to upload the latest Android AAB for /Users/me/Projects/MyApp to the internal Play track as a draft release.
```

### iOS

```text
Use fastlane-mcp to tell me the latest TestFlight build number for /Users/me/Projects/MyApp.
```

```text
Use fastlane-mcp to upload /tmp/MyApp.ipa to TestFlight for /Users/me/Projects/MyApp.
```

### Combined release prompts

```text
Use fastlane-mcp to validate Android Play auth and upload the latest AAB to the internal track for /Users/me/Projects/MyApp.
```

```text
Use fastlane-mcp to upload the IPA at /tmp/MyApp.ipa to TestFlight and then verify the latest build number.
```

## Current Caveats

These are important if you want to use this as a shared generic repo:

- iOS upload is generic, but iOS archive/export is still outside the MCP tool surface.
- App Store Connect build numbers must increase every upload.
- Google Play version codes must increase every upload.
- First-store setup is still partly manual:
  - create the app listing
  - create service accounts / API keys
  - grant permissions
- Some clients may time out before Apple finishes uploading. When that happens, verify actual success with `ios_get_latest_build_info` instead of assuming failure.

## When To Use This Repo

Use `fastlane-mcp` when:

- you want one local MCP server to publish many app repos
- you want agents to ship Android and iOS binaries through a consistent interface
- you want app repos to stay small and config-driven

Do not oversell it as:

- a full replacement for native iOS build tooling
- a zero-setup replacement for Play Console or App Store Connect onboarding

## Development

Run tests:

```bash
pytest
```

Useful files while extending the server:

- [src/fastlane_mcp/android_tools.py](src/fastlane_mcp/android_tools.py)
- [src/fastlane_mcp/ios_tools.py](src/fastlane_mcp/ios_tools.py)
- [tests/test_android_tools.py](tests/test_android_tools.py)
- [tests/test_ios_tools.py](tests/test_ios_tools.py)
