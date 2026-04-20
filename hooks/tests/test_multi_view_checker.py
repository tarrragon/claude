"""
Multi-View Status Checker Tests

對應 Ticket 0.18.0-W10-051：
驗證 ANA Ticket 的 Solution 區段是否含合法 multi_view_status 標註。

覆蓋四種情境：
  (1) missing   - 未標註 → 警告
  (2) reviewed  - 標註完整 → 通過
  (3) skipped   - 標註完整（含 reason）→ 通過
  (4) n_a       - 標註完整（含 reason）→ 通過

額外情境：
  - 非 ANA ticket 應直接跳過
  - reviewed 缺少 reviewers → 警告
  - 非法值 → 警告
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

_hooks_dir = Path(__file__).parent.parent
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

from acceptance_checkers.multi_view_checker import check_multi_view_status  # noqa: E402


@pytest.fixture
def logger():
    log = logging.getLogger("test-multi-view-checker")
    log.addHandler(logging.NullHandler())
    log.setLevel(logging.CRITICAL)
    return log


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """建立含 ana-solution-schema.yaml 的臨時專案目錄。

    測試時若 schema 不存在，checker 會使用 _DEFAULT_SCHEMA，行為一致。
    此 fixture 保留原始行為（不建立 schema），以 _DEFAULT_SCHEMA 驗證。
    """
    return tmp_path


def _make_content(solution_body: str) -> str:
    return (
        "---\nid: 0.18.0-W10-999\ntype: ANA\n---\n\n"
        "## Problem Analysis\n\nsome analysis\n\n"
        "## Solution\n\n"
        f"{solution_body}\n\n"
        "## Test Results\n\n"
    )


# ---------------------------------------------------------------------------
# 情境 1：missing - Solution 未含 multi_view_status → 警告
# ---------------------------------------------------------------------------

def test_ana_missing_multi_view_status_should_warn(project_dir, logger):
    content = _make_content("some solution without status field")
    fm = {"id": "0.18.0-W10-999", "type": "ANA"}

    should_warn, msg = check_multi_view_status(content, fm, project_dir, logger)

    assert should_warn is True
    assert msg is not None
    assert "multi_view_status" in msg


# ---------------------------------------------------------------------------
# 情境 2：reviewed - 標註完整 → 通過
# ---------------------------------------------------------------------------

def test_ana_reviewed_with_complete_subfields_should_pass(project_dir, logger):
    body = (
        "multi_view_status: reviewed\n"
        "reviewers: [linux-reviewer, security-reviewer]\n"
        "conclusion: 三層防護 DRY 違反確認\n"
    )
    content = _make_content(body)
    fm = {"id": "0.18.0-W10-999", "type": "ANA"}

    should_warn, msg = check_multi_view_status(content, fm, project_dir, logger)

    assert should_warn is False
    assert msg is None


# ---------------------------------------------------------------------------
# 情境 3：skipped - 標註含 reason → 通過
# ---------------------------------------------------------------------------

def test_ana_skipped_with_reason_should_pass(project_dir, logger):
    body = (
        "multi_view_status: skipped\n"
        "reason: 本 ANA 僅彙整既有資料，無新設計決策\n"
    )
    content = _make_content(body)
    fm = {"id": "0.18.0-W10-999", "type": "ANA"}

    should_warn, msg = check_multi_view_status(content, fm, project_dir, logger)

    assert should_warn is False
    assert msg is None


# ---------------------------------------------------------------------------
# 情境 4：n_a - 標註含 reason → 通過
# ---------------------------------------------------------------------------

def test_ana_na_with_reason_should_pass(project_dir, logger):
    body = (
        "multi_view_status: n_a\n"
        "reason: 純文件調查，無程式碼影響\n"
    )
    content = _make_content(body)
    fm = {"id": "0.18.0-W10-999", "type": "ANA"}

    should_warn, msg = check_multi_view_status(content, fm, project_dir, logger)

    assert should_warn is False
    assert msg is None


def test_ana_na_alias_slash_should_normalize_and_pass(project_dir, logger):
    """n/a 應被正規化為 n_a。"""
    body = (
        "multi_view_status: n/a\n"
        "reason: 純文件調查\n"
    )
    content = _make_content(body)
    fm = {"id": "0.18.0-W10-999", "type": "ANA"}

    should_warn, msg = check_multi_view_status(content, fm, project_dir, logger)

    assert should_warn is False


# ---------------------------------------------------------------------------
# 額外情境：非 ANA ticket 應跳過
# ---------------------------------------------------------------------------

def test_non_ana_ticket_should_skip(project_dir, logger):
    content = _make_content("no multi_view_status field")
    fm = {"id": "0.18.0-W10-999", "type": "IMP"}

    should_warn, msg = check_multi_view_status(content, fm, project_dir, logger)

    assert should_warn is False
    assert msg is None


# ---------------------------------------------------------------------------
# 額外情境：reviewed 缺少 reviewers → 警告
# ---------------------------------------------------------------------------

def test_ana_reviewed_missing_reviewers_should_warn(project_dir, logger):
    body = (
        "multi_view_status: reviewed\n"
        "conclusion: 已審查\n"
    )
    content = _make_content(body)
    fm = {"id": "0.18.0-W10-999", "type": "ANA"}

    should_warn, msg = check_multi_view_status(content, fm, project_dir, logger)

    assert should_warn is True
    assert msg is not None
    assert "reviewers" in msg


def test_ana_skipped_without_reason_should_warn(project_dir, logger):
    body = "multi_view_status: skipped\n"
    content = _make_content(body)
    fm = {"id": "0.18.0-W10-999", "type": "ANA"}

    should_warn, msg = check_multi_view_status(content, fm, project_dir, logger)

    assert should_warn is True
    assert "reason" in (msg or "")


# ---------------------------------------------------------------------------
# 額外情境：非法值 → 警告
# ---------------------------------------------------------------------------

def test_ana_invalid_value_should_warn(project_dir, logger):
    body = (
        "multi_view_status: done\n"
        "conclusion: ok\n"
    )
    content = _make_content(body)
    fm = {"id": "0.18.0-W10-999", "type": "ANA"}

    should_warn, msg = check_multi_view_status(content, fm, project_dir, logger)

    assert should_warn is True
    assert msg is not None
    assert "非法" in msg or "invalid" in msg.lower()


# ---------------------------------------------------------------------------
# 額外情境：Solution 區段缺失 → 警告
# ---------------------------------------------------------------------------

def test_ana_missing_solution_section_should_warn(project_dir, logger):
    content = (
        "---\nid: 0.18.0-W10-999\ntype: ANA\n---\n\n"
        "## Problem Analysis\n\nsome analysis\n\n"
    )
    fm = {"id": "0.18.0-W10-999", "type": "ANA"}

    should_warn, msg = check_multi_view_status(content, fm, project_dir, logger)

    assert should_warn is True
    assert msg is not None


# ---------------------------------------------------------------------------
# Schema 載入：從真實 .claude/config/ana-solution-schema.yaml
# ---------------------------------------------------------------------------

def test_schema_loads_from_real_config_file():
    """驗證專案實際 schema 檔能被正確讀取。"""
    from acceptance_checkers.multi_view_checker import load_schema

    project_root = Path(__file__).resolve().parents[3]
    logger = logging.getLogger("test-schema-load")
    logger.addHandler(logging.NullHandler())
    logger.setLevel(logging.CRITICAL)

    schema = load_schema(project_root, logger)

    assert schema["field_key"] == "multi_view_status"
    assert "reviewed" in schema["allowed_values"]
    assert "skipped" in schema["allowed_values"]
    assert "n_a" in schema["allowed_values"]
    assert "reviewers" in schema["required_subfields"]["reviewed"]
    assert "conclusion" in schema["required_subfields"]["reviewed"]
    assert "reason" in schema["required_subfields"]["skipped"]
    assert "reason" in schema["required_subfields"]["n_a"]
