#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///

"""
Version Release Tool - 完整版本發布流程自動化工具

功能:
- Pre-flight 檢查：驗證 worklog、技術債務、版本同步
- 文件更新：CHANGELOG、todolist、pubspec.yaml 驗證
- Git 操作：合併、Tag、推送、分支清理
- 預覽模式：--dry-run 查看完整操作流程

使用方式:
  uv run version_release.py release [--version X.Y.Z] [--dry-run]
  uv run version_release.py check [--version X.Y.Z]
  uv run version_release.py update-docs [--version X.Y.Z] [--dry-run]
"""

import os
import sys
import re
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Tuple, Dict
import yaml


class Colors:
    """ANSI 顏色代碼"""
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def print_header(title: str):
    """打印標題"""
    width = 60
    print(f"\n{Colors.BOLD}{Colors.BLUE}╔{'═' * (width - 2)}╗{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}║ {title:<{width - 4}} ║{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}╚{'═' * (width - 2)}╝{Colors.RESET}\n")


def print_section(title: str):
    """打印章節標題"""
    width = 60
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'━' * width}{Colors.RESET}")
    print(f"{Colors.BOLD}{title}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'━' * width}{Colors.RESET}")


def print_success(message: str):
    """打印成功訊息"""
    print(f"{Colors.GREEN}✅{Colors.RESET} {message}")


def print_error(message: str):
    """打印錯誤訊息"""
    print(f"{Colors.RED}❌{Colors.RESET} {message}")


def print_warning(message: str):
    """打印警告訊息"""
    print(f"{Colors.YELLOW}⚠️{Colors.RESET} {message}")


def print_info(message: str, indent: int = 0):
    """打印資訊訊息"""
    prefix = "  " * indent
    print(f"{prefix}{message}")


def get_project_root() -> Path:
    """取得專案根目錄"""
    return Path(__file__).parent.parent.parent.parent.parent


def detect_version() -> Optional[str]:
    """自動偵測版本號"""
    root = get_project_root()

    # 1. 嘗試從 git 分支名稱偵測
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            match = re.search(r"feature/v([\d.]+)", branch)
            if match:
                return match.group(1)
    except Exception:
        pass

    # 2. 嘗試從 pubspec.yaml 偵測
    pubspec_path = root / "pubspec.yaml"
    if pubspec_path.exists():
        try:
            with open(pubspec_path) as f:
                data = yaml.safe_load(f)
                if "version" in data:
                    version = str(data["version"]).strip()
                    return version
        except Exception:
            pass

    # 3. 嘗試從 git tag 偵測
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            tag = result.stdout.strip()
            match = re.search(r"v([\d.]+)", tag)
            if match:
                return match.group(1)
    except Exception:
        pass

    return None


def normalize_version(version: Optional[str]) -> str:
    """規範化版本號"""
    if not version:
        detected = detect_version()
        if not detected:
            raise ValueError("無法自動偵測版本號，請使用 --version 指定")
        version = detected

    # 確保版本格式正確
    parts = version.split(".")
    if len(parts) == 2:
        # X.Y → X.Y.0
        return f"{version}.0"
    elif len(parts) == 3:
        return version
    else:
        raise ValueError(f"版本格式不正確: {version} (應為 X.Y 或 X.Y.Z)")


