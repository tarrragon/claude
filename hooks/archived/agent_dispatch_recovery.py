#!/usr/bin/env python3
"""
代理人分派錯誤恢復工具模組

提供錯誤訊息解析、自動重試邏輯和糾正歷史記錄功能。

版本：v0.12.N.7
作者：rosemary-project-manager
日期：2025-10-18

使用範例：
    from agent_dispatch_recovery import dispatch_with_auto_retry, record_agent_correction

    # 自動重試邏輯（主線程使用）
    success, final_agent, attempts = dispatch_with_auto_retry(
        prompt="開發 Hook 腳本",
        initial_agent="parsley-flutter-developer"
    )

    # 記錄糾正歷史
    record_agent_correction(
        task_type="Hook 開發",
        wrong_agent="parsley-flutter-developer",
        correct_agent="basil-hook-architect",
        prompt_preview="開發 Hook 腳本來檢查..."
    )
"""

import re
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List, Tuple


# ========== 配置 ==========

# 日誌檔案路徑
CORRECTION_LOG_FILE = Path(".claude/hook-logs/agent-dispatch-corrections.jsonl")

# 最大重試次數
DEFAULT_MAX_RETRIES = 1


# ========== 錯誤訊息解析 ==========

def parse_agent_dispatch_error(error_message: str) -> Optional[Dict[str, str]]:
    """
    從 Hook 錯誤訊息中解析結構化資訊

    參數:
        error_message: Hook 返回的錯誤訊息

    回傳:
        包含任務類型、當前代理人、正確代理人的字典，無法解析則返回 None

    範例:
        >>> error_msg = '''❌ 代理人分派錯誤：
        ... 任務類型：Hook 開發
        ... 當前代理人：parsley-flutter-developer
        ... 正確代理人：basil-hook-architect'''
        >>> result = parse_agent_dispatch_error(error_msg)
        >>> result['correct_agent']
        'basil-hook-architect'
    """
    result = {}

    # 解析任務類型
    task_type_match = re.search(r"任務類型：(.+)", error_message)
    if task_type_match:
        result["task_type"] = task_type_match.group(1).strip()

    # 解析當前代理人
    current_agent_match = re.search(r"當前代理人：(\S+)", error_message)
    if current_agent_match:
        result["current_agent"] = current_agent_match.group(1).strip()

    # 解析正確代理人
    correct_agent_match = re.search(r"正確代理人：(\S+)", error_message)
    if correct_agent_match:
        result["correct_agent"] = correct_agent_match.group(1).strip()

    # 驗證必要欄位
    if "correct_agent" in result:
        return result

    return None


def should_retry(error_message: str) -> bool:
    """
    判斷是否應該自動重試

    參數:
        error_message: 錯誤訊息

    回傳:
        True 如果應該重試，False 否則

    判斷依據:
        - 錯誤訊息包含「代理人分派錯誤」
        - 錯誤訊息包含「正確代理人：」
    """
    return ("代理人分派錯誤" in error_message and
            "正確代理人：" in error_message)


# ========== 糾正歷史記錄 ==========

def record_agent_correction(
    task_type: str,
    wrong_agent: str,
    correct_agent: str,
    prompt_preview: str = "",
    metadata: Optional[Dict] = None
) -> None:
    """
    記錄代理人分派糾正歷史到日誌檔案

    參數:
        task_type: 任務類型
        wrong_agent: 錯誤的代理人
        correct_agent: 正確的代理人
        prompt_preview: 任務描述預覽（可選）
        metadata: 額外的元數據（可選）

    日誌格式:
        每行一個 JSON 物件（JSONL 格式）
    """
    # 確保日誌目錄存在
    CORRECTION_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    # 建立糾正記錄
    correction = {
        "timestamp": datetime.now().isoformat(),
        "task_type": task_type,
        "wrong_agent": wrong_agent,
        "correct_agent": correct_agent,
        "prompt_preview": prompt_preview[:200] if prompt_preview else "",  # 限制長度
        "metadata": metadata or {}
    }

    # 寫入日誌檔案（JSONL 格式，每行一個 JSON）
    with open(CORRECTION_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(correction, ensure_ascii=False) + "\n")


