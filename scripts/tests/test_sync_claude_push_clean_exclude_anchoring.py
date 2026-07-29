"""Tests for sync-claude-push.py 的 clean 豁免比對維度（IMP-BAL-004，0.2.1-W3-140）.

`_should_skip_clean_file` 的豁免清單原本是單一集合，同時混入目錄名（`.git`）與
根目錄 metadata 檔名（`README.md` 等），兩者共用檔名比對。結果每一個巢狀
`README.md` 都獲豁免，clean 無法完整刪除任何含 README 的目錄——實測刪除
8 檔目錄只傳播了 7 檔，canonical 留下孤兒 README。

本測試對兩個維度分別成對驗證：
  - 目錄名集合：任意深度都豁免（`.git` 在路徑任一層皆命中）
  - 根目錄檔名集合：只有 `len(rel.parts) == 1` 時豁免，巢狀同名檔不豁免

成對驗證是必要的：只測「有豁免到」的單向測試無法捕捉過度匹配，而過度匹配
正是本缺陷的形態。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-push.py"
_spec = importlib.util.spec_from_file_location("sync_claude_push", _SCRIPT)
assert _spec and _spec.loader
sync_mod = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_push"] = sync_mod
_spec.loader.exec_module(sync_mod)  # type: ignore[union-attr]


def _skip(rel: str) -> bool:
    """以空 preserve / lineage / skills_config 呼叫，只驗豁免集合本身的行為。"""
    return sync_mod._should_skip_clean_file(Path(rel), set(), set(), None)


# ---------- 根目錄 metadata 檔名：僅根目錄豁免 ----------

def test_root_metadata_files_are_exempt():
    """canonical repo 自身的根目錄 metadata 不可被 clean 刪除。

    LICENSE 與 .gitignore 在本地 .claude/ 不存在，全靠本豁免避免被誤判為
    「本地已刪除」而傳播刪除。
    """
    for name in ("README.md", "CHANGELOG.md", "VERSION", "LICENSE", ".gitignore"):
        assert _skip(name) is True, f"根目錄 {name} 應豁免"


def test_nested_same_name_files_are_not_exempt():
    """巢狀同名檔屬框架內容，必須可被刪除傳播涵蓋（IMP-BAL-004 的核心迴歸）。

    第一條是缺陷的實際現場：0.2.1-W3-133 刪除 integration-patterns 整目錄 8 檔，
    clean 只傳播了 7 檔，README.md 因檔名比對獲豁免而在 canonical 留成孤兒目錄。

    注意選例須避開其他排除機制：同層的 project-integration 目錄本身命中
    manifest 的 PUSH_ONLY_EXCLUDE_PATTERNS，會因不同理由被排除，不能用來驗本缺陷。
    """
    nested = (
        "skills/wrap-decision/references/integration-patterns/README.md",
        "skills/ticket/README.md",
        "error-patterns/README.md",
        "skills/ticket/CHANGELOG.md",
        "skills/ticket/VERSION",
        "rules/core/.gitignore",
    )
    for rel in nested:
        assert _skip(rel) is False, f"巢狀 {rel} 不應豁免"


def test_nested_readme_in_single_level_dir_is_not_exempt():
    """深度只差一層也不豁免——判準是根目錄錨定，不是深度門檻。"""
    assert _skip("agents/README.md") is False


# ---------- 目錄名：任意深度豁免 ----------

def test_git_dir_is_exempt_at_any_depth():
    """VCS 內部目錄出現在路徑任一層都不該被清理。"""
    assert _skip(".git/config") is True
    assert _skip(".git/objects/ab/cdef") is True
    assert _skip("skills/vendored/.git/HEAD") is True


def test_dir_name_set_does_not_leak_into_file_name_matching():
    """名為 .git 的一般檔案（非目錄層）不在保護意圖內，但因 parts 比對仍會命中。

    此行為為既有設計（`.git` 作為路徑成分即豁免），本測試將其固定下來，
    避免後續調整目錄集合時無意改變語意。
    """
    assert _skip(".git") is True


# ---------- 一般框架檔案不受影響 ----------

def test_ordinary_framework_files_are_not_exempt():
    for rel in (
        "rules/core/quality-baseline.md",
        "skills/wrap-decision/SKILL.md",
        "config/wrap-triggers.yaml",
    ):
        assert _skip(rel) is False, f"{rel} 不應豁免"