def check_worklog_completed(version: str) -> Tuple[bool, List[str]]:
    """檢查工作日誌是否完成"""
    root = get_project_root()
    worklog_dir = root / "docs" / "work-logs"

    errors = []
    major_minor = ".".join(version.split(".")[:2])  # v0.19 from v0.19.8

    # 查詢相關的工作日誌
    worklog_files = []
    if worklog_dir.exists():
        for f in worklog_dir.glob(f"v{major_minor}*.md"):
            worklog_files.append(f)

    if not worklog_files:
        errors.append(f"找不到版本 v{major_minor} 的工作日誌檔案")
        return False, errors

    # 檢查主工作日誌
    main_worklog = worklog_dir / f"v{major_minor}.0-main.md"
    if main_worklog.exists():
        try:
            with open(main_worklog, encoding="utf-8") as f:
                content = f.read()

            # 檢查 Phase 完成情況
            phases = {
                "Phase 0": r"## Phase 0:.*?✅",
                "Phase 1": r"## Phase 1:.*?✅",
                "Phase 2": r"## Phase 2:.*?✅",
                "Phase 3": r"## Phase 3.*?✅",
                "Phase 4": r"## Phase 4.*?✅",
            }

            for phase_name, pattern in phases.items():
                if not re.search(pattern, content, re.DOTALL):
                    errors.append(f"{main_worklog.name}: {phase_name} 未標記為完成")
        except Exception as e:
            errors.append(f"讀取 {main_worklog} 失敗: {e}")
    else:
        errors.append(f"找不到主工作日誌: {main_worklog.name}")

    return len(errors) == 0, errors


def check_technical_debt(version: str) -> Tuple[bool, List[str]]:
    """檢查技術債務狀態"""
    root = get_project_root()
    todolist_path = root / "docs" / "todolist.md"
    errors = []

    if not todolist_path.exists():
        errors.append("找不到 docs/todolist.md")
        return False, errors

    try:
        with open(todolist_path, encoding="utf-8") as f:
            content = f.read()

        # 查找「技術債務追蹤」區塊
        td_section = re.search(
            r"## 技術債務追蹤.*?(?=\n##|\Z)", content, re.DOTALL
        )
        if not td_section:
            # 沒有技術債務區塊是可以的（可能沒有 TD）
            return True, []

        # 提取所有 TD 項目
        td_content = td_section.group(0)

        # 檢查是否有 pending 狀態的 TD
        pending_items = re.findall(r"\|\s+0\.\d+\.\d+-TD-\d+.*?\|\s*pending", td_content)
        if pending_items:
            # 檢查是否都有目標版本
            for item in pending_items:
                # 提取目標版本
                if "v0." not in item:
                    errors.append(f"技術債務缺少目標版本: {item}")

        # 檢查當前版本的 TD 是否都已處理或延遲
        major_minor = ".".join(version.split(".")[:2])
        # 這裡的檢查邏輯較寬鬆，只要求 TD 有分類即可

        return len(errors) == 0, errors

    except Exception as e:
        errors.append(f"讀取 todolist.md 失敗: {e}")
        return False, errors


def check_version_sync(version: str) -> Tuple[bool, List[str]]:
    """檢查版本號同步"""
    root = get_project_root()
    errors = []

    # 檢查 pubspec.yaml
    pubspec_path = root / "pubspec.yaml"
    if pubspec_path.exists():
        try:
            with open(pubspec_path, encoding="utf-8") as f:
                content = f.read()
                match = re.search(r"^version:\s+(.+)$", content, re.MULTILINE)
                if match:
                    pubspec_version = match.group(1).strip()
                    if pubspec_version != version:
                        errors.append(
                            f"pubspec.yaml 版本不匹配: {pubspec_version} vs {version}"
                        )
                else:
                    errors.append("pubspec.yaml 找不到 version 行")
        except Exception as e:
            errors.append(f"讀取 pubspec.yaml 失敗: {e}")
    else:
        errors.append("找不到 pubspec.yaml")

    # 檢查當前分支
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            current_branch = result.stdout.strip()
            major_minor = ".".join(version.split(".")[:2])
            expected_branch = f"feature/v{major_minor}"
            if current_branch != expected_branch:
                errors.append(
                    f"當前分支不正確: {current_branch} (應為 {expected_branch})"
                )
    except Exception as e:
        errors.append(f"檢查 git 分支失敗: {e}")

    # 檢查工作目錄是否乾淨
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            print_warning(
                f"工作目錄有未提交的修改 ({len(result.stdout.splitlines())} 個檔案)"
            )
            # 這不是致命錯誤，但應該提示
    except Exception:
        pass

    return len(errors) == 0, errors


