#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.8"
# dependencies = ["pyyaml"]
# ///
"""
代理人分派正確性檢查 Hook
PreToolUse Hook: 在使用 Task 工具前檢查代理人分派是否正確

確保任務類型與代理人匹配（例如 Hook 開發 → basil-hook-architect）。
任務需求完整性檢查已由 Ticket 系統（command-entrance-gate-hook）負責。

重構紀錄:
- v0.31.0: 移除 check_task_requirements（已被 Ticket 檢查機制取代）
- v0.28.0: 使用共用模組和配置檔案
"""

import json
import sys
import re
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# 加入共用模組路徑
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
sys.path.insert(0, str(Path(__file__).parent))


def is_handoff_recovery_mode() -> bool:
    """
    檢查是否處於 Handoff 恢復模式

    Handoff 恢復時，Claude 自動讀取 Ticket 和派發代理人，
    這些操作應被豁免，允許恢復流程正常進行。
    """
    project_dir = Path(os.getenv("CLAUDE_PROJECT_DIR", Path.cwd()))
    handoff_pending_dir = project_dir / ".claude" / "handoff" / "pending"

    # 檢查是否存在 pending Handoff 任務
    if handoff_pending_dir.exists() and handoff_pending_dir.is_dir():
        # 檢查是否有任何 pending JSON 檔案
        if any(handoff_pending_dir.glob("*.json")):
            return True

    return False

from hook_utils import setup_hook_logging
from hook_io import read_hook_input, write_hook_output, create_pretooluse_output
from config_loader import load_agents_config

# Hook 模式常數
HOOK_MODE_STRICT = "strict"
HOOK_MODE_WARNING = "warning"
DEFAULT_HOOK_MODE = HOOK_MODE_STRICT


def get_hook_mode(logger) -> str:
    """取得當前 Hook 運作模式"""
    env_mode = os.environ.get("HOOK_MODE", "").lower()
    if env_mode in [HOOK_MODE_STRICT, HOOK_MODE_WARNING]:
        return env_mode

    try:
        project_root = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
        config_file = Path(project_root) / ".claude" / "hook-config.json"
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                mode = config.get("agent_dispatch_check", {}).get("mode", "").lower()
                if mode in [HOOK_MODE_STRICT, HOOK_MODE_WARNING]:
                    return mode
    except Exception as e:
        logger.warning(f"讀取配置檔案失敗: {e}")

    return DEFAULT_HOOK_MODE


def log_warning_to_file(warning_data: Dict, logger) -> None:
    """記錄警告到 JSONL 檔案"""
    try:
        project_root = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
        log_dir = Path(project_root) / ".claude" / "hook-logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        warning_file = log_dir / "agent-dispatch-warnings.jsonl"
        warning_data["timestamp"] = datetime.now().isoformat()
        with open(warning_file, 'a', encoding='utf-8') as f:
            json.dump(warning_data, f, ensure_ascii=False)
            f.write('\n')
    except Exception as e:
        logger.error(f"記錄警告失敗: {e}")


def detect_task_type(prompt: str, config: Dict, logger) -> str:
    """偵測任務類型"""
    # 優先級 1: 明確 Phase 標記檢測
    explicit_phase_patterns = [
        (r'\[Phase 1[^\]]*\]', "Phase 1 設計"),
        (r'\[Phase 2[^\]]*\]', "Phase 2 測試設計"),
        (r'\[Phase 3a[^\]]*\]', "Phase 3a 策略規劃"),
        (r'\[Phase 3b[^\]]*\]', "Phase 3b 實作"),
        (r'\[Phase 4[^\]]*\]', "Phase 4 重構"),
    ]

    prompt_head = prompt[:500]
    for pattern, task_type in explicit_phase_patterns:
        if re.search(pattern, prompt_head, re.IGNORECASE):
            logger.info(f"檢測到明確 Phase 標記：{task_type}")
            return task_type

    # 優先級 2: 關鍵字權重評估
    weight_map = config.get("weight_map", {"high": 3, "medium": 2, "low": 1})
    exclude_keywords = config.get("exclude_keywords", {})
    task_type_priorities = config.get("task_type_priorities", [])

    task_weights: Dict[str, int] = {}

    for task_config in task_type_priorities:
        task_type = task_config["type"]
        positive_weight = 0
        exclude_penalty = 0

        # 檢查排除關鍵字
        if task_type in exclude_keywords:
            for exclude_keyword in exclude_keywords[task_type]:
                if exclude_keyword in prompt:
                    exclude_penalty += 5

        # 掃描正面關鍵字
        keywords = task_config.get("keywords", {})
        for level, kw_list in keywords.items():
            for keyword in kw_list:
                if keyword in prompt:
                    positive_weight += weight_map.get(level, 1)

        final_weight = positive_weight - exclude_penalty
        if final_weight > 0:
            task_weights[task_type] = final_weight

    if task_weights:
        best_task = max(task_weights, key=task_weights.get)
        logger.info(f"任務類型識別：{best_task} (權重: {task_weights[best_task]})")
        return best_task

    return "未知"


