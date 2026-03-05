#!/usr/bin/env python3
"""
.claude 資料夾同步腳本 - 從獨立 repo 拉取更新

跨平台支援：macOS / Linux / Windows
依賴：Python 3.8+, git

拉取內容:
  - .claude/ 目錄所有檔案（同步覆蓋 + 清理遠端已刪除的檔案）
  - FLUTTER.md

不覆蓋內容:
  - 根目錄 CLAUDE.md（保留專案特定配置）
  - .claude/hook-logs/（本地日誌）
  - .claude/handoff/（本地交接檔案）
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_URL = "https://github.com/tarrragon/claude.git"

EXCLUDE_FROM_SYNC = {
    ".git",
    "project-templates",
    "hook-logs",
    "handoff",
}

# 本地專有目錄/檔案，pull 時不刪除
LOCAL_ONLY = {
    "hook-logs",
    "handoff",
    "PM_INTERVENTION_REQUIRED",
    "ARCHITECTURE_REVIEW_REQUIRED",
    "pm-status.json",
    "__pycache__",
    ".pytest_cache",
    ".venv",
}


def print_color(msg: str, color: str = "yellow") -> None:
    """Print colored message (ANSI codes, gracefully degrades on Windows)."""
    colors = {"green": "\033[0;32m", "yellow": "\033[1;33m", "red": "\033[0;31m"}
    nc = "\033[0m"
    if sys.platform == "win32" and not os.environ.get("TERM"):
        print(msg)
    else:
        print(f"{colors.get(color, '')}{msg}{nc}")


def run_git(args: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    """Run a git command and return the result."""
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def find_project_root() -> Path:
    """Find the project root by looking for .claude/ directory upward."""
    current = Path.cwd()
    while current != current.parent:
        if (current / ".claude").is_dir():
            return current
        current = current.parent
    print_color("找不到 .claude 目錄，請在專案根目錄執行此腳本", "red")
    sys.exit(1)


def check_uncommitted_changes(project_root: Path) -> None:
    """Check for uncommitted changes in .claude and FLUTTER.md."""
    result = run_git(
        ["diff", "--name-only", ".claude", "FLUTTER.md"],
        cwd=str(project_root),
    )
    cached = run_git(
        ["diff", "--cached", "--name-only", ".claude", "FLUTTER.md"],
        cwd=str(project_root),
    )
    if result.returncode != 0 or cached.returncode != 0:
        print_color("警告: git diff 執行失敗，請確認 git 狀態正常", "red")
        sys.exit(1)
    has_changes = bool(result.stdout.strip() or cached.stdout.strip())
    if has_changes:
        print_color("警告: .claude 或 FLUTTER.md 有未提交的變更", "red")
        print("請先提交或暫存變更，避免衝突")
        sys.exit(1)


def clone_repo(temp_dir: Path) -> None:
    """Clone the remote repo with timeout protection."""
    env = os.environ.copy()
    env["GIT_HTTP_LOW_SPEED_LIMIT"] = "1000"
    env["GIT_HTTP_LOW_SPEED_TIME"] = "30"

    result = subprocess.run(
        ["git", "clone", "--depth", "1", REPO_URL, str(temp_dir)],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    if result.returncode != 0:
        print_color(f"git clone 失敗: {result.stderr}", "red")
        sys.exit(1)


def sync_directory(src: Path, dst: Path) -> int:
    """Incrementally sync src to dst, skipping excluded directories and symlinks.

    Returns the number of files updated.
    """
    count = 0
    for item in src.iterdir():
        if item.name in EXCLUDE_FROM_SYNC:
            continue
        if item.is_symlink():
            continue

        dest_item = dst / item.name
        if item.is_dir():
            if dest_item.exists():
                count += sync_directory(item, dest_item)
            else:
                shutil.copytree(item, dest_item, symlinks=False,
                                ignore=shutil.ignore_patterns(*EXCLUDE_FROM_SYNC))
                count += sum(1 for f in dest_item.rglob("*") if f.is_file())
        else:
            dest_item.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest_item)
            count += 1
    return count


def collect_remote_files(src: Path, prefix: Path = Path()) -> set[Path]:
    """Collect all relative file paths from the remote repo."""
    files: set[Path] = set()
    for item in src.iterdir():
        if item.name in EXCLUDE_FROM_SYNC:
            continue
        if item.is_symlink():
            continue
        rel = prefix / item.name
        if item.is_dir():
            files.update(collect_remote_files(item, rel))
        else:
            files.add(rel)
    return files


def cleanup_stale_files(claude_dir: Path, remote_files: set[Path]) -> list[str]:
    """Remove local files that no longer exist in the remote repo.

    Returns a list of removed file paths (relative to claude_dir).
    """
    removed: list[str] = []

    def _walk(directory: Path, prefix: Path = Path()) -> None:
        if not directory.exists():
            return
        for item in sorted(directory.iterdir()):
            if item.name in LOCAL_ONLY or item.name in EXCLUDE_FROM_SYNC:
                continue
            if item.is_symlink():
                continue
            rel = prefix / item.name
            if item.is_dir():
                _walk(item, rel)
                # Remove empty directories after cleaning files
                if item.exists() and not any(item.iterdir()):
                    item.rmdir()
                    removed.append(f"{rel}/ (empty dir)")
            elif rel not in remote_files:
                item.unlink()
                removed.append(str(rel))

    _walk(claude_dir)
    return removed


def main() -> None:
    print_color("開始從獨立 repo 拉取 .claude 更新...")

    # 1. Find project root
    project_root = find_project_root()
    claude_dir = project_root / ".claude"

    # 2. Check uncommitted changes
    print_color("檢查本地狀態...")
    check_uncommitted_changes(project_root)

    # 3. Clone to temp directory
    print_color("從獨立 repo 拉取更新...")
    temp_dir = Path(tempfile.mkdtemp())
    try:
        clone_repo(temp_dir)

        # 4. Backup
        print_color("備份當前配置...")
        backup_dir = Path(tempfile.mkdtemp(prefix="claude-backup-"))
        shutil.copytree(claude_dir, backup_dir / ".claude")
        flutter_md = project_root / "FLUTTER.md"
        if flutter_md.exists():
            shutil.copy2(flutter_md, backup_dir / "FLUTTER.md")

        # 5. Sync .claude directory
        print_color("更新 .claude 資料夾...")
        remote_files = collect_remote_files(temp_dir)
        file_count = sync_directory(temp_dir, claude_dir)
        print_color(f"   已更新 {file_count} 個檔案", "green")

        # 5.5. Remove stale files (local-only but not in remote)
        removed = cleanup_stale_files(claude_dir, remote_files)
        if removed:
            print_color(f"   已清理 {len(removed)} 個過時檔案:", "green")
            for r in removed:
                print_color(f"     - {r}")
        else:
            print_color("   無過時檔案需清理", "green")

        # 6. Update FLUTTER.md (not CLAUDE.md)
        templates_dir = temp_dir / "project-templates"
        if templates_dir.is_dir():
            print_color("更新專案模板檔案...")
            src_flutter = templates_dir / "FLUTTER.md"
            if src_flutter.exists():
                shutil.copy2(src_flutter, project_root / "FLUTTER.md")
                print_color("   已更新 FLUTTER.md", "green")
            print_color("   注意: CLAUDE.md 未被覆蓋（保留專案特定配置）")

        # 7. Done
        print_color("成功拉取 .claude 更新！", "green")
        print_color(f"備份位置: {backup_dir}", "green")
        print_color("請檢查變更並測試 Hook 系統是否正常運作", "green")
        print_color(f"如需還原，執行: cp -r {backup_dir}/.claude .")
        print()
        print_color("=== 新專案初始化提示 ===")
        print_color("如果是新專案，請手動建立 CLAUDE.md:")
        print_color("  1. cp .claude/templates/CLAUDE-template.md CLAUDE.md")
        print_color("  2. 填入專案特定資訊")
        print_color("  3. 驗證所有連結有效")

    except subprocess.TimeoutExpired:
        print_color("git clone 超時（120 秒），請檢查網路連線", "red")
        sys.exit(1)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
