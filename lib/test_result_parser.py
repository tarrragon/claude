"""
測試結果 JSON 解析器

解析 pytest 和 jest 的結構化 JSON 輸出，提取 passed/failed/skipped 計數。
替代既有的 grep 文字行計數方式，提供穩定的紅綠燈判斷依據。

支援格式:
- pytest: pytest --json-report (pytest-json-report plugin)
- pytest: pytest -q --tb=no (fallback: 解析 summary line)
- jest: npx jest --json

使用方式:
    from lib.test_result_parser import parse_test_json, TestSummary, TestFramework

    summary = parse_test_json(json_string)
    print(summary.passed, summary.failed, summary.skipped)
    print(summary.is_green)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class TestFramework(Enum):
    PYTEST = "pytest"
    JEST = "jest"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class TestSummary:
    framework: TestFramework
    passed: int
    failed: int
    skipped: int
    total: int
    raw_data: Optional[dict] = None

    @property
    def is_green(self) -> bool:
        return self.failed == 0 and self.total > 0


def detect_framework(data: dict) -> TestFramework:
    if "numPassedTests" in data and "testResults" in data:
        return TestFramework.JEST
    if "summary" in data or "tests" in data:
        if any(k in data for k in ("created", "duration", "root", "environment")):
            return TestFramework.PYTEST
    if "collectors" in data or "exitcode" in data:
        return TestFramework.PYTEST
    return TestFramework.UNKNOWN


def _parse_pytest(data: dict) -> TestSummary:
    summary = data.get("summary", {})
    passed = summary.get("passed", 0)
    failed = summary.get("failed", 0)
    skipped = summary.get("skipped", 0)
    error = summary.get("error", 0)
    total = summary.get("total", passed + failed + skipped + error)

    return TestSummary(
        framework=TestFramework.PYTEST,
        passed=passed,
        failed=failed + error,
        skipped=skipped,
        total=total,
        raw_data=data,
    )


def _parse_jest(data: dict) -> TestSummary:
    passed = data.get("numPassedTests", 0)
    failed = data.get("numFailedTests", 0)
    total = data.get("numTotalTests", 0)
    pending = data.get("numPendingTests", 0)

    return TestSummary(
        framework=TestFramework.JEST,
        passed=passed,
        failed=failed,
        skipped=pending,
        total=total,
        raw_data=data,
    )


def parse_test_json(json_input: str | dict) -> TestSummary:
    """解析測試 JSON 輸出，回傳 TestSummary。

    Args:
        json_input: JSON 字串或已解析的 dict

    Raises:
        ValueError: JSON 格式無效或無法辨識框架
    """
    if isinstance(json_input, str):
        try:
            data = json.loads(json_input)
        except json.JSONDecodeError as e:
            raise ValueError(f"無效的 JSON: {e}") from e
    elif isinstance(json_input, dict):
        data = json_input
    else:
        raise ValueError(f"預期 str 或 dict，收到 {type(json_input).__name__}")

    framework = detect_framework(data)

    if framework == TestFramework.PYTEST:
        return _parse_pytest(data)
    elif framework == TestFramework.JEST:
        return _parse_jest(data)
    else:
        raise ValueError(
            "無法辨識測試框架。支援: pytest --json-report, jest --json"
        )
