"""Tests for sync-claude-pull.py 大小寫不敏感檔案系統下的刪除防護。

背景（2026-08 P0 事故）：下游消費專案執行 sync-pull 後，三個 skill 入口檔在工作區
消失（git 顯示三筆刪除），事後以 sha256 比對確認無內容遺失（可從 HEAD 還原），但屬
實際資料刪除。受控實驗（隔離 fixture repo，四種組合 x 兩種 upstream 大小寫，共 8
組）證實：cleanup_stale_files 對 rel 不在 remote_files 集合的檔案，於 git 未追蹤時
直接 unlink；_is_git_tracked 用 `git ls-files --error-unmatch` 查詢，其 pathspec
比對固定為大小寫敏感（即使 core.ignorecase=true 亦不受影響，已用裸 git 指令驗證），
而查詢用的路徑字串來自「磁碟 dirent」（cleanup_stale_files._walk 的 item.name），
非 git index 的實際條目名稱。當「本地磁碟大小寫」同時偏離「本地 git index 大小寫」
與「上游大小寫」時，_is_git_tracked 誤判為未追蹤，安全網被繞過，已追蹤內容遭
unlink 而非移至 .sync-conflicts/。

實驗證實觸發條件精確式：DELETED iff (磁碟大小寫 != 上游大小寫) 且
(磁碟大小寫 != 本地 index 大小寫)。原票面假說「僅 index 與磁碟不一致」不足以
解釋刪除（該假說描述的組合 index=lower/disk=upper/upstream=upper 實測不刪除，
因磁碟大小寫恰好與上游一致而完全不觸發 stale 判定）；真正觸發需磁碟大小寫同時
偏離另外兩者。修復：_is_git_tracked 於 exact match 失敗時，改列出同目錄下的
git 追蹤條目做大小寫不敏感 fallback 比對。
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

# sync-claude-pull.py 含連字符且 shebang 為 uv script，須以 importlib 載入
_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location("sync_claude_pull_case_mismatch", _SCRIPT)
assert _spec and _spec.loader
sync_mod = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_case_mismatch"] = sync_mod
_spec.loader.exec_module(sync_mod)  # type: ignore[union-attr]


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    assert result.returncode == 0, (
        f"cmd failed: {args} in {cwd}\nSTDOUT:{result.stdout}\nSTDERR:{result.stderr}"
    )
    return result


def _init_git_repo(root: Path) -> None:
    _run(["git", "init", "-q"], root)
    _run(["git", "config", "user.email", "t@example.com"], root)
    _run(["git", "config", "user.name", "test"], root)


def _make_local_repo(root: Path, index_case: str, disk_case: str, content: bytes) -> Path:
    """建立本地（受影響端）fixture repo：index 與磁碟大小寫可獨立設定。

    磁碟建 disk_case 名稱的真實檔案；git index 用
    `update-index --add --cacheinfo` 直接寫入 index_case 名稱的條目（不觸碰磁碟），
    模擬案例級大小寫改名只更新 index、未真正改寫磁碟 dirent 的長期分歧狀態
    （macOS/APFS 等大小寫不敏感檔案系統的 case-preserving 特性下可自然發生）。
    """
    claude_dir = root / ".claude"
    skill_dir = claude_dir / "skills" / "foo"
    skill_dir.mkdir(parents=True)

    disk_name = "SKILL.md" if disk_case == "upper" else "skill.md"
    index_name = "SKILL.md" if index_case == "upper" else "skill.md"

    disk_path = skill_dir / disk_name
    disk_path.write_bytes(content)

    _init_git_repo(root)
    blob_sha = _run(
        ["git", "hash-object", "-w", str(disk_path.relative_to(root))], root
    ).stdout.strip()
    index_rel = f".claude/skills/foo/{index_name}"
    _run(
        ["git", "update-index", "--add", "--cacheinfo", f"100644,{blob_sha},{index_rel}"],
        root,
    )
    _run(["git", "commit", "-q", "-m", "setup fixture"], root)
    return claude_dir


def _make_remote_src(root: Path, case: str, content: bytes) -> Path:
    """建立上游樹：index 與磁碟一致（新鮮 clone 天然一致，非本測試變數）。"""
    claude_dir = root / ".claude"
    skill_dir = claude_dir / "skills" / "foo"
    skill_dir.mkdir(parents=True)
    name = "SKILL.md" if case == "upper" else "skill.md"
    (skill_dir / name).write_bytes(content)
    return claude_dir


CASE_COMBINATIONS = [
    ("lower", "lower", "upper"),
    ("lower", "upper", "upper"),
    ("upper", "lower", "upper"),
    ("upper", "upper", "upper"),
    ("lower", "lower", "lower"),
    ("lower", "upper", "lower"),
    ("upper", "lower", "lower"),
    ("upper", "upper", "lower"),
]


@pytest.mark.parametrize("index_case,disk_case,upstream_case", CASE_COMBINATIONS)
def test_case_mismatch_never_deletes_tracked_file(
    tmp_path: Path, index_case: str, disk_case: str, upstream_case: str
) -> None:
    """四組（index x disk）在兩種 upstream 大小寫下皆不得刪除已追蹤的 skill 入口檔。

    驗收條件：檔案內容須存活於本地磁碟上（不論最終落在原路徑或
    .sync-conflicts/），任何組合都不得觸發 unlink。
    """
    content = b"skill entry content\n"
    local_claude = _make_local_repo(tmp_path / "local", index_case, disk_case, content)
    remote_claude = _make_remote_src(tmp_path / "remote", upstream_case, content)

    remote_files = sync_mod.collect_remote_files(remote_claude)
    removed, preserved_as_conflict = sync_mod.cleanup_stale_files(
        local_claude, remote_files, preserve=set(), project_root=tmp_path / "local"
    )

    non_empty_removed = [r for r in removed if "(empty dir)" not in r]
    assert not non_empty_removed, (
        f"不應刪除已追蹤檔（index={index_case}, disk={disk_case}, "
        f"upstream={upstream_case}）：removed={removed}"
    )

    # 內容須存活：原路徑存在，或已移至 .sync-conflicts/
    survives_in_place = any(local_claude.rglob("*.md"))
    survives_in_conflicts = bool(preserved_as_conflict)
    assert survives_in_place or survives_in_conflicts, (
        f"檔案內容必須存活於磁碟（index={index_case}, disk={disk_case}, "
        f"upstream={upstream_case}）"
    )


def test_is_git_tracked_case_insensitive_fallback(tmp_path: Path) -> None:
    """_is_git_tracked 對「查詢路徑大小寫」與「index 條目大小寫」不一致時仍須回 True。

    直接針對修復的函式做單元級驗證：exact match 失敗（大小寫不同）時，
    fallback 列出同目錄 git 追蹤條目做大小寫不敏感比對。
    """
    root = tmp_path
    claude_dir = root / ".claude"
    skill_dir = claude_dir / "skills" / "foo"
    skill_dir.mkdir(parents=True)
    disk_path = skill_dir / "skill.md"
    disk_path.write_bytes(b"content\n")

    _init_git_repo(root)
    blob_sha = _run(
        ["git", "hash-object", "-w", str(disk_path.relative_to(root))], root
    ).stdout.strip()
    _run(
        [
            "git", "update-index", "--add", "--cacheinfo",
            f"100644,{blob_sha},.claude/skills/foo/SKILL.md",
        ],
        root,
    )
    _run(["git", "commit", "-q", "-m", "setup"], root)

    # 查詢用磁碟案例（lower），但 index 條目是 upper（模擬 _walk 傳入的路徑來源）
    assert sync_mod._is_git_tracked(
        ".claude/skills/foo/skill.md", root
    ), "大小寫不同但同名（fold 後相等）的 index 條目應被判定為已追蹤"


def test_is_git_tracked_still_false_for_genuinely_untracked(tmp_path: Path) -> None:
    """回歸保護：fallback 不可讓真正未追蹤的檔被誤判為已追蹤。"""
    root = tmp_path
    claude_dir = root / ".claude"
    skill_dir = claude_dir / "skills" / "foo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "other.md").write_bytes(b"content\n")

    _init_git_repo(root)
    _run(["git", "commit", "-q", "-m", "empty", "--allow-empty"], root)

    assert not sync_mod._is_git_tracked(
        ".claude/skills/foo/other.md", root
    ), "未追蹤檔不應因 fallback 誤判為已追蹤"
