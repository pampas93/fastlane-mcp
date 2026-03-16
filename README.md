# fastlane-mcp

`fastlane-mcp` is a local, open-source MCP server that exposes a clean tool interface over Android and iOS release workflows powered by Gradle and fastlane.

It is designed for this exact setup:

- This repo is the MCP server repo, not an individual app repo.
- Target apps are existing Android or React Native apps.
- Each app should provide a small config file or environment variables instead of duplicating a large `fastlane/` setup.
- v1 is local-first and optimized for Google Play and App Store Connect release flows.

## Why put MCP on top of fastlane?

fastlane already solves most of the Android / Google Play release problem well. What it does not give you by default is a stable, LLM-friendly tool surface that can be reused across many app repos.

`fastlane-mcp` adds that layer:

- Thin MCP wrapper over real fastlane and Gradle commands
- Strong input validation and clearer failure messages
- Structured responses for agents and humans
- A reusable app config contract for many future React Native apps
- Local debugging without hiding the underlying commands

The design goal is not to replace fastlane. It is to make fastlane easier to consume from MCP clients and easier to standardize across multiple Android app repos.

## Scope

### Included in v1

- Local MCP server over stdio
- Android AAB and APK builds via Gradle
- Google Play uploads via fastlane `upload_to_play_store`
- Metadata, image, and changelog uploads
- Track promotion
- Play auth validation
- iOS TestFlight uploads and distribution
- App Store uploads for binaries, metadata, screenshots, and privacy details
- App creation, precheck, build-number introspection, and signing sync
- Effective config inspection
- Basic doctor / healthcheck workflows

### Non-goals in v1

- Cloud hosting
- Checking Play credentials into source control
- Replacing the need for an app that already exists in Play Console

## Architecture

The codebase is intentionally small and thin:

- `src/fastlane_mcp/server.py`
  FastMCP entrypoint and tool registration
- `src/fastlane_mcp/config.py`
  Config discovery, YAML loading, env expansion, merge rules
- `src/fastlane_mcp/models.py`
  Typed Pydantic models for config and responses
- `src/fastlane_mcp/fastlane_runner.py`
  Safe subprocess execution, Bundler detection, output normalization
- `src/fastlane_mcp/android_tools.py`
  Tool implementations for Android build, upload, metadata, diagnostics, and introspection flows
- `src/fastlane_mcp/ios_tools.py`
  Tool implementations for TestFlight, App Store Connect, and signing flows
- `src/fastlane_mcp/validators.py`
  Input validation and artifact lookup helpers
- `src/fastlane_mcp/exceptions.py`
  Purpose-specific error classes
- `examples/fastlane-mcp.yaml`
  Example per-app config
- `tests/`
  Basic validation and command-generation tests

## How it works

### Build operations

Build tools call Gradle directly. This keeps the app-side setup minimal and avoids requiring a large app-local fastlane lane setup for routine builds.

### Google Play operations

Upload and Play inspection tools call fastlane through the local CLI:

- Prefer `bundle exec fastlane ...` when a `Gemfile` is present in the app root or Android directory
- Otherwise fall back to `fastlane ...`

This keeps the server compatible with apps that already use Bundler while still working for apps that only have fastlane installed globally.

### Release notes behavior

fastlane's Android upload flow is metadata-oriented. It does not accept an arbitrary inline `release_notes` flag in the same way some custom wrappers do. When a tool call includes `release_notes`, `fastlane-mcp` creates a temporary supply-compatible changelog overlay and passes that to fastlane instead of inventing unsupported behavior.

## Prerequisites

### Required

- Python 3.11+
- Ruby
- fastlane
- An Android app project with a working Gradle build
- A Play Console app that already exists
- A Google service account with Play Console API access and app permissions

### Usually recommended

- Bundler and a `Gemfile` in the target app repo
- Android SDK / Java set up correctly for the target app
- A supply-compatible metadata tree such as `fastlane/metadata/android`

