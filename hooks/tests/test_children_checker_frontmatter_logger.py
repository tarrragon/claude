"""
Children Checker - frontmatter 解析失敗可觀測性回歸測試（F2-a）

對應 Ticket 0.2.1-W3-665.7：
`check_children_completed` 呼叫 `parse_ticket_frontmatter` 時原本不傳 logger，
子任務 YAML frontmatter 格式錯誤時解析失敗與「無 frontmatter」皆靜默回 `{}`，
acceptance-gate checker 因此無從分辨，全程零訊息即略過檢查誤放行。

本測試驗證修正後：解析失敗會透過傳入的 logger 產生可見的 warning。
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from acceptance_checkers.children_checker import check_children_completed


def _write_child_ticket(project_dir: Path, ticket_id: str, content: str) -> Path:
    version_part = ticket_id.split("-W")[0]
    ticket_dir = project_dir / "docs" / "work-logs" / f"v{version_part}" / "tickets"
    ticket_dir.mkdir(parents=True, exist_ok=True)
    ticket_file = ticket_dir / f"{ticket_id}.md"
    ticket_file.write_text(content, encoding="utf-8")
    return ticket_file


def test_malformed_child_frontmatter_logs_warning(tmp_path, caplog):
    """子任務 frontmatter 為真正的 YAML 語法錯誤時，warning 須可見（F2-a）。"""
    logger = logging.getLogger("test-children-checker-f2a")

    # 真正的 YAML 語法錯誤：flow-style 序列未閉合中括號（模擬手動 Edit 打錯字）
    _write_child_ticket(
        tmp_path,
        "0.0.0-W1-100",
        "---\nid: 0.0.0-W1-100\nchildren: [a, b\nstatus: pending\n---\n\n# Body\n",
    )

    with caplog.at_level(logging.WARNING, logger="test-children-checker-f2a"):
        all_completed, incomplete = check_children_completed(
            ["0.0.0-W1-100"], tmp_path, logger
        )

    # frontmatter 解析失敗 → status 退化為 "unknown" → 視為未完成
    assert all_completed is False
    assert incomplete[0][0] == "0.0.0-W1-100"

    parse_warnings = [
        r for r in caplog.records
        if r.levelno == logging.WARNING and "解析 frontmatter 失敗" in r.getMessage()
    ]
    assert len(parse_warnings) == 1, "frontmatter 解析失敗應透過 logger 產生恰一則可見 warning"


def test_well_formed_child_frontmatter_has_no_parse_warning(tmp_path, caplog):
    """格式正確的 frontmatter 不應觸發解析失敗 warning（對照組，防止誤報）。"""
    logger = logging.getLogger("test-children-checker-f2a-ok")

    _write_child_ticket(
        tmp_path,
        "0.0.0-W1-101",
        "---\nid: 0.0.0-W1-101\nstatus: completed\n---\n\n# Body\n",
    )

    with caplog.at_level(logging.WARNING, logger="test-children-checker-f2a-ok"):
        all_completed, incomplete = check_children_completed(
            ["0.0.0-W1-101"], tmp_path, logger
        )

    assert all_completed is True
    assert incomplete == []

    parse_warnings = [
        r for r in caplog.records
        if r.levelno == logging.WARNING and "解析 frontmatter 失敗" in r.getMessage()
    ]
    assert len(parse_warnings) == 0
