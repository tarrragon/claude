#!/usr/bin/env python3
"""
Hook 合規性驗證工具

驗證 Hook 腳本是否遵循專案規範，包含：
- 共用模組導入檢查
- 輸出格式檢查
- 測試存在性檢查
- 命名規範檢查

使用方式:
    # 驗證單一 Hook
    python .claude/lib/hook_validator.py .claude/hooks/my-hook.py

    # 驗證所有 Hook
    python .claude/lib/hook_validator.py --all

    # 輸出 JSON 格式
    python .claude/lib/hook_validator.py --all --json

    # 作為模組使用
    from hook_validator import validate_hook, validate_all_hooks
    result = validate_hook(".claude/hooks/my-hook.py")
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional, List


@dataclass
class ValidationIssue:
    """驗證問題描述"""
    level: str  # "error" | "warning" | "info"
    message: str
    line: Optional[int] = None
    suggestion: Optional[str] = None


@dataclass
class ValidationResult:
    """單個 Hook 的驗證結果"""
    hook_path: str
    issues: List[ValidationIssue] = field(default_factory=list)
    is_compliant: bool = True

    def __post_init__(self):
        """計算 is_compliant 狀態"""
        self.is_compliant = not any(issue.level == "error" for issue in self.issues)


class HookValidator:
    """Hook 合規性驗證器"""

    # ===== 常數定義 =====

    # 共用模組導入模式
    HOOK_IO_PATTERNS = [
        r"from\s+hook_io\s+import",
        r"from\s+lib\.hook_io\s+import",
    ]

    HOOK_LOGGING_PATTERNS = [
        r"from\s+hook_logging\s+import",
        r"from\s+lib\.hook_logging\s+import",
    ]

    CONFIG_LOADER_PATTERNS = [
        r"from\s+config_loader\s+import",
        r"from\s+lib\.config_loader\s+import",
    ]

    GIT_UTILS_PATTERNS = [
        r"from\s+git_utils\s+import",
        r"from\s+lib\.git_utils\s+import",
    ]

    # 輸出函式使用模式
    OUTPUT_PATTERNS = [
        r"write_hook_output\s*\(",
        r"create_pretooluse_output\s*\(",
        r"create_posttooluse_output\s*\(",
    ]

    # 不推薦的輸出模式
    BAD_OUTPUT_PATTERNS = [
        r'print\s*\(\s*json\.dumps\s*\(',
        r'sys\.stdout\.write\s*\(\s*json\.dumps\s*\(',
    ]

    # 命名規範模式
    VALID_NAME_PATTERNS = [
        r"^[a-z0-9]([a-z0-9\-_]*[a-z0-9])?\.py$",  # snake-case 或 kebab-case
    ]

    # Hook 類型推測模式
    HOOK_TYPE_HINTS = [
        ("PreToolUse", r"create_pretooluse_output|permissionDecision"),
        ("PostToolUse", r"create_posttooluse_output|additionalContext"),
        ("Stop", r"Stop|subagent"),
        ("SessionStart", r"SessionStart|session_id"),
    ]

    def __init__(self, project_root: Optional[str] = None):
        """
        初始化驗證器

        Args:
            project_root: 專案根目錄，預設從環境變數或當前目錄
        """
        if project_root is None:
            project_root = os.environ.get(
                "CLAUDE_PROJECT_DIR",
                os.getcwd()
            )
        self.project_root = Path(project_root)

    def validate_hook(self, hook_path: str) -> ValidationResult:
        """
        驗證單個 Hook 檔案

        Args:
            hook_path: Hook 檔案路徑（相對或絕對）

        Returns:
            ValidationResult: 驗證結果
        """
        hook_path = self._resolve_path(hook_path)

        if not hook_path.exists():
            return ValidationResult(
                hook_path=str(hook_path),
                issues=[
                    ValidationIssue(
                        level="error",
                        message=f"Hook 檔案不存在: {hook_path}",
                        suggestion=f"確認檔案路徑: {hook_path}"
                    )
                ]
            )

        if hook_path.suffix != ".py":
            return ValidationResult(
                hook_path=str(hook_path),
                issues=[
                    ValidationIssue(
                        level="warning",
                        message=f"Hook 應使用 .py 副檔名，實際: {hook_path.suffix}",
                        suggestion="重命名為 .py 檔案"
                    )
                ]
            )

        # 讀取檔案內容
        try:
            with open(hook_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            return ValidationResult(
                hook_path=str(hook_path),
                issues=[
                    ValidationIssue(
                        level="error",
                        message=f"無法讀取 Hook 檔案: {e}",
                        suggestion="確認檔案權限和編碼格式"
                    )
                ]
            )

        # 執行各項檢查
        issues = []
        issues.extend(self.check_naming_convention(hook_path))
        issues.extend(self.check_lib_imports(content, hook_path))
        issues.extend(self.check_output_format(content))
        issues.extend(self.check_test_exists(hook_path))

        return ValidationResult(
            hook_path=str(hook_path),
            issues=issues
        )

    def validate_all_hooks(self, hooks_dir: Optional[str] = None) -> List[ValidationResult]:
        """
        驗證所有 Hook 檔案

        Args:
            hooks_dir: Hook 目錄路徑，預設 .claude/hooks

        Returns:
            list[ValidationResult]: 所有 Hook 的驗證結果
        """
        if hooks_dir is None:
            hooks_dir = str(self.project_root / ".claude" / "hooks")

        hooks_dir = self._resolve_path(hooks_dir)

        if not hooks_dir.is_dir():
            return [
                ValidationResult(
                    hook_path=str(hooks_dir),
                    issues=[
                        ValidationIssue(
                            level="error",
                            message=f"Hook 目錄不存在: {hooks_dir}",
                            suggestion=f"確認目錄路徑: {hooks_dir}"
                        )
                    ]
                )
            ]

        # 找出所有 .py 檔案（排除子目錄、__pycache__、測試檔案）
        results = []
        for hook_file in sorted(hooks_dir.glob("*.py")):
            if hook_file.name.startswith("_"):
                continue  # 跳過 __init__.py 等
            results.append(self.validate_hook(str(hook_file)))

        return results

    def check_lib_imports(self, content: str, hook_path: Optional[Path] = None) -> List[ValidationIssue]:
        """
        檢查共用模組導入

        根據 Hook 的功能推測需要的模組，檢查是否正確導入。

        Args:
            content: Hook 檔案內容
            hook_path: Hook 檔案路徑（用於推測功能）

        Returns:
            list[ValidationIssue]: 發現的問題
        """
        issues = []

        # 推測 Hook 功能
        needs_config = self._needs_config_loader(content, hook_path)
        needs_git = self._needs_git_utils(content, hook_path)

        # 檢查 hook_io 導入（基本上所有 Hook 都需要）
        if not self._has_import(content, self.HOOK_IO_PATTERNS):
            issues.append(
                ValidationIssue(
                    level="warning",
                    message="未導入 hook_io 模組",
                    suggestion=(
                        "在 Hook 開頭添加:\n"
                        "  from hook_io import read_hook_input, write_hook_output\n"
                        "或\n"
                        "  from lib.hook_io import read_hook_input, write_hook_output"
                    )
                )
            )

        # 檢查 hook_logging 導入（推薦所有 Hook）
        if not self._has_import(content, self.HOOK_LOGGING_PATTERNS):
            issues.append(
                ValidationIssue(
                    level="info",
                    message="未導入 hook_logging 模組（推薦使用）",
                    suggestion=(
                        "在 Hook 開頭添加:\n"
                        "  from hook_logging import setup_hook_logging"
                    )
                )
            )

        # 檢查 config_loader 導入（如果需要）
        if needs_config and not self._has_import(content, self.CONFIG_LOADER_PATTERNS):
            issues.append(
                ValidationIssue(
                    level="warning",
                    message="Hook 似乎需要配置，但未導入 config_loader 模組",
                    suggestion=(
                        "在 Hook 開頭添加:\n"
                        "  from config_loader import load_config"
                    )
                )
            )

        # 檢查 git_utils 導入（如果需要）
        if needs_git and not self._has_import(content, self.GIT_UTILS_PATTERNS):
            issues.append(
                ValidationIssue(
                    level="warning",
                    message="Hook 似乎需要 Git 操作，但未導入 git_utils 模組",
                    suggestion=(
                        "在 Hook 開頭添加:\n"
                        "  from git_utils import get_current_branch, run_git_command"
                    )
                )
            )

        return issues

    def check_output_format(self, content: str) -> List[ValidationIssue]:
        """
        檢查 Hook 輸出格式

        驗證是否使用了推薦的輸出函式而非直接 print JSON。

        Args:
            content: Hook 檔案內容

        Returns:
            list[ValidationIssue]: 發現的問題
        """
        issues = []

        # 檢查是否使用正確的輸出函式
        has_good_output = self._has_import_and_usage(
            content,
            self.OUTPUT_PATTERNS
        )

        # 檢查是否使用不推薦的輸出方式
        has_bad_output = self._matches_pattern(content, self.BAD_OUTPUT_PATTERNS)

        # 如果有輸出相關程式碼但沒有使用正確方式
        if (has_bad_output or not has_good_output) and self._has_json_output(content):
            if has_bad_output:
                issues.append(
                    ValidationIssue(
                        level="warning",
                        message="使用 print(json.dumps(...)) 而非推薦的 write_hook_output()",
                        suggestion=(
                            "替換為:\n"
                            "  from hook_io import write_hook_output\n"
                            "  write_hook_output(output_dict)"
                        )
                    )
                )

        return issues

    def check_test_exists(self, hook_path: Path) -> List[ValidationIssue]:
        """
        檢查對應的測試檔案是否存在

        Args:
            hook_path: Hook 檔案路徑

        Returns:
            list[ValidationIssue]: 發現的問題
        """
        issues = []

        # 生成測試檔案名稱
        hook_name = hook_path.stem
        test_name = f"test_{hook_name.replace('-', '_')}.py"

        # 測試檔案應該在 .claude/lib/tests/ 或 .claude/hooks/tests/
        possible_test_paths = [
            self.project_root / ".claude" / "lib" / "tests" / test_name,
            self.project_root / ".claude" / "hooks" / "tests" / test_name,
        ]

        test_exists = any(p.exists() for p in possible_test_paths)

        if not test_exists:
            issues.append(
                ValidationIssue(
                    level="info",
                    message=f"未找到對應的測試檔案: {test_name}",
                    suggestion=(
                        f"建議在以下位置建立測試:\n"
                        f"  .claude/lib/tests/{test_name}"
                    )
                )
            )

        return issues

    def check_naming_convention(self, hook_path: Path) -> List[ValidationIssue]:
        """
        檢查命名規範

        Args:
            hook_path: Hook 檔案路徑

        Returns:
            list[ValidationIssue]: 發現的問題
        """
        issues = []

        filename = hook_path.name

        # 檢查是否符合命名規範
        valid_name = any(
            re.match(pattern, filename)
            for pattern in self.VALID_NAME_PATTERNS
        )

        if not valid_name:
            issues.append(
                ValidationIssue(
                    level="warning",
                    message=f"檔案名稱不符合規範: {filename}",
                    suggestion=(
                        "建議使用 snake-case 或 kebab-case 命名，例如:\n"
                        "  check_permissions.py 或 check-permissions.py"
                    )
                )
            )

        # 檢查是否有有意義的功能描述
        stem = hook_path.stem
        if len(stem) < 3 or stem in ["hook", "check", "test"]:
            issues.append(
                ValidationIssue(
                    level="warning",
                    message=f"檔案名稱缺少功能描述: {filename}",
                    suggestion=(
                        "建議包含具體功能，例如:\n"
                        "  check_file_permissions.py\n"
                        "  validate_format.py"
                    )
                )
            )

        return issues

    # ===== 輔助方法 =====

    def _resolve_path(self, path: str) -> Path:
        """解析路徑為絕對路徑"""
        p = Path(path)
        if p.is_absolute():
            return p
        return self.project_root / p

    def _has_import(self, content: str, patterns: List[str]) -> bool:
        """檢查是否有符合任一模式的導入"""
        return any(
            re.search(pattern, content)
            for pattern in patterns
        )

    def _matches_pattern(self, content: str, patterns: List[str]) -> bool:
        """檢查是否符合任一模式"""
        return any(
            re.search(pattern, content)
            for pattern in patterns
        )

    def _has_json_output(self, content: str) -> bool:
        """檢查是否有 JSON 輸出相關程式碼"""
        patterns = [
            r"json\.dumps",
            r"write_hook_output",
            r"create_.*_output",
        ]
        return any(
            re.search(pattern, content)
            for pattern in patterns
        )

    def _has_import_and_usage(self, content: str, usage_patterns: List[str]) -> bool:
        """檢查是否有使用推薦的函式"""
        return any(
            re.search(pattern, content)
            for pattern in usage_patterns
        )

    def _needs_config_loader(self, content: str, hook_path: Optional[Path] = None) -> bool:
        """判斷 Hook 是否需要配置載入"""
        # 檢查內容中的關鍵字
        keywords = ["load_config", "configuration", "config", "yaml", "json"]
        if any(keyword in content.lower() for keyword in keywords):
            return True

        # 根據檔案名稱推測
        if hook_path:
            name_lower = hook_path.stem.lower()
            if any(keyword in name_lower for keyword in ["config", "agent", "dispatch"]):
                return True

        return False

    def _needs_git_utils(self, content: str, hook_path: Optional[Path] = None) -> bool:
        """判斷 Hook 是否需要 Git 操作"""
        # 檢查內容中的關鍵字
        keywords = [
            "git", "branch", "commit", "worktree",
            "is_protected_branch", "get_current_branch"
        ]
        if any(keyword in content.lower() for keyword in keywords):
            return True

        # 根據檔案名稱推測
        if hook_path:
            name_lower = hook_path.stem.lower()
            if any(
                keyword in name_lower
                for keyword in ["branch", "git", "commit", "worktree"]
            ):
                return True

        return False


def validate_hook(hook_path: str, project_root: Optional[str] = None) -> ValidationResult:
    """
    驗證單個 Hook 檔案

    Args:
        hook_path: Hook 檔案路徑（相對或絕對）
        project_root: 專案根目錄（預設從環境變數）

    Returns:
        ValidationResult: 驗證結果

    Example:
        result = validate_hook(".claude/hooks/my-hook.py")
        if not result.is_compliant:
            for issue in result.issues:
                print(f"[{issue.level}] {issue.message}")
    """
    validator = HookValidator(project_root)
    return validator.validate_hook(hook_path)


def validate_all_hooks(
    hooks_dir: Optional[str] = None,
    project_root: Optional[str] = None
) -> List[ValidationResult]:
    """
    驗證所有 Hook 檔案

    Args:
        hooks_dir: Hook 目錄路徑（預設 .claude/hooks）
        project_root: 專案根目錄（預設從環境變數）

    Returns:
        list[ValidationResult]: 所有 Hook 的驗證結果

    Example:
        results = validate_all_hooks()
        for result in results:
            if not result.is_compliant:
                print(f"\\n{result.hook_path}:")
                for issue in result.issues:
                    print(f"  [{issue.level}] {issue.message}")
    """
    validator = HookValidator(project_root)
    return validator.validate_all_hooks(hooks_dir)


def format_validation_report(results: List[ValidationResult]) -> str:
    """
    格式化驗證報告為可讀的文字格式

    Args:
        results: 驗證結果列表

    Returns:
        str: 格式化的報告
    """
    lines = []
    lines.append("=" * 70)
    lines.append("Hook 合規性驗證報告")
    lines.append("=" * 70)

    # 統計
    total = len(results)
    compliant = sum(1 for r in results if r.is_compliant)
    non_compliant = total - compliant

    lines.append(f"\n概括:")
    lines.append(f"  總數: {total}")
    lines.append(f"  合規: {compliant}")
    lines.append(f"  不合規: {non_compliant}")

    # 詳細結果
    lines.append(f"\n詳細結果:")

    for result in results:
        status = "✓ 合規" if result.is_compliant else "✗ 不合規"
        lines.append(f"\n{status}: {result.hook_path}")

        if result.issues:
            for issue in result.issues:
                level_marker = {
                    "error": "❌",
                    "warning": "⚠️",
                    "info": "ℹ️"
                }.get(issue.level, "•")
                lines.append(f"  {level_marker} [{issue.level}] {issue.message}")

                if issue.suggestion:
                    lines.append(f"     建議: {issue.suggestion}")
        else:
            lines.append("  (無問題)")

    lines.append("\n" + "=" * 70)
    return "\n".join(lines)


def main():
    """命令行介面"""
    parser = argparse.ArgumentParser(
        description="Hook 合規性驗證工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用範例:
  # 驗證單一 Hook
  python .claude/lib/hook_validator.py .claude/hooks/my-hook.py

  # 驗證所有 Hook
  python .claude/lib/hook_validator.py --all

  # 輸出 JSON 格式
  python .claude/lib/hook_validator.py --all --json

  # 自訂 Hook 目錄
  python .claude/lib/hook_validator.py --all --dir .claude/hooks
        """
    )

    parser.add_argument(
        "hook_path",
        nargs="?",
        help="Hook 檔案路徑（相對或絕對）"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="驗證所有 Hook 檔案"
    )
    parser.add_argument(
        "--dir",
        help="自訂 Hook 目錄路徑（預設 .claude/hooks）"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="輸出 JSON 格式"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="嚴格模式：將 warning 視為 error"
    )

    args = parser.parse_args()

    # 確定工作模式
    if args.all:
        results = validate_all_hooks(hooks_dir=args.dir)
    elif args.hook_path:
        results = [validate_hook(args.hook_path)]
    else:
        parser.print_help()
        sys.exit(1)

    # 輸出結果
    if args.json:
        # JSON 格式輸出
        output = {
            "total": len(results),
            "compliant": sum(1 for r in results if r.is_compliant),
            "non_compliant": sum(1 for r in results if not r.is_compliant),
            "results": [
                {
                    "hook_path": r.hook_path,
                    "is_compliant": r.is_compliant,
                    "issues": [asdict(issue) for issue in r.issues]
                }
                for r in results
            ]
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        # 文字格式輸出
        print(format_validation_report(results))

    # 決定 exit code
    all_compliant = all(r.is_compliant for r in results)

    if args.strict:
        # 嚴格模式：有任何 warning 也視為失敗
        has_issues = any(r.issues for r in results)
        sys.exit(0 if (all_compliant and not has_issues) else 1)
    else:
        # 一般模式：只有 error 時才失敗
        sys.exit(0 if all_compliant else 1)


if __name__ == "__main__":
    main()
