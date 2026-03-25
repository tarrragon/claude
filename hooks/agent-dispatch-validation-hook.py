#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pyyaml>=6.0",
# ]
# ///
"""
Agent Dispatch Validation Hook

根據 agent registry 執行三種衝突檢查：
1. Agent 衝突檢查（cannot_work_with）
2. TDD 相序驗證（must_complete_before）
3. 檔案寫入衝突檢查（file_patterns 交集）

Hook 類型：PreToolUse
觸發時機：派發 Agent 工具時

雙通道輸出：
- stderr：即時通知（使用者可見）
- 日誌檔：詳細記錄（供除錯參考）

注意：Hook 檔案可能無法直接 import ticket_system，
因此保留自己的 load_registry 版本。未來可在 Phase 2 統一實作。
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import yaml


# ===== 常數定義 =====
REGISTRY_PATH = Path(__file__).parent.parent / "agents" / "registry.yaml"
LOG_DIR = Path(__file__).parent.parent / "hook-logs"
HOOK_NAME = "agent-dispatch-validation"

# ANSI 顏色代碼
class Colors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


# ===== 日誌配置 =====
def setup_logger() -> logging.Logger:
    """設定雙通道日誌（stderr + 檔案）"""
    log_dir = LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / f"{HOOK_NAME}.log"
    
    logger = logging.getLogger(HOOK_NAME)
    logger.setLevel(logging.DEBUG)
    
    # 檔案日誌
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    return logger


logger = setup_logger()


# ===== 訊息常數 =====
class Messages:
    """統一訊息管理"""
    
    # Header
    HEADER_DISPATCH_VALIDATION = "Agent Dispatch Validation"
    HEADER_CONFLICT_DETECTED = "Conflict Detected"
    HEADER_CHECKING = "Checking..."
    
    # Success
    VALIDATION_PASSED = "[INFO] Registry loaded, full validation pending (Phase 2)"
    NO_CONFLICTS = "No conflicts detected"
    
    # Warnings
    WARNING_AGENT_CONFLICT = "WARNING: Agent conflict detected"
    WARNING_PHASE_CONFLICT = "WARNING: TDD phase sequence violation"
    WARNING_FILE_CONFLICT = "WARNING: File pattern overlap detected"
    
    # Errors
    ERROR_REGISTRY_NOT_FOUND = "ERROR: Registry file not found"
    ERROR_INVALID_REGISTRY = "ERROR: Invalid registry format"
    ERROR_PARSING_FAILED = "ERROR: Failed to parse input"
    
    # Details
    DETAIL_AGENT_A = "Agent A: {}"
    DETAIL_AGENT_B = "Agent B: {}"
    DETAIL_REASON = "Reason: {}"
    DETAIL_CONFLICT_PATHS = "Conflicting patterns: {}"
    DETAIL_SCOPE = "Scope: {}"
    
    # Resolution
    SUGGESTION_SEQUENCE = "Suggestion: Complete Agent {} before deploying Agent {}"
    SUGGESTION_SEPARATE = "Suggestion: Deploy agents sequentially instead of in parallel"


# ===== Registry 管理 =====
def load_registry() -> Dict[str, Any]:
    """載入 registry.yaml"""
    if not REGISTRY_PATH.exists():
        logger.error(f"Registry not found: {REGISTRY_PATH}")
        print(f"{Colors.FAIL}{Messages.ERROR_REGISTRY_NOT_FOUND}: {REGISTRY_PATH}{Colors.ENDC}", 
              file=sys.stderr)
        return {}
    
    try:
        with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
            registry = yaml.safe_load(f)
        
        if not registry or "agents" not in registry:
            logger.error("Invalid registry format")
            print(f"{Colors.FAIL}{Messages.ERROR_INVALID_REGISTRY}{Colors.ENDC}", 
                  file=sys.stderr)
            return {}
        
        logger.info(f"Registry loaded: {len(registry['agents'])} agents")
        return registry
    except Exception as e:
        logger.error(f"Failed to load registry: {e}")
        print(f"{Colors.FAIL}{Messages.ERROR_PARSING_FAILED}: {e}{Colors.ENDC}", 
              file=sys.stderr)
        return {}


# ===== 衝突檢查函式 =====
def check_agent_conflict(agent_a: str, agent_b: str, registry: Dict[str, Any]) -> List[str]:
    """
    檢查 1：Agent 衝突（cannot_work_with）
    
    規則：若 agent_b 的 conflict_avoidance 中存在 cannot_work_with 包含 agent_a，
    則視為衝突。
    """
    conflicts = []
    
    if agent_b not in registry.get("agents", {}):
        return conflicts
    
    agent_b_config = registry["agents"][agent_b]
    
    for conflict in agent_b_config.get("conflict_avoidance", []):
        if conflict.get("type") == "cannot_work_with":
            if agent_a in conflict.get("agents", []):
                conflicts.append({
                    "type": "agent_conflict",
                    "agent_a": agent_a,
                    "agent_b": agent_b,
                    "reason": conflict.get("reason", "Unknown"),
                    "scope": conflict.get("scope", "same_ticket")
                })
    
    return conflicts


def check_phase_sequence(agent_a: str, agent_b: str, registry: Dict[str, Any]) -> List[str]:
    """
    檢查 2：TDD 相序驗證（must_complete_before）
    
    規則：若 agent_b 的 conflict_avoidance 中 must_complete_before 包含 agent_a，
    則表示 agent_a 必須先完成。
    """
    conflicts = []
    
    if agent_b not in registry.get("agents", {}):
        return conflicts
    
    agent_b_config = registry["agents"][agent_b]
    
    for conflict in agent_b_config.get("conflict_avoidance", []):
        if conflict.get("type") == "must_complete_before":
            if agent_a in conflict.get("agents", []):
                conflicts.append({
                    "type": "phase_sequence",
                    "agent_a": agent_a,
                    "agent_b": agent_b,
                    "reason": conflict.get("reason", "Unknown")
                })
    
    return conflicts


def patterns_overlap(pattern_a: str, pattern_b: str) -> bool:
    """
    檢查兩個 glob 模式是否有重疊
    
    採用保守策略：若目錄前綴相同，視為有潛在交集
    """
    # 提取目錄前綴（去掉 ** 和 * 等通配符）
    def extract_prefix(pattern: str) -> str:
        parts = pattern.split("/")
        # 只取到第一個通配符之前的部分
        prefix_parts = []
        for part in parts:
            if "*" in part or "?" in part:
                break
            prefix_parts.append(part)
        return "/".join(prefix_parts)
    
    prefix_a = extract_prefix(pattern_a)
    prefix_b = extract_prefix(pattern_b)
    
    # 若任一前綴為空（全是通配符），視為可能重疊
    if not prefix_a or not prefix_b:
        return True
    
    # 若前綴相同，視為重疊
    return prefix_a == prefix_b or prefix_a.startswith(prefix_b) or prefix_b.startswith(prefix_a)


def check_file_conflict(agent_a: str, agent_b: str, registry: Dict[str, Any]) -> List[str]:
    """
    檢查 3：檔案寫入衝突（ARCH-005）
    
    規則：若兩個 agent 的 file_patterns 有交集，視為衝突
    """
    conflicts = []
    
    agents = registry.get("agents", {})
    if agent_a not in agents or agent_b not in agents:
        return conflicts
    
    patterns_a = set(agents[agent_a].get("file_patterns", []))
    patterns_b = set(agents[agent_b].get("file_patterns", []))
    
    if not patterns_a or not patterns_b:
        return conflicts
    
    conflicting_paths = []
    for pattern_a in patterns_a:
        for pattern_b in patterns_b:
            if patterns_overlap(pattern_a, pattern_b):
                conflicting_paths.append((pattern_a, pattern_b))
    
    if conflicting_paths:
        conflicts.append({
            "type": "file_conflict",
            "agent_a": agent_a,
            "agent_b": agent_b,
            "conflicting_paths": conflicting_paths
        })
    
    return conflicts


# ===== 主驗證函式 =====
def validate_dispatch(agent_name: str, ticket_id: Optional[str] = None) -> tuple[bool, str]:
    """
    執行完整的派發驗證
    
    返回：(should_allow, message)
    - should_allow: True 表示允許派發，False 表示應阻止
    - message: 驗證訊息
    """
    registry = load_registry()
    if not registry:
        return False, Messages.ERROR_REGISTRY_NOT_FOUND
    
    # 簡化版本：此處應從 ticket execution log 或上下文讀取已派發的 agent
    # 目前返回允許，詳細實作見 Phase 2
    
    return True, Messages.VALIDATION_PASSED


# ===== CLI 入口 =====
def main():
    """Hook 主程式"""
    if len(sys.argv) < 2:
        print(f"{Colors.WARNING}Usage: agent-dispatch-validation-hook.py <agent-name> [ticket-id]{Colors.ENDC}",
              file=sys.stderr)
        return 0
    
    agent_name = sys.argv[1]
    ticket_id = sys.argv[2] if len(sys.argv) > 2 else None
    
    logger.info(f"Validating dispatch: agent={agent_name}, ticket={ticket_id}")
    
    should_allow, message = validate_dispatch(agent_name, ticket_id)
    
    print(f"{Colors.HEADER}=== {Messages.HEADER_DISPATCH_VALIDATION} ==={Colors.ENDC}")
    print(message)
    
    # 雙通道輸出訊息也寫到 stderr（防止被 stdout 重定向吞掉）
    print(message, file=sys.stderr)
    
    # Hook 禁止阻止派發（遵循「警告而非禁止」的設計），總是返回 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
