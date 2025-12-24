#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.8"
# dependencies = []
# ///
"""
任務分派準備度檢查 Hook
PreToolUse Hook: 在使用 Task 工具前檢查是否包含必要參考文件和代理人分派正確性

符合敏捷重構方法論的任務分派原則，確保所有任務都有完整的需求依據和正確的代理人分派
"""

import json
import sys
import re
import os
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path

# ===== Hook 模式配置 =====

# Hook 運作模式
HOOK_MODE_STRICT = "strict"    # 嚴格模式：阻擋執行
HOOK_MODE_WARNING = "warning"  # 警告模式：記錄警告但允許執行

# 預設模式
DEFAULT_HOOK_MODE = HOOK_MODE_STRICT

# ===== 代理人分派檢查常數 =====

# 已知代理人清單
KNOWN_AGENTS: List[str] = [
    "basil-hook-architect",
    "thyme-documentation-integrator",
    "mint-format-specialist",
    "lavender-interface-designer",
    "sage-test-architect",
    "pepper-test-implementer",
    "cinnamon-refactor-owl",
    "parsley-flutter-developer",
    "memory-network-builder",
    "rosemary-project-manager"
]

# 已知代理人集合（快速查找）
KNOWN_AGENTS_SET = set(KNOWN_AGENTS)

# 任務類型對應代理人規則
AGENT_DISPATCH_RULES: Dict[str, str] = {
    "Hook 開發": "basil-hook-architect",
    "文件整合": "thyme-documentation-integrator",
    "程式碼格式化": "mint-format-specialist",
    "Phase 1 設計": "lavender-interface-designer",
    "Phase 2 測試設計": "sage-test-architect",
    "Phase 3a 策略規劃": "pepper-test-implementer",
    "Phase 3b 實作": "parsley-flutter-developer",  # Phase 3b Flutter/Dart 實作
    "Phase 4 重構": "cinnamon-refactor-owl",
    "記憶網路建構": "memory-network-builder"
}

# 任務類型優先級和關鍵字
# 優先級順序：TDD Phase 1-4 > 專業任務 > 應用程式開發
TASK_TYPE_PRIORITIES: List[Dict] = [
    # ===== TDD 四階段（最高優先級） =====
    {
        "type": "Phase 1 設計",
        "keywords": {
            "high": ["Phase 1", "功能設計", "需求規格"],
            "medium": ["設計階段", "功能規劃"],
            "low": ["設計文件"]
        },
        "weight_threshold": 3
    },
    {
        "type": "Phase 2 測試設計",
        "keywords": {
            "high": ["Phase 2", "測試設計", "測試案例設計"],
            "medium": ["測試計畫", "測試規劃"],
            "low": ["測試文件"]
        },
        "weight_threshold": 3
    },
    {
        "type": "Phase 3a 策略規劃",
        "keywords": {
            "high": ["Phase 3a", "語言無關策略", "虛擬碼設計"],
            "medium": ["策略規劃", "虛擬碼", "實作策略規劃"],
            "low": ["實作計畫"]
        },
        "weight_threshold": 3
    },
    {
        "type": "Phase 3b 實作",
        "keywords": {
            "high": ["Phase 3b", "[Phase 3b 實作]", "Flutter/Dart 實作", "將虛擬碼轉換"],
            "medium": ["Dart 實作", "Flutter 實作", "parsley-flutter-developer", "實作測試", "撰寫測試程式碼"],
            "low": ["實作程式碼", "撰寫程式", "建立測試檔案", "test/unit/", "flutter test"]
        },
        "weight_threshold": 3
    },
    {
        "type": "Phase 4 重構",
        "keywords": {
            "high": ["Phase 4", "重構評估", "程式碼品質評估", "cinnamon-refactor-owl"],
            "medium": ["重構建議", "品質改善", "重構執行", "重構決策"],
            "low": ["程式碼檢視", "測試通過率", "執行測試", "測試驗證", "重構後驗證"]
        },
        "weight_threshold": 3
    },
    # ===== 專業任務（次優先級） =====
    {
        "type": "Hook 開發",
        "keywords": {
            "high": ["開發 Hook", "Hook 系統", "撰寫 Hook", "實作 Hook", "建立 Hook", "Hook 開發"],
            "medium": [".claude/hooks/", "PreToolUse", "PostToolUse", "Hook 整合", "擴展 Hook", "修改 Hook"],
            "low": ["Hook 配置", "Hook 測試"]
        },
        "weight_threshold": 3
    },
    {
        "type": "文件整合",
        "keywords": {
            "high": ["文件整合", "方法論轉化", "work-log → 方法論"],
            "medium": ["整合文件", "方法論整合", "文件合併"],
            "low": ["文件更新", "文件同步"]
        },
        "weight_threshold": 3
    },
    {
        "type": "程式碼格式化",
        "keywords": {
            "high": ["格式化", "Lint 修復", "程式碼品質修正"],
            "medium": ["dart format", "修復格式", "整理程式碼"],
            "low": ["程式碼風格", "縮排調整"]
        },
        "weight_threshold": 3
    },
    # ===== 應用程式開發（最低優先級） =====
    {
        "type": "應用程式開發",
        "keywords": {
            "high": ["實作 Widget", "開發應用程式", "Flutter 開發"],
            "medium": ["撰寫程式碼", "實作功能"],
            "low": ["程式開發"]
        },
        "weight_threshold": 3
    },
    {
        "type": "記憶網路建構",
        "keywords": {
            "high": ["建立記憶網路", "知識圖譜", "決策記錄"],
            "medium": ["記憶建構", "知識管理"],
            "low": ["記錄決策"]
        },
        "weight_threshold": 3
    }
]

