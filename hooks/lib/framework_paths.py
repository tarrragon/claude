"""Framework path SSOT 共用模組（W17-127.1）

讀取 .claude/config/framework-paths.yaml，提供 framework 路徑分類函式給多個 hook 共用。

設計目的：
- linux 視角警示（W17-122 ANA）：layer-boundary-validator 與 agent-dispatch-validation
  各自 inline framework 路徑判定（LAYER1_PATTERNS / _META_TASK_PATTERNS），存在 SSOT
  漂移風險。本模組將分類規則收斂至 framework-paths.yaml 單一來源。

提供 API：
- is_framework_path(path) -> bool：strict 範圍判定（規範性文字層；PreToolUse hook 用）
- is_framework_path_broad(path) -> bool：broad 範圍判定（strict + .claude/hooks/；
  lifecycle.py claim WRAP S 問用）
- is_layer1_path(path) -> bool：路徑是否屬於 Layer 1 子集（layer-boundary 專用）
- get_categories() -> List[str]：framework 類別名清單（rules/pm-rules/...）
- get_framework_paths() -> List[str]：strict framework 路徑前綴清單
- get_framework_paths_broad() -> List[str]：broad framework 路徑前綴清單
- get_layer1_paths() -> List[str]：Layer 1 路徑前綴清單

消費端對照（W17-132 SSOT 邊界拆分）：
- PreToolUse framework-rule-edit-skill-trigger-hook → is_framework_path（strict）
- lifecycle.py _has_framework_path（claim WRAP S 問） → is_framework_path_broad（broad）

效能：模組級 lru_cache（同 process 只讀 YAML 一次），對齊 ginger 視角 cache 警示。

Python 3.9 相容：使用 typing.List/Optional，不用 PEP 604 union 語法。
"""

from __future__ import annotations

import fnmatch
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

import yaml


# YAML 路徑：相對於 .claude/ 根目錄
# 本模組位於 .claude/hooks/lib/framework_paths.py → 上溯 2 層至 .claude/
_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "framework-paths.yaml"


@lru_cache(maxsize=1)
def _load_config() -> Dict[str, List[str]]:
    """讀取 framework-paths.yaml 並 cache 結果。

    YAML 不存在或解析失敗時回傳空字典（保守降級，呼叫端視為「無任何 framework 路徑」）。
    """
    if not _CONFIG_PATH.exists():
        return {}
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    # 規範化：缺項補空 list，型別不符視為空
    result: Dict[str, List[str]] = {}
    for key in (
        "categories",
        "framework_paths",
        "framework_paths_strict",
        "framework_paths_broad",
        "layer1_paths",
        "exempt_paths",
    ):
        value = data.get(key, [])
        result[key] = [str(x) for x in value] if isinstance(value, list) else []
    # framework_paths_strict 缺項時 fallback 至 framework_paths（向後相容）
    if not result["framework_paths_strict"]:
        result["framework_paths_strict"] = list(result["framework_paths"])
    # framework_paths_broad 缺項時 fallback 至 strict（保守降級，行為等同舊版）
    if not result["framework_paths_broad"]:
        result["framework_paths_broad"] = list(result["framework_paths_strict"])
    return result


def get_categories() -> List[str]:
    """回傳 framework 類別名清單（rules/pm-rules/references/...）。"""
    return list(_load_config().get("categories", []))


def get_framework_paths() -> List[str]:
    """回傳 strict framework 路徑前綴清單（規範性文字層；含 .claude/ 前綴）。

    向後相容：W17-127.1 既有消費端讀此 API。strict = framework_paths_strict
    （yaml 內 framework_paths 為其別名）。
    """
    return list(_load_config().get("framework_paths_strict", []))


def get_framework_paths_broad() -> List[str]:
    """回傳 broad framework 路徑前綴清單（strict + .claude/hooks/）。

    用途：lifecycle.py claim WRAP S 問判定，範圍含 hooks/（hook 內警告訊息屬規範性產物）。
    """
    return list(_load_config().get("framework_paths_broad", []))


def get_layer1_paths() -> List[str]:
    """回傳 Layer 1 路徑前綴清單（layer-boundary 專用 narrower scope）。"""
    return list(_load_config().get("layer1_paths", []))


