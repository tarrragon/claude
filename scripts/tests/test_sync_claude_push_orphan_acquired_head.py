"""3.6.0-W1-274：--clean 刪除歷史只採計取得 base 之後的刪除。

pull 寫 base 時記下當下本地 HEAD（base_acquired_local_head）；push 判定 D 時以
merge-base --is-ancestor 比對：D 是該 HEAD 的祖先（取得 base 之前）不算刪過。
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-push.py"
_spec = importlib.util.spec_from_file_location("sync_claude_push_acq", _SCRIPT)
assert _spec and _spec.loader
push = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_push_acq"] = push
_spec.loader.exec_module(push)  # type: ignore[union-attr]

REL = ".claude/skills/x/f.md"


def _git(root: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=str(root), check=True, capture_output=True, text=True)
    return r.stdout.strip()


def _init(root: Path) -> None:
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".claude").mkdir()
    (root / ".claude" / "CLAUDE.md").write_text("b\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")


def _commit(root: Path, msg: str, delete: bool = False) -> str:
    p = root / REL
    if delete:
        p.unlink()
    else:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", msg)
    return _git(root, "rev-parse", "HEAD")


def _set_acquired(root: Path, sha: str) -> None:
    push.write_sync_base_field(root / ".claude", push.BASE_ACQUIRED_HEAD_FIELD, sha)


def _classify(root: Path) -> str:
    return push.classify_orphan_candidate(Path("skills/x/f.md"), root / ".claude", root)


def test_deletion_before_acquired_head_with_file_restored_is_not_true_orphan(tmp_path):
    # 3.6.0-W1-365：原例檔不在工作樹即判保留，與「本地先刪後 pull」同形，改為 pull 帶回檔的情境
    _init(tmp_path)
    _commit(tmp_path, "add")
    _commit(tmp_path, "del", delete=True)
    _set_acquired(tmp_path, _git(tmp_path, "rev-parse", "HEAD"))
    (tmp_path / REL).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / REL).write_text("x\n", encoding="utf-8")
    assert _classify(tmp_path) == push._ORPHAN_UNTRACKED_LOCAL


def test_deletion_after_acquired_head_is_true_orphan(tmp_path):
    _init(tmp_path)
    _commit(tmp_path, "add")
    acquired = _git(tmp_path, "rev-parse", "HEAD")
    _commit(tmp_path, "del", delete=True)
    _set_acquired(tmp_path, acquired)
    assert _classify(tmp_path) == push._ORPHAN_TRUE


def test_missing_field_keeps_legacy_behavior(tmp_path):
    _init(tmp_path)
    _commit(tmp_path, "add")
    _commit(tmp_path, "del", delete=True)
    assert _classify(tmp_path) == push._ORPHAN_TRUE


def test_pull_write_base_sha_records_local_head(tmp_path):
    """acceptance 1：pull 的 write_base_sha 同時記錄當下本地 HEAD。"""
    pull_script = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
    spec = importlib.util.spec_from_file_location("sync_claude_pull_acq", pull_script)
    assert spec and spec.loader
    pull = importlib.util.module_from_spec(spec)
    sys.modules["sync_claude_pull_acq"] = pull
    spec.loader.exec_module(pull)  # type: ignore[union-attr]
    _init(tmp_path)
    pull.write_base_sha(tmp_path / ".claude", "a" * 40)
    head = _git(tmp_path, "rev-parse", "HEAD")
    got = push.read_sync_base_field(tmp_path / ".claude", push.BASE_ACQUIRED_HEAD_FIELD)
    assert got == head


def test_unreachable_acquired_head_keeps_legacy_behavior(tmp_path):
    _init(tmp_path)
    _commit(tmp_path, "add")
    _commit(tmp_path, "del", delete=True)
    _set_acquired(tmp_path, "0" * 40)
    assert _classify(tmp_path) == push._ORPHAN_TRUE


# 3.6.0-W1-365：對照 A／B。差異只在 pull 之後該檔是否回到工作樹。
def test_contrast_a_pull_restored_file_keeps_old_deletion_excluded(tmp_path):
    """對照 A（canonical #63）：D 早於 acquired_head，pull 把檔帶回工作樹，不判刪過。"""
    _init(tmp_path)
    _commit(tmp_path, "add")
    _commit(tmp_path, "del", delete=True)
    head = _git(tmp_path, "rev-parse", "HEAD")
    _set_acquired(tmp_path, head)
    restored = tmp_path / REL
    restored.parent.mkdir(parents=True, exist_ok=True)
    restored.write_text("x\n", encoding="utf-8")
    assert push._has_local_deletion_history(tmp_path, REL, head) is False
    assert _classify(tmp_path) != push._ORPHAN_TRUE


def test_contrast_b_local_delete_then_pull_without_restore_is_true_orphan(tmp_path):
    """對照 B：本地先 git rm 並 commit，之後 pull 推進 base 但沒帶回該檔，判 true_orphan。"""
    _init(tmp_path)
    _commit(tmp_path, "add")
    _commit(tmp_path, "git rm", delete=True)
    _set_acquired(tmp_path, _git(tmp_path, "rev-parse", "HEAD"))
    assert not (tmp_path / REL).exists()
    assert _classify(tmp_path) == push._ORPHAN_TRUE


def test_judgement_failure_keeps_file(tmp_path):
    """判定失敗（非 git 目錄、acquired_head 不可解析）落在保留一側：不判刪過。"""
    assert push._has_local_deletion_history(tmp_path, REL, "0" * 40) is False
