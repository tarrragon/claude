"""Tests for sync-claude-pull.py --audit 孤兒稽核（1.0.0-W8-037.3，缺口 2）。

背景（W8-037 缺口 2）：
  無主動孤兒稽核——專案無法一鍵列「本地 .claude/ 有但上游 HEAD 無」之檔
  （含早於 base 不在 delta 窗者）。delta 路徑只看 base..HEAD 窗。本功能以
  上游 HEAD 全檔集對比本地全檔集做全量差集，涵蓋所有孤兒候選。

涵蓋 acceptance：
  - compute_orphan_candidates：
      本地有上游無之檔 → 入孤兒候選清單
      本地與上游皆有之檔 → 不入
      preserve / should_exclude（LOCAL_ONLY）之本地檔 → 不入（非孤兒）
      無孤兒時回空清單
  - run_audit 走 CLI --audit 分支（透過 main argv 判斷，不動同步主流程）
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location(
    "sync_claude_pull_audit", _SCRIPT
)
assert _spec and _spec.loader
pull = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_audit"] = pull
_spec.loader.exec_module(pull)  # type: ignore[union-attr]


# ============================================================================
# Helpers
# ============================================================================

def _make_tree(root: Path, files: dict[str, str]) -> None:
    """在 root 下建立 {相對路徑: 內容} 的檔案樹。"""
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


# ============================================================================
# 單元：compute_orphan_candidates 全量差集
# ============================================================================

def test_orphan_detected_when_local_only(tmp_path):
    """本地有上游無之檔列入孤兒候選；共有檔不列。"""
    claude = tmp_path / "claude"
    upstream = tmp_path / "upstream"
    _make_tree(claude, {
        "rules/shared.md": "x\n",
        "rules/orphan.md": "local only\n",  # 上游無 → 孤兒候選
    })
    _make_tree(upstream, {
        "rules/shared.md": "x\n",
    })

    orphans = pull.compute_orphan_candidates(claude, upstream)

    assert orphans == ["rules/orphan.md"]


def test_no_orphan_when_all_present_upstream(tmp_path):
    """本地全檔皆存在於上游 → 回空清單。"""
    claude = tmp_path / "claude"
    upstream = tmp_path / "upstream"
    _make_tree(claude, {"rules/a.md": "a\n", "rules/b.md": "b\n"})
    _make_tree(upstream, {
        "rules/a.md": "a\n",
        "rules/b.md": "b\n",
        "rules/c.md": "upstream only\n",  # 上游獨有，不屬本地孤兒
    })

    assert pull.compute_orphan_candidates(claude, upstream) == []


def test_preserve_file_not_listed_as_orphan(tmp_path):
    """preserve 清單中的本地特化檔不列為孤兒（即使上游無）。"""
    claude = tmp_path / "claude"
    upstream = tmp_path / "upstream"
    _make_tree(claude, {"settings.local.json": "{}\n", "rules/orphan.md": "x\n"})
    upstream.mkdir(parents=True, exist_ok=True)  # clone 後上游目錄恆存在

    orphans = pull.compute_orphan_candidates(
        claude, upstream, preserve={"rules/orphan.md"}
    )

    # rules/orphan.md 在 preserve → 排除；settings.local.json 由 should_exclude
    # (LOCAL_ONLY) 排除
    assert orphans == []


def test_local_only_runtime_state_excluded(tmp_path):
    """LOCAL_ONLY runtime state（如 hook-logs 下檔）不列為孤兒。"""
    claude = tmp_path / "claude"
    upstream = tmp_path / "upstream"
    _make_tree(claude, {
        "hook-logs/today.log": "log\n",   # LOCAL_ONLY → collect_remote_files 已跳過
        "rules/orphan.md": "x\n",
    })
    upstream.mkdir(parents=True, exist_ok=True)  # clone 後上游目錄恆存在

    orphans = pull.compute_orphan_candidates(claude, upstream)

    assert "rules/orphan.md" in orphans
    assert all("hook-logs" not in o for o in orphans)


# ============================================================================
# 整合：CLI --audit 分支（不動同步主流程）
# ============================================================================

def test_main_audit_flag_routes_to_run_audit(monkeypatch, capsys):
    """main 見 --audit → 呼叫 run_audit，不執行同步主流程。"""
    called = {"audit": False, "sync": False}

    def _fake_audit() -> None:
        called["audit"] = True
        print("AUDIT_RAN")

    def _fake_clone_backup(_root):
        called["sync"] = True
        raise AssertionError("同步主流程不應在 --audit 下執行")

    monkeypatch.setattr(pull, "run_audit", _fake_audit)
    monkeypatch.setattr(pull, "_clone_and_backup", _fake_clone_backup)
    monkeypatch.setattr(sys, "argv", ["sync-claude-pull.py", "--audit"])

    pull.main()

    assert called["audit"] is True
    assert called["sync"] is False
    assert "AUDIT_RAN" in capsys.readouterr().out


def test_run_audit_prints_orphans(monkeypatch, tmp_path, capsys):
    """run_audit clone 上游後列出孤兒候選（非阻擋措辭）。"""
    project_root = tmp_path / "proj"
    claude = project_root / ".claude"
    _make_tree(claude, {"rules/orphan.md": "x\n"})

    def _fake_clone(temp_dir: Path) -> None:
        temp_dir.mkdir(parents=True, exist_ok=True)
        (temp_dir / "rules").mkdir()
        # 上游無 orphan.md → 應被列出

    monkeypatch.setattr(pull, "find_project_root", lambda: project_root)
    monkeypatch.setattr(pull, "clone_repo", _fake_clone)

    pull.run_audit()

    out = capsys.readouterr().out
    assert "rules/orphan.md" in out
    assert "孤兒候選" in out
    # 非阻擋措辭
    assert "本地特化" in out


def test_run_audit_silent_message_when_no_orphan(monkeypatch, tmp_path, capsys):
    """無孤兒時 run_audit 輸出「無孤兒候選」。"""
    project_root = tmp_path / "proj"
    claude = project_root / ".claude"
    _make_tree(claude, {"rules/a.md": "a\n"})

    def _fake_clone(temp_dir: Path) -> None:
        temp_dir.mkdir(parents=True, exist_ok=True)
        (temp_dir / "rules").mkdir()
        (temp_dir / "rules" / "a.md").write_text("a\n", encoding="utf-8")

    monkeypatch.setattr(pull, "find_project_root", lambda: project_root)
    monkeypatch.setattr(pull, "clone_repo", _fake_clone)

    pull.run_audit()

    assert "無孤兒候選" in capsys.readouterr().out