# 權重定義
WEIGHT_MAP: Dict[str, int] = {
    "high": 3,
    "medium": 2,
    "low": 1
}

# 排除關鍵字配置（方案 A）
# 用於處理「Phase X 完成」等負面語境，每次匹配扣 5 分
EXCLUDE_KEYWORDS: Dict[str, List[str]] = {
    "Phase 1 設計": [
        "Phase 1 完成",
        "Phase 1 產出",
        "Phase 1 已完成",
        "基於 Phase 1",
        "參考 Phase 1",
        "Phase 1 交付物",
        "Phase 1 設計完成",
        "依據 Phase 1"
    ],
    "Phase 2 測試設計": [
        "Phase 2 完成",
        "Phase 2 產出",
        "Phase 2 已完成",
        "基於 Phase 2",
        "參考 Phase 2",
        "Phase 2 交付物",
        "Phase 2 測試完成",
        "依據 Phase 2"
    ],
    "Phase 3a 策略規劃": [
        "Phase 3a 完成",
        "Phase 3a 產出",
        "Phase 3a 已完成",
        "基於 Phase 3a",
        "參考 Phase 3a",
        "Phase 3a 交付物",
        "Phase 3a 虛擬碼",
        "依據 Phase 3a"
    ],
    "Phase 3b 實作": [
        "Phase 3b 完成",
        "Phase 3b 產出",
        "Phase 3b 已完成",
        "基於 Phase 3b",
        "參考 Phase 3b",
        "Phase 3b 交付物"
    ],
    "Phase 4 重構": [
        "Phase 4 完成",
        "Phase 4 產出",
        "Phase 4 已完成",
        "基於 Phase 4",
        "參考 Phase 4",
        "Phase 4 交付物"
    ]
}

# 專案類型快取
_PROJECT_TYPE_CACHE: Optional[str] = None

# 設定日誌
def setup_logging() -> logging.Logger:
    """設定日誌"""
    logger = logging.getLogger("agent_dispatch_check")
    logger.setLevel(logging.DEBUG)

    project_root = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    log_dir = os.path.join(project_root, ".claude", "hook-logs")
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, f"agent-dispatch-check-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log")

    handler = logging.FileHandler(log_file, encoding='utf-8')
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger

logger = setup_logging()


# ===== Hook 模式管理函式 =====

def get_hook_mode() -> str:
    """
    取得當前 Hook 運作模式

    優先級：
    1. 環境變數 HOOK_MODE
    2. 配置檔案 .claude/hook-config.json
    3. 預設值 strict

    Returns:
        str - "strict" 或 "warning"
    """
    # 優先級 1: 環境變數
    env_mode = os.environ.get("HOOK_MODE", "").lower()
    if env_mode in [HOOK_MODE_STRICT, HOOK_MODE_WARNING]:
        logger.info(f"使用環境變數模式: {env_mode}")
        return env_mode

    # 優先級 2: 配置檔案
    try:
        project_root = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
        config_file = Path(project_root) / ".claude" / "hook-config.json"

        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                mode = config.get("agent_dispatch_check", {}).get("mode", "").lower()

                if mode in [HOOK_MODE_STRICT, HOOK_MODE_WARNING]:
                    logger.info(f"使用配置檔案模式: {mode}")
                    return mode
    except Exception as e:
        logger.warning(f"讀取配置檔案失敗: {e}")

    # 優先級 3: 預設值
    logger.info(f"使用預設模式: {DEFAULT_HOOK_MODE}")
    return DEFAULT_HOOK_MODE


