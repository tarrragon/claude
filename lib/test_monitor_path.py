"""測試監控檔路徑：pre／post 兩支 hook 共用，鍵的決定規則只在此定義。

鍵的退路：tool_use_id -> session_id -> 舊單檔 test-monitor.json。
"""

import re
import time
from pathlib import Path
from typing import Optional

_UNSAFE_KEY_CHARS = re.compile(r"[^A-Za-z0-9_.-]")


def monitor_key(input_data: dict) -> Optional[str]:
    """回傳監控檔鍵；兩個識別都缺時回傳 None（走舊單檔）。"""
    for field in ("tool_use_id", "session_id"):
        value = input_data.get(field)
        if isinstance(value, str) and value:
            return _UNSAFE_KEY_CHARS.sub("_", value)
    return None


def keyed_monitor_file(project_dir: Path, key: str) -> Path:
    return project_dir / ".claude" / "hook-logs" / "test-monitor" / f"{key}.json"


def legacy_monitor_file(project_dir: Path) -> Path:
    return project_dir / ".claude" / "hook-logs" / "test-monitor.json"


# 未收尾鍵檔的保留時長：post-test-hook LIMIT_THRESHOLD（1800 秒）的 2 倍。
# 超過此值的鍵檔，其命令早已超過最高逾時閾值仍未收尾，視為被中斷或 post 未觸發的殘留。
STALE_KEYFILE_SECONDS = 3600


def prune_stale_keyed_files(project_dir: Path, logger=None,
                            now: Optional[float] = None) -> int:
    """刪除鍵檔目錄內 mtime 超過 STALE_KEYFILE_SECONDS 的殘留，回傳刪除數。

    fail-open：任何失敗只寫日誌、不拋出；不碰舊單檔本身。
    """
    removed = 0
    try:
        directory = keyed_monitor_file(project_dir, "x").parent
        if not directory.is_dir():
            return 0
        current = time.time() if now is None else now
        for path in directory.glob("*.json"):
            try:
                if current - path.stat().st_mtime > STALE_KEYFILE_SECONDS:
                    path.unlink()
                    removed += 1
            except OSError as e:
                if logger:
                    logger.info(f"清理殘留鍵檔失敗（略過）{path.name}: {e}")
    except OSError as e:
        if logger:
            logger.info(f"清理殘留鍵檔失敗（略過）: {e}")
    if removed and logger:
        logger.info(f"已清理 {removed} 個逾 {STALE_KEYFILE_SECONDS} 秒的殘留鍵檔")
    return removed
