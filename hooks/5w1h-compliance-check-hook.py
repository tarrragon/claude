#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
5W1H Compliance Check Hook

自動檢查 5W1H 決策格式是否符合敏捷重構原則

功能：
- 格式檢查：驗證 Who 和 How 欄位格式
- 合規性檢查：驗證執行者 × 任務類型組合
- 即時阻止：在建立 todo 前阻止違規行為

使用方式：
    PreToolUse Hook 自動觸發 TodoWrite 操作

環境變數：
    HOOK_DEBUG: 啟用詳細日誌（true/false）
"""

import sys
import json
import logging
import re
from pathlib import Path
from typing import Dict, Any, Optional, List

# ============================================================================
# 日誌設置
# ============================================================================

def setup_logging() -> None:
    """初始化日誌系統"""
    import os

    log_level = logging.DEBUG if os.getenv("HOOK_DEBUG") == "true" else logging.INFO

    # 建立日誌目錄
    project_dir = Path(os.getenv("CLAUDE_PROJECT_DIR", Path.cwd()))
    log_dir = project_dir / ".claude" / "hook-logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "5w1h-compliance-hook.log"

    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s] %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stderr)
        ]
    )


# ============================================================================
# 正則表達式定義（基於 Phase 3a 設計）
# ============================================================================

# Who 欄位正則表達式 - 格式 1: 代理人執行（不含 "Who:" 前綴）
WHO_PATTERN_DELEGATE = r'^\s*([a-z-]+)\s*\(執行者\)\s*\|\s*([a-z-]+)\s*\(分派者\)\s*$'

# Who 欄位正則表達式 - 格式 2: 主線程自行執行（不含 "Who:" 前綴）
WHO_PATTERN_SELF = r'^\s*rosemary-project-manager\s*\(自行執行\s*-\s*分派/驗收\)\s*$'

# How 欄位正則表達式（不含 "How:" 前綴，case-insensitive）
HOW_PATTERN = r'^\s*\[Task Type:\s*(implementation|dispatch|review|documentation|analysis|planning)\]\s*(.+)\s*$'


# ============================================================================
# 允許的代理人和任務類型清單
# ============================================================================

ALLOWED_AGENTS = [
    "lavender-interface-designer",
    "sage-test-architect",
    "pepper-test-implementer",
    "parsley-flutter-developer",
    "cinnamon-refactor-owl",
    "mint-format-specialist",
    "thyme-documentation-integrator",
    "memory-network-builder",
    "rosemary-project-manager"
]

ALLOWED_TASK_TYPES = [
    "implementation",
    "dispatch",
    "review",
    "documentation",
    "analysis",
    "planning"
]


# ============================================================================
# 違反組合矩陣（6 種禁止組合）
# ============================================================================

VIOLATION_MATRIX = [
    {
        "executor": "rosemary-project-manager",
        "task_type": "implementation",
        "reason": "主線程不應執行 Implementation 任務",
        "suggestion": "將此任務分派給 parsley-flutter-developer 執行"
    },
    {
        "executor": "lavender-interface-designer",
        "task_type": "implementation",
        "reason": "設計代理人不應執行 Implementation 任務",
        "suggestion": "lavender-interface-designer 負責 TDD Phase 1 功能設計，不執行程式碼實作"
    },
    {
        "executor": "sage-test-architect",
        "task_type": "implementation",
        "reason": "測試設計代理人不應執行 Implementation 任務",
        "suggestion": "sage-test-architect 負責 TDD Phase 2 測試設計，不執行程式碼實作"
    },
    {
        "executor": "parsley-flutter-developer",
        "task_type": "dispatch",
        "reason": "執行代理人不應分派任務",
        "suggestion": "任務分派是主線程的職責"
    },
    {
        "executor": "cinnamon-refactor-owl",
        "task_type": "dispatch",
        "reason": "重構代理人不應分派任務",
        "suggestion": "任務分派是主線程的職責"
    },
    {
        "executor": "thyme-documentation-integrator",
        "task_type": "implementation",
        "reason": "文件代理人不應執行 Implementation 任務",
        "suggestion": "thyme-documentation-integrator 負責文件整合，不執行程式碼實作"
    }
]


# ============================================================================
# 核心函式 1: extract_field()
# ============================================================================

def extract_field(content: str, field_name: str) -> Optional[str]:
    """
    從 todo 內容中提取特定欄位的值

    Args:
        content: 完整的 todo 內容
        field_name: 欄位名稱（"Who" 或 "How"）

    Returns:
        欄位的值（不含欄位名稱），或 None（欄位不存在）
    """
    # 使用正則表達式提取
    pattern = field_name + r':\s*(.+?)(?:\n|$)'
    match = re.search(pattern, content, re.MULTILINE)
    if match:
        return match.group(1)

    return None


# ============================================================================
# 核心函式 2: detect_fullwidth_characters()
# ============================================================================

def detect_fullwidth_characters(text: str) -> Optional[Dict[str, Any]]:
    """
    檢測字串中的全形字元

    Args:
        text: 要檢查的文字

    Returns:
        錯誤資訊字典（含 error, found, suggestion），或 None
    """
    fullwidth_chars = {
        '（': '(',
        '）': ')',
        '【': '[',
        '】': ']',
        '｜': '|'
    }

    found_chars = []
    for char in text:
        if char in fullwidth_chars:
            found_chars.append(char)

    if found_chars:
        return {
            "error": "使用了全形符號",
            "found": found_chars,
            "suggestion": "請替換為半形符號：" + ', '.join([f"{k}→{v}" for k, v in fullwidth_chars.items() if k in found_chars])
        }

    return None


# ============================================================================
# 核心函式 3: parse_who_field()
# ============================================================================

def parse_who_field(who_field: Optional[str]) -> Dict[str, Any]:
    """
    解析 Who 欄位，提取執行者和分派者

    Args:
        who_field: Who 欄位的文字內容

    Returns:
        成功: { "executor": str, "dispatcher": str }
        失敗: { "error": str, "details": dict, "suggestions": list }
    """
    # 步驟 1: 檢查欄位是否存在
    if who_field is None:
        return {
            "error": "缺少必要欄位：Who",
            "details": {
                "violation_type": "format_error",
                "field": "Who"
            },
            "suggestions": [
                "5W1H 決策必須包含 Who 和 How 欄位",
                "Who 欄位格式：{代理人名稱} (執行者) | {分派者名稱} (分派者)"
            ]
        }

    # 步驟 2: 移除前導和尾隨空白
    trimmed = who_field.strip()

    # 步驟 3: 檢查欄位是否為空
    if not trimmed:
        return {
            "error": "Who 欄位不可為空",
            "details": {
                "violation_type": "format_error",
                "field": "Who"
            },
            "suggestions": [
                "Who 欄位格式：{代理人名稱} (執行者) | {分派者名稱} (分派者)"
            ]
        }

    # 步驟 4: 嘗試匹配格式 1（代理人執行）
    match1 = re.match(WHO_PATTERN_DELEGATE, trimmed, re.MULTILINE)
    if match1:
        executor = match1.group(1)
        dispatcher = match1.group(2)
        return {"executor": executor, "dispatcher": dispatcher}

    # 步驟 5: 嘗試匹配格式 2（主線程自行執行）
    match2 = re.match(WHO_PATTERN_SELF, trimmed, re.MULTILINE)
    if match2:
        return {
            "executor": "rosemary-project-manager",
            "dispatcher": "rosemary-project-manager"
        }

    # 步驟 6: 兩種格式都不匹配 → 檢測可能的錯誤原因

    # 6a: 檢測全形字元
    fullwidth_error = detect_fullwidth_characters(trimmed)
    if fullwidth_error:
        return {
            "error": "Who 欄位格式錯誤：使用了全形符號",
            "details": {
                "violation_type": "format_error",
                "field": "Who",
                "current_value": trimmed,
                "expected_format": "使用半形括號和豎線分隔符 |"
            },
            "suggestions": [
                "確認使用半形括號 () 而非全形括號（）",
                "確認使用豎線 | 分隔執行者和分派者",
                "正確範例：Who: parsley-flutter-developer (執行者) | rosemary-project-manager (分派者)"
            ]
        }

    # 6b: 檢查是否缺少執行者/分派者標記
    if "(執行者)" not in trimmed or "(分派者)" not in trimmed:
        return {
            "error": "Who 欄位格式錯誤：缺少執行者/分派者標記",
            "details": {
                "violation_type": "format_error",
                "field": "Who",
                "current_value": trimmed,
                "expected_format": "{代理人名稱} (執行者) | {分派者名稱} (分派者)"
            },
            "suggestions": [
                "使用標準格式：Who: {代理人名稱} (執行者) | rosemary-project-manager (分派者)",
                "或主線程自行執行：Who: rosemary-project-manager (自行執行 - 分派/驗收)"
            ]
        }

    # 6c: 檢查是否缺少豎線分隔符
    if "|" not in trimmed:
        return {
            "error": "Who 欄位格式錯誤：格式不符合標準",
            "details": {
                "violation_type": "format_error",
                "field": "Who",
                "current_value": trimmed,
                "expected_format": "使用半形括號和豎線分隔符 |"
            },
            "suggestions": [
                "確認使用豎線 | 分隔執行者和分派者",
                "正確範例：Who: parsley-flutter-developer (執行者) | rosemary-project-manager (分派者)"
            ]
        }

    # 6d: 其他格式錯誤
    return {
        "error": "Who 欄位格式錯誤：格式不符合標準",
        "details": {
            "violation_type": "format_error",
            "field": "Who",
            "current_value": trimmed,
            "expected_format": "{代理人名稱} (執行者) | {分派者名稱} (分派者)"
        },
        "suggestions": [
            "使用標準格式：Who: parsley-flutter-developer (執行者) | rosemary-project-manager (分派者)",
            "或主線程自行執行：Who: rosemary-project-manager (自行執行 - 分派/驗收)"
        ]
    }


# ============================================================================
# 核心函式 4: parse_how_field()
# ============================================================================

def parse_how_field(how_field: Optional[str]) -> Dict[str, Any]:
    """
    解析 How 欄位，提取任務類型和實作策略

    Args:
        how_field: How 欄位的文字內容

    Returns:
        成功: { "task_type": str, "strategy": str }
        失敗: { "error": str, "details": dict, "suggestions": list }
    """
    # 步驟 1: 檢查欄位是否存在
    if how_field is None:
        return {
            "error": "缺少必要欄位：How",
            "details": {
                "violation_type": "format_error",
                "field": "How"
            },
            "suggestions": [
                "5W1H 決策必須包含 Who 和 How 欄位",
                "How 欄位格式：[Task Type: {任務類型}] {具體實作策略}"
            ]
        }

    # 步驟 2: 移除前導和尾隨空白
    trimmed = how_field.strip()

    # 步驟 3: 檢查欄位是否為空
    if not trimmed:
        return {
            "error": "How 欄位不可為空",
            "details": {
                "violation_type": "format_error",
                "field": "How"
            },
            "suggestions": [
                "How 欄位格式：[Task Type: {任務類型}] {具體實作策略}"
            ]
        }

    # 步驟 4: 使用正則表達式匹配（IGNORECASE 模式）
    match = re.match(HOW_PATTERN, trimmed, re.IGNORECASE | re.MULTILINE)
    if match:
        task_type = match.group(1).lower()
        strategy = match.group(2).strip()
        return {"task_type": task_type, "strategy": strategy}

    # 步驟 5: 格式不匹配 → 檢測可能的錯誤原因

    # 5a: 檢測全形字元
    fullwidth_error = detect_fullwidth_characters(trimmed)
    if fullwidth_error:
        return {
            "error": "How 欄位格式錯誤：使用了全形符號",
            "details": {
                "violation_type": "format_error",
                "field": "How",
                "current_value": trimmed,
                "expected_format": "使用半形方括號 []"
            },
            "suggestions": [
                "確認使用半形方括號 [] 而非全形【】",
                "正確範例：How: [Task Type: Implementation] TDD 實作策略"
            ]
        }

    # 5b: 檢查是否缺少 [Task Type: XXX] 標記
    if "[Task Type:" not in trimmed:
        return {
            "error": "How 欄位格式錯誤：缺少 [Task Type: XXX] 標記",
            "details": {
                "violation_type": "format_error",
                "field": "How",
                "current_value": trimmed,
                "expected_format": "[Task Type: {任務類型}] {具體實作策略}"
            },
            "suggestions": [
                "在 How 欄位開頭加上 [Task Type: XXX] 標記",
                "允許的任務類型：Implementation, Dispatch, Review, Documentation, Analysis, Planning",
                "範例：How: [Task Type: Implementation] TDD 實作策略"
            ]
        }

    # 5c: 檢查是否缺少方括號
    if "[" not in trimmed or "]" not in trimmed:
        return {
            "error": "How 欄位格式錯誤：Task Type 標記格式不正確",
            "details": {
                "violation_type": "format_error",
                "field": "How",
                "current_value": trimmed,
                "expected_format": "使用方括號、冒號和空格：[Task Type: XXX]"
            },
            "suggestions": [
                "確認使用方括號 []",
                "確認使用冒號和空格：Task Type: ",
                "正確範例：How: [Task Type: Implementation] TDD 實作策略"
            ]
        }

    # 5d: 其他格式錯誤（可能是任務類型拼寫錯誤）
    return {
        "error": "How 欄位格式錯誤：任務類型不在允許清單中",
        "details": {
            "violation_type": "format_error",
            "field": "How",
            "current_value": trimmed,
            "expected_format": "必須使用允許的任務類型"
        },
        "suggestions": [
            "允許的任務類型：Implementation, Dispatch, Review, Documentation, Analysis, Planning",
            "檢查是否拼寫錯誤或使用了未定義的類型"
        ]
    }


# ============================================================================
# 核心函式 5: check_compliance()
# ============================================================================

def check_compliance(executor: str, task_type: str) -> Dict[str, Any]:
    """
    檢查執行者 × 任務類型組合是否違反敏捷重構原則

    Args:
        executor: 執行者名稱
        task_type: 任務類型

    Returns:
        成功: { "compliant": True }
        失敗: { "compliant": False, "error": str, "details": dict, "suggestions": list }
    """
    # 步驟 1: 檢查執行者是否在允許清單中
    if executor not in ALLOWED_AGENTS:
        return {
            "compliant": False,
            "error": "Who 欄位格式錯誤：使用了未定義的代理人名稱",
            "details": {
                "violation_type": "format_error",
                "field": "Who",
                "current_value": executor,
                "expected_format": "必須使用允許的代理人清單中的名稱"
            },
            "suggestions": [
                "允許的執行代理人：lavender-interface-designer, sage-test-architect, pepper-test-implementer, parsley-flutter-developer, cinnamon-refactor-owl, mint-format-specialist",
                "允許的文件代理人：thyme-documentation-integrator, memory-network-builder",
                "主線程：rosemary-project-manager"
            ]
        }

    # 步驟 2: 檢查任務類型是否在允許清單中
    if task_type not in ALLOWED_TASK_TYPES:
        return {
            "compliant": False,
            "error": "How 欄位格式錯誤：任務類型不在允許清單中",
            "details": {
                "violation_type": "format_error",
                "field": "How",
                "current_value": task_type,
                "expected_format": "必須使用允許的任務類型"
            },
            "suggestions": [
                "允許的任務類型：Implementation, Dispatch, Review, Documentation, Analysis, Planning",
                "檢查是否拼寫錯誤或使用了未定義的類型"
            ]
        }

    # 步驟 3: 檢查執行者 × 任務類型組合是否違反原則
    for violation in VIOLATION_MATRIX:
        if executor == violation["executor"] and task_type == violation["task_type"]:
            return {
                "compliant": False,
                "error": f"違反敏捷重構原則：{violation['reason']}",
                "details": {
                    "violation_type": "compliance_violation",
                    "field": "Who + How",
                    "current_value": f"執行者={executor}, 任務類型={task_type}",
                    "expected_format": violation["reason"]
                },
                "suggestions": [
                    violation["suggestion"],
                    "修改 Who 欄位為對應的執行代理人",
                    "參考敏捷重構方法論：主線程只負責任務分派和統籌管理"
                ]
            }

    # 步驟 4: 通過合規性檢查
    return {"compliant": True}


# ============================================================================
# 核心函式 6: make_decision()
# ============================================================================

def make_decision(tool_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    整合 3 層檢查並輸出最終決策

    Args:
        tool_input: TodoWrite 工具的輸入 JSON

    Returns:
        { "decision": "allow" | "block", "reason": str, "details": dict (optional), "suggestions": list (optional) }
    """
    try:
        # 步驟 1: 提取 content
        content = tool_input.get("content", "")

        # 步驟 2: 提取 Who 和 How 欄位
        who_field = extract_field(content, "Who")
        how_field = extract_field(content, "How")

        logging.debug(f"提取到 Who 欄位: {who_field}")
        logging.debug(f"提取到 How 欄位: {how_field}")

        # 步驟 3: 第一層檢查 - Who 欄位格式驗證
        who_result = parse_who_field(who_field)
        if "error" in who_result:
            logging.warning(f"Who 欄位格式錯誤: {who_result['error']}")
            return {
                "decision": "block",
                "reason": who_result["error"],
                "details": who_result["details"],
                "suggestions": who_result["suggestions"]
            }

        executor = who_result["executor"]
        dispatcher = who_result["dispatcher"]
        logging.debug(f"解析結果 - 執行者: {executor}, 分派者: {dispatcher}")

        # 步驟 4: 第二層檢查 - How 欄位格式驗證
        how_result = parse_how_field(how_field)
        if "error" in how_result:
            logging.warning(f"How 欄位格式錯誤: {how_result['error']}")
            return {
                "decision": "block",
                "reason": how_result["error"],
                "details": how_result["details"],
                "suggestions": how_result["suggestions"]
            }

        task_type = how_result["task_type"]
        strategy = how_result["strategy"]
        logging.debug(f"解析結果 - 任務類型: {task_type}, 策略: {strategy}")

        # 步驟 5: 第三層檢查 - 合規性檢查
        compliance_result = check_compliance(executor, task_type)
        if not compliance_result.get("compliant", False):
            logging.warning(f"合規性違反: {compliance_result['error']}")
            return {
                "decision": "block",
                "reason": compliance_result["error"],
                "details": compliance_result["details"],
                "suggestions": compliance_result["suggestions"]
            }

        # 步驟 6: 所有檢查通過 → Allow
        logging.info("5W1H 格式檢查通過，符合敏捷重構原則")
        return {
            "decision": "allow",
            "reason": "5W1H 格式檢查通過，符合敏捷重構原則"
        }

    except Exception as e:
        # 優雅降級：Hook 執行錯誤時預設 allow
        logging.error(f"Hook 執行錯誤：{str(e)}")
        logging.debug(f"錯誤堆疊：", exc_info=True)
        return {
            "decision": "allow",
            "reason": "Hook 執行錯誤，預設允許執行"
        }