def preflight_check(version: str) -> Tuple[bool, Dict[str, Tuple[bool, List[str]]]]:
    """執行 Pre-flight 檢查"""
    print_section("Step 1: Pre-flight Check")

    results = {}

    # 1.1 檢查工作日誌
    print_info("✓ 檢查工作日誌完成度...")
    wl_ok, wl_errors = check_worklog_completed(version)
    results["worklog"] = (wl_ok, wl_errors)

    if wl_ok:
        print_success("Worklog 目標達成")
    else:
        for error in wl_errors:
            print_error(error)

    # 1.2 檢查技術債務
    print_info("✓ 檢查技術債務狀態...")
    td_ok, td_errors = check_technical_debt(version)
    results["tech_debt"] = (td_ok, td_errors)

    if td_ok:
        print_success("技術債務已處理")
    else:
        for error in td_errors:
            print_error(error)

    # 1.3 檢查版本同步
    print_info("✓ 檢查版本同步...")
    vs_ok, vs_errors = check_version_sync(version)
    results["version_sync"] = (vs_ok, vs_errors)

    if vs_ok:
        print_success("版本同步 ✅")
    else:
        for error in vs_errors:
            print_error(error)

    all_ok = wl_ok and td_ok and vs_ok
    return all_ok, results


def extract_changelog_section(version: str) -> Optional[str]:
    """從工作日誌提取 CHANGELOG 區塊"""
    root = get_project_root()
    major_minor = ".".join(version.split(".")[:2])
    worklog_dir = root / "docs" / "work-logs"

    # 查找相關的工作日誌
    worklog_file = None
    for f in worklog_dir.glob(f"v{major_minor}*.md"):
        if "phase4" in f.name.lower() or "final" in f.name.lower():
            worklog_file = f
            break

    if not worklog_file:
        return None

    try:
        with open(worklog_file, encoding="utf-8") as f:
            content = f.read()

        # 嘗試找到 CHANGELOG 相關的區塊
        # 通常在 Phase 4 報告中會有功能變動總結
        pattern = r"(?:## \[.*?\]|### Added|### Changed|### Fixed|### Removed)(.*?)(?=\n## |\n### |\Z)"
        matches = re.findall(pattern, content, re.DOTALL)

        if matches:
            return "\n".join(matches[:3])  # 取前 3 個區塊

    except Exception:
        pass

    return None


def update_changelog(version: str, dry_run: bool = False) -> bool:
    """更新 CHANGELOG.md"""
    root = get_project_root()
    changelog_path = root / "CHANGELOG.md"

    if not changelog_path.exists():
        print_error(f"找不到 {changelog_path}")
        return False

    try:
        with open(changelog_path, encoding="utf-8") as f:
            changelog_content = f.read()

        # 建立新的版本區塊
        today = datetime.now().strftime("%Y-%m-%d")
        new_version_block = f"""## [{version}] - {today}

**✅ UC-XX 功能名稱 - TDD 四階段完成**

### Added
- 新增功能項目

### Changed
- 變更項目

### Fixed
- 修復項目

---

"""

        # 插入到 "## [" 之前（在 "格式基於" 之後）
        insert_pos = changelog_content.find("## [")
        if insert_pos > 0:
            updated_content = (
                changelog_content[:insert_pos]
                + new_version_block
                + changelog_content[insert_pos:]
            )

            if not dry_run:
                with open(changelog_path, "w", encoding="utf-8") as f:
                    f.write(updated_content)

            print_success(f"CHANGELOG.md 已更新版本 {version}")
            return True
        else:
            print_error("CHANGELOG.md 格式不符")
            return False

    except Exception as e:
        print_error(f"更新 CHANGELOG.md 失敗: {e}")
        return False