def get_exempt_paths() -> List[str]:
    """回傳豁免路徑 glob 清單（測試檔、暫存檔等）。"""
    return list(_load_config().get("exempt_paths", []))


def _matches_exempt(path_str: str) -> bool:
    """檢查路徑是否匹配任一豁免 glob。

    支援 fnmatch 風格（`**` 視為任意層級，前綴比對為主）。
    """
    for pattern in get_exempt_paths():
        # fnmatch.fnmatch 不支援 `**` 跨層；手動處理：將 `**/` 替換為 `*`
        # 並對 prefix 模式（結尾 /）改用 startswith 比對
        if pattern.endswith("/"):
            # 前綴比對；支援 `**` 中段：將 ** 改為 *，再用 fnmatch
            normalized = pattern.replace("**/", "")
            if path_str.startswith(normalized) or fnmatch.fnmatch(path_str, pattern + "*"):
                return True
        else:
            if fnmatch.fnmatch(path_str, pattern):
                return True
    return False


def is_framework_path(path: str) -> bool:
    """判斷檔案路徑是否屬於廣義 framework 規則層。

    Args:
        path: 檔案路徑（相對或絕對；自動正規化前綴）

    Returns:
        True 若路徑前綴匹配任一 framework_paths 條目且未命中 exempt_paths。

    範例：
        >>> is_framework_path(".claude/rules/core/quality-baseline.md")
        True
        >>> is_framework_path(".claude/skills/tdd/tests/test_phase.py")
        False  # exempt_paths 命中
        >>> is_framework_path("src/foo.py")
        False
    """
    if not path:
        return False
    path_str = str(path)
    # 正規化：去掉 leading ./
    if path_str.startswith("./"):
        path_str = path_str[2:]

    # 豁免優先檢查
    if _matches_exempt(path_str):
        return False

    for prefix in get_framework_paths():
        if prefix in path_str or path_str.startswith(prefix):
            return True
    return False


def is_framework_path_broad(path: str) -> bool:
    """判斷檔案路徑是否屬於 broad framework 範圍（strict + .claude/hooks/）。

    與 is_framework_path（strict）的差異：
    - strict：規範性文字層（rules/pm-rules/methodologies/skills/agents/error-patterns/references）
              用於 PreToolUse framework-rule-edit-skill-trigger-hook
    - broad：strict + .claude/hooks/
             用於 lifecycle.py claim WRAP S 問（hook 內警告訊息屬規範性產物，
             應提示讀 SKILL；W17-131 ANA 結論 / W17-132 落地）

    Args:
        path: 檔案路徑

    Returns:
        True 若路徑前綴匹配任一 framework_paths_broad 條目且未命中 exempt_paths。

    範例：
        >>> is_framework_path_broad(".claude/hooks/foo.py")
        True
        >>> is_framework_path(".claude/hooks/foo.py")
        False
        >>> is_framework_path_broad(".claude/hooks/tests/test_foo.py")
        False  # exempt
    """
    if not path:
        return False
    path_str = str(path)
    if path_str.startswith("./"):
        path_str = path_str[2:]
    if _matches_exempt(path_str):
        return False
    for prefix in get_framework_paths_broad():
        if prefix in path_str or path_str.startswith(prefix):
            return True
    return False


def is_layer1_path(path: str) -> bool:
    """判斷檔案路徑是否屬於 Layer 1 子集（layer-boundary-validator 專用）。

    保留 layer-boundary-validator-hook.py 既有 LAYER1_PATTERNS 行為：
    - 路徑須含某個 layer1_paths 前綴（支援 substring match，與既有實作一致）
    - 結尾須為 .md（既有 is_layer1_file 行為）

    Args:
        path: 檔案路徑

    Returns:
        True 若路徑符合 Layer 1 範圍。
    """
    if not path:
        return False
    path_str = str(path)
    if not path_str.endswith(".md"):
        return False
    for pattern in get_layer1_paths():
        if pattern in path_str:
            return True
    return False


def reset_cache() -> None:
    """重置 cache（測試用）。"""
    _load_config.cache_clear()
