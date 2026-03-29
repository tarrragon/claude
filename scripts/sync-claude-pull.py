#!/usr/bin/env python3
"""
.claude 資料夾同步腳本 - 從獨立 repo 拉取更新

跨平台支援：macOS / Linux / Windows
依賴：Python 3.8+, git

拉取內容:
  - .claude/ 目錄所有檔案（同步覆蓋 + 清理遠端已刪除的檔案）
  - FLUTTER.md（若遠端 project-templates 中存在）

不覆蓋內容:
  - 根目錄 CLAUDE.md（保留專案特定配置）
  - .claude/hook-logs/（本地日誌）
  - .claude/handoff/（本地交接檔案）
"""

import filecmp
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

# ============================================================================
# Constants
# ============================================================================

REPO_URL = "https://github.com/tarrragon/claude.git"

# Git clone timeout protection (in seconds)
GIT_CLONE_TIMEOUT_SECONDS = 120
GIT_HTTP_LOW_SPEED_LIMIT_BYTES = "1000"
GIT_HTTP_LOW_SPEED_TIME_SECONDS = "30"

# Changed files display limit
MAX_CHANGED_FILES_DISPLAY = 3

# 遠端 repo 專有：存在於遠端但不需複製到本地
REMOTE_ONLY = frozenset({".git", "project-templates"})

# 本地專有：只存在於本地，同步時不刪除也不覆蓋
LOCAL_ONLY = frozenset({
    "hook-logs",
    "handoff",
    "PM_INTERVENTION_REQUIRED",
    "ARCHITECTURE_REVIEW_REQUIRED",
    "pm-status.json",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "sync-preserve.yaml",  # 各專案的 preserve 清單不同，不可被遠端覆蓋
})

# 同步時跳過的所有路徑（合併使用）
SKIP_DURING_SYNC = REMOTE_ONLY | LOCAL_ONLY


def load_preserve_list(claude_dir: Path) -> set[str]:
    """讀取 sync-preserve.yaml 中的本地特化檔案清單。

    若檔案不存在或無法解析，回傳空集合（向下相容）。

    參數:
        claude_dir: .claude 目錄路徑

    傳回:
        set[str]: 需要保留的相對路徑集合（相對於 .claude/）
    """
    preserve_file = claude_dir / "sync-preserve.yaml"
    if not preserve_file.exists():
        return set()

    content = preserve_file.read_text(encoding="utf-8")

    # 嘗試使用 PyYAML，若未安裝則用簡易解析
    if yaml is not None:
        try:
            data = yaml.safe_load(content)
            if isinstance(data, dict) and isinstance(data.get("preserve"), list):
                return set(data["preserve"])
        except Exception:
            pass
        return set()

    # 簡易 fallback 解析：讀取 "- path" 格式的行
    paths: set[str] = set()
    in_preserve = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        if stripped == "preserve:":
            in_preserve = True
            continue
        if in_preserve and stripped.startswith("- "):
            paths.add(stripped[2:].strip())
        elif stripped and not stripped.startswith("#"):
            # 只有非空、非註解的行才關閉 preserve 區塊
            in_preserve = False
        # 空行和註解行不影響 in_preserve 狀態
    return paths


def print_color(msg: str, color: str = "yellow") -> None:
    """輸出彩色訊息到標準輸出。

    使用 ANSI 顏色代碼，在 Windows 無終端環境下自動降級為無色輸出。

    參數:
        msg: 要輸出的訊息文字
        color: 顏色名稱，支援 "green"、"yellow"、"red"，預設為 "yellow"

    異常:
        無，異常情況會自動降級處理
    """
    colors = {"green": "\033[0;32m", "yellow": "\033[1;33m", "red": "\033[0;31m"}
    nc = "\033[0m"
    if sys.platform == "win32" and not os.environ.get("TERM"):
        print(msg)
    else:
        print(f"{colors.get(color, '')}{msg}{nc}")