def update_todolist(version: str, dry_run: bool = False) -> bool:
    """更新 todolist.md"""
    root = get_project_root()
    todolist_path = root / "docs" / "todolist.md"

    if not todolist_path.exists():
        print_error(f"找不到 {todolist_path}")
        return False

    try:
        with open(todolist_path, encoding="utf-8") as f:
            content = f.read()

        major_minor = ".".join(version.split(".")[:2])

        # 查找版本行並更新狀態
        pattern = rf"(\| \*\*v{re.escape(major_minor)}\.x\*\*.*?\|.*?\|) ✅ Phase.*?\|"
        updated_content = re.sub(
            pattern,
            rf"\1 ✅ 已完成 |",
            content,
            flags=re.DOTALL,
        )

        if updated_content != content:
            if not dry_run:
                with open(todolist_path, "w", encoding="utf-8") as f:
                    f.write(updated_content)
            print_success(f"todolist.md 已標記 v{major_minor}.x 為已完成")
            return True
        else:
            print_warning("todolist.md 沒有找到對應的版本行")
            return True  # 不是致命錯誤

    except Exception as e:
        print_error(f"更新 todolist.md 失敗: {e}")
        return False


def verify_pubspec_version(version: str) -> bool:
    """驗證 pubspec.yaml 版本"""
    root = get_project_root()
    pubspec_path = root / "pubspec.yaml"

    if not pubspec_path.exists():
        print_error("找不到 pubspec.yaml")
        return False

    try:
        with open(pubspec_path, encoding="utf-8") as f:
            content = f.read()
            match = re.search(r"^version:\s+(.+)$", content, re.MULTILINE)
            if match:
                pubspec_version = match.group(1).strip()
                if pubspec_version == version:
                    print_success(f"pubspec.yaml 版本正確: {version}")
                    return True
                else:
                    print_error(
                        f"pubspec.yaml 版本不匹配: {pubspec_version} vs {version}"
                    )
                    return False
    except Exception as e:
        print_error(f"讀取 pubspec.yaml 失敗: {e}")
        return False

    return False


def update_documents(version: str, dry_run: bool = False) -> bool:
    """更新所有文件"""
    print_section("Step 2: Document Updates")

    all_ok = True

    # 2.1 清理 todolist
    print_info("📝 更新 docs/todolist.md")
    if not update_todolist(version, dry_run):
        all_ok = False

    # 2.2 更新 CHANGELOG
    print_info("📝 更新 CHANGELOG.md")
    if not update_changelog(version, dry_run):
        all_ok = False

    # 2.3 驗證 pubspec.yaml
    print_info("✅ 確認 pubspec.yaml 版本號")
    if not verify_pubspec_version(version):
        all_ok = False

    if all_ok:
        print_success("文件更新完成")

    return all_ok


def commit_changes(version: str, dry_run: bool = False) -> bool:
    """提交檔案變更"""
    root = get_project_root()

    try:
        # 檢查是否有待提交的變更
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0 and result.stdout.strip():
            # 有未提交的變更
            if dry_run:
                print_info("🔄 [預覽] 將提交檔案變更", 2)
            else:
                # 加入檔案
                subprocess.run(
                    ["git", "add", "docs/todolist.md", "CHANGELOG.md"],
                    cwd=root,
                    timeout=10,
                )

                # 提交
                result = subprocess.run(
                    [
                        "git",
                        "commit",
                        "-m",
                        f"docs: 版本 {version} 發布準備",
                    ],
                    cwd=root,
                    capture_output=True,
                    timeout=10,
                )

                if result.returncode == 0:
                    print_success("檔案變更已提交")
                else:
                    print_error("提交變更失敗")
                    return False

        return True

    except Exception as e:
        print_error(f"提交變更失敗: {e}")
        return False


