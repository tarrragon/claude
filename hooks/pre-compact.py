#!/usr/bin/env python3
"""
🔄 PreCompact Hook - 自動生成上下文恢復提示詞

功能：
- 在 auto-compact 執行前自動生成恢復提示詞
- 確保重要工作狀態不會在上下文壓縮後遺失
- 提供完整的恢復指引和文件引用

觸發時機：
- auto-compact 執行前
- manual compact 執行前 (可選)

輸出：
- 生成 .claude/hook-logs/context-resume-{timestamp}.md
- 記錄當前工作狀態到 .claude/hook-logs/pre-compact-{timestamp}.log
"""

import json
import sys
import os
import subprocess
import datetime
from pathlib import Path

def main():
    try:
        # 讀取 Hook 輸入
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"❌ PreCompact Hook: JSON 解析錯誤: {e}", file=sys.stderr)
        sys.exit(1)

    # 獲取 Hook 資訊
    trigger = input_data.get("trigger", "unknown")
    session_id = input_data.get("session_id", "unknown")
    custom_instructions = input_data.get("custom_instructions", "")

    # 獲取專案目錄
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())

    # 建立時間戳
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # 建立 hook-logs 目錄
    hook_logs_dir = Path(project_dir) / ".claude" / "hook-logs"
    hook_logs_dir.mkdir(parents=True, exist_ok=True)

    # 記錄 Hook 執行日誌
    log_file = hook_logs_dir / f"pre-compact-{timestamp}.log"

    with open(log_file, "w", encoding="utf-8") as f:
        f.write(f"🔄 PreCompact Hook 執行記錄\n")
        f.write(f"時間: {datetime.datetime.now().isoformat()}\n")
        f.write(f"觸發方式: {trigger}\n")
        f.write(f"Session ID: {session_id}\n")
        f.write(f"自訂指令: {custom_instructions}\n")
        f.write(f"專案目錄: {project_dir}\n\n")

    # 檢查是否為 auto-compact 或需要生成恢復提示詞
    should_generate = True

    if trigger == "manual" and not custom_instructions:
        # 手動 compact 但無特殊指令，詢問是否需要生成
        should_generate = True
    elif trigger == "auto":
        # 自動 compact，一定要生成
        should_generate = True

    if should_generate:
        try:
            # 執行生成恢復提示詞腳本
            script_path = Path(project_dir) / ".claude" / "hooks" / "generate-context-resume.sh"

            if script_path.exists():
                result = subprocess.run(
                    [str(script_path)],
                    cwd=project_dir,
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"✅ 恢復提示詞生成結果:\n")
                    f.write(f"返回碼: {result.returncode}\n")
                    f.write(f"標準輸出:\n{result.stdout}\n")
                    if result.stderr:
                        f.write(f"標準錯誤:\n{result.stderr}\n")

                if result.returncode == 0:
                    print(f"✅ PreCompact Hook: 恢復提示詞已生成 (觸發: {trigger})")

                    # 如果是 auto-compact，提供額外上下文
                    if trigger == "auto":
                        context_info = {
                            "hookSpecificOutput": {
                                "hookEventName": "PreCompact",
                                "additionalContext": f"""
🔄 自動壓縮前提醒：

上下文即將被壓縮，重要工作狀態已保存到恢復提示詞。
請在壓縮完成後檢查 .claude/hook-logs/ 目錄中的最新恢復提示詞。

當前工作狀態：
- 觸發時間: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- Session ID: {session_id}
- 專案目錄: {project_dir}

恢復指引：使用最新的 context-resume-*.md 檔案內容作為新對話的起始提示詞。
"""
                            }
                        }
                        print(json.dumps(context_info))
                else:
                    print(f"⚠️ PreCompact Hook: 恢復提示詞生成失敗 (返回碼: {result.returncode})")
            else:
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"❌ 生成腳本不存在: {script_path}\n")
                print(f"❌ PreCompact Hook: 生成腳本不存在: {script_path}")

        except subprocess.TimeoutExpired:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write("❌ 生成腳本執行超時 (30秒)\n")
            print("⚠️ PreCompact Hook: 生成腳本執行超時")

        except Exception as e:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"❌ 執行生成腳本時發生錯誤: {e}\n")
            print(f"❌ PreCompact Hook: 執行錯誤: {e}")
    else:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write("ℹ️ 跳過恢復提示詞生成 (不符合觸發條件)\n")
        print("ℹ️ PreCompact Hook: 跳過恢復提示詞生成")

    # 正常結束，允許 compact 繼續
    sys.exit(0)

if __name__ == "__main__":
    main()