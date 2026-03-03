#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Required Features Check - Session 啟動必要功能驗證

驗證所有在 required-features-config.json 中定義的必要功能是否正確配置和可用。

檢查類型：
- script: 執行腳本並檢查返回值
- script_exists: 檢查腳本是否存在且有執行權限
- settings_hook: 檢查 Hook 是否已在 settings.json 中註冊

Usage:
    uv run .claude/hooks/required-features-check.py
    uv run .claude/hooks/required-features-check.py --verbose
    uv run .claude/hooks/required-features-check.py --category quality-assurance
"""

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class CheckResult:
    """檢查結果"""
    feature_id: str
    feature_name: str
    passed: bool
    message: str
    remediation: Optional[str] = None
    required: bool = True


def get_project_root() -> Path:
    """取得專案根目錄"""
    env_root = os.getenv("CLAUDE_PROJECT_DIR")
    if env_root:
        return Path(env_root)

    # 從腳本位置推算
    script_dir = Path(__file__).parent
    return script_dir.parent.parent


def load_config(project_root: Path) -> dict:
    """載入必要功能配置"""
    config_path = project_root / ".claude" / "hooks" / "required-features-config.json"

    if not config_path.exists():
        raise FileNotFoundError(f"配置檔不存在: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_settings(project_root: Path, settings_file: str) -> dict:
    """載入 Claude Code settings.json"""
    settings_path = project_root / settings_file

    if not settings_path.exists():
        return {}

    with open(settings_path, "r", encoding="utf-8") as f:
        return json.load(f)


def check_script_exists(project_root: Path, script_path: str) -> tuple[bool, str]:
    """檢查腳本是否存在且有執行權限"""
    full_path = project_root / script_path

    if not full_path.exists():
        return False, f"腳本不存在: {script_path}"

    if not os.access(full_path, os.X_OK):
        return False, f"腳本無執行權限: {script_path}"

    return True, f"腳本存在且可執行: {script_path}"


def check_script_run(project_root: Path, script_path: str) -> tuple[bool, str]:
    """執行腳本並檢查返回值"""
    full_path = project_root / script_path

    if not full_path.exists():
        return False, f"腳本不存在: {script_path}"

    try:
        result = subprocess.run(
            [str(full_path)],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            return True, f"腳本執行成功: {script_path}"
        else:
            return False, f"腳本執行失敗 (exit code {result.returncode}): {script_path}"

    except subprocess.TimeoutExpired:
        return False, f"腳本執行超時: {script_path}"
    except Exception as e:
        return False, f"腳本執行錯誤: {script_path} - {str(e)}"


def check_settings_hook(
    settings: dict,
    hook_event: str,
    hook_matcher: Optional[str],
    hook_command: str
) -> tuple[bool, str]:
    """檢查 Hook 是否已在 settings.json 中註冊"""
    hooks = settings.get("hooks", {})
    event_hooks = hooks.get(hook_event, [])

    for hook_config in event_hooks:
        # 檢查 matcher（如果指定）
        config_matcher = hook_config.get("matcher")
        if hook_matcher is not None and config_matcher != hook_matcher:
            continue

        # 檢查 hooks 列表中是否包含指定的命令
        hook_list = hook_config.get("hooks", [])
        for h in hook_list:
            command = h.get("command", "")
            # 檢查命令是否包含目標腳本
            if hook_command in command:
                matcher_info = f"/{hook_matcher}" if hook_matcher else ""
                return True, f"Hook 已註冊: {hook_event}{matcher_info} -> {hook_command}"

    matcher_info = f"/{hook_matcher}" if hook_matcher else ""
    return False, f"Hook 未註冊: {hook_event}{matcher_info} -> {hook_command}"


def check_feature(
    project_root: Path,
    settings: dict,
    feature: dict
) -> CheckResult:
    """檢查單個功能"""
    feature_id = feature["id"]
    feature_name = feature["name"]
    check_type = feature["check_type"]
    required = feature.get("required", True)
    remediation = feature.get("remediation")

    if check_type == "script":
        script_path = feature["check_script"]
        passed, message = check_script_run(project_root, script_path)

    elif check_type == "script_exists":
        script_path = feature["script_path"]
        passed, message = check_script_exists(project_root, script_path)

    elif check_type == "settings_hook":
        hook_event = feature["hook_event"]
        hook_matcher = feature.get("hook_matcher")
        hook_command = feature["hook_command"]
        passed, message = check_settings_hook(settings, hook_event, hook_matcher, hook_command)

    else:
        passed = False
        message = f"未知的檢查類型: {check_type}"

    return CheckResult(
        feature_id=feature_id,
        feature_name=feature_name,
        passed=passed,
        message=message,
        remediation=remediation if not passed else None,
        required=required
    )


def print_results(results: list[CheckResult], verbose: bool = False, show_remediation: bool = True):
    """輸出檢查結果"""
    passed_count = sum(1 for r in results if r.passed)
    failed_count = len(results) - passed_count
    required_failed = sum(1 for r in results if not r.passed and r.required)

    print("=" * 60)
    print("📋 Session 啟動必要功能檢查報告")
    print("=" * 60)
    print()

    # 分類輸出
    passed_results = [r for r in results if r.passed]
    failed_results = [r for r in results if not r.passed]

    if passed_results:
        print("✅ 通過的檢查:")
        for r in passed_results:
            req_mark = "[必要]" if r.required else "[可選]"
            print(f"   {req_mark} {r.feature_name}")
            if verbose:
                print(f"       {r.message}")
        print()

    if failed_results:
        print("❌ 失敗的檢查:")
        for r in failed_results:
            req_mark = "[必要]" if r.required else "[可選]"
            print(f"   {req_mark} {r.feature_name}")
            print(f"       {r.message}")
            if show_remediation and r.remediation:
                print(f"       💡 修復方式: {r.remediation}")
        print()

    # 摘要
    print("-" * 60)
    print(f"📊 檢查摘要: {passed_count}/{len(results)} 通過")

    if required_failed > 0:
        print(f"🚨 {required_failed} 個必要功能未通過檢查!")
        print()
        print("⚠️  必要功能缺失可能導致品質控制機制失效")
        print("   請依照上方修復方式進行修正")
    else:
        print("✅ 所有必要功能檢查通過")

    print("=" * 60)

    return required_failed == 0


def main() -> int:
    """主程式入口"""
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    # 取得專案根目錄
    project_root = get_project_root()

    try:
        # 載入配置
        config = load_config(project_root)
        settings_file = config.get("settings", {}).get("settings_file", ".claude/settings.json")
        show_remediation = config.get("settings", {}).get("show_remediation", True)

        # 載入 settings.json
        settings = load_settings(project_root, settings_file)

        # 過濾分類（如果指定）
        category_filter = None
        for i, arg in enumerate(sys.argv):
            if arg == "--category" and i + 1 < len(sys.argv):
                category_filter = sys.argv[i + 1]
                break

        # 取得要檢查的功能清單
        features = config.get("features", [])
        if category_filter:
            features = [f for f in features if f.get("category") == category_filter]

        # 按優先級排序
        features = sorted(features, key=lambda f: f.get("priority", 999))

        # 執行檢查
        results = []
        for feature in features:
            result = check_feature(project_root, settings, feature)
            results.append(result)

        # 輸出結果
        all_required_passed = print_results(results, verbose, show_remediation)

        # 返回狀態碼
        return 0 if all_required_passed else 1

    except FileNotFoundError as e:
        print(f"❌ 錯誤: {e}")
        return 1
    except json.JSONDecodeError as e:
        print(f"❌ JSON 解析錯誤: {e}")
        return 1
    except Exception as e:
        print(f"❌ 未預期的錯誤: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
