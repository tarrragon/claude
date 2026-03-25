"""
Registry Loader - 共用的 registry 載入函式

提供統一的 registry.yaml 載入介面，供多個模組使用。
"""

import sys
from pathlib import Path
from typing import Any, Dict
import yaml


def load_registry(registry_path: Path) -> Dict[str, Any]:
    """
    載入 registry.yaml

    Args:
        registry_path: registry.yaml 的路徑

    Returns:
        dict: 載入的 registry 資料，若載入失敗則返回空字典

    設計原則：
    - 若檔案不存在或格式異常，返回空字典而不拋出異常
    - 允許呼叫端檢查返回值判斷是否載入成功
    """
    if not registry_path.exists():
        return {}
    
    try:
        with open(registry_path, "r", encoding="utf-8") as f:
            registry = yaml.safe_load(f)

        if not registry or not isinstance(registry, dict):
            return {}

        return registry
    except Exception as e:
        print(f"[registry_loader] Failed to load {registry_path}: {e}", file=sys.stderr)
        return {}
