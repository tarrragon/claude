#!/usr/bin/env python3
"""
配置載入工具

提供統一的 YAML 配置檔案載入功能。
支援從 .claude/config/ 目錄載入配置。

主要功能:
- load_config: 載入指定的配置檔案
- load_agents_config: 載入代理人配置
- load_quality_rules: 載入品質規則配置
"""

import os
from pathlib import Path
from typing import Any, Optional

# 嘗試導入 PyYAML，如果失敗則使用內建的 JSON 作為備案
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False
    import json


def get_config_dir() -> Path:
    """
    獲取配置目錄路徑

    Returns:
        Path: 配置目錄路徑
    """
    project_root = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    return Path(project_root) / ".claude" / "config"


def load_config(config_name: str) -> dict:
    """
    載入指定的配置檔案

    Args:
        config_name: 配置檔案名稱（不含副檔名）

    Returns:
        dict: 配置內容

    Raises:
        FileNotFoundError: 配置檔案不存在
        ValueError: 配置格式錯誤

    Example:
        config = load_config("agents")
        known_agents = config.get("known_agents", [])
    """
    config_dir = get_config_dir()

    # 優先嘗試 YAML
    yaml_path = config_dir / f"{config_name}.yaml"
    yml_path = config_dir / f"{config_name}.yml"
    json_path = config_dir / f"{config_name}.json"

    if yaml_path.exists():
        result = _load_yaml_file(yaml_path)
        if result is not None:
            return result
    elif yml_path.exists():
        result = _load_yaml_file(yml_path)
        if result is not None:
            return result

    if json_path.exists():
        return _load_json_file(json_path)

    raise FileNotFoundError(
        f"Configuration file not found: {config_name}.yaml/yml/json"
    )


def _load_yaml_file(file_path: Path) -> dict:
    """載入 YAML 檔案"""
    if not HAS_YAML:
        # PyYAML 不可用時返回 None，讓呼叫者使用預設配置
        return None

    with open(file_path, "r", encoding="utf-8") as f:
        content = yaml.safe_load(f)
        return content if content else {}


def _load_json_file(file_path: Path) -> dict:
    """載入 JSON 檔案"""
    import json
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ===== 專用載入函式 =====

_agents_config_cache: Optional[dict] = None
_quality_rules_cache: Optional[dict] = None


def load_agents_config() -> dict:
    """
    載入代理人配置

    Returns:
        dict: 代理人配置，包含:
            - known_agents: 已知代理人列表
            - agent_dispatch_rules: 任務類型對應代理人
            - task_type_priorities: 任務類型優先級
            - weight_map: 權重定義
            - exclude_keywords: 排除關鍵字

    Example:
        config = load_agents_config()
        known_agents = set(config.get("known_agents", []))
        dispatch_rules = config.get("agent_dispatch_rules", {})
    """
    global _agents_config_cache
    if _agents_config_cache is None:
        try:
            _agents_config_cache = load_config("agents")
        except FileNotFoundError:
            # 返回預設配置
            _agents_config_cache = _get_default_agents_config()
    return _agents_config_cache


def load_quality_rules() -> dict:
    """
    載入品質規則配置

    Returns:
        dict: 品質規則配置，包含:
            - trigger_conditions: 觸發條件
            - cache: 快取配置
            - code_smell_rules: Code Smell 規則
            - decision_rules: 決策規則

    Example:
        config = load_quality_rules()
        trigger = config.get("trigger_conditions", {})
        allowed_tools = trigger.get("allowed_tools", [])
    """
    global _quality_rules_cache
    if _quality_rules_cache is None:
        try:
            _quality_rules_cache = load_config("quality_rules")
        except FileNotFoundError:
            # 返回預設配置
            _quality_rules_cache = _get_default_quality_rules()
    return _quality_rules_cache


def _get_default_agents_config() -> dict:
    """返回預設代理人配置（當配置檔案不存在時使用）"""
    return {
        "known_agents": [
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
        ],
        "agent_dispatch_rules": {
            "Hook 開發": "basil-hook-architect",
            "文件整合": "thyme-documentation-integrator",
            "程式碼格式化": "mint-format-specialist",
            "Phase 1 設計": "lavender-interface-designer",
            "Phase 2 測試設計": "sage-test-architect",
            "Phase 3a 策略規劃": "pepper-test-implementer",
            "Phase 3b 實作": "parsley-flutter-developer",
            "Phase 4 重構": "cinnamon-refactor-owl",
            "記憶網路建構": "memory-network-builder"
        },
        "weight_map": {
            "high": 3,
            "medium": 2,
            "low": 1
        }
    }


def _get_default_quality_rules() -> dict:
    """返回預設品質規則配置（當配置檔案不存在時使用）"""
    return {
        "trigger_conditions": {
            "allowed_tools": ["Write", "Edit", "MultiEdit"],
            "file_extension": ".md",
            "ticket_path_keywords": [
                "docs/work-logs/",
                "docs/tickets/",
                "-ticket-",
                "-task-"
            ]
        },
        "cache": {
            "ttl_minutes": 5
        },
        "decision_rules": {
            "failed_action": "block",
            "warning_action": "allow",
            "passed_action": "allow",
            "error_action": "allow"
        }
    }


def clear_config_cache() -> None:
    """清除配置快取（用於測試或配置熱更新）"""
    global _agents_config_cache, _quality_rules_cache
    _agents_config_cache = None
    _quality_rules_cache = None
