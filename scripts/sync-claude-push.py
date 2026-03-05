#!/usr/bin/env python3
"""
.claude 資料夾同步腳本 - 推送到獨立 repo

跨平台支援：macOS / Linux / Windows
依賴：Python 3.8+, git

推送內容:
  - .claude/ 目錄所有檔案（排除暫存檔案）
  - project-templates/FLUTTER.md

不推送內容:
  - 根目錄 CLAUDE.md（專案特定配置）
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

REPO_URL = "https://github.com/tarrragon/claude.git"

EXCLUDE_PATTERNS = {
    "hook-logs",
    "PM_INTERVENTION_REQUIRED",
    "ARCHITECTURE_REVIEW_REQUIRED",
    "pm-status.json",
    "__pycache__",
    ".pytest_cache",
}

EXCLUDE_SUFFIXES = {".pyc"}


def print_color(msg: str, color: str = "yellow") -> None:
    """Print colored message (ANSI codes, gracefully degrades on Windows)."""
    colors = {"green": "\033[0;32m", "yellow": "\033[1;33m", "red": "\033[0;31m"}
    nc = "\033[0m"
    if sys.platform == "win32" and not os.environ.get("TERM"):
        print(msg)
    else:
        print(f"{colors.get(color, '')}{msg}{nc}")


def run_git(args: list[str], cwd: str | None = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command and return the result."""
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    if check and result.returncode != 0:
        print_color(f"git {' '.join(args)} 失敗: {result.stderr}", "red")
        sys.exit(1)
    return result


def find_project_root() -> Path:
    """Find the project root by looking for .claude/ directory upward."""
    current = Path.cwd()
    while current != current.parent:
        if (current / ".claude").is_dir():
            return current
        current = current.parent
    print_color("找不到 .claude 目錄，請在專案根目錄執行此腳本", "red")
    sys.exit(1)


def should_exclude(path: Path) -> bool:
    """Check if a path should be excluded from sync."""
    if path.name in EXCLUDE_PATTERNS:
        return True
    if path.suffix in EXCLUDE_SUFFIXES:
        return True
    return any(part in EXCLUDE_PATTERNS for part in path.parts)


def copy_filtered(src: Path, dst: Path) -> int:
    """Copy src to dst, excluding files matching EXCLUDE_PATTERNS and symlinks.

    Returns the number of files copied.
    """
    count = 0
    for item in src.iterdir():
        if should_exclude(item):
            continue
        if item.is_symlink():
            continue

        dest_item = dst / item.name
        if item.is_dir():
            dest_item.mkdir(parents=True, exist_ok=True)
            count += copy_filtered(item, dest_item)
        else:
            dest_item.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest_item)
            count += 1
    return count


def bump_patch_version(version: str) -> str:
    """Increment the patch version number."""
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", version)
    if not match:
        return "1.0.1"
    major, minor, patch = match.groups()
    return f"{major}.{minor}.{int(patch) + 1}"


def update_changelog(repo_dir: Path, new_version: str, commit_message: str, old_content: str = "") -> None:
    """Update CHANGELOG.md with a new version entry, preserving old entries."""
    changelog_path = repo_dir / "CHANGELOG.md"
    current_date = datetime.now().strftime("%Y-%m-%d")

    new_entry = f"## [{new_version}] - {current_date}\n\n### Summary\n{commit_message}\n\n---\n\n"

    if old_content:
        match = re.search(r"^## \[", old_content, re.MULTILINE)
        if match:
            updated = new_entry + old_content[match.start():]
        else:
            updated = new_entry + old_content
    else:
        updated = f"# CHANGELOG\n\n{new_entry}"

    changelog_path.write_text(updated, encoding="utf-8")


def main() -> None:
    if len(sys.argv) < 2:
        print_color('錯誤: 請提供提交訊息', "red")
        print(f'使用方式: python3 {sys.argv[0]} "提交訊息"')
        sys.exit(1)

    commit_message = sys.argv[1]

    print_color("開始推送 .claude 資料夾到獨立 repo...")

    # 1. Find project root
    project_root = find_project_root()
    claude_dir = project_root / ".claude"

    # 2. Check uncommitted changes
    print_color("檢查 .claude 資料夾狀態...")
    result = run_git(["status", "--porcelain", ".claude"], cwd=str(project_root), check=False)
    if result.stdout.strip():
        print_color("警告: .claude 有未提交的變更", "red")
        print("請先提交到主專案，或使用 git add .claude")
        sys.exit(1)

    # 3. Clone remote repo (preserve history)
    print_color("Clone 遠端 repo（保留歷史）...")
    temp_dir = Path(tempfile.mkdtemp())
    try:
        run_git(["clone", REPO_URL, str(temp_dir)])

        # 4. Read remote version
        print_color("讀取遠端版本號...")
        version_file = temp_dir / "VERSION"
        if version_file.exists():
            remote_version = version_file.read_text(encoding="utf-8").strip()
            print_color(f"   遠端版本: v{remote_version}", "green")
        else:
            remote_version = "1.0.0"
            print_color("   遠端無版本檔案，使用預設 v1.0.0")

        # Save CHANGELOG content before cleaning
        changelog_path = temp_dir / "CHANGELOG.md"
        saved_changelog = changelog_path.read_text(encoding="utf-8") if changelog_path.exists() else ""

        # 5. Clean existing content (preserve .git)
        print_color("清空舊內容...")
        for item in temp_dir.iterdir():
            if item.name == ".git":
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()

        # 6. Copy .claude/ content with exclusions
        print_color("複製 .claude 配置檔案...")
        file_count = copy_filtered(claude_dir, temp_dir)
        print_color(f"   已複製 {file_count} 個檔案", "green")
        print_color("   注意: CLAUDE.md 不再同步（專案特定配置）")

        # 7. Calculate new version
        new_version = bump_patch_version(remote_version)
        (temp_dir / "VERSION").write_text(new_version + "\n", encoding="utf-8")

        # 8. Update CHANGELOG
        update_changelog(temp_dir, new_version, commit_message, saved_changelog)
        print_color(f"版本: v{new_version} (自動遞增)", "green")

        # 9. Commit and push
        commit_msg = f"v{new_version}: {commit_message}"
        print_color("提交變更...")
        run_git(["add", "-A"], cwd=str(temp_dir))

        # Check if there are actual changes
        diff_result = run_git(["diff", "--cached", "--quiet"], cwd=str(temp_dir), check=False)
        if diff_result.returncode == 0:
            print_color("沒有變更需要推送")
            return

        run_git(["commit", "-m", commit_msg], cwd=str(temp_dir))

        print_color("推送到獨立 repo...")
        run_git(["push", "origin", "main"], cwd=str(temp_dir))

        print_color("成功推送 .claude 到獨立 repo！", "green")
        print_color(f"Remote: {REPO_URL}", "green")
        print_color("遠端 commit 歷史已保留", "green")
        print_color("注意: 根目錄 CLAUDE.md 未被推送（專案特定配置）")

    except subprocess.TimeoutExpired:
        print_color("git 操作超時，請檢查網路連線", "red")
        sys.exit(1)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