def check_agent_dispatch(prompt: str, current_agent: str, config: Dict, logger) -> Dict:
    """檢查代理人分派是否正確"""
    known_agents = set(config.get("known_agents", []))
    agent_to_task_map = config.get("agent_to_task_map", {})
    agent_dispatch_rules = config.get("agent_dispatch_rules", {})
    dispatch_error_reasons = config.get("dispatch_error_reasons", {})

    if not current_agent:
        return {"is_error": False}

    if current_agent not in known_agents:
        logger.warning(f"未知代理人: {current_agent}")
        return {"is_error": False}

    # 代理人名稱優先判定
    if current_agent in agent_to_task_map:
        expected_task_type = agent_to_task_map[current_agent]
        return {
            "is_error": False,
            "detected_task_type": expected_task_type,
            "correct_agent": current_agent
        }

    # 任務類型關鍵字判定
    task_type = detect_task_type(prompt, config, logger)
    if task_type == "未知":
        return {"is_error": False}

    correct_agent = agent_dispatch_rules.get(task_type, "")
    if current_agent == correct_agent:
        return {
            "is_error": False,
            "detected_task_type": task_type,
            "correct_agent": correct_agent
        }

    # 代理人分派錯誤
    reason = dispatch_error_reasons.get(task_type, "任務類型不匹配")
    error_msg = f"""代理人分派錯誤

任務類型：{task_type}
當前代理人：{current_agent}
正確代理人：{correct_agent}

原因：{reason}
"""
    return {
        "is_error": True,
        "error_message": error_msg,
        "detected_task_type": task_type,
        "correct_agent": correct_agent
    }


def main() -> None:
    """主執行函式"""
    logger = setup_hook_logging("agent-dispatch-check")

    try:
        input_data = read_hook_input()
        if not input_data:
            logger.error("Invalid JSON input")
            sys.exit(1)
    except Exception as e:
        logger.error(f"讀取輸入失敗: {e}")
        sys.exit(1)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    # 只處理 Task 工具
    if tool_name != "Task":
        sys.exit(0)

    prompt = tool_input.get("prompt", "")
    if not prompt:
        output = create_pretooluse_output("deny", "Task 工具缺少 prompt 參數")
        write_hook_output(output)
        sys.exit(0)

    # Handoff 恢復模式：略過所有檢查
    if is_handoff_recovery_mode():
        logger.info("檢測到 Handoff 恢復模式，略過代理人分派檢查")
        sys.exit(0)

    # 載入配置
    config = load_agents_config()

    # 代理人分派檢查
    subagent_type = tool_input.get("subagent_type", "")
    if subagent_type:
        hook_mode = get_hook_mode(logger)
        agent_check_result = check_agent_dispatch(prompt, subagent_type, config, logger)

        if agent_check_result.get("is_error"):
            if hook_mode == HOOK_MODE_STRICT:
                output = create_pretooluse_output(
                    "deny",
                    agent_check_result["error_message"],
                    system_message="代理人分派錯誤，請根據任務類型重新分派"
                )
                write_hook_output(output)
                sys.exit(0)
            else:
                log_warning_to_file({
                    "mode": "warning",
                    "task_type": agent_check_result.get("detected_task_type", "未知"),
                    "wrong_agent": subagent_type,
                    "correct_agent": agent_check_result.get("correct_agent", "未知"),
                    "prompt_preview": prompt[:200]
                }, logger)
                print(f"[WARNING] {agent_check_result['error_message']}")

    logger.info("所有檢查通過")
    sys.exit(0)


if __name__ == "__main__":
    main()