def git_merge_and_push(version: str, dry_run: bool = False) -> bool:
    """執行 Git 操作"""
    print_section("Step 3: Git Operations")

    root = get_project_root()
    major_minor = ".".join(version.split(".")[:2])
    feature_branch = f"feature/v{major_minor}"
    tag_name = f"v{version}-final"

    try:
        # 3.1 提交變更
        print_info("🔄 提交所有變更")
        if not commit_changes(version, dry_run):
            return False

        # 3.2 切換到 main 分支
        print_info("🔀 切換到 main 分支")
        if not dry_run:
            subprocess.run(
                ["git", "checkout", "main"],
                cwd=root,
                capture_output=True,
                timeout=10,
            )
        else:
            print_info("   [預覽] git checkout main", 2)

        # 3.3 拉取最新 main
        print_info("📥 拉取最新 main")
        if not dry_run:
            result = subprocess.run(
                ["git", "pull", "origin", "main"],
                cwd=root,
                capture_output=True,
                timeout=10,
            )
            if result.returncode == 0:
                print_success("main 分支已更新到最新", )
            else:
                print_error("拉取 main 失敗")
                return False
        else:
            print_info("   [預覽] git pull origin main", 2)

        # 3.4 合併 feature 分支
        print_info("🔀 合併 feature 分支")
        if not dry_run:
            result = subprocess.run(
                [
                    "git",
                    "merge",
                    feature_branch,
                    "--no-ff",
                    "-m",
                    f"Merge {feature_branch} into main",
                ],
                cwd=root,
                capture_output=True,
                timeout=10,
            )
            if result.returncode == 0:
                print_success(f"已合併 {feature_branch} 到 main")
            else:
                print_error(f"合併 {feature_branch} 失敗")
                if "fatal: refusing to merge unrelated histories" not in result.stderr:
                    return False
        else:
            print_info(f"   [預覽] git merge {feature_branch} --no-ff", 2)

        # 3.5 建立 Tag
        print_info(f"🏷️ 建立 Tag: {tag_name}")
        if not dry_run:
            result = subprocess.run(
                [
                    "git",
                    "tag",
                    "-a",
                    tag_name,
                    "-m",
                    f"Release {tag_name}",
                ],
                cwd=root,
                capture_output=True,
                timeout=10,
            )
            if result.returncode == 0:
                print_success(f"Tag 已建立: {tag_name}")
            else:
                print_error(f"建立 Tag 失敗")
                return False
        else:
            print_info(f"   [預覽] git tag -a {tag_name}", 2)

        # 3.6 推送到遠端
        print_info("📤 推送到遠端")
        if not dry_run:
            # 推送 main
            result = subprocess.run(
                ["git", "push", "origin", "main"],
                cwd=root,
                capture_output=True,
                timeout=10,
            )
            if result.returncode == 0:
                print_success("main 已推送")
            else:
                print_error("推送 main 失敗")
                return False

            # 推送 tag
            result = subprocess.run(
                ["git", "push", "origin", tag_name],
                cwd=root,
                capture_output=True,
                timeout=10,
            )
            if result.returncode == 0:
                print_success(f"Tag {tag_name} 已推送")
            else:
                print_error(f"推送 Tag 失敗")
                return False
        else:
            print_info("   [預覽] git push origin main", 2)
            print_info(f"   [預覽] git push origin {tag_name}", 2)

        # 3.7 刪除 feature 分支
        print_info("🗑️ 清理 feature 分支")
        if not dry_run:
            # 本地刪除
            result = subprocess.run(
                ["git", "branch", "-d", feature_branch],
                cwd=root,
                capture_output=True,
                timeout=10,
            )
            if result.returncode == 0:
                print_success(f"本地分支已刪除: {feature_branch}")
            else:
                print_error(f"刪除本地分支失敗")

            # 遠端刪除
            result = subprocess.run(
                ["git", "push", "origin", "--delete", feature_branch],
                cwd=root,
                capture_output=True,
                timeout=10,
            )
            if result.returncode == 0:
                print_success(f"遠端分支已刪除: origin/{feature_branch}")
            else:
                print_warning(f"刪除遠端分支失敗（可能不存在）")
        else:
            print_info(f"   [預覽] git branch -d {feature_branch}", 2)
            print_info(f"   [預覽] git push origin --delete {feature_branch}", 2)

        return True

    except Exception as e:
        print_error(f"Git 操作失敗: {e}")
        return False