def log_warning_to_file(warning_data: Dict) -> None:
    """
    記錄警告到 JSONL 檔案

    Parameters:
        warning_data: dict - 警告資料
    """
    try:
        project_root = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
        log_dir = Path(project_root) / ".claude" / "hook-logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        warning_file = log_dir / "agent-dispatch-warnings.jsonl"

        # 加入時間戳記
        warning_data["timestamp"] = datetime.now().isoformat()

        # 追加寫入 JSONL
        with open(warning_file, 'a', encoding='utf-8') as f:
            json.dump(warning_data, f, ensure_ascii=False)
            f.write('\n')

        logger.info(f"警告已記錄到: {warning_file}")
    except Exception as e:
        logger.error(f"記錄警告失敗: {e}")


def main() -> None:
    """主執行函式"""
    # 1. 讀取 JSON 輸入
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON input: {e}")
        sys.exit(1)

    # 2. 提取必要資訊
    hook_event = input_data.get("hook_event_name", "")
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    # 3. 只處理 Task 工具
    if tool_name != "Task":
        sys.exit(0)  # 不是 Task 工具，跳過檢查

    # 4. 提取 prompt 參數
    prompt = tool_input.get("prompt", "")

    if not prompt:
        # 沒有 prompt，可能是空任務
        logger.warning("Task 工具缺少 prompt 參數")
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "Task 工具缺少 prompt 參數"
            },
            "suppressOutput": True
        }
        print(json.dumps(output, ensure_ascii=False))
        sys.exit(0)

    # 5. 檢查必要參考文件（敏捷重構方法論要求）
    missing_items = []

    # 5.1 識別任務類型（基礎設施 vs UseCase vs 文件編寫）
    infrastructure_keywords = [
        r'Hook 系統',
        r'Hook 開發',
        r'基礎設施',
        r'Infrastructure',
        r'方法論',
        r'Methodology',
        r'文件更新',
        r'架構改善'
    ]

    # 5.1.1 識別文件編寫任務
    documentation_keywords = [
        r'\.md',  # 檔案路徑包含 .md
        r'文件編寫',
        r'文件撰寫',
        r'方法論設計',
        r'方法論驗證',
        r'測試驗證',
        r'Phase \d+ - 測試驗證',
        r'Phase \d+ - 功能設計',
        r'Phase \d+ - 重構優化',
        r'設計文件',
        r'驗證文件',
        r'審查文件',
        r'評估文件',
        r'文件品質',
        r'README',
        r'CHANGELOG',
        r'文檔',
        r'Documentation'
    ]

    is_infrastructure_task = any(re.search(keyword, prompt, re.IGNORECASE) for keyword in infrastructure_keywords)
    is_documentation_task = any(re.search(keyword, prompt, re.IGNORECASE) for keyword in documentation_keywords)

    # 5.1.2 識別 Phase 4 重構任務
    is_phase4_task = bool(re.search(r'Phase 4|重構評估|cinnamon-refactor-owl', prompt, re.IGNORECASE))

    # 5.1.3 識別 Phase 3b 測試實作任務
    is_phase3b_test_task = bool(re.search(r'Phase 3b.*測試|實作測試|撰寫測試程式碼|test/unit/', prompt, re.IGNORECASE))

    # 5.2 UseCase 開發任務必須包含 UseCase 和 Event 參考
    # 文件編寫任務、基礎設施任務、Phase 4 重構任務和 Phase 3b 測試實作不需要這些檢查
    if not is_infrastructure_task and not is_documentation_task and not is_phase4_task and not is_phase3b_test_task:
        # 檢查 UseCase 參考 (UC-XX 格式)
        if not re.search(r'UC-\d{2}', prompt):
            missing_items.append("UseCase 參考 (格式: UC-XX)")

        # 檢查流程圖 Event 參考（支援中英文）
        if not re.search(r'Event \d+|事件 \d+', prompt, re.IGNORECASE):
            missing_items.append("流程圖 Event 參考")

    # 5.3 架構規範引用檢查（文件編寫任務、Phase 4 重構任務和 Phase 3b 測試實作不需要）
    if not is_documentation_task and not is_phase4_task and not is_phase3b_test_task:
        architecture_patterns = [
            r'Clean Architecture',
            r'Domain 層',
            r'Application 層',
            r'Presentation 層',
            r'Infrastructure 層'
        ]
        if not any(re.search(pattern, prompt, re.IGNORECASE) for pattern in architecture_patterns):
            missing_items.append("架構規範引用")

    # 5.4 依賴類別說明檢查（文件編寫任務、基礎設施任務、Phase 4 重構任務和 Phase 3b 測試實作不需要）
    if not is_infrastructure_task and not is_documentation_task and not is_phase4_task and not is_phase3b_test_task:
        dependency_patterns = [
            r'Repository',
            r'Service',
            r'Entity',
            r'ValueObject',
            r'UseCase'
        ]
        if not any(re.search(pattern, prompt, re.IGNORECASE) for pattern in dependency_patterns):
            missing_items.append("依賴類別說明")

    # 6. 如果缺少必要項目，提供詳細建議
    if missing_items:
        # 生成建議訊息
        suggestions = []

        if "UseCase 參考 (格式: UC-XX)" in missing_items:
            suggestions.append("- 請參考 docs/app-use-cases.md 並引用相關 UseCase 編號")

        if "流程圖 Event 參考" in missing_items:
            suggestions.append("- 請參考事件驅動架構設計文件，標明處理哪些 Event")

        if "架構規範引用" in missing_items:
            suggestions.append("- 請明確指出任務屬於哪個架構層級 (Domain/Application/Presentation/Infrastructure)")

        if "依賴類別說明" in missing_items:
            suggestions.append("- 請說明需要依賴哪些 Repository、Service、Entity 等類別")

        reason = f"任務分派準備度不足，缺失: {', '.join(missing_items)}\n\n建議補充:\n" + "\n".join(suggestions)

        logger.warning(f"現有檢查失敗: {reason}")
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason
            },
            "systemMessage": "⚠️ 請補充完整的參考文件後重新分派任務（符合敏捷重構方法論）"
        }
        print(json.dumps(output, ensure_ascii=False))
        sys.exit(0)

    logger.info("現有檢查通過")

    # 7. 新增：代理人分派檢查（支援模式切換）
    subagent_type = tool_input.get("subagent_type", "")

    if subagent_type:  # 只在有指定代理人時才檢查
        logger.info(f"開始代理人分派檢查，當前代理人: {subagent_type}")

        # 讀取 Hook 模式
        hook_mode = get_hook_mode()
        logger.info(f"Hook 模式: {hook_mode}")

        agent_check_result = check_agent_dispatch(prompt, subagent_type)

        if agent_check_result["is_error"]:
            logger.error(f"代理人檢查失敗: {agent_check_result['error_message']}")

            if hook_mode == HOOK_MODE_STRICT:
                # 嚴格模式：阻擋執行
                output = {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": agent_check_result["error_message"]
                    },
                    "systemMessage": "⚠️ 代理人分派錯誤，請根據任務類型重新分派"
                }
                print(json.dumps(output, ensure_ascii=False))
                sys.exit(0)

            elif hook_mode == HOOK_MODE_WARNING:
                # 警告模式：記錄警告但允許執行
                logger.warning(f"[WARNING 模式] 代理人分派錯誤，但允許執行")

                # 記錄警告到 JSONL 檔案
                warning_data = {
                    "mode": "warning",
                    "task_type": agent_check_result.get("detected_task_type", "未知"),
                    "wrong_agent": subagent_type,
                    "correct_agent": agent_check_result.get("correct_agent", "未知"),
                    "prompt_preview": prompt[:200],
                    "action": "allowed_with_warning"
                }
                log_warning_to_file(warning_data)

                # 輸出警告訊息但允許執行
                print(f"⚠️ [WARNING] {agent_check_result['error_message']}", file=sys.stderr)
                print("⚠️ [WARNING] 任務將繼續執行，但建議檢查代理人分派", file=sys.stderr)
        else:
            logger.info(f"代理人檢查通過: {agent_check_result.get('detected_task_type', '未知')} → {subagent_type}")

    # 8. 所有檢查通過，允許執行
    logger.info("✅ 所有檢查通過，允許執行")
    sys.exit(0)


