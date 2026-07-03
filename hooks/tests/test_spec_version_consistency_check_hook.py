"""
Spec 版本標示一致性檢查 Hook 測試

涵蓋範圍：
1. frontmatter version 擷取
2. 變更歷史表最大版號擷取（含跨區段截斷）
3. 單檔漂移判定（一致 / 不一致 / 缺資料）
4. 掃描彙整與警告訊息格式化
"""

import importlib.util
import sys
from pathlib import Path

import pytest


_HOOKS_DIR = Path(__file__).parent.parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

_spec = importlib.util.spec_from_file_location(
    "spec_version_consistency_check_hook",
    _HOOKS_DIR / "spec-version-consistency-check-hook.py",
)
_hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hook)


CONSISTENT_SPEC = """---
id: SPEC-999
title: "測試規格"
version: "1.2"
---

# 測試規格

## 概述

內容。

## 變更歷史

| 版本 | 日期 | 變更內容 |
|------|------|---------|
| 1.0 | 2026-06-21 | 初始版本 |
| 1.2 | 2026-07-01 | 補欄位 |
"""

DRIFTED_SPEC = """---
id: SPEC-998
title: "漂移規格"
version: "1.0"
---

# 漂移規格

## 變更歷史

| 版本 | 日期 | 變更內容 |
|------|------|---------|
| 1.0 | 2026-06-21 | 初始版本 |
| 1.3 | 2026-07-03 | 補 FR-05 |
"""

NO_HISTORY_SPEC = """---
id: SPEC-997
title: "無變更歷史"
version: "1.0"
---

# 無變更歷史

## 概述

內容，無變更歷史表。
"""

NO_FRONTMATTER_SPEC = """# 無 frontmatter

## 變更歷史

| 版本 | 日期 | 變更內容 |
|------|------|---------|
| 1.0 | 2026-06-21 | 初始版本 |
"""

TRAILING_TABLE_SPEC = """---
id: SPEC-996
title: "變更歷史後仍有其他表格"
version: "1.1"
---

## 變更歷史

| 版本 | 日期 | 變更內容 |
|------|------|---------|
| 1.1 | 2026-07-03 | 版本更新 |

## 附錄

| 9.9 | 不應被誤判為版號 |
|-----|-----------------|
| 9.9 | 附錄表格資料 |
"""


# ---------------------------------------------------------------------------
# extract_frontmatter_version
# ---------------------------------------------------------------------------


def test_extract_frontmatter_version_found():
    assert _hook.extract_frontmatter_version(CONSISTENT_SPEC) == "1.2"


def test_extract_frontmatter_version_missing_frontmatter():
    assert _hook.extract_frontmatter_version(NO_FRONTMATTER_SPEC) is None


# ---------------------------------------------------------------------------
# extract_history_max_version
# ---------------------------------------------------------------------------


def test_extract_history_max_version_picks_largest():
    assert _hook.extract_history_max_version(CONSISTENT_SPEC) == "1.2"


def test_extract_history_max_version_missing_section():
    assert _hook.extract_history_max_version(NO_HISTORY_SPEC) is None


def test_extract_history_max_version_stops_at_next_heading():
    # 附錄表格的 9.9 不應污染變更歷史區段的最大版號判定
    assert _hook.extract_history_max_version(TRAILING_TABLE_SPEC) == "1.1"


# ---------------------------------------------------------------------------
# check_spec_file
# ---------------------------------------------------------------------------


def test_check_spec_file_consistent_returns_none(tmp_path):
    file_path = tmp_path / "consistent.md"
    file_path.write_text(CONSISTENT_SPEC, encoding="utf-8")

    assert _hook.check_spec_file(file_path) is None


def test_check_spec_file_drift_returns_result(tmp_path):
    file_path = tmp_path / "drifted.md"
    file_path.write_text(DRIFTED_SPEC, encoding="utf-8")

    result = _hook.check_spec_file(file_path)

    assert result is not None
    assert result.frontmatter_version == "1.0"
    assert result.history_max_version == "1.3"


def test_check_spec_file_missing_history_returns_none(tmp_path):
    file_path = tmp_path / "no_history.md"
    file_path.write_text(NO_HISTORY_SPEC, encoding="utf-8")

    assert _hook.check_spec_file(file_path) is None


def test_check_spec_file_missing_frontmatter_returns_none(tmp_path):
    file_path = tmp_path / "no_frontmatter.md"
    file_path.write_text(NO_FRONTMATTER_SPEC, encoding="utf-8")

    assert _hook.check_spec_file(file_path) is None


# ---------------------------------------------------------------------------
# scan_spec_drifts + format_drift_warning
# ---------------------------------------------------------------------------


def test_scan_spec_drifts_across_directory(tmp_path):
    spec_dir = tmp_path / "docs" / "spec" / "core"
    spec_dir.mkdir(parents=True)
    (spec_dir / "consistent.md").write_text(CONSISTENT_SPEC, encoding="utf-8")
    (spec_dir / "drifted.md").write_text(DRIFTED_SPEC, encoding="utf-8")

    drifts = _hook.scan_spec_drifts(tmp_path)

    assert len(drifts) == 1
    assert drifts[0].file_path.name == "drifted.md"


def test_scan_spec_drifts_no_drift_returns_empty(tmp_path):
    spec_dir = tmp_path / "docs" / "spec"
    spec_dir.mkdir(parents=True)
    (spec_dir / "consistent.md").write_text(CONSISTENT_SPEC, encoding="utf-8")

    assert _hook.scan_spec_drifts(tmp_path) == []


def test_format_drift_warning_includes_both_versions(tmp_path):
    file_path = tmp_path / "docs" / "spec" / "drifted.md"
    file_path.parent.mkdir(parents=True)
    file_path.write_text(DRIFTED_SPEC, encoding="utf-8")

    drift = _hook.check_spec_file(file_path)
    warning = _hook.format_drift_warning([drift], tmp_path)

    assert "frontmatter=1.0" in warning
    assert "變更歷史最大版號=1.3" in warning
    assert "drifted.md" in warning


# ---------------------------------------------------------------------------
# _version_key
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "left,right,expected",
    [
        ("1.2", "1.10", True),   # 1.10 > 1.2（非字串比較）
        ("1.0", "1.0", False),
        ("1.9", "2.0", True),
    ],
)
def test_version_key_numeric_comparison(left, right, expected):
    assert (_hook._version_key(right) > _hook._version_key(left)) == expected
