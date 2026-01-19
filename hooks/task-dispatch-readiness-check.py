#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.8"
# dependencies = ["pyyaml"]
# ///
"""
任務分派準備度檢查 Hook
PreToolUse Hook: 在使用 Task 工具前檢查是否包含必要參考文件和代理人分派正確性

符合敏捷重構方法論的任務分派原則，確保所有任務都有完整的需求依據和正確的代理人分派

重構紀錄 (v0.28.0):
- 使用 .claude/lib/hook_logging 共用模組
- 使用 .claude/lib/hook_io 共用模組
- 使用 .claude/config/agents.yaml 配置檔案
- 從 858 行精簡至約 300 行
"""

import json
import sys
import re
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# 添加 lib 目錄到路徑
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from hook_logging import setup_hook_logging
from hook_io import read_hook_input, write_hook_output, create_pretooluse_output
from config_loader import load_agents_config

# 設定日誌
logger = setup_hook_logging("agent-dispatch-check")

# Hook 模式常數
HOOK_MODE_STRICT = "strict"
HOOK_MODE_WARNING = "warning"
DEFAULT_HOOK_MODE = HOOK_MODE_STRICT


def get_hook_mode() -> str:
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


def log_warning_to_file(warning_data: Dict) -> None:
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


def detect_task_type(prompt: str, config: Dict) -> str:
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


def check_agent_dispatch(prompt: str, current_agent: str, config: Dict) -> Dict:
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
    task_type = detect_task_type(prompt, config)
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


def check_task_requirements(prompt: str, config: Dict) -> List[str]:
    """檢查任務必要參考文件"""
    missing_items = []
    task_detection = config.get("task_detection", {})

    # 識別任務類型
    infrastructure_keywords = task_detection.get("infrastructure_keywords", [])
    documentation_keywords = task_detection.get("documentation_keywords", [])

    is_infrastructure_task = any(
        re.search(kw, prompt, re.IGNORECASE) for kw in infrastructure_keywords
    )
    is_documentation_task = any(
        re.search(kw, prompt, re.IGNORECASE) for kw in documentation_keywords
    )
    is_phase4_task = bool(re.search(r'Phase 4|重構評估|cinnamon-refactor-owl', prompt, re.IGNORECASE))
    is_phase3b_test_task = bool(re.search(r'Phase 3b.*測試|實作測試|撰寫測試程式碼|test/unit/', prompt, re.IGNORECASE))

    # 跳過特定任務類型的檢查
    if is_infrastructure_task or is_documentation_task or is_phase4_task or is_phase3b_test_task:
        return []

    # UseCase 參考檢查
    if not re.search(r'UC-\d{2}', prompt):
        missing_items.append("UseCase 參考 (格式: UC-XX)")

    # Event 參考檢查
    if not re.search(r'Event \d+|事件 \d+', prompt, re.IGNORECASE):
        missing_items.append("流程圖 Event 參考")

    # 架構規範引用檢查
    architecture_patterns = task_detection.get("architecture_patterns", [])
    if not any(re.search(p, prompt, re.IGNORECASE) for p in architecture_patterns):
        missing_items.append("架構規範引用")

    # 依賴類別說明檢查
    dependency_patterns = task_detection.get("dependency_patterns", [])
    if not any(re.search(p, prompt, re.IGNORECASE) for p in dependency_patterns):
        missing_items.append("依賴類別說明")

    return missing_items


def main() -> None:
    """主執行函式"""
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

    # 載入配置
    config = load_agents_config()

    # 檢查必要參考文件
    missing_items = check_task_requirements(prompt, config)
    if missing_items:
        reason = f"任務分派準備度不足，缺失: {', '.join(missing_items)}"
        output = create_pretooluse_output("deny", reason)
        write_hook_output(output)
        sys.exit(0)

    # 代理人分派檢查
    subagent_type = tool_input.get("subagent_type", "")
    if subagent_type:
        hook_mode = get_hook_mode()
        agent_check_result = check_agent_dispatch(prompt, subagent_type, config)

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
                })
                print(f"[WARNING] {agent_check_result['error_message']}", file=sys.stderr)

    logger.info("所有檢查通過")
    sys.exit(0)


if __name__ == "__main__":
    main()
