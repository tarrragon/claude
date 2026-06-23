"""test_result_parser 單元測試"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.test_result_parser import (
    TestFramework,
    TestSummary,
    detect_framework,
    parse_test_json,
)


# ── pytest JSON fixtures ──


PYTEST_JSON_ALL_PASS = {
    "created": 1719100000.0,
    "duration": 2.5,
    "exitcode": 0,
    "root": "/project",
    "environment": {"Python": "3.12"},
    "summary": {"passed": 10, "total": 10},
    "tests": [],
}

PYTEST_JSON_MIXED = {
    "created": 1719100000.0,
    "duration": 5.0,
    "exitcode": 1,
    "root": "/project",
    "environment": {"Python": "3.12"},
    "summary": {"passed": 7, "failed": 2, "skipped": 1, "total": 10},
    "tests": [],
}

PYTEST_JSON_WITH_ERRORS = {
    "created": 1719100000.0,
    "duration": 1.0,
    "exitcode": 2,
    "root": "/project",
    "environment": {"Python": "3.12"},
    "summary": {"passed": 3, "failed": 1, "error": 2, "skipped": 0, "total": 6},
    "tests": [],
}


# ── jest JSON fixtures ──


JEST_JSON_ALL_PASS = {
    "numFailedTestSuites": 0,
    "numFailedTests": 0,
    "numPassedTestSuites": 5,
    "numPassedTests": 42,
    "numPendingTestSuites": 0,
    "numPendingTests": 0,
    "numTotalTestSuites": 5,
    "numTotalTests": 42,
    "success": True,
    "testResults": [],
}

JEST_JSON_MIXED = {
    "numFailedTestSuites": 1,
    "numFailedTests": 3,
    "numPassedTestSuites": 4,
    "numPassedTests": 39,
    "numPendingTestSuites": 0,
    "numPendingTests": 2,
    "numTotalTestSuites": 5,
    "numTotalTests": 44,
    "success": False,
    "testResults": [],
}


# ── detect_framework ──


class TestDetectFramework:
    def test_detects_pytest(self):
        assert detect_framework(PYTEST_JSON_ALL_PASS) == TestFramework.PYTEST

    def test_detects_jest(self):
        assert detect_framework(JEST_JSON_ALL_PASS) == TestFramework.JEST

    def test_unknown_for_empty_dict(self):
        assert detect_framework({}) == TestFramework.UNKNOWN

    def test_unknown_for_unrecognized(self):
        assert detect_framework({"foo": "bar"}) == TestFramework.UNKNOWN


# ── parse_test_json: pytest ──


class TestParsePytest:
    def test_all_pass(self):
        result = parse_test_json(PYTEST_JSON_ALL_PASS)
        assert result.framework == TestFramework.PYTEST
        assert result.passed == 10
        assert result.failed == 0
        assert result.skipped == 0
        assert result.total == 10
        assert result.is_green is True

    def test_mixed(self):
        result = parse_test_json(PYTEST_JSON_MIXED)
        assert result.passed == 7
        assert result.failed == 2
        assert result.skipped == 1
        assert result.total == 10
        assert result.is_green is False

    def test_errors_counted_as_failed(self):
        result = parse_test_json(PYTEST_JSON_WITH_ERRORS)
        assert result.failed == 3  # 1 failed + 2 error
        assert result.passed == 3
        assert result.total == 6

    def test_accepts_json_string(self):
        result = parse_test_json(json.dumps(PYTEST_JSON_ALL_PASS))
        assert result.passed == 10
        assert result.is_green is True


# ── parse_test_json: jest ──


class TestParseJest:
    def test_all_pass(self):
        result = parse_test_json(JEST_JSON_ALL_PASS)
        assert result.framework == TestFramework.JEST
        assert result.passed == 42
        assert result.failed == 0
        assert result.skipped == 0
        assert result.total == 42
        assert result.is_green is True

    def test_mixed(self):
        result = parse_test_json(JEST_JSON_MIXED)
        assert result.passed == 39
        assert result.failed == 3
        assert result.skipped == 2
        assert result.total == 44
        assert result.is_green is False


# ── edge cases ──


class TestEdgeCases:
    def test_invalid_json_string(self):
        with pytest.raises(ValueError, match="無效的 JSON"):
            parse_test_json("{broken")

    def test_unrecognized_framework(self):
        with pytest.raises(ValueError, match="無法辨識測試框架"):
            parse_test_json({"random": "data"})

    def test_wrong_type(self):
        with pytest.raises(ValueError, match="預期 str 或 dict"):
            parse_test_json(42)

    def test_empty_pytest_summary(self):
        data = {
            "created": 1.0,
            "duration": 0.1,
            "exitcode": 0,
            "root": "/x",
            "environment": {},
            "summary": {},
        }
        result = parse_test_json(data)
        assert result.passed == 0
        assert result.failed == 0
        assert result.total == 0
        assert result.is_green is False  # total == 0

    def test_is_green_requires_positive_total(self):
        summary = TestSummary(
            framework=TestFramework.PYTEST,
            passed=0,
            failed=0,
            skipped=0,
            total=0,
        )
        assert summary.is_green is False
