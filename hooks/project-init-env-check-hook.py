#!/usr/bin/env python3
"""
Project Init 環境檢查 Hook

在 Session 啟動時執行 project-init check，偵測環境問題並輸出引導訊息。

Hook Event: SessionStart

Purpose:
    檢查開發環境狀態（Python、UV、ripgrep、Hook 系統、自製套件）。
    如果偵測到問題，輸出結構化的引導訊息供用戶參考。

Exit codes:
    0 - Always (不阻塊 session)
"""

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import setup_hook_logging, run_hook_safely


def get_project_root(logger) -> Path:
    """取得專案根目錄。

    Args:
        logger: 日誌物件

    Returns:
        Path - 專案根目錄
    """
    project_dir = os.getenv("CLAUDE_PROJECT_DIR")
    if project_dir:
        return Path(project_dir)

    # Fallback: 使用 git 查找
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        return Path(result.stdout.strip())
    except Exception:
        return Path.cwd()


def run_project_init_check(project_root: Path, logger) -> tuple[bool, str]:
    """執行 project-init check 命令。

    Args:
        project_root: 專案根目錄
        logger: 日誌物件

    Returns:
        (success, output) - 成功標誌和輸出內容
    """
    try:
        result = subprocess.run(
            ["project-init", "check", "--project-root", str(project_root)],
            capture_output=True,
            text=True,
            timeout=30
        )

        output = result.stdout.strip() if result.stdout else ""
        logger.debug(f"project-init check exit code: {result.returncode}")

        if result.returncode == 0:
            return True, output
        else:
            # 檢查失敗（returncode != 0），輸出內容包含問題
            return False, output

    except FileNotFoundError:
        logger.debug("project-init CLI 未安裝")
        return None, None
    except subprocess.TimeoutExpired:
        logger.debug("project-init check 執行超時（30 秒）")
        return False, ""
    except Exception as e:
        logger.debug(f"執行 project-init check 失敗: {e}")
        return False, ""


def generate_hook_output(status: bool | None, output: str, logger) -> dict:
    """生成 Hook 輸出。

    Args:
        status: 檢查狀態（True=成功, False=失敗, None=CLI 未安裝）
        output: project-init check 的輸出內容
        logger: 日誌物件

    Returns:
        dict - Hook 輸出 JSON
    """
    if status is None:
        # project-init CLI 未安裝
        message = "[Project Init] CLI 未安裝，執行 project-init setup 可自動設定環境"
        logger.debug("project-init CLI 未安裝，輸出提示")
        return {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": message
            },
            "suppressOutput": False
        }

    if status is True:
        # 所有正常，輸出簡潔訊息
        message = "[Project Init] 環境已就緒"
        logger.debug("環境檢查通過")
        return {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": message
            },
            "suppressOutput": False
        }

    if status is False:
        # 偵測到問題，輸出完整的 check 結果（已包含 RemediationGuidance）
        logger.debug("環境檢查發現問題")
        return {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": output if output else "[Project Init] 環境檢查失敗，請查看詳細日誌"
            },
            "suppressOutput": False
        }

    # 其他情況不輸出
    return {
        "suppressOutput": True
    }


def main() -> int:
    """主入口點。

    執行流程:
    1. 初始化日誌
    2. 取得專案根目錄
    3. 執行 project-init check
    4. 根據結果產生 Hook 輸出
    5. 輸出 JSON 結果

    Returns:
        int - Exit code (0 = 成功，不阻塊 session)
    """
    logger = setup_hook_logging("project-init-env-check-hook")

    try:
        logger.debug("Project Init 環境檢查 Hook 啟動")

        # 取得專案根目錄
        project_root = get_project_root(logger)
        logger.debug(f"專案根目錄: {project_root}")

        # 執行 project-init check
        status, output = run_project_init_check(project_root, logger)

        # 產生 Hook 輸出
        hook_output = generate_hook_output(status, output, logger)

        logger.debug("Hook 執行完成")

        # 輸出 JSON 結果（在最後輸出，避免日誌混入）
        print(json.dumps(hook_output, ensure_ascii=False, indent=2))
        return 0

    except Exception as e:
        logger.critical(f"Hook 執行錯誤: {e}", exc_info=True)
        # 錯誤時靜默跳過（非阻塊）
        print(json.dumps({
            "suppressOutput": True
        }, ensure_ascii=False, indent=2))
        return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "project-init-env-check"))
