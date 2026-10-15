"""共用模組：hook 分派 registry 的唯一讀取點。

Bash 事件的 hook 合併後由 hook-dispatcher 啟動，settings.json 只剩分派器一筆，
其餘 hook 登記在 `.claude/hooks/hook-dispatch-registry.json`。以 settings.json 為
註冊表的消費端（涵蓋率檢查、依賴隔離檢查、健康監控、liveness 彙整）改經本模組
取得完整清單，避免把被併入的 hook 判成未註冊。

本模組只依賴標準庫，使 hook-dispatcher 能以檔案路徑直接載入，不受 lib 套件
（含 yaml 等相依）匯入失敗影響。
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

REGISTRY_RELATIVE_PATH = Path(".claude") / "hooks" / "hook-dispatch-registry.json"
COMMAND_TEMPLATE = "uv run --quiet $CLAUDE_PROJECT_DIR/{path}"


def registry_path(root: Path) -> Path:
    return Path(root) / REGISTRY_RELATIVE_PATH


def load_registry_groups(root: Path, registry_file: Optional[Path] = None) -> Dict[str, dict]:
    """讀取 registry 的 groups；檔案不存在回傳空 dict，內容損壞則拋例外（呼叫端決定可見性）"""
    path = registry_file if registry_file is not None else registry_path(root)
    if not Path(path).is_file():
        return {}
    with open(str(path), encoding="utf-8") as f:
        return json.load(f).get("groups", {})


def load_group(group: str, registry_file: Path) -> dict:
    """分派器用：取單一 group（缺 group 拋 KeyError）"""
    return load_registry_groups(Path("."), registry_file)[group]


def split_group_key(key: str) -> tuple:
    """`PreToolUse:Bash` -> (`PreToolUse`, `Bash`)"""
    event, _, matcher = key.partition(":")
    return event, matcher


def registry_commands(root: Path) -> List[str]:
    """與原 settings.json 註冊等價的 command 字串清單（供文字型消費端使用）"""
    commands = []
    for group in load_registry_groups(root).values():
        for entry in group.get("hooks", []):
            commands.append(COMMAND_TEMPLATE.format(path=entry.get("path", "")))
    return commands


def merge_dispatch_registry(settings: dict, root: Path, logger=None) -> dict:
    """把 registry 內的 hook 併入 settings 的 hooks 區塊（就地修改並回傳）。

    併入形式與原註冊等價：事件與 matcher 取自 group 鍵，command 為
    `uv run --quiet $CLAUDE_PROJECT_DIR/<path>`，timeout 沿用 registry 值。
    registry 讀不到或損壞時記錄並維持原 settings。
    """
    try:
        groups = load_registry_groups(root)
    except (OSError, ValueError) as e:
        # 退回「只看 settings.json」會讓被併入的 hook 被判為未註冊：雙通道可見（日誌 warning + stderr）
        message = "讀取分派 registry 失敗（{}），未併入註冊清單: {}".format(registry_path(root), e)
        if logger is not None:
            logger.warning(message)
        sys.stderr.write("[hook_registry] {}\n".format(message))
        return settings
    hooks_cfg = settings.setdefault("hooks", {})
    for key, group in groups.items():
        event, matcher = split_group_key(key)
        entries = []
        for entry in group.get("hooks", []):
            item = {"type": "command", "command": COMMAND_TEMPLATE.format(path=entry.get("path", ""))}
            if entry.get("timeout"):
                item["timeout"] = entry["timeout"]
            entries.append(item)
        hooks_cfg.setdefault(event, []).append({"matcher": matcher, "hooks": entries})
    return settings