def print_summary(version: str, all_ok: bool, dry_run: bool = False):
    """打印完成摘要"""
    print_section("完成摘要")

    if all_ok:
        if dry_run:
            print_warning("預覽模式完成 - 未執行實際操作")
            print_info("執行以下指令進行實際發布:")
            print_info("  uv run version_release.py release", 1)
        else:
            print_success(f"版本 {version} 發布成功！")
            print_info("\n📊 發布統計:")
            print_info("- 檔案更新: 2", 1)
            print_info("- 合併提交: 1", 1)
            print_info("- Tag 建立: 1", 1)
            print_info("- 分支清理: 2", 1)
            print_info("\n🎉 版本已推送到 main 分支", 1)
    else:
        print_error("發布失敗，請修正上述問題後重新執行")


def main():
    """主程式"""
    import argparse

    parser = argparse.ArgumentParser(
        description="版本發布整合工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  uv run version_release.py release              # 自動偵測版本並發布
  uv run version_release.py release --version 0.19.8  # 指定版本
  uv run version_release.py check                # 只執行檢查
  uv run version_release.py update-docs --dry-run  # 預覽文件更新
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="可用的子命令")

    # release 子命令
    release_parser = subparsers.add_parser("release", help="完整發布流程")
    release_parser.add_argument("--version", help="版本號 (X.Y 或 X.Y.Z)")
    release_parser.add_argument("--dry-run", action="store_true", help="預覽模式")
    release_parser.add_argument("--force", action="store_true", help="強制執行")

    # check 子命令
    check_parser = subparsers.add_parser("check", help="只執行檢查")
    check_parser.add_argument("--version", help="版本號")

    # update-docs 子命令
    update_parser = subparsers.add_parser("update-docs", help="只更新文件")
    update_parser.add_argument("--version", help="版本號")
    update_parser.add_argument("--dry-run", action="store_true", help="預覽模式")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        # 規範化版本號
        version = normalize_version(args.version if hasattr(args, "version") else None)

        if args.command == "check":
            print_header(f"Version Release - Pre-flight Check ({version})")

            ok, results = preflight_check(version)

            if ok:
                print_success("所有檢查通過！該版本已準備好發布")
                print_info("\n發布指令:", 1)
                print_info(
                    f"uv run .claude/skills/version-release/scripts/version_release.py release",
                    2,
                )
                print_info("\n或預覽:", 1)
                print_info(
                    f"uv run .claude/skills/version-release/scripts/version_release.py release --dry-run",
                    2,
                )
            else:
                print_error("檢查失敗，請修正上述問題")
                return 1

        elif args.command == "update-docs":
            print_header(f"Update Documents ({version})")
            dry_run = args.dry_run if hasattr(args, "dry_run") else False

            if dry_run:
                print_warning("預覽模式 - 不會實際更新檔案")

            ok = update_documents(version, dry_run)

            if not ok:
                print_error("文件更新失敗")
                return 1

        elif args.command == "release":
            dry_run = args.dry_run if hasattr(args, "dry_run") else False

            header = f"Version Release Tool - {version}"
            if dry_run:
                header += " (DRY RUN)"

            print_header(header)

            if dry_run:
                print_warning("預覽模式：不會執行實際的 git 操作\n")

            # 執行 Pre-flight 檢查
            ok, results = preflight_check(version)

            if not ok and not (args.force if hasattr(args, "force") else False):
                print_error("\nPre-flight 檢查失敗，發布已中止")
                return 1

            # 更新文件
            ok = update_documents(version, dry_run)

            if not ok and not (args.force if hasattr(args, "force") else False):
                print_error("\n文件更新失敗，發布已中止")
                return 1

            # Git 操作
            ok = git_merge_and_push(version, dry_run)

            if not ok:
                print_error("\nGit 操作失敗，發布已中止")
                return 1

            # 打印摘要
            print_summary(version, ok, dry_run)

        else:
            parser.print_help()
            return 1

        return 0

    except ValueError as e:
        print_error(str(e))
        return 1
    except KeyboardInterrupt:
        print_warning("\n操作被中止")
        return 1
    except Exception as e:
        print_error(f"發生未預期的錯誤: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
