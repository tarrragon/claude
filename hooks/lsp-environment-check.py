#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
LSP 環境檢查 Hook（簡化版 v1.2.0）

在 Claude Code Session 啟動時檢查 LSP 環境：
1. 檢查基本 LSP (marksman, yaml-language-server)
2. 偵測專案類型並檢查語言特定 LSP
3. 缺失時顯示安裝指令（不自動安裝）

跨平台支援: macOS, Linux, Windows

改進 (v1.2.0):
- 使用 common_functions 統一 logging 和 output
- 避免 stderr 污染，減少 "hook error"
"""

import json
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Any

# 添加 lib 目錄到路徑（M-003 標準化）
sys.path.insert(0, str(Path(__file__).parent))

try:
    from hook_utils import setup_hook_logging
    from lib.common_functions import hook_output
except ImportError as e:
    print(f"[Hook Import Error] {Path(__file__).name}: {e}", file=sys.stderr)
    sys.exit(1)

# === 常數定義 ===

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR", SCRIPT_DIR.parent.parent))
CONFIG_FILE = SCRIPT_DIR / "lsp-check-config.json"


# === 工具函數 ===

def get_os_type() -> str:
    """偵測作業系統類型"""
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    elif system == "linux":
        return "linux"
    elif system == "windows":
        return "windows"
    return "unknown"


def check_lsp_installed(command: str) -> bool:
    """檢查 LSP 是否已安裝（統一使用 shutil.which）"""
    return shutil.which(command) is not None


def load_config() -> dict[str, Any]:
    """載入配置檔案"""
    if not CONFIG_FILE.exists():
        print(f"  配置檔案不存在: {CONFIG_FILE}")
        return {}

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# === 專案類型偵測 ===

def detect_project_type(config: dict[str, Any]) -> list[str]:
    """偵測專案類型（簡化版：只檢查檔案存在）"""
    detected_types = []
    project_detection = config.get("project_type_detection", {})

    for project_type, detection_config in project_detection.items():
        indicators = detection_config.get("indicators", [])

        # 只檢查檔案是否存在
        for indicator in indicators:
            if (PROJECT_ROOT / indicator).exists():
                detected_types.append(project_type)
                break

    return detected_types


def get_required_lsp(config: dict[str, Any], project_types: list[str]) -> set[str]:
    """根據專案類型取得需要的 LSP"""
    required = set()
    project_detection = config.get("project_type_detection", {})

    for project_type in project_types:
        if project_type in project_detection:
            required_lsp = project_detection[project_type].get("required_lsp", [])
            required.update(required_lsp)

    return required


# === 主要檢查邏輯 ===

def check_basic_lsp(config: dict[str, Any], os_type: str, logger) -> tuple[dict[str, bool], list[tuple[str, str, str]]]:
    """檢查基本 LSP，返回結果和缺失列表"""
    results = {}
    missing = []
    basic_lsp = config.get("basic_lsp", {})

    hook_output("\n" + "=" * 50, "info")
    hook_output("LSP 環境檢查 - 基本 LSP", "info")
    hook_output("=" * 50, "info")

    for lsp_name, lsp_config in basic_lsp.items():
        if not isinstance(lsp_config, dict):
            continue

        command = lsp_config.get("command", lsp_name)
        display_name = lsp_config.get("name", lsp_name)
        installed = check_lsp_installed(command)
        results[lsp_name] = installed

        status = "V" if installed else "X"
        status_text = '已安裝' if installed else '未安裝'
        msg = f"[{status}] {display_name}: {status_text}"
        hook_output(msg, "info")
        logger.debug(f"LSP check: {display_name} ({lsp_name}) - {status_text}")

        if not installed:
            install_cmd = lsp_config.get("install", {}).get(os_type, "")
            missing.append((lsp_name, display_name, install_cmd))

    return results, missing


def check_language_specific_lsp(
    config: dict[str, Any],
    os_type: str,
    project_types: list[str],
    logger
) -> tuple[dict[str, bool], list[tuple[str, str, str]]]:
    """檢查語言特定 LSP，返回結果和缺失列表"""
    results = {}
    missing = []
    required_lsp = get_required_lsp(config, project_types)
    language_lsp = config.get("language_specific_lsp", {})

    if not project_types:
        hook_output("\n未偵測到特定專案類型", "info")
        logger.debug("No specific project types detected")
        return results, missing

    hook_output("\n" + "-" * 50, "info")
    hook_output("語言特定 LSP", "info")
    hook_output("-" * 50, "info")
    hook_output(f"偵測到: {', '.join(project_types)}", "info")
    logger.debug(f"Detected project types: {project_types}")

    for lsp_name in required_lsp:
        if lsp_name not in language_lsp:
            continue

        lsp_config = language_lsp[lsp_name]
        command = lsp_config.get("command", lsp_name)
        display_name = lsp_config.get("name", lsp_name)
        installed = check_lsp_installed(command)
        results[lsp_name] = installed

        status = "V" if installed else "X"
        status_text = '已安裝' if installed else '未安裝'
        msg = f"[{status}] {display_name}: {status_text}"
        hook_output(msg, "info")
        logger.debug(f"LSP check: {display_name} ({lsp_name}) - {status_text}")

        if not installed:
            install_cmd = lsp_config.get("install", {}).get(os_type, "")
            missing.append((lsp_name, display_name, install_cmd))

    return results, missing


def show_install_commands(missing: list[tuple[str, str, str]], logger) -> None:
    """顯示安裝指令（不自動執行）"""
    if not missing:
        return

    hook_output("\n" + "=" * 50, "info")
    hook_output("缺失的 LSP 安裝指令", "info")
    hook_output("=" * 50, "info")
    hook_output("請手動執行以下指令安裝缺失的 LSP：", "info")
    hook_output("", "info")

    for lsp_name, display_name, install_cmd in missing:
        if install_cmd:
            hook_output(f"# {display_name}", "info")
            hook_output(f"{install_cmd}", "info")
            hook_output("", "info")
            logger.debug(f"Missing LSP: {display_name} ({lsp_name})")


def generate_report(
    basic_results: dict[str, bool],
    language_results: dict[str, bool],
    project_types: list[str],
    missing_count: int,
    logger
) -> None:
    """產生檢查報告"""
    hook_output("\n" + "=" * 50, "info")
    hook_output("LSP 環境檢查報告", "info")
    hook_output("=" * 50, "info")
    hook_output(f"作業系統: {platform.system()} {platform.release()}", "info")
    hook_output(f"專案類型: {', '.join(project_types) if project_types else '未偵測到'}", "info")

    basic_ok = all(basic_results.values()) if basic_results else True
    hook_output(f"基本 LSP: {'全部就緒' if basic_ok else '有缺失'}", "info")

    if language_results:
        lang_ok = all(language_results.values())
        hook_output(f"語言 LSP: {'全部就緒' if lang_ok else '有缺失'}", "info")

    all_ok = basic_ok and (not language_results or all(language_results.values()))

    hook_output("", "info")
    if all_ok:
        hook_output("[OK] LSP 環境已就緒", "info")
        logger.info("LSP environment check passed")
    else:
        hook_output(f"[!!] {missing_count} 個 LSP 未安裝，請參考上方安裝指令", "warning")
        logger.warning(f"{missing_count} LSPs are missing")

    hook_output("=" * 50, "info")


def main() -> int:
    """主程式"""
    logger = setup_hook_logging("lsp-environment-check")

    hook_output("\n[LSP] 環境檢查 Hook 啟動", "info")
    logger.info("LSP environment check started")

    # 載入配置
    config = load_config()
    if not config:
        hook_output("[LSP] 無法載入配置檔案，跳過檢查", "warning")
        logger.warning("Failed to load configuration file")
        return 0

    # 偵測作業系統
    os_type = get_os_type()
    hook_output(f"作業系統: {os_type}", "info")
    logger.debug(f"Detected OS type: {os_type}")

    # 偵測專案類型
    project_types = detect_project_type(config)

    # 檢查基本 LSP
    basic_results, basic_missing = check_basic_lsp(config, os_type, logger)

    # 檢查語言特定 LSP
    language_results, language_missing = check_language_specific_lsp(
        config, os_type, project_types, logger
    )

    # 合併缺失列表
    all_missing = basic_missing + language_missing

    # 顯示安裝指令
    show_install_commands(all_missing, logger)

    # 產生報告
    generate_report(basic_results, language_results, project_types, len(all_missing), logger)

    return 0


if __name__ == "__main__":
    sys.exit(main())