# ===== 代理人分派檢查函式 =====

def check_agent_dispatch(prompt: str, current_agent: str) -> Dict:
    """
    檢查代理人分派是否正確

    優先級：
    1. 代理人名稱直接判定（最高優先級）- 避免誤判
    2. 任務類型關鍵字判定

    Parameters:
        prompt: str - 任務描述
        current_agent: str - 當前指定的代理人

    Returns:
        dict - {
            "is_error": bool,
            "error_message": str,
            "detected_task_type": str,
            "correct_agent": str
        }
    """
    try:
        # Edge Case 4: subagent_type 為空
        if not current_agent or current_agent == "":
            logger.info("subagent_type 為空，跳過代理人檢查")
            return {"is_error": False}

        # Edge Case 5: 未知代理人
        if current_agent not in KNOWN_AGENTS_SET:
            warning_msg = generate_unknown_agent_warning(current_agent)
            logger.warning(f"未知代理人: {current_agent}")
            return {"is_error": False}

        # ===== 優先級 1: 代理人名稱直接判定（新增） =====
        # 代理人名稱 → 任務類型的反向映射
        agent_to_task_map = {
            "basil-hook-architect": "Hook 開發",
            "thyme-documentation-integrator": "文件整合",
            "mint-format-specialist": "程式碼格式化",
            "lavender-interface-designer": "Phase 1 設計",
            "sage-test-architect": "Phase 2 測試設計",
            "pepper-test-implementer": "Phase 3a 策略規劃",
            "parsley-flutter-developer": "Phase 3b 實作",
            "cinnamon-refactor-owl": "Phase 4 重構",
            "memory-network-builder": "記憶網路建構",
            "rosemary-project-manager": "專案管理"
        }

        # 如果當前代理人有明確的任務類型映射，直接使用（避免誤判）
        if current_agent in agent_to_task_map:
            expected_task_type = agent_to_task_map[current_agent]
            logger.info(f"✅ 代理人名稱優先判定：{current_agent} → {expected_task_type}")
            return {
                "is_error": False,
                "detected_task_type": expected_task_type,
                "correct_agent": current_agent
            }

        # ===== 優先級 2: 任務類型關鍵字判定（原邏輯） =====
        # 1. 偵測任務類型
        task_type = detect_task_type(prompt)

        # Edge Case 2: 無明確任務類型
        if task_type == "未知":
            warning_msg = "無法識別任務類型，建議在 prompt 中明確說明任務性質"
            logger.warning(warning_msg)
            return {"is_error": False}

        # 2. 取得正確代理人
        project_type = detect_project_type() if task_type == "應用程式開發" else None
        correct_agent = get_correct_agent(task_type, project_type)

        # 3. 比對代理人
        if current_agent == correct_agent:
            logger.info(f"代理人分派正確：{task_type} → {current_agent}")
            return {
                "is_error": False,
                "detected_task_type": task_type,
                "correct_agent": correct_agent
            }

        # 4. 代理人分派錯誤
        error_msg = generate_error_message(task_type, current_agent, correct_agent)
        logger.error(f"代理人分派錯誤：{task_type} - {current_agent} != {correct_agent}")
        return {
            "is_error": True,
            "error_message": error_msg,
            "detected_task_type": task_type,
            "correct_agent": correct_agent
        }

    except Exception as e:
        # 異常發生時優雅降級
        logger.error(f"代理人檢查發生異常：{e}")
        return {"is_error": False}


