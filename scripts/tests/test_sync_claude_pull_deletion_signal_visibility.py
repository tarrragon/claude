"""Tests for sync-claude-pull.py 刪除類訊號的輸出顯著性（2026-08 P0 事故收尾）。

背景：下游消費專案回報 sync-pull 刪除 skill 入口檔的事故中，輸出裡有兩則字面
正確的訊號皆被格式弱化——反向孤兒提醒（`compute_reverse_orphan_candidates`）與
skill 版本摘要的「移除」列，兩者都以與「新增/更新」同級的 green / 「提醒」措辭
呈現，讀來像例行版本統計而非需要立即注意的刪除告警。全量 overlay 路徑下真正
執行 unlink 的訊息（`cleanup_stale_files` 回傳的 removed 清單）過去也以 green +
「已清理」（例行成功語氣）呈現。

本檔驗證三處輸出已改為顯著的警示措辭（red + 「[警示]」前綴），不再與新增/更新/
一致等例行訊息同色同級。
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location(
    "sync_claude_pull_deletion_signal", _SCRIPT
)
assert _spec and _spec.loader
pull = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_deletion_signal"] = pull
_spec.loader.exec_module(pull)  # type: ignore[union-attr]


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    )


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(["init", "-q"], repo)
    _git(["config", "user.email", "t@t.t"], repo)
    _git(["config", "user.name", "t"], repo)


def _commit_all(repo: Path, msg: str) -> str:
    _git(["add", "-A"], repo)
    _git(["commit", "-q", "-m", msg], repo)
    out = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo),
        check=True, capture_output=True, text=True,
    )
    return out.stdout.strip()


def test_full_overlay_deletion_uses_alert_not_routine_wording(
    tmp_path, monkeypatch, capsys
) -> None:
    """全量 overlay 下真刪除非追蹤過時檔，輸出須為警示措辭，不得是「已清理」。"""
    upstream = tmp_path / "upstream"
    _init_repo(upstream)
    (upstream / "rules").mkdir()
    (upstream / "rules" / "keep.md").write_text("keep\n", encoding="utf-8")
    _commit_all(upstream, "base")

    project_root = tmp_path / "proj"
    claude = project_root / ".claude"
    (claude / "rules").mkdir(parents=True)
    (claude / "rules" / "keep.md").write_text("keep\n", encoding="utf-8")
    (claude / "rules" / "stale.txt").write_text("stale\n", encoding="utf-8")
    # 不寫 .sync-state.json → 無 base SHA → 走全量 overlay（should_use_full_overlay）

    monkeypatch.setattr("builtins.input", lambda *_a, **_k: "y")

    pull._sync_with_backup(project_root, upstream)

    out = capsys.readouterr().out
    assert "[警示]" in out, f"應含警示前綴，實際輸出:\n{out}"
    assert "已清理" not in out, "不應再出現例行成功語氣的舊措辭"
    assert "stale.txt" in out


def test_reverse_orphan_uses_alert_not_routine_wording(tmp_path, capsys) -> None:
    """三方合併路徑下，上游有本地缺漏之檔須為警示措辭，不得是舊版「提醒」用語。"""
    upstream = tmp_path / "upstream"
    _init_repo(upstream)
    (upstream / "rules").mkdir()
    (upstream / "rules" / "keep.md").write_text("keep\n", encoding="utf-8")
    (upstream / "rules" / "missing_locally.md").write_text("gone\n", encoding="utf-8")
    base = _commit_all(upstream, "base")

    project_root = tmp_path / "proj"
    claude = project_root / ".claude"
    (claude / "rules").mkdir(parents=True)
    (claude / "rules" / "keep.md").write_text("keep\n", encoding="utf-8")
    claude.mkdir(parents=True, exist_ok=True)
    (claude / ".sync-state.json").write_text(
        f'{{"last_synced_base_sha": "{base}"}}', encoding="utf-8"
    )

    pull._sync_with_backup(project_root, upstream)

    out = capsys.readouterr().out
    assert "missing_locally.md" in out
    assert "[警示]" in out, f"反向孤兒提醒應為警示措辭，實際輸出:\n{out}"


def test_skill_removal_uses_alert_not_routine_wording(tmp_path, capsys) -> None:
    """skill 版本摘要含移除項時，須先印獨立的警示行，不得只靠例行 green 摘要帶過。

    移除須透過真實 delta（base 有、HEAD 刪除）觸發，純快照比較不足以構造此情境
    ——skill 版本 diff 是「pull 前掃描 vs pull 後掃描」，若上游從未刪除、也沒有
    其他機制動它，本地檔案不會消失，diff 自然不會出現「移除」。
    """
    upstream = tmp_path / "upstream"
    _init_repo(upstream)
    (upstream / "rules").mkdir()
    (upstream / "rules" / "keep.md").write_text("keep\n", encoding="utf-8")
    upstream_skill = upstream / "skills" / "foo" / "SKILL.md"
    upstream_skill.parent.mkdir(parents=True)
    upstream_skill.write_text("**Version**: 1.0.0\n", encoding="utf-8")
    base = _commit_all(upstream, "base")
    upstream_skill.unlink()  # 上游第二版：retire skill foo
    _commit_all(upstream, "retire foo")

    project_root = tmp_path / "proj"
    claude = project_root / ".claude"
    (claude / "rules").mkdir(parents=True)
    (claude / "rules" / "keep.md").write_text("keep\n", encoding="utf-8")
    local_skill = claude / "skills" / "foo" / "SKILL.md"
    local_skill.parent.mkdir(parents=True)
    local_skill.write_text("**Version**: 1.0.0\n", encoding="utf-8")  # 與 base 一致，未本地修改
    (claude / ".sync-state.json").write_text(
        f'{{"last_synced_base_sha": "{base}"}}', encoding="utf-8"
    )

    pull._sync_with_backup(project_root, upstream)

    out = capsys.readouterr().out
    assert not local_skill.exists(), "本地未修改，應隨上游一併刪除（前置條件）"
    assert "foo" in out
    assert "[警示]" in out, f"skill 移除應含獨立警示行，實際輸出:\n{out}"
