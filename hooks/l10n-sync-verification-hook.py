#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
L10n 生成流程同步驗證 Hook (PostEdit)

功能: 偵測 ARB 檔案變更，驗證是否需要執行 flutter gen-l10n 生成步驟
規範: ARB 檔案修改後必須執行 flutter gen-l10n 更新對應的 Dart 生成檔案

觸發時機: 編輯 .arb 檔案後執行
檢查位置: lib/l10n/ 目錄中的所有 ARB 檔案

執行結果:
  - ARB 和生成檔案同步: 無警告，正常結束
  - ARB 新於生成檔案: 警告使用者執行 flutter gen-l10n
  - 生成檔案不存在: 錯誤，要求執行 flutter gen-l10n
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from hook_utils import setup_hook_logging, run_hook_safely


def get_project_root() -> Path:
    """取得專案根目錄"""
    return Path(os.getenv("CLAUDE_PROJECT_DIR", Path.cwd()))


def is_arb_file(file_path: str) -> bool:
    """檢查是否為 ARB 檔案"""
    return file_path.endswith(".arb") and "l10n" in file_path


def get_arb_files(project_root: Path) -> list[Path]:
    """取得所有 ARB 檔案"""
    l10n_dir = project_root / "lib" / "l10n"
    if not l10n_dir.exists():
        return []

    arb_files = []
    for file in l10n_dir.glob("app_*.arb"):
        # 跳過備份檔案
        if not file.name.endswith(".bak"):
            arb_files.append(file)

    return arb_files


def get_generated_dart_file(arb_file: Path) -> Path:
    """根據 ARB 檔案取得對應的生成 Dart 檔案"""
    # app_en.arb -> app_localizations_en.dart
    # app_zh_TW.arb -> app_localizations_zh.dart (注意：Flutter gen-l10n 的命名規則)
    arb_name = arb_file.stem  # 去掉 .arb
    lang_code = arb_name.replace("app_", "")

    # 特殊處理：Flutter gen-l10n 使用簡化的語言碼
    # app_zh_TW.arb 對應 app_localizations_zh.dart
    if "_" in lang_code:
        lang_code = lang_code.split("_")[0]

    # 主要的 AppLocalizations 檔案
    if arb_name == "app":
        dart_file = arb_file.parent / "generated" / "app_localizations.dart"
    else:
        dart_file = arb_file.parent / "generated" / f"app_localizations_{lang_code}.dart"

    return dart_file


def check_l10n_sync(project_root: Path, logger) -> tuple[bool, str, dict]:
    """
    檢查 L10n 同步狀態

    返回: (is_synced, decision, details)
      - is_synced: True 表示已同步，False 表示需要重新生成
      - decision: "allow" (同步) 或 "warn" (不同步) 或 "error" (缺少生成檔案)
      - details: 詳細檢查結果
    """
    arb_files = get_arb_files(project_root)

    if not arb_files:
        return True, "allow", {"reason": "未找到 ARB 檔案"}

    details = {
        "arb_files_checked": [],
        "sync_status": {},
        "out_of_sync_files": [],
        "missing_generated_files": []
    }

    needs_regeneration = False
    missing_files = []

    for arb_file in arb_files:
        dart_file = get_generated_dart_file(arb_file)
        arb_mtime = arb_file.stat().st_mtime
        arb_mtime_str = datetime.fromtimestamp(arb_mtime).isoformat()

        details["arb_files_checked"].append(arb_file.name)

        if not dart_file.exists():
            # 生成檔案不存在
            details["sync_status"][arb_file.name] = "missing"
            details["missing_generated_files"].append(dart_file.name)
            needs_regeneration = True
            missing_files.append(dart_file.name)
        else:
            dart_mtime = dart_file.stat().st_mtime
            dart_mtime_str = datetime.fromtimestamp(dart_mtime).isoformat()

            if arb_mtime > dart_mtime:
                # ARB 檔案新於生成檔案
                details["sync_status"][arb_file.name] = "out_of_sync"
                details["out_of_sync_files"].append({
                    "arb_file": arb_file.name,
                    "arb_mtime": arb_mtime_str,
                    "dart_file": dart_file.name,
                    "dart_mtime": dart_mtime_str
                })
                needs_regeneration = True
            else:
                # 已同步
                details["sync_status"][arb_file.name] = "synced"

    if missing_files:
        return False, "error", details

    if needs_regeneration:
        return False, "warn", details

    return True, "allow", details