def detect_task_type(prompt: str) -> str:
    """
    偵測任務類型（支援排除關鍵字和權重機制，方案 A + B）

    優先級：
    1. 明確 Phase 標記檢測（[Phase 1], [Phase 3a] 等）
    2. 關鍵字權重評估

    Parameters:
        prompt: str - 任務描述文字

    Returns:
        str - 任務類型名稱或"未知"
    """
    import re

    # ===== 優先級 1: 明確 Phase 標記檢測 =====
    # 支援格式: [Phase 1], [Phase 1 設計], [Phase 3a], [Phase 3a 策略規劃] 等
    explicit_phase_patterns = [
        (r'\[Phase 1[^\]]*\]', "Phase 1 設計"),
        (r'\[Phase 2[^\]]*\]', "Phase 2 測試設計"),
        (r'\[Phase 3a[^\]]*\]', "Phase 3a 策略規劃"),
        (r'\[Phase 3b[^\]]*\]', "Phase 3b 實作"),
        (r'\[Phase 4[^\]]*\]', "Phase 4 重構"),
    ]

    # 檢查 prompt 前 500 字元（通常標記會放在開頭）
    prompt_head = prompt[:500]
    for pattern, task_type in explicit_phase_patterns:
        if re.search(pattern, prompt_head, re.IGNORECASE):
            logger.info(f"✅ 檢測到明確 Phase 標記：{task_type}")
            return task_type

    # ===== 優先級 2: 關鍵字權重評估 =====
    task_weights: Dict[str, int] = {}

    # 方案 B: 移除提前退出，評估所有任務類型
    for task_config in TASK_TYPE_PRIORITIES:
        task_type = task_config["type"]
        positive_weight = 0
        exclude_penalty = 0

        # 1️⃣ 方案 A: 檢查排除關鍵字（負面語境）
        if task_type in EXCLUDE_KEYWORDS:
            for exclude_keyword in EXCLUDE_KEYWORDS[task_type]:
                if exclude_keyword in prompt:
                    exclude_penalty += 5  # 每次匹配扣 5 分
                    logger.debug(f"匹配排除關鍵字：{exclude_keyword} (扣 5 分)")

        # 2️⃣ 掃描正面關鍵字
        for level, keywords in task_config["keywords"].items():
            for keyword in keywords:
                if keyword in prompt:
                    positive_weight += WEIGHT_MAP[level]
                    logger.debug(f"匹配關鍵字：{keyword} ({level}, +{WEIGHT_MAP[level]})")

        # 3️⃣ 計算最終權重（正面權重 - 排除懲罰）
        final_weight = positive_weight - exclude_penalty

        # 4️⃣ 只記錄正權重的任務類型
        if final_weight > 0:
            task_weights[task_type] = final_weight
            logger.debug(f"{task_type} 最終權重：{final_weight} (正面: {positive_weight}, 懲罰: {exclude_penalty})")

        # ❌ 方案 B: 移除提前退出機制，繼續評估所有任務類型

    # 5️⃣ 返回權重最高的任務類型（方案 B）
    if task_weights:
        best_task = max(task_weights, key=task_weights.get)
        logger.info(f"任務類型識別：{best_task} (權重: {task_weights[best_task]})")
        return best_task

    # 無法識別任務類型
    logger.warning("無法識別任務類型")
    return "未知"


