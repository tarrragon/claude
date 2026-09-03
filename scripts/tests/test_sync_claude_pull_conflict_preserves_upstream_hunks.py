"""Tests for sync-claude-pull.py 衝突檔 upstream 非衝突變更不再靜默丟棄。

涵蓋 acceptance（0.2.1-W3-1207）：
  - 衝突檔的 upstream 非衝突變更不再靜默消失：本地與 upstream 各自修改不同
    區塊的檔案，拉取後 upstream 該區塊的變更可在工作區取得
  - 輸出須列出每個衝突檔有多少 upstream 合併標記待人工解決
  - add/add（base 無此檔）衝突不反向靜默丟棄本地版本
  - 版本號/內容一致性：仍有未解衝突時，輸出明示版本檔可能已前進但內容未必
    一致（採「輸出明示」路徑，非阻擋版本號前進）
  - hooks/ 或 lib/ 路徑衝突額外走 stderr（quality-baseline 規則 4：寫入標記
    可能導致該 Hook 語法損毀，需比一般路徑更高的可見性）
  - consumer 真實樣本精確重現：以 fixtures/w3-1207-consumer-sample/ 三檔案
    （取自實際 consumer 專案）驗證同一根因的實際實例，而非僅合成 fixture
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location(
    "sync_claude_pull_conflict_preserves_upstream_hunks", _SCRIPT
)
assert _spec and _spec.loader
pull = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_conflict_preserves_upstream_hunks"] = pull
_spec.loader.exec_module(pull)  # type: ignore[union-attr]


# ============================================================================
# Helpers：建立可控的 git upstream repo fixture
# ============================================================================

def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(
        ["git", *args], cwd=str(cwd), check=True,
        capture_output=True, text=True,
    )


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(["init", "-q"], repo)
    _git(["config", "user.email", "t@t.t"], repo)
    _git(["config", "user.name", "t"], repo)
    _git(["config", "commit.gpgsign", "false"], repo)


def _commit_all(repo: Path, msg: str) -> str:
    _git(["add", "-A"], repo)
    _git(["commit", "-q", "-m", msg], repo)
    out = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo),
        check=True, capture_output=True, text=True,
    )
    return out.stdout.strip()


# ============================================================================
# 情境 1：本地與 upstream 各自修改不同（但相鄰重疊）區塊 → upstream 變更可取得
# ============================================================================

def _setup_adjacent_edit_conflict(tmp_path: Path):
    """local 改第 2、5 行，upstream 改第 3 行（與 local 改動相鄰導致真衝突）。

    回傳 (project_root, upstream_repo, base_sha)。實測（git merge-file）此排列
    會產生單一衝突區塊，同時包含 local 與 upstream 雙方文字。
    """
    upstream = tmp_path / "upstream"
    _init_repo(upstream)
    rules = upstream / "rules"
    rules.mkdir()
    (rules / "adjacent.md").write_text(
        "line1\nline2\nline3\nline4\nline5\n", encoding="utf-8"
    )
    base = _commit_all(upstream, "base")

    (rules / "adjacent.md").write_text(
        "line1\nline2\nUPSTREAM3\nline4\nline5\n", encoding="utf-8"
    )
    _commit_all(upstream, "head")

    project_root = tmp_path / "proj"
    claude = project_root / ".claude"
    (claude / "rules").mkdir(parents=True)
    (claude / "rules" / "adjacent.md").write_text(
        "line1\nLOCAL2\nline3\nline4\nLOCAL5\n", encoding="utf-8"
    )
    return project_root, upstream, base


def test_upstream_change_retrievable_after_conflict(tmp_path):
    """衝突檔的 upstream 變更文字仍可在工作區取得，不隨衝突靜默消失。"""
    project_root, upstream, base = _setup_adjacent_edit_conflict(tmp_path)
    claude = project_root / ".claude"

    _applied, conflicts, _residue = pull.apply_upstream_delta(
        project_root, upstream, base
    )

    assert "rules/adjacent.md" in conflicts
    text = (claude / "rules" / "adjacent.md").read_text(encoding="utf-8")
    assert "UPSTREAM3" in text
    assert "LOCAL2" in text
    # 非重疊區（line4/line5）不受衝突影響，local 的第 5 行改動仍完整保留
    assert "LOCAL5" in text


def test_conflict_message_reports_marker_count_not_local_preserved(tmp_path, capsys):
    """輸出須列出未解合併標記數，不得僅稱「本地原檔保留」。"""
    project_root, upstream, base = _setup_adjacent_edit_conflict(tmp_path)

    pull.apply_upstream_delta(project_root, upstream, base)

    out = capsys.readouterr().out
    assert "本地原檔保留" not in out
    assert "1 處合併標記待人工解決" in out
    assert "upstream 其餘變更已套用" in out


# ============================================================================
# 情境 1b：hooks/ 或 lib/ 路徑衝突額外走 stderr（quality-baseline 規則 4）
# ============================================================================

def _setup_hook_path_conflict(tmp_path: Path):
    """與 _setup_adjacent_edit_conflict 相同的相鄰編輯衝突，但路徑落在 hooks/。"""
    upstream = tmp_path / "upstream"
    _init_repo(upstream)
    hooks = upstream / "hooks"
    hooks.mkdir()
    (hooks / "example-guard-hook.py").write_text(
        "line1\nline2\nline3\nline4\nline5\n", encoding="utf-8"
    )
    base = _commit_all(upstream, "base")

    (hooks / "example-guard-hook.py").write_text(
        "line1\nline2\nUPSTREAM3\nline4\nline5\n", encoding="utf-8"
    )
    _commit_all(upstream, "head")

    project_root = tmp_path / "proj"
    claude = project_root / ".claude"
    (claude / "hooks").mkdir(parents=True)
    (claude / "hooks" / "example-guard-hook.py").write_text(
        "line1\nLOCAL2\nline3\nline4\nLOCAL5\n", encoding="utf-8"
    )
    return project_root, upstream, base


def test_hook_path_conflict_writes_stderr_warning(tmp_path, capsys):
    """hooks/ 路徑衝突寫入標記後，額外在 stderr 提示語法可能損毀。"""
    project_root, upstream, base = _setup_hook_path_conflict(tmp_path)

    pull.apply_upstream_delta(project_root, upstream, base)

    err = capsys.readouterr().err
    assert "hooks/example-guard-hook.py" in err
    assert "語法可能因標記而損毀" in err


def test_non_hook_path_conflict_has_no_stderr_warning(tmp_path, capsys):
    """一般 rules/ 路徑衝突不觸發 hooks/lib 專屬 stderr 警告。"""
    project_root, upstream, base = _setup_adjacent_edit_conflict(tmp_path)

    pull.apply_upstream_delta(project_root, upstream, base)

    err = capsys.readouterr().err
    assert err == ""


# ============================================================================
# 情境 2：add/add 衝突（base 無此檔）不得反向靜默丟棄本地版本
# ============================================================================

def _setup_add_add_conflict(tmp_path: Path):
    """base 無此檔，local 與 upstream 各自獨立新增且內容不同 → add/add 衝突。"""
    upstream = tmp_path / "upstream"
    _init_repo(upstream)
    rules = upstream / "rules"
    rules.mkdir()
    (rules / "keep.md").write_text("unrelated\n", encoding="utf-8")
    base = _commit_all(upstream, "base")

    (rules / "new-both.md").write_text("upstream version\n", encoding="utf-8")
    _commit_all(upstream, "head")

    project_root = tmp_path / "proj"
    claude = project_root / ".claude"
    (claude / "rules").mkdir(parents=True)
    (claude / "rules" / "keep.md").write_text("unrelated\n", encoding="utf-8")
    (claude / "rules" / "new-both.md").write_text("local version\n", encoding="utf-8")
    return project_root, upstream, base


def test_add_add_conflict_preserves_both_sides(tmp_path):
    """add/add 衝突：本地版本不被 upstream 原文靜默取代，雙方皆可在工作區取得。"""
    project_root, upstream, base = _setup_add_add_conflict(tmp_path)
    claude = project_root / ".claude"

    _applied, conflicts, _residue = pull.apply_upstream_delta(
        project_root, upstream, base
    )

    assert "rules/new-both.md" in conflicts
    text = (claude / "rules" / "new-both.md").read_text(encoding="utf-8")
    assert "local version" in text
    assert "upstream version" in text
    assert "<<<<<<<" in text
    assert ">>>>>>>" in text


# ============================================================================
# 情境 3：版本號/內容一致性 —— 未解衝突時輸出明示落差
# ============================================================================

def test_unresolved_conflict_warns_version_content_mismatch(tmp_path, capsys, monkeypatch):
    """有未解衝突時，_sync_with_backup 輸出明示版本號可能與內容不一致。"""
    project_root, upstream, base = _setup_adjacent_edit_conflict(tmp_path)
    claude = project_root / ".claude"
    (claude / ".sync-state.json").write_text(
        f'{{"last_synced_base_sha": "{base}"}}', encoding="utf-8"
    )

    pull._sync_with_backup(project_root, upstream)

    out = capsys.readouterr().out
    assert "版本號" in out
    assert "未必完全一致" in out


# ============================================================================
# 情境 4：consumer 真實樣本精確重現（acceptance 4）
# ============================================================================
#
# 三檔取自一實際 consumer 專案：base.md 為其最後一次推送時的合併基準
# （framework v2.43.1 的 error-patterns/README.md），local.md 為其拉取前版本
# （含該 consumer 獨有的 PC-GPD-005/006），upstream.md 為 framework v2.50.3
# 版本（新增 ARCH-BAL-021）。三檔以 git merge-file 實測回傳 1（單一衝突
# 區塊，位於 PC-GPD-004 之後——local 在該處插入 PC-GPD-005/006，upstream
# 於同位置無對應內容），ARCH-BAL-021 與 PC-GPD-005/006 皆落在合併結果的
# 非衝突段。此為「本地與 upstream 各自修改不同區塊」場景的實際實例，與
# 情境 1 的合成 fixture 測同一根因類別、互不取代。

_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "w3-1207-consumer-sample"


def _setup_consumer_sample_conflict(tmp_path: Path):
    """以真實 consumer 三版本重建 delta：base.md -> upstream.md 為上游演進，
    local.md 為 consumer 本地（含獨有 PC-GPD-005/006）。

    回傳 (project_root, upstream_repo, base_sha)。
    """
    base_content = (_FIXTURE_DIR / "base.md").read_bytes()
    upstream_content = (_FIXTURE_DIR / "upstream.md").read_bytes()
    local_content = (_FIXTURE_DIR / "local.md").read_bytes()

    upstream = tmp_path / "upstream"
    _init_repo(upstream)
    error_patterns = upstream / "error-patterns"
    error_patterns.mkdir()
    (error_patterns / "README.md").write_bytes(base_content)
    base = _commit_all(upstream, "base（framework v2.43.1）")

    (error_patterns / "README.md").write_bytes(upstream_content)
    _commit_all(upstream, "head（framework v2.50.3）")

    project_root = tmp_path / "proj"
    claude = project_root / ".claude"
    (claude / "error-patterns").mkdir(parents=True)
    (claude / "error-patterns" / "README.md").write_bytes(local_content)
    return project_root, upstream, base


def test_consumer_sample_upstream_addition_retrievable(tmp_path):
    """acceptance 4：ARCH-BAL-021（upstream 新增）拉取後可在工作區取得，
    不再只存在於 .sync-conflicts/。"""
    project_root, upstream, base = _setup_consumer_sample_conflict(tmp_path)
    claude = project_root / ".claude"

    _applied, conflicts, _residue = pull.apply_upstream_delta(
        project_root, upstream, base
    )

    assert "error-patterns/README.md" in conflicts
    working_text = (claude / "error-patterns" / "README.md").read_text(
        encoding="utf-8"
    )
    assert "ARCH-BAL-021" in working_text


def test_consumer_sample_local_unique_entries_not_overwritten(tmp_path):
    """acceptance 4：consumer 獨有的 PC-GPD-005/006 未被 upstream 覆蓋丟失。"""
    project_root, upstream, base = _setup_consumer_sample_conflict(tmp_path)
    claude = project_root / ".claude"

    pull.apply_upstream_delta(project_root, upstream, base)

    working_text = (claude / "error-patterns" / "README.md").read_text(
        encoding="utf-8"
    )
    assert "PC-GPD-005" in working_text
    assert "PC-GPD-006" in working_text
