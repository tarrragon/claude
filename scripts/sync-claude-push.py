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

commit 訊息生成:
  - 無參數時自動分析 .claude/ 相關 commit 生成結構化摘要
  - 提供參數時使用用戶指定的訊息
  - 自動建議版本遞增幅度（patch/minor/major）
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path

REPO_URL = "https://github.com/tarrragon/claude.git"

EXCLUDE_PATTERNS = {
    "handoff",
    "hook-logs",
    "PM_INTERVENTION_REQUIRED",
    "ARCHITECTURE_REVIEW_REQUIRED",
    "pm-status.json",
    "__pycache__",
    ".pytest_cache",
    "sync-preserve.yaml",
}

EXCLUDE_SUFFIXES = {".pyc"}

# commit 訊息中需要過濾的專案特定模式
# 獨立 repo 是跨專案通用框架，commit 訊息禁止包含專案版本號/Wave/Ticket 編號
PROJECT_SPECIFIC_PATTERNS = [
    r"\b\d+\.\d+\.\d+-W\d+-\d+\b",  # Ticket ID: 0.2.0-W5-014
    r"\bW\d+-\d+\b",                  # 短格式 Ticket: W5-014
    r"\bv\d+\.\d+\.\d+\b",           # 版本號: v0.2.0
    r"\bWave\s*\d+\b",               # Wave 5
    r"\b0\.\d+\.\d+\b",              # 裸版本: 0.2.0
]

# commit type 分類對應的版本遞增建議
VERSION_BUMP_WEIGHTS = {
    "feat": "minor",
    "refactor": "minor",
    "fix": "patch",
    "docs": "patch",
    "chore": "patch",
    "style": "patch",
    "test": "patch",
    "perf": "minor",
}


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


def strip_project_specific_info(text: str) -> str:
    """Remove project-specific info (Ticket IDs, version numbers, Wave refs) from text.

    The independent repo is a cross-project framework.
    Commit messages must focus on framework functionality, not project-specific progress.
    """
    result = text
    for pattern in PROJECT_SPECIFIC_PATTERNS:
        result = re.sub(pattern, "", result)
    # Clean up leftover artifacts: multiple spaces, trailing colons, empty parens
    result = re.sub(r"\(\s*\)", "", result)
    result = re.sub(r":\s*$", "", result, flags=re.MULTILINE)
    result = re.sub(r"  +", " ", result)
    return result.strip()


def parse_commit_type(subject: str) -> tuple[str, str]:
    """Parse conventional commit subject into (type, description).

    Returns (type, description) where type is feat/fix/refactor/docs/chore/etc.
    If no conventional prefix, returns ("other", full_subject).
    """
    match = re.match(r"^(\w+)(?:\([^)]*\))?:\s*(.+)", subject)
    if match:
        return match.group(1).lower(), match.group(2).strip()
    return "other", subject.strip()


