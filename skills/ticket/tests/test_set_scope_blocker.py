"""ticket track set-scope-blocker 測試。

Why: scope_blocker 原僅在建立當下可寫入；凍結前已存在的必要票沒有建立
時機補這個欄位。本命令補上事後設定路徑，測試涵蓋三面向：

- 設定 / 清除的基本讀寫往返
- E1（紅輸入對照）：空理由與缺旗標同樣拒
- E2（跨 skill 整合斷言）：設定後 version-release 的
  collect_ticket_scope_groups 將該票歸入阻擋組而非前移清單
"""

import argparse
import sys
from pathlib import Path

import pytest
import yaml

from ticket_system.commands.fields import execute_set_scope_blocker


def _create_ticket_file(tmp_path, ticket_id, version, **extra_fields):
    """建立測試用 Ticket 檔案，回傳檔案路徑。"""
    tickets_dir = (
        tmp_path
        / "docs"
        / "work-logs"
        / f"v{version.split('.')[0]}"
        / f"v{'.'.join(version.split('.')[:2])}"
        / f"v{version}"
        / "tickets"
    )
    tickets_dir.mkdir(parents=True)

    frontmatter = {
        "id": ticket_id,
        "title": "Test",
        "type": "IMP",
        "status": "pending",
        "version": version,
        "wave": 1,
        "priority": "P2",
        "what": "測試用 ticket",
    }
    frontmatter.update(extra_fields)

    ticket_path = tickets_dir / f"{ticket_id}.md"
    content = "---\n" + yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False) + "---\n\n# Execution Log\n"
    ticket_path.write_text(content, encoding="utf-8")
    return ticket_path, tickets_dir


def _make_args(ticket_id, reason=None, clear=False, version=None):
    return argparse.Namespace(ticket_id=ticket_id, reason=reason, clear=clear, version=version)


def _load_frontmatter(ticket_path):
    content = ticket_path.read_text(encoding="utf-8")
    parts = content.split("---", 2)
    return yaml.safe_load(parts[1])


def _setup_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))


def test_set_reason_writes_frontmatter_and_readable(tmp_path, monkeypatch):
    """--reason 寫入 frontmatter，load_and_validate/直接讀檔皆可讀回。"""
    _setup_env(tmp_path, monkeypatch)
    ticket_path, _ = _create_ticket_file(tmp_path, "9.9.9-W1-001", "9.9.9")

    args = _make_args("9.9.9-W1-001", reason="必要契約項：凍結前既有必要票", version="9.9.9")
    result = execute_set_scope_blocker(args, "9.9.9")

    assert result == 0
    fm = _load_frontmatter(ticket_path)
    assert fm["scope_blocker"] == "必要契約項：凍結前既有必要票"


def test_clear_removes_scope_blocker(tmp_path, monkeypatch):
    """--clear 將 scope_blocker 設回 None（等同移除阻擋）。"""
    _setup_env(tmp_path, monkeypatch)
    ticket_path, _ = _create_ticket_file(
        tmp_path, "9.9.9-W1-002", "9.9.9", scope_blocker="舊理由"
    )

    args = _make_args("9.9.9-W1-002", clear=True, version="9.9.9")
    result = execute_set_scope_blocker(args, "9.9.9")

    assert result == 0
    fm = _load_frontmatter(ticket_path)
    assert fm.get("scope_blocker") is None


def test_empty_reason_rejected_same_as_missing_flag(tmp_path, monkeypatch):
    """E1：空字串理由與缺旗標同樣拒（不寫入 frontmatter）。"""
    _setup_env(tmp_path, monkeypatch)
    ticket_path, _ = _create_ticket_file(tmp_path, "9.9.9-W1-003", "9.9.9")

    # 空字串理由：視同未給，拒絕寫入
    args_empty = _make_args("9.9.9-W1-003", reason="   ", version="9.9.9")
    result_empty = execute_set_scope_blocker(args_empty, "9.9.9")
    assert result_empty == 1

    # 缺旗標（reason=None, clear=False）：同樣拒絕
    args_missing = _make_args("9.9.9-W1-003", version="9.9.9")
    result_missing = execute_set_scope_blocker(args_missing, "9.9.9")
    assert result_missing == 1

    fm = _load_frontmatter(ticket_path)
    assert fm.get("scope_blocker") is None


def test_set_scope_blocker_moves_ticket_into_blocked_group(tmp_path, monkeypatch):
    """E2（跨 skill 整合斷言）：設定後 collect_ticket_scope_groups 歸入阻擋組。

    對照：設定前該票（pending 且無 scope_blocker）屬前移組；設定後改屬阻擋組。
    """
    _setup_env(tmp_path, monkeypatch)
    ticket_path, tickets_dir = _create_ticket_file(tmp_path, "9.9.9-W1-004", "9.9.9")

    version_release_scripts = (
        Path(__file__).resolve().parents[2] / "version-release" / "scripts"
    )
    sys.path.insert(0, str(version_release_scripts))
    try:
        import version_release as vr

        # 設定前：無 scope_blocker，pending 票應落在 overflow（前移）組
        groups_before = vr.collect_ticket_scope_groups(tickets_dir, "9.9.9")
        before_ids = {t["id"] for t in groups_before["overflow"]}
        assert "9.9.9-W1-004" in before_ids
        blocked_before_ids = {t["id"] for t in groups_before["blocked"]}
        assert "9.9.9-W1-004" not in blocked_before_ids

        args = _make_args("9.9.9-W1-004", reason="版本契約必要項", version="9.9.9")
        result = execute_set_scope_blocker(args, "9.9.9")
        assert result == 0

        groups_after = vr.collect_ticket_scope_groups(tickets_dir, "9.9.9")
        blocked_after_ids = {t["id"] for t in groups_after["blocked"]}
        assert "9.9.9-W1-004" in blocked_after_ids
        overflow_after_ids = {t["id"] for t in groups_after["overflow"]}
        assert "9.9.9-W1-004" not in overflow_after_ids
    finally:
        sys.path.remove(str(version_release_scripts))
        sys.modules.pop("version_release", None)
