from fastlane_mcp.validators import build_gradle_task, parse_bracketed_list, validate_rollout, validate_track_name


def test_build_gradle_task_with_flavor_and_type() -> None:
    assert build_gradle_task("aab", "production", "release") == "bundleProductionRelease"
    assert build_gradle_task("apk", "qa_internal", "debug") == "assembleQaInternalDebug"


def test_validate_track_name_accepts_closed_testing_names() -> None:
    assert validate_track_name("internal") == "internal"
    assert validate_track_name("qa-team") == "qa-team"


def test_validate_rollout_rejects_invalid_values() -> None:
    try:
        validate_rollout(1.5)
    except Exception as exc:  # noqa: BLE001
        assert "rollout" in str(exc)
    else:
        raise AssertionError("validate_rollout should reject values above 1")


def test_parse_bracketed_list() -> None:
    assert parse_bracketed_list("Result: [123, 456]") == [123, 456]
    assert parse_bracketed_list('Result: ["1.2.3", "1.2.4"]') == ["1.2.3", "1.2.4"]