def run_flutter_gen_l10n(project_root: Path, logger) -> tuple[bool, str]:
    """
    自動執行 flutter gen-l10n 生成 L10n 檔案

    返回: (success, message)
    """
    try:
        result = subprocess.run(
            ["flutter", "gen-l10n"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=60
        )

        logger.info("auto_gen_l10n: return_code=%d, stdout=%s, stderr=%s",
                    result.returncode,
                    result.stdout[:500] if result.stdout else "",
                    result.stderr[:500] if result.stderr else "")

        if result.returncode == 0:
            return True, "✅ 自動執行 flutter gen-l10n 成功"
        else:
            return False, f"❌ flutter gen-l10n 執行失敗: {result.stderr}"

    except subprocess.TimeoutExpired:
        return False, "❌ flutter gen-l10n 執行超時 (60s)"
    except FileNotFoundError:
        return False, "❌ 找不到 flutter 命令，請確保 Flutter 已安裝並在 PATH 中"
    except Exception as e:
        return False, f"❌ 執行 flutter gen-l10n 時發生錯誤: {e}"


def generate_error_message(details: dict) -> str:
    """生成錯誤訊息"""
    message = ""

    if details.get("missing_generated_files"):
        message += "❌ 錯誤: L10n 生成檔案缺失\n\n"
        message += "以下生成檔案不存在:\n"
        for dart_file in details["missing_generated_files"]:
            message += f"  - {dart_file}\n"
        message += "\n"

    if details.get("out_of_sync_files"):
        message += "⚠️  警告: ARB 檔案未同步\n\n"
        message += "以下 ARB 檔案新於其對應的生成檔案:\n"
        for item in details["out_of_sync_files"]:
            message += f"  - {item['arb_file']} (修改: {item['arb_mtime']})\n"
            message += f"    → {item['dart_file']} (生成: {item['dart_mtime']})\n"
        message += "\n"

    message += "📋 修復步驟:\n"
    message += "1. 執行命令: flutter gen-l10n\n"
    message += "2. 驗證生成成功: flutter analyze\n"
    message += "3. 重新執行編輯操作或提交\n\n"

    message += "📖 詳細資訊:\n"
    message += f"  - 檢查的 ARB 檔案: {', '.join(details.get('arb_files_checked', []))}\n"
    message += f"  - 同步狀態: {json.dumps(details.get('sync_status', {}), ensure_ascii=False, indent=2)}\n"

    return message


def main() -> int:
    """主程式"""
    logger = setup_hook_logging("l10n-sync-verification")
    project_root = get_project_root()

    try:
        # 讀取 stdin JSON (Hook 輸入)
        input_data = json.load(sys.stdin)

        # 檢查編輯的檔案是否為 ARB 檔案
        tool_input = input_data.get("tool_input", {})
        file_path = tool_input.get("file_path", "")

        # 只在編輯 ARB 檔案時執行檢查
        if not is_arb_file(file_path):
            # 非 ARB 檔案，不需要檢查
            logger.debug("非 ARB 檔案，跳過檢查: %s", file_path)
            return 0

        # 執行 L10n 同步檢查
        is_synced, decision, details = check_l10n_sync(project_root, logger)

        # 記錄檢查結果
        logger.info("l10n_check: file_edited=%s, is_synced=%s, decision=%s",
                    file_path, is_synced, decision)

        # 輸出結果
        if is_synced:
            # L10n 已同步，允許繼續
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "decision": "allow"
                }
            }
            print(json.dumps(output, ensure_ascii=False))
            return 0
        else:
            # ARB 不同步或生成檔案缺失，自動執行 flutter gen-l10n
            print("偵測到 L10n 不同步，自動執行 flutter gen-l10n...")

            gen_success, gen_message = run_flutter_gen_l10n(project_root, logger)
            print(gen_message)

            if gen_success:
                # 自動生成成功，允許繼續
                output = {
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                        "decision": "allow",
                        "reason": "ARB 檔案已修改，已自動執行 flutter gen-l10n 更新生成檔案"
                    }
                }
                print(json.dumps(output, ensure_ascii=False))
                return 0
            else:
                # 自動生成失敗，顯示手動修復步驟
                error_msg = generate_error_message(details)
                print(error_msg)

                output = {
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                        "decision": "block"
                    }
                }
                print(json.dumps(output, ensure_ascii=False))
                return 2

    except json.JSONDecodeError as e:
        logger.error("JSON 解析錯誤: %s", e)
        print(f"Error: Invalid JSON input: {e}")
        return 1
    except Exception as e:
        logger.error("執行錯誤: %s", e)
        raise


if __name__ == "__main__":
    exit_code = run_hook_safely(main, "l10n-sync-verification")
    sys.exit(exit_code)
