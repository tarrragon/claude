"""sync_exclude_manifest LOCAL_ONLY_PATTERNS 與 gitignore 對齊測試。

驗證 W1-018.2 補入的 runtime 排除缺口（logs / state / scheduled_tasks.lock /
dispatch-active.lock）：

- 4 個新 pattern 進入 LOCAL_ONLY_PATTERNS
- should_exclude 對這 4 類路徑回傳 True（含目錄段命中）
- GITIGNORE_EXPECTED 與根目錄 .gitignore 對齊（每個 pattern 都被涵蓋）

Ticket：1.0.0-W1-018.2
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.sync_exclude_manifest import (  # noqa: E402
    GITIGNORE_EXPECTED,
    LOCAL_ONLY_PATTERNS,
    LOCAL_ONLY_ROOT_DIRS,
    should_exclude,
)

# W1-018.2 補入的 name-level pattern（具名足夠，可作 part-level 黑名單）
W1_018_2_NAME_PATTERNS = {
    "scheduled_tasks.lock",
    "dispatch-active.lock",
}

# W1-018.2 補入的 root-anchored 目錄（通用名，僅 .claude/ 根層為 runtime）
W1_018_2_ROOT_DIRS = {
    "logs",
    "state",
}

# W1-018.3 補入的 root-anchored 目錄（agent worktree 產物，曾誤推遠端為 gitlink 垃圾）
W1_018_3_ROOT_DIRS = {
    "worktrees",
}

REPO_ROOT = Path(__file__).resolve().parents[3]
GITIGNORE_PATH = REPO_ROOT / ".gitignore"


# ---------------------------------------------------------------------------
# 1. 新 pattern 進入對應集合
# ---------------------------------------------------------------------------
def test_new_name_patterns_in_local_only():
    missing = W1_018_2_NAME_PATTERNS - LOCAL_ONLY_PATTERNS
    assert not missing, f"LOCAL_ONLY_PATTERNS 缺少 W1-018.2 name pattern：{missing}"


def test_new_root_dirs_in_root_dirs_set():
    missing = W1_018_2_ROOT_DIRS - LOCAL_ONLY_ROOT_DIRS
    assert not missing, f"LOCAL_ONLY_ROOT_DIRS 缺少 W1-018.2 root dir：{missing}"


# ---------------------------------------------------------------------------
# 2. should_exclude 對新 pattern 路徑回傳 True
# ---------------------------------------------------------------------------
def test_should_exclude_matches_new_name_patterns():
    assert should_exclude(Path("scheduled_tasks.lock"))
    assert should_exclude(Path("dispatch-active.lock"))


def test_should_exclude_matches_root_dirs():
    # root-anchored 命中：根層 logs/ 與 state/ 下的任何檔案都應排除
    assert should_exclude(Path("logs/session-2026-06-07.log"))
    assert should_exclude(Path("state/session-start.marker"))


def test_root_dirs_do_not_false_positive_on_nested():
    # 關鍵 regression 防護（W1-018.2）：skill 內部同名 state/ 目錄是 live tracked 內容，
    # 不可被 root-anchored pattern 誤排除（否則停止同步 + 被 --clean 誤刪）。
    assert not should_exclude(
        Path("skills/cc-release-impact-review/state/last-reviewed.md")
    )
    assert not should_exclude(Path("skills/some-skill/logs/notes.md"))


def test_worktrees_root_dir_in_root_dirs_set():
    """W1-018.3：worktrees 進入 LOCAL_ONLY_ROOT_DIRS。"""
    missing = W1_018_3_ROOT_DIRS - LOCAL_ONLY_ROOT_DIRS
    assert not missing, f"LOCAL_ONLY_ROOT_DIRS 缺少 W1-018.3 root dir：{missing}"


def test_should_exclude_matches_worktrees():
    """W1-018.3：根層 worktrees/ 下的 agent worktree 內容都應排除。"""
    assert should_exclude(Path("worktrees/agent-a81aee7d/src/export/foo.js"))
    assert should_exclude(Path("worktrees/agent-a0455599/tests/unit/bar.test.js"))
    assert should_exclude(Path("worktrees"))


def test_worktrees_root_anchored_does_not_false_positive_on_nested():
    """W1-018.3 regression：未來若 skill 內部出現巢狀 worktrees/ 目錄，root-anchored
    判定僅命中第一段，不誤殺 skill 內 live 內容（與 logs / state 同防護）。"""
    assert not should_exclude(
        Path("skills/some-skill/worktrees/template-notes.md")
    )
    assert not should_exclude(
        Path("rules/core/worktrees/example.md")
    )


def test_should_not_exclude_unrelated_paths():
    # 防 false positive：與新 pattern 無關的路徑不應被誤排除
    assert not should_exclude(Path("hooks/lib/sync_exclude_manifest.py"))
    assert not should_exclude(Path("rules/core/quality-baseline.md"))


# ---------------------------------------------------------------------------
# 3. GITIGNORE_EXPECTED 與根目錄 .gitignore 對齊
# ---------------------------------------------------------------------------
def _parse_gitignore_names(content: str) -> set[str]:
    """正規化 gitignore 條目為裸名稱（strip .claude/ 前綴、**/ glob、尾 /）。"""
    names: set[str] = set()
    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        line = line.removeprefix(".claude/")
        line = line.removeprefix("**/")
        line = line.rstrip("/")
        names.add(line)
    return names


def test_gitignore_covers_new_patterns():
    content = GITIGNORE_PATH.read_text(encoding="utf-8")
    names = _parse_gitignore_names(content)
    all_new = W1_018_2_NAME_PATTERNS | W1_018_2_ROOT_DIRS | W1_018_3_ROOT_DIRS
    missing = all_new - names
    assert not missing, f".gitignore 未涵蓋 W1-018.2/W1-018.3 pattern：{missing}"


def test_gitignore_covers_all_expected():
    """GITIGNORE_EXPECTED 全集都應在 .gitignore 出現（防未來漂移）。"""
    content = GITIGNORE_PATH.read_text(encoding="utf-8")
    names = _parse_gitignore_names(content)
    missing = set(GITIGNORE_EXPECTED) - names
    assert not missing, f".gitignore 未涵蓋 GITIGNORE_EXPECTED：{missing}"