# ============================================================================
# 主程式入口
# ============================================================================

def main() -> None:
    """主程式入口"""
    setup_logging()

    try:
        # 讀取 stdin 輸入
        input_data = json.load(sys.stdin)
        logging.debug(f"接收到 Hook 輸入: {json.dumps(input_data, ensure_ascii=False, indent=2)}")

        # 提取工具資訊
        tool_name = input_data.get("tool_name")
        tool_input = input_data.get("tool_input", {})

        # 只檢查 TodoWrite 工具
        if tool_name != "TodoWrite":
            logging.info(f"非 TodoWrite 工具（{tool_name}），允許執行")
            result = {"decision": "allow", "reason": "非 TodoWrite 工具"}
        else:
            # 執行決策邏輯
            result = make_decision(tool_input)

        # 輸出結果
        print(json.dumps(result, ensure_ascii=False, indent=2))
        logging.info(f"Hook 決策: {result['decision']}")

        # 設置正確的退出碼
        if result["decision"] == "block":
            sys.exit(1)
        else:
            sys.exit(0)

    except json.JSONDecodeError as e:
        logging.error(f"JSON 解析錯誤: {e}")
        result = {"decision": "allow", "reason": "Hook 執行錯誤，預設允許執行"}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0)

    except Exception as e:
        logging.error(f"未預期的錯誤: {e}")
        logging.debug("錯誤堆疊：", exc_info=True)
        result = {"decision": "allow", "reason": "Hook 執行錯誤，預設允許執行"}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0)


if __name__ == "__main__":
    main()