## Install

### Server repo setup

1. Clone this repo.
2. Create a virtual environment.
3. Install the package.

Example with `pip`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

If you prefer `uv`, that also works fine:

```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

### fastlane setup

Install fastlane in the way your team prefers. Two common options:

- Global fastlane install
- Bundler-managed fastlane inside each app repo

If an app repo has a `Gemfile`, `fastlane-mcp` will prefer `bundle exec fastlane`.

## Local usage

Run the server locally over stdio:

```bash
fastlane-mcp
```

or:

```bash
python -m fastlane_mcp
```

## MCP client config examples

Different clients use slightly different config formats. The common idea is the same: register a local stdio server.

Generic example:

```json
{
  "mcpServers": {
    "fastlane-mcp": {
      "command": "/absolute/path/to/.venv/bin/fastlane-mcp",
      "args": [],
      "env": {
        "FASTLANE_MCP_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

Windows example:

```json
{
  "mcpServers": {
    "fastlane-mcp": {
      "command": "C:\\Projects\\fastlane-mcp\\.venv\\Scripts\\fastlane-mcp.exe",
      "args": [],
      "env": {
        "FASTLANE_MCP_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

If your client expects `python -m ...` instead of the console script:

```json
{
  "mcpServers": {
    "fastlane-mcp": {
      "command": "/absolute/path/to/.venv/bin/python",
      "args": ["-m", "fastlane_mcp"]
    }
  }
}
```

## Configuration model

`fastlane-mcp` supports two styles:

- Global environment variables
- Per-app config file

Supported config file discovery:

- `fastlane-mcp.yaml`
- `fastlane-mcp.yml`
- `.fastlane-mcp/app.yaml`
- `.fastlane-mcp/app.yml`

Merge precedence is:

1. Explicit tool arguments
2. Environment variables
3. App config file
4. Built-in defaults

### Example app config

See `examples/fastlane-mcp.yaml`.

```yaml
app_name: Example RN App
platform: android
project_root: /absolute/path/to/app
android_dir: android
package_name: com.example.app
default_track: internal

artifacts:
  aab_glob: android/app/build/outputs/bundle/**/*.aab
  apk_glob: android/app/build/outputs/apk/**/*.apk

play:
  json_key_file: ${GOOGLE_PLAY_JSON_KEY_FILE}
  metadata_dir: fastlane/metadata/android
  images_dir: fastlane/metadata/android
  changelogs_dir: fastlane/metadata/android
  default_language: en-US

apple:
  api_key_path: ${APP_STORE_CONNECT_API_KEY_PATH}
  metadata_dir: fastlane/metadata/ios
  screenshots_dir: fastlane/screenshots
  privacy_details_path: fastlane/app_privacy_details.json
  age_rating_config_path: fastlane/age_rating_config.json

gradle:
  build_aab_task: bundleRelease
  build_apk_task: assembleRelease

defaults:
  changes_not_sent_for_review: true
  skip_upload_metadata: false
  skip_upload_images: false
  skip_upload_changelogs: false
```

### Environment variables

See `.env.example`.

Important variables:

- `FASTLANE_MCP_PROJECT_ROOT`
- `FASTLANE_MCP_ANDROID_DIR`
- `FASTLANE_MCP_PACKAGE_NAME`
- `FASTLANE_MCP_DEFAULT_TRACK`
- `FASTLANE_MCP_AAB_GLOB`
- `FASTLANE_MCP_APK_GLOB`
- `FASTLANE_MCP_PLAY_JSON_KEY_FILE`
- `FASTLANE_MCP_PLAY_JSON_KEY_CONTENT`
- `GOOGLE_PLAY_JSON_KEY_FILE`
- `GOOGLE_PLAY_JSON_KEY_CONTENT`
- `FASTLANE_MCP_PLAY_METADATA_DIR`
- `FASTLANE_MCP_PLAY_IMAGES_DIR`
- `FASTLANE_MCP_PLAY_CHANGELOGS_DIR`
- `FASTLANE_MCP_PLAY_DEFAULT_LANGUAGE`
- `FASTLANE_MCP_APPLE_AGE_RATING_CONFIG_PATH`
- `FASTLANE_MCP_GRADLE_BUILD_AAB_TASK`
- `FASTLANE_MCP_GRADLE_BUILD_APK_TASK`
- `FASTLANE_MCP_DEFAULT_CHANGES_NOT_SENT_FOR_REVIEW`
- `FASTLANE_MCP_DEFAULT_SKIP_UPLOAD_METADATA`
- `FASTLANE_MCP_DEFAULT_SKIP_UPLOAD_IMAGES`
- `FASTLANE_MCP_DEFAULT_SKIP_UPLOAD_CHANGELOGS`
- `FASTLANE_MCP_TIMEOUT_SECONDS`
- `FASTLANE_MCP_LOG_LEVEL`

## Google Play auth setup

Supported patterns:

- Service account JSON file path
- Service account JSON content via env var

If JSON content is provided through env vars, the server writes it to a temporary file at runtime so it can call fastlane safely without exposing raw JSON in command arguments.

### iOS metadata and age ratings

If your app repo includes `fastlane/age_rating_config.json`, add this to `fastlane-mcp.yaml`:

```yaml
apple:
  age_rating_config_path: fastlane/age_rating_config.json
```

`ios_upload_metadata` and `ios_upload_to_app_store` will pass that file to fastlane as `app_rating_config_path`, which uploads the App Store age rating through the normal metadata flow.

### Required Play Console setup

The credentials are not enough by themselves. The service account must also:

- Be linked in Play Console API access
- Be granted access to the target app
- Have the permissions required for the action you want to run

Use `android_validate_play_auth` to catch the common failure modes early.

## Supported tools

### Discovery / diagnostics

- `healthcheck()`
- `doctor(project_root, app_config_path?)`
- `list_supported_actions()`

### Build

- `android_build_aab(project_root, app_config_path?, flavor?, build_type?, gradle_task?, clean?)`
- `android_build_apk(project_root, app_config_path?, flavor?, build_type?, gradle_task?, clean?)`

### Google Play upload / release

- `android_upload_to_internal(project_root, app_config_path?, aab_path?, apk_path?, release_notes?, changes_not_sent_for_review?, rollout?)`
- `android_upload_to_beta(project_root, app_config_path?, aab_path?, apk_path?, release_notes?, changes_not_sent_for_review?, rollout?)`
- `android_upload_to_production(project_root, app_config_path?, aab_path?, apk_path?, release_notes?, changes_not_sent_for_review?, rollout?)`
- `android_promote_track(project_root, app_config_path?, from_track, to_track, rollout?)`
- `android_validate_play_auth(project_root?, app_config_path?)`

### Metadata / store listing

- `android_upload_metadata(project_root, app_config_path?, metadata_dir?)`
- `android_upload_images(project_root, app_config_path?, images_dir?)`
- `android_upload_changelogs(project_root, app_config_path?, changelogs_dir?)`
- `android_upload_everything(project_root, app_config_path?, aab_path?, release_notes?, track?)`

### Introspection

- `android_get_latest_build_info(project_root, app_config_path?, track?)`
- `android_show_effective_config(project_root?, app_config_path?)`

## Example tool calls

### Validate a target app

```json
{
  "tool": "doctor",
  "arguments": {
    "project_root": "/absolute/path/to/app"
  }
}
```

### Build an AAB

```json
{
  "tool": "android_build_aab",
  "arguments": {
    "project_root": "/absolute/path/to/app",
    "clean": true
  }
}
```

### Upload the latest AAB to internal testing

```json
{
  "tool": "android_upload_to_internal",
  "arguments": {
    "project_root": "/absolute/path/to/app",
    "release_notes": "Internal QA build for regression pass."
  }
}
```

### Promote internal to production

```json
{
  "tool": "android_promote_track",
  "arguments": {
    "project_root": "/absolute/path/to/app",
    "from_track": "internal",
    "to_track": "production",
    "rollout": 0.1
  }
}
```

### Show resolved config

```json
{
  "tool": "android_show_effective_config",
  "arguments": {
    "project_root": "/absolute/path/to/app"
  }
}
```

## Recommended app setup

This server tries hard not to require a large app-side fastlane setup, but a small amount of discipline in each app repo still helps.

Recommended for each React Native app:

- Keep a stable Gradle wrapper in `android/`
- Keep artifact locations predictable
- Keep a small app config file such as `fastlane-mcp.yaml`
- Keep Play metadata under `fastlane/metadata/android`
- Optionally keep a `Gemfile` for reproducible fastlane versions

### Minimal app-side setup

You do not need a large `fastlane/Fastfile` to use v1.

For many apps, this is enough:

- Gradle wrapper
- Service account credentials provided at runtime
- A supply-compatible metadata directory if you upload listing content
- Optional `Gemfile`

### When a small app-local fastlane setup is still worth it

You may still want a tiny app-side fastlane setup if you need:

- App-specific Ruby plugin dependencies
- Existing team workflows already built around Bundler
- Custom lanes outside the scope of this MCP server

## Response shape

Tool responses are structured for LLM consumption and manual debugging. Most command-based tools return:

- `success`
- `message`
- `command`
- `command_display`
- `cwd`
- `return_code`
- `stdout_excerpt`
- `stderr_excerpt`
- `artifact_paths`
- `warnings`
- `next_steps`
- `data`

Sensitive values are redacted from command display output.

## Troubleshooting

### `fastlane` not found

- Install fastlane globally or via Bundler
- If using Bundler, make sure `bundle` is installed and a `Gemfile` exists in the app repo

### Play auth validates but uploads still fail

- Confirm the service account is linked in Play Console API access
- Confirm the app exists in Play Console already
- Confirm the service account has permissions on that specific app

### Metadata upload fails

- Check that your metadata tree matches fastlane / supply expectations
- Prefer using a single root such as `fastlane/metadata/android`
- Point `metadata_dir`, `images_dir`, and `changelogs_dir` to that root unless you have a strong reason not to

### Artifact not found

- Check your configured `aab_glob` / `apk_glob`
- Build first
- Or pass an explicit `aab_path` / `apk_path`

### Gradle wrapper not found

- Keep `android/gradlew` or `android/gradlew.bat` in the target repo
- The server will fall back to `gradle` if available, but the wrapper is preferred

## Security notes

- Do not commit Play service account JSON files into source control
- Prefer environment variables or secure local secret management
- The server avoids printing raw secret content
- The server redacts JSON key paths in command display output
- Commands are executed with `subprocess.run(..., shell=False)`

## Development

Run tests:

```bash
PYTHONPATH=src pytest
```

On Windows PowerShell:

```powershell
$env:PYTHONPATH='src'
python -m pytest
```

## Roadmap

- Better parsing of fastlane output into richer structured data
- Optional generated ephemeral Fastfiles for more advanced fastlane scenarios
- Better support for custom closed testing tracks and richer rollout flows
- More end-to-end tests against fixture projects
- Optional iOS support in a later major expansion

## Contributing

Issues and pull requests are welcome.

Good contributions for early versions:

- Better test coverage
- More robust output parsing
- Additional validation around Play metadata layouts
- Documentation improvements for real-world React Native repos

When contributing:

- Keep the MCP layer thin
- Prefer official fastlane capabilities over custom behavior
- Keep secrets out of logs and source control
- Preserve structured, LLM-friendly responses

## License

MIT. See `LICENSE`.