def get_correction_history(limit: int = 10) -> List[Dict]:
    """
    讀取最近的糾正歷史記錄

    參數:
        limit: 最多返回幾筆記錄

    回傳:
        糾正記錄列表（最新的在前）
    """
    if not CORRECTION_LOG_FILE.exists():
        return []

    corrections = []
    with open(CORRECTION_LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                corrections.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                continue

    # 返回最新的 N 筆記錄
    return corrections[-limit:][::-1]


def get_correction_stats() -> Dict:
    """
    取得糾正統計資訊

    回傳:
        包含總數、各任務類型統計、各代理人統計的字典
    """
    if not CORRECTION_LOG_FILE.exists():
        return {
            "total": 0,
            "by_task_type": {},
            "by_wrong_agent": {},
            "by_correct_agent": {}
        }

    corrections = []
    with open(CORRECTION_LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                corrections.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                continue

    # 統計
    stats = {
        "total": len(corrections),
        "by_task_type": {},
        "by_wrong_agent": {},
        "by_correct_agent": {}
    }

    for correction in corrections:
        task_type = correction.get("task_type", "未知")
        wrong_agent = correction.get("wrong_agent", "未知")
        correct_agent = correction.get("correct_agent", "未知")

        # 按任務類型統計
        stats["by_task_type"][task_type] = stats["by_task_type"].get(task_type, 0) + 1

        # 按錯誤代理人統計
        stats["by_wrong_agent"][wrong_agent] = stats["by_wrong_agent"].get(wrong_agent, 0) + 1

        # 按正確代理人統計
        stats["by_correct_agent"][correct_agent] = stats["by_correct_agent"].get(correct_agent, 0) + 1

    return stats


# ========== 自動重試邏輯（參考實作）==========

def dispatch_with_auto_retry(
    prompt: str,
    initial_agent: str,
    description: str = "",
    max_retries: int = DEFAULT_MAX_RETRIES,
    dry_run: bool = True
) -> Tuple[bool, str, List[str]]:
    """
    智慧任務分派（支援自動糾正）

    參數:
        prompt: 任務描述
        initial_agent: 初始分派的代理人
        description: 任務簡短描述
        max_retries: 最大重試次數（預設 1 次）
        dry_run: 是否為測試模式（不實際執行任務）

    回傳:
        (是否成功, 最終代理人, 嘗試歷史)

    使用範例:
        >>> success, agent, attempts = dispatch_with_auto_retry(
        ...     prompt="開發 Hook 腳本",
        ...     initial_agent="parsley-flutter-developer"
        ... )
        >>> if success:
        ...     print(f"成功分派給 {agent}")

    注意:
        此函式為參考實作，實際使用時需要整合到主線程的任務分派邏輯中。
        dry_run=True 時不會實際執行 Task 工具。
    """
    current_agent = initial_agent
    attempts = [initial_agent]

    for attempt in range(max_retries + 1):
        try:
            if dry_run:
                # 測試模式：模擬成功
                print(f"[DRY RUN] 嘗試分派給 {current_agent}")
                return (True, current_agent, attempts)

            # 實際模式：調用 Task 工具（需要在主線程中實作）
            # result = Task(
            #     subagent_type=current_agent,
            #     description=description,
            #     prompt=prompt
            # )
            #
            # return (True, current_agent, attempts)

            raise NotImplementedError("實際執行模式需要在主線程中實作")

        except Exception as e:
            error_msg = str(e)

            # 檢查是否是代理人分派錯誤
            if not should_retry(error_msg):
                # 其他類型的錯誤，不重試
                return (False, current_agent, attempts)

            # 解析正確的代理人
            parsed = parse_agent_dispatch_error(error_msg)

            if not parsed or attempt >= max_retries:
                # 無法解析或已達最大重試次數
                return (False, current_agent, attempts)

            # 記錄糾正
            record_agent_correction(
                task_type=parsed.get("task_type", "未知"),
                wrong_agent=current_agent,
                correct_agent=parsed["correct_agent"],
                prompt_preview=prompt[:200]
            )

            # 更新代理人並重試
            current_agent = parsed["correct_agent"]
            attempts.append(current_agent)

            print(f"🔄 代理人分派糾正：{parsed.get('current_agent')} → {current_agent}")
            print(f"🔄 自動重試中...（第 {attempt + 2} 次嘗試）")

    return (False, current_agent, attempts)


# ========== CLI 工具 ==========

def main():
    """
    命令列工具：查看糾正歷史和統計
    """
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "stats":
        # 顯示統計資訊
        stats = get_correction_stats()
        print(f"\n📊 代理人分派糾正統計\n")
        print(f"總糾正次數：{stats['total']}\n")

        if stats['by_task_type']:
            print("按任務類型統計：")
            for task_type, count in sorted(stats['by_task_type'].items(), key=lambda x: -x[1]):
                print(f"  {task_type}: {count} 次")
            print()

        if stats['by_wrong_agent']:
            print("最常被糾正的代理人：")
            for agent, count in sorted(stats['by_wrong_agent'].items(), key=lambda x: -x[1])[:5]:
                print(f"  {agent}: {count} 次")
            print()

    elif len(sys.argv) > 1 and sys.argv[1] == "history":
        # 顯示最近的糾正歷史
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        history = get_correction_history(limit)

        print(f"\n📋 最近 {len(history)} 筆糾正記錄\n")
        for i, record in enumerate(history, 1):
            print(f"{i}. [{record['timestamp']}]")
            print(f"   任務類型：{record['task_type']}")
            print(f"   糾正：{record['wrong_agent']} → {record['correct_agent']}")
            if record.get('prompt_preview'):
                print(f"   任務：{record['prompt_preview']}")
            print()

    else:
        # 顯示使用說明
        print("""
代理人分派錯誤恢復工具

使用方式：
  python agent_dispatch_recovery.py stats    - 顯示統計資訊
  python agent_dispatch_recovery.py history [N]  - 顯示最近 N 筆記錄

Python 模組使用：
  from agent_dispatch_recovery import parse_agent_dispatch_error, record_agent_correction

  # 解析錯誤訊息
  parsed = parse_agent_dispatch_error(error_msg)

  # 記錄糾正歷史
  record_agent_correction(
      task_type="Hook 開發",
      wrong_agent="parsley-flutter-developer",
      correct_agent="basil-hook-architect"
  )
""")


if __name__ == "__main__":
    main()