def get_last_sync_timestamp(remote_repo_dir: str) -> str | None:
    """Get the timestamp of the latest commit in the remote repo.

    This represents when the last sync-push happened.
    """
    result = run_git(
        ["log", "-1", "--format=%aI"],
        cwd=remote_repo_dir,
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return None


def collect_claude_commits(project_root: str, since: str | None) -> list[str]:
    """Collect commit subjects that touch .claude/ since the given timestamp.

    Returns list of commit subject lines.
    """
    args = ["log", "--format=%s", "--no-merges", "--", ".claude/"]
    if since:
        args.insert(2, f"--since={since}")
    result = run_git(args, cwd=project_root, check=False)
    if result.returncode != 0 or not result.stdout.strip():
        return []
    return [line for line in result.stdout.strip().split("\n") if line.strip()]


def categorize_commits(subjects: list[str]) -> dict[str, list[str]]:
    """Categorize commit subjects by conventional commit type.

    Returns dict mapping type -> list of descriptions.
    """
    categories: dict[str, list[str]] = defaultdict(list)
    for subject in subjects:
        commit_type, description = parse_commit_type(subject)
        cleaned = strip_project_specific_info(description)
        if cleaned:
            categories[commit_type].append(cleaned)
    return dict(categories)


def suggest_version_bump(categories: dict[str, list[str]]) -> str:
    """Suggest version bump level based on commit types.

    Returns "major", "minor", or "patch".
    """
    has_minor = False
    for commit_type in categories:
        bump = VERSION_BUMP_WEIGHTS.get(commit_type, "patch")
        if bump == "major":
            return "major"
        if bump == "minor":
            has_minor = True
    return "minor" if has_minor else "patch"


def generate_commit_summary(categories: dict[str, list[str]], bump_suggestion: str) -> str:
    """Generate a structured commit message from categorized commits.

    The first line is always a descriptive summary suitable for git commit subject.
    Additional detail lines follow after a blank line.
    """
    display_order = ["feat", "refactor", "fix", "docs", "chore", "style", "test", "perf", "other"]

    # Collect all unique descriptions with their types, preserving order
    all_items: list[tuple[str, str]] = []
    for t in display_order:
        if t not in categories:
            continue
        for desc in dict.fromkeys(categories[t]):
            all_items.append((t, desc))

    total_count = len(all_items)

    # First line: descriptive summary (not just counts)
    # Few commits (1-3): list actual descriptions joined by "; "
    # Many commits (4+): highlight top items with count context
    MAX_SUBJECT_ITEMS = 3
    if total_count <= MAX_SUBJECT_ITEMS:
        subject_parts = [f"{t}: {desc}" for t, desc in all_items]
        summary_line = "; ".join(subject_parts)
    else:
        # Show first few items + count of remaining
        shown_parts = [f"{t}: {desc}" for t, desc in all_items[:MAX_SUBJECT_ITEMS]]
        remaining = total_count - MAX_SUBJECT_ITEMS
        summary_line = "; ".join(shown_parts) + f" (+{remaining} more)"

    # Build detail lines for body (all items)
    details: list[str] = []
    for t, desc in all_items:
        details.append(f"- {t}: {desc}")

    # Stats line for context
    type_counts = []
    for t in display_order:
        if t in categories:
            type_counts.append(f"{len(categories[t])} {t}")
    stats = ", ".join(type_counts)

    body_parts = [f"Changes: {stats}"]
    if details:
        body_parts.append("")
        body_parts.extend(details)

    return f"{summary_line}\n\n" + "\n".join(body_parts)


def bump_version(version: str, bump_level: str) -> str:
    """Increment version based on bump level (major/minor/patch)."""
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", version)
    if not match:
        return "1.0.1"
    major, minor, patch = int(match.group(1)), int(match.group(2)), int(match.group(3))
    if bump_level == "major":
        return f"{major + 1}.0.0"
    if bump_level == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def bump_patch_version(version: str) -> str:
    """Increment the patch version number."""
    return bump_version(version, "patch")


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
    # commit message is now optional - auto-generated when not provided
    user_message = sys.argv[1] if len(sys.argv) >= 2 else None

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

        # 5. Auto-analyze commits since last sync
        bump_suggestion = "patch"
        if user_message:
            commit_message = user_message
            print_color(f"使用用戶指定的 commit 訊息: {commit_message}")
        else:
            print_color("分析自上次推送以來的 .claude/ 變更...")
            last_sync = get_last_sync_timestamp(str(temp_dir))
            if last_sync:
                print_color(f"   上次推送時間: {last_sync}", "green")

            subjects = collect_claude_commits(str(project_root), last_sync)
            if subjects:
                print_color(f"   找到 {len(subjects)} 個相關 commit", "green")
                categories = categorize_commits(subjects)
                bump_suggestion = suggest_version_bump(categories)
                commit_message = generate_commit_summary(categories, bump_suggestion)
                print_color("--- 自動生成的 commit 摘要 ---")
                print(commit_message)
                print_color("--- 摘要結束 ---")
            else:
                print_color("   未找到新的 .claude/ commit，使用預設訊息")
                commit_message = "sync .claude configuration"

        # Save CHANGELOG content before cleaning
        changelog_path = temp_dir / "CHANGELOG.md"
        saved_changelog = changelog_path.read_text(encoding="utf-8") if changelog_path.exists() else ""

        # 6. Merge 模式：不清空遠端內容，直接增量覆蓋
        # 保留遠端獨有的檔案（其他專案推送的內容）

        # 7. Copy .claude/ content with exclusions（覆蓋本地有修改的檔案）
        print_color("複製 .claude 配置檔案...")
        file_count = copy_filtered(claude_dir, temp_dir)
        print_color(f"   已複製 {file_count} 個檔案", "green")
        print_color("   注意: CLAUDE.md 不再同步（專案特定配置）")

        # 8. Calculate new version (use bump suggestion for auto-generated messages)
        new_version = bump_version(remote_version, bump_suggestion)
        (temp_dir / "VERSION").write_text(new_version + "\n", encoding="utf-8")

        # 9. Update CHANGELOG (use full commit message for detailed history)
        update_changelog(temp_dir, new_version, commit_message, saved_changelog)
        print_color(f"版本: v{new_version} ({bump_suggestion} bump)", "green")

        # 10. Commit and push
        # For git commit, use only the summary line to keep it clean
        commit_summary = commit_message.split("\n")[0] if "\n" in commit_message else commit_message
        commit_msg = f"v{new_version}: {commit_summary}"
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