def get_correct_agent(task_type: str, project_type: Optional[str] = None) -> str:
    """
    根據任務類型和專案類型取得正確的代理人

    Parameters:
        task_type: str - 任務類型
        project_type: str | None - 專案類型（僅當任務類型為「應用程式開發」時需要）

    Returns:
        str - 正確的代理人名稱
    """
    # 直接對照任務類型
    if task_type in AGENT_DISPATCH_RULES:
        return AGENT_DISPATCH_RULES[task_type]

    # Edge Case 3: 需要判斷專案類型
    if task_type == "應用程式開發":
        if project_type == "Flutter":
            return "parsley-flutter-developer"
        elif project_type == "React":
            return "react-developer"  # 未來支援
        elif project_type == "Vue":
            return "vue-developer"  # 未來支援
        elif project_type == "Python":
            return "python-developer"  # 未來支援
        else:
            logger.warning(f"未知的專案類型：{project_type}")
            return "parsley-flutter-developer"  # 預設使用 Flutter

    # 未知任務類型
    logger.error(f"未知的任務類型：{task_type}")
    return ""


def detect_project_type() -> str:
    """
    偵測專案類型（檢查特徵檔案）

    Returns:
        str - 專案類型 ("Flutter", "React", "Vue", "Python" 等)
    """
    global _PROJECT_TYPE_CACHE

    # 檢查快取
    if _PROJECT_TYPE_CACHE is not None:
        return _PROJECT_TYPE_CACHE

    project_root = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())

    # 檢查 Flutter
    if os.path.exists(os.path.join(project_root, "pubspec.yaml")):
        if os.path.exists(os.path.join(project_root, "lib")):
            _PROJECT_TYPE_CACHE = "Flutter"
            logger.info("偵測到 Flutter 專案")
            return "Flutter"

    # 檢查 React/Vue
    package_json_path = os.path.join(project_root, "package.json")
    if os.path.exists(package_json_path):
        try:
            with open(package_json_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if '"react"' in content:
                    _PROJECT_TYPE_CACHE = "React"
                    logger.info("偵測到 React 專案")
                    return "React"
                elif '"vue"' in content:
                    _PROJECT_TYPE_CACHE = "Vue"
                    logger.info("偵測到 Vue 專案")
                    return "Vue"
        except Exception as e:
            logger.warning(f"讀取 package.json 失敗：{e}")

    # 檢查 Python
    python_markers = ["requirements.txt", "setup.py", "pyproject.toml"]
    if any(os.path.exists(os.path.join(project_root, marker)) for marker in python_markers):
        _PROJECT_TYPE_CACHE = "Python"
        logger.info("偵測到 Python 專案")
        return "Python"

    # 預設為 Flutter（因為當前專案是 Flutter）
    logger.warning("無法偵測專案類型，使用預設值 Flutter")
    _PROJECT_TYPE_CACHE = "Flutter"
    return "Flutter"


def generate_error_message(task_type: str, current_agent: str, correct_agent: str) -> str:
    """
    生成代理人分派錯誤訊息

    Parameters:
        task_type: str - 識別的任務類型
        current_agent: str - 當前指定的代理人
        correct_agent: str - 正確的代理人

    Returns:
        str - 格式化的錯誤訊息
    """
    reason = get_dispatch_error_reason(task_type)

    template = """❌ 代理人分派錯誤

任務類型：{task_type}
當前代理人：{current_agent}
正確代理人：{correct_agent}

原因：{reason}

請參考：
- CLAUDE.md - 代理人分派機制（任務類型優先原則）
- .claude/tdd-collaboration-flow.md - Phase 3b 代理人分派決策樹

決策樹：
1. 首先判斷任務類型（Hook 開發、文件整合、程式碼格式化、TDD Phase 等）
2. 專業任務 → 對應專業代理人
3. 應用程式開發 → 根據專案類型判斷"""

    return template.format(
        task_type=task_type,
        current_agent=current_agent,
        correct_agent=correct_agent,
        reason=reason
    )


def get_dispatch_error_reason(task_type: str) -> str:
    """取得分派錯誤的詳細原因"""
    reason_map = {
        "Hook 開發": "Hook 開發是專業任務，應優先判斷任務類型而非專案類型。basil-hook-architect 是 Hook 系統的專業代理人。",
        "文件整合": "文件整合是專業任務，需要使用 Serena 和 Context7 MCP 工具。thyme-documentation-integrator 是文件整合的專業代理人。",
        "程式碼格式化": "程式碼格式化是專業任務，需要批量處理多個檔案。mint-format-specialist 是格式化的專業代理人。",
        "Phase 1 設計": "Phase 1 功能設計階段應由 lavender-interface-designer 負責，專注於需求分析和功能規格設計。",
        "Phase 2 測試設計": "Phase 2 測試設計階段應由 sage-test-architect 負責，專注於測試案例設計和測試策略規劃。",
        "Phase 3a 策略規劃": "Phase 3a 實作策略階段應由 pepper-test-implementer 負責，提供語言無關的實作策略（虛擬碼）。",
        "Phase 3b 實作": "Phase 3b 語言特定實作階段應由 parsley-flutter-developer 負責，將 Phase 3a 虛擬碼轉換為 Flutter/Dart 程式碼。",
        "Phase 4 重構": "Phase 4 重構評估階段應由 cinnamon-refactor-owl 負責，評估程式碼品質並提供重構建議。",
        "應用程式開發": "應用程式開發應由對應的語言代理人負責（Flutter → parsley-flutter-developer）。",
        "記憶網路建構": "記憶網路建構應由 memory-network-builder 負責，專注於知識圖譜和決策記錄。"
    }

    return reason_map.get(task_type, "任務類型不匹配，請檢查任務描述和代理人分派。")


def generate_unknown_agent_warning(subagent_type: str) -> str:
    """
    生成未知代理人警告訊息

    Parameters:
        subagent_type: str - 未知的代理人名稱

    Returns:
        str - 警告訊息
    """
    agents_list = "\n".join([f"  - {agent}" for agent in KNOWN_AGENTS])

    warning = f"""⚠️ 未知的代理人名稱：{subagent_type}

已知代理人清單：
{agents_list}

建議：
1. 檢查代理人名稱是否拼寫正確
2. 如果是新增的代理人，請更新 Hook 的已知代理人清單"""

    return warning


if __name__ == "__main__":
    main()