def run_git(args: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    """執行 git 命令並回傳結果。

    以子流程方式執行 git 命令，捕獲標準輸出和標準錯誤，
    結果以文字格式儲存在 CompletedProcess 物件中。

    參數:
        args: git 命令的引數清單（不包含 "git" 本身）
        cwd: 執行命令的工作目錄，預設為 None（使用目前工作目錄）

    傳回:
        subprocess.CompletedProcess: 包含 returncode、stdout、stderr 的結果物件
    """
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def find_project_root() -> Path:
    """向上尋找專案根目錄。

    從目前工作目錄開始，逐層向上尋找 .claude 目錄。
    若找不到，輸出錯誤訊息並終止程式。

    傳回:
        Path: 專案根目錄路徑（包含 .claude 的目錄）

    異常:
        呼叫 sys.exit(1)，如果找不到 .claude 目錄則終止程式
    """
    current = Path.cwd()
    while current != current.parent:
        if (current / ".claude").is_dir():
            return current
        current = current.parent
    print_color("找不到 .claude 目錄，請在專案根目錄執行此腳本", "red")
    sys.exit(1)


def check_uncommitted_changes(project_root: Path) -> None:
    """檢查 .claude 的未提交變更。

    執行 git diff 檢查工作目錄和暫存區是否有未提交的變更。
    若發現變更則輸出警告訊息並終止程式，防止同步時發生衝突。

    參數:
        project_root: 專案根目錄路徑

    異常:
        呼叫 sys.exit(1)，若有未提交變更或 git 命令失敗則終止程式
    """
    result = run_git(
        ["diff", "--name-only", "--", ".claude"],
        cwd=str(project_root),
    )
    cached = run_git(
        ["diff", "--cached", "--name-only", "--", ".claude"],
        cwd=str(project_root),
    )
    if result.returncode != 0 or cached.returncode != 0:
        print_color("警告: git diff 執行失敗，請確認 git 狀態正常", "red")
        sys.exit(1)
    has_changes = bool(result.stdout.strip() or cached.stdout.strip())
    if has_changes:
        print_color("警告: .claude 有未提交的變更", "red")
        print("請先提交或暫存變更，避免衝突")
        sys.exit(1)


def clone_repo(temp_dir: Path) -> None:
    """從遠端 repo 克隆最新版本到臨時目錄。

    使用淺層克隆（--depth 1）並設定超時保護和低速限制。
    若克隆失敗則輸出錯誤訊息並終止程式。

    參數:
        temp_dir: 臨時目錄路徑，克隆內容將放置於此

    異常:
        subprocess.TimeoutExpired: 若克隆超過設定的超時時間
        呼叫 sys.exit(1)，若克隆命令失敗則終止程式
    """
    env = os.environ.copy()
    env["GIT_HTTP_LOW_SPEED_LIMIT"] = GIT_HTTP_LOW_SPEED_LIMIT_BYTES
    env["GIT_HTTP_LOW_SPEED_TIME"] = GIT_HTTP_LOW_SPEED_TIME_SECONDS

    result = subprocess.run(
        ["git", "clone", "--depth", "1", REPO_URL, str(temp_dir)],
        capture_output=True,
        text=True,
        env=env,
        timeout=GIT_CLONE_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        print_color(f"git clone 失敗: {result.stderr}", "red")
        sys.exit(1)


def sync_directory(
    src: Path,
    dst: Path,
    preserve: set[str] | None = None,
    prefix: Path = Path(),
) -> int:
    """增量同步來源目錄到目標目錄。

    遞迴地同步檔案和目錄，跳過排除清單中的項目和符號連結。
    對於已存在的目錄進行增量同步，對於新目錄則整體複製。
    在 preserve 清單中的檔案不會被覆蓋。

    參數:
        src: 來源目錄路徑
        dst: 目標目錄路徑
        preserve: 需要保留的本地特化檔案相對路徑集合
        prefix: 目前遞迴的相對路徑前綴

    傳回:
        int: 更新或複製的檔案總數

    說明:
        - 跳過 SKIP_DURING_SYNC 清單中的目錄和檔案
        - 跳過所有符號連結
        - 跳過 preserve 清單中的本地特化檔案
        - 保留檔案的修改時間戳（使用 shutil.copy2）
    """
    if preserve is None:
        preserve = set()
    count = 0
    for item in src.iterdir():
        if item.name in SKIP_DURING_SYNC:
            continue
        if item.is_symlink():
            continue

        rel = prefix / item.name
        dest_item = dst / item.name
        if item.is_dir():
            if dest_item.exists():
                count += sync_directory(item, dest_item, preserve, rel)
            else:
                shutil.copytree(item, dest_item, symlinks=False,
                                ignore=shutil.ignore_patterns(*SKIP_DURING_SYNC))
                count += sum(1 for f in dest_item.rglob("*") if f.is_file())
        else:
            rel_str = str(rel).replace("\\", "/")
            if rel_str in preserve:
                if not dest_item.exists():
                    print_color(f"   本地特化檔案不存在（可能已刪除）: {rel_str}", "yellow")
                else:
                    try:
                        if not filecmp.cmp(str(item), str(dest_item), shallow=False):
                            print_color(f"   本地特化檔案有遠端更新可用: {rel_str}", "yellow")
                        else:
                            print_color(f"   保留本地特化檔案: {rel_str}", "green")
                    except (FileNotFoundError, OSError):
                        print_color(f"   警告: 無法比對檔案 {rel_str}", "yellow")
                continue
            dest_item.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest_item)
            count += 1
    return count


def collect_remote_files(src: Path, prefix: Path = Path()) -> set[Path]:
    """遞迴蒐集遠端 repo 中所有檔案的相對路徑。

    跳過排除清單中的項目和符號連結，返回所有檔案的相對路徑集合，
    用於後續的過時檔案清理工作。

    參數:
        src: 來源目錄路徑
        prefix: 相對於起始目錄的路徑前綴，用於遞迴調用

    傳回:
        set[Path]: 所有檔案的相對路徑集合
    """
    files: set[Path] = set()
    for item in src.iterdir():
        if item.name in SKIP_DURING_SYNC:
            continue
        if item.is_symlink():
            continue
        rel = prefix / item.name
        if item.is_dir():
            files.update(collect_remote_files(item, rel))
        else:
            files.add(rel)
    return files


def cleanup_stale_files(
    claude_dir: Path,
    remote_files: set[Path],
    preserve: set[str] | None = None,
) -> list[str]:
    """移除本地有但遠端 repo 中不存在的過時檔案。

    在 preserve 清單中的檔案不會被刪除。

    傳回:
        list[str]: 已移除的檔案路徑清單（相對於 claude_dir）
    """
    if preserve is None:
        preserve = set()
    removed: list[str] = []

    def _walk(directory: Path, prefix: Path = Path()) -> None:
        """遞迴走訪目錄，移除不存在於遠端 repo 中的過時檔案。

        跳過排除清單中的項目、符號連結和 preserve 清單中的檔案。
        對於空目錄在清理後自動刪除。

        參數:
            directory: 目前走訪的目錄路徑
            prefix: 相對於 claude_dir 的路徑前綴
        """
        if not directory.exists():
            return
        for item in sorted(directory.iterdir()):
            if item.name in SKIP_DURING_SYNC:
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
                rel_str = str(rel).replace("\\", "/")
                if rel_str in preserve:
                    print_color(f"   保留本地特化檔案: {rel_str}", "green")
                    continue
                item.unlink()
                removed.append(str(rel))

    _walk(claude_dir)
    return removed


def detect_changed_packages(project_root: Path) -> None:
    """偵測 .claude/skills/*/pyproject.toml 的變更檔案。

    使用 git diff --name-only 避免 glob pathspec 問題，改由 Python 端過濾檔案。

    使用三層 fallback 策略：
    1. origin/HEAD...HEAD（標準情況）
    2. HEAD~1...HEAD（無 origin/HEAD 時）
    3. HEAD（最後手段）

    不會中止主流程，僅記錄警告。
    """
    changed_pyproject_files = []

    # Try git diff --name-only with fallback strategy
    # 使用 --name-only 取得變更檔案列表，避免 glob 被 shell 展開
    git_commands = [
        ["diff", "--name-only", "origin/HEAD...HEAD"],
        ["diff", "--name-only", "HEAD~1...HEAD"],
        ["diff", "--name-only", "HEAD"],
    ]

    for git_args in git_commands:
        result = run_git(git_args, cwd=str(project_root))
        if result.returncode == 0:
            # 解析檔案列表並過濾 .claude/skills/*/pyproject.toml
            for line in result.stdout.splitlines():
                line = line.strip()
                # 篩選符合模式的檔案
                if ".claude/skills/" in line and "pyproject.toml" in line:
                    changed_pyproject_files.append(line)
            break  # Found a working git command
    else:
        # All git commands failed
        print_color("   提示: 無法執行 git diff，跳過套件版本檢查", "yellow")
        return

    if not changed_pyproject_files:
        print_color("   無套件版本變更", "green")
        return

    print_color(f"   偵測到 {len(changed_pyproject_files)} 個套件版本變更", "yellow")

    # For now, we only log the detection
    # The actual reinstallation will happen when the hook runs
    for file_path in changed_pyproject_files[:MAX_CHANGED_FILES_DISPLAY]:
        print_color(f"     - {file_path}")
    if len(changed_pyproject_files) > MAX_CHANGED_FILES_DISPLAY:
        print_color(f"     ... 及 {len(changed_pyproject_files) - MAX_CHANGED_FILES_DISPLAY} 個檔案")

    print_color("   套件將在下次 SessionStart 自動重新安裝", "green")


def _sync_with_backup(project_root: Path, temp_dir: Path) -> Path:
    """執行備份和同步操作。

    備份當前配置，然後同步遠端更新至本地。
    返回備份目錄路徑。

    參數:
        project_root: 專案根目錄
        temp_dir: 臨時目錄（含遠端 repo 內容）

    傳回:
        backup_dir: 備份目錄路徑
    """
    claude_dir = project_root / ".claude"

    # 備份當前配置
    print_color("備份當前配置...")
    backup_dir = Path(tempfile.mkdtemp(prefix="claude-backup-"))
    shutil.copytree(claude_dir, backup_dir / ".claude")
    flutter_md = project_root / "FLUTTER.md"
    if flutter_md.exists():
        shutil.copy2(flutter_md, backup_dir / "FLUTTER.md")

    # 載入本地特化檔案清單
    preserve = load_preserve_list(claude_dir)
    if preserve:
        print_color(f"   載入 {len(preserve)} 個本地特化檔案路徑", "green")

    # 同步 .claude 目錄
    print_color("更新 .claude 資料夾...")
    remote_files = collect_remote_files(temp_dir)
    file_count = sync_directory(temp_dir, claude_dir, preserve)
    print_color(f"   已更新 {file_count} 個檔案", "green")

    # 清理過時檔案
    removed = cleanup_stale_files(claude_dir, remote_files, preserve)
    if removed:
        print_color(f"   已清理 {len(removed)} 個過時檔案:", "green")
        for r in removed:
            print_color(f"     - {r}")
    else:
        print_color("   無過時檔案需清理", "green")

    # 偵測套件版本變更
    print_color("檢查套件版本變更...")
    detect_changed_packages(project_root)

    return backup_dir


def _update_project_templates(temp_dir: Path, project_root: Path) -> None:
    """更新專案模板檔案。

    從遠端 repo 的 project-templates 目錄更新 FLUTTER.md。
    不覆蓋根目錄的 CLAUDE.md（保留專案特定配置）。

    參數:
        temp_dir: 臨時目錄（含遠端 repo 內容）
        project_root: 專案根目錄
    """
    templates_dir = temp_dir / "project-templates"
    if templates_dir.is_dir():
        print_color("更新專案模板檔案...")
        src_flutter = templates_dir / "FLUTTER.md"
        if src_flutter.exists():
            shutil.copy2(src_flutter, project_root / "FLUTTER.md")
            print_color("   已更新 FLUTTER.md", "green")
        print_color("   注意: CLAUDE.md 未被覆蓋（保留專案特定配置）")


def _finalize_sync(backup_dir: Path) -> None:
    """完成同步並輸出提示訊息。

    顯示成功訊息、備份位置和初始化提示。

    參數:
        backup_dir: 備份目錄路徑
    """
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


def _validate_environment(project_root: Path) -> None:
    """驗證專案環境和本地狀態。

    檢查專案根目錄有效性和本地未提交變更。若檢查失敗則終止程式。

    參數:
        project_root: 專案根目錄路徑

    異常:
        呼叫 sys.exit(1)，若檢查失敗則終止程式
    """
    print_color("檢查本地狀態...", "yellow")
    check_uncommitted_changes(project_root)


def _clone_and_backup(project_root: Path) -> tuple[Path, Path]:
    """克隆遠端 repo 並執行備份和同步。

    建立臨時目錄、克隆遠端 repo、執行備份和同步操作。
    返回臨時目錄和備份目錄路徑。

    參數:
        project_root: 專案根目錄路徑

    傳回:
        tuple[Path, Path]: (臨時目錄路徑, 備份目錄路徑)

    異常:
        subprocess.TimeoutExpired: 若克隆超過設定的超時時間
    """
    print_color("從獨立 repo 拉取更新...", "yellow")
    temp_dir = Path(tempfile.mkdtemp())
    clone_repo(temp_dir)
    backup_dir = _sync_with_backup(project_root, temp_dir)
    return temp_dir, backup_dir


def _complete_sync(temp_dir: Path, project_root: Path, backup_dir: Path) -> None:
    """完成同步：更新專案模板和輸出結果。

    更新專案模板檔案、清理臨時目錄、輸出完成訊息。

    參數:
        temp_dir: 臨時目錄路徑
        project_root: 專案根目錄路徑
        backup_dir: 備份目錄路徑
    """
    _update_project_templates(temp_dir, project_root)
    shutil.rmtree(temp_dir, ignore_errors=True)
    _finalize_sync(backup_dir)


def main() -> None:
    """同步 .claude 配置從獨立 repo。

    主要流程：
    1. 找出專案根目錄
    2. 驗證環境和本地狀態
    3. 克隆遠端 repo 並執行備份同步
    4. 完成同步（更新模板、清理、輸出結果）
    """
    print_color("開始從獨立 repo 拉取 .claude 更新...")

    project_root = find_project_root()
    _validate_environment(project_root)

    try:
        temp_dir, backup_dir = _clone_and_backup(project_root)
        _complete_sync(temp_dir, project_root, backup_dir)
    except subprocess.TimeoutExpired:
        print_color(f"git clone 超時（{GIT_CLONE_TIMEOUT_SECONDS} 秒），請檢查網路連線", "red")
        sys.exit(1)


if __name__ == "__main__":
    main()
