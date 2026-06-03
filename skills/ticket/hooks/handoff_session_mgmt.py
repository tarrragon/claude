"""
handoff-auto-resume-stop-hook session 管理模組（W3-039 部分拆分）

從 handoff-auto-resume-stop-hook.py 抽出的 session 層級 flag 與狀態管理函式。

職責邊界（單一 domain：session 管理）：
- stop flag 檔案路徑解析與防重複觸發判定（過期檢查）
- session 狀態檔案路徑解析與讀取

抽出動機：來源 ANA 0.19.0-W3-038 重現實驗確認原 hook 檔承載 3 大 domain
超過 cognitive-load.md「單檔 domain 數 > 2 必須拆分」閾值。本模組為方案 2
部分拆分產物，使原 hook 檔降至 domain 數 2。

這 5 個函式為原 hook 呼叫圖的葉節點（由 generate_hook_output 呼叫，彼此間
無交叉依賴），抽出後行為完全不變；frontmatter_cache（PC-097）不涉及本模組。

import 約束：本模組依賴 hook_utils.get_project_root，呼叫端（hook 主檔）
須在 import 本模組前完成 .claude/hooks 的 sys.path 設定。
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

from hook_utils import get_project_root

# session 管理相關常數
STOP_FLAG_FILE = ".claude/handoff/.stop-blocked"
STOP_FLAG_EXPIRY_SECONDS = 7200  # 2 小時過期（一個 session 的合理長度）
STATE_FILE_TEMPLATE = "/tmp/claude-handoff-state-{ppid}.json"


def get_session_stop_flag() -> Path:
    """
    取得 session stop flag 檔案路徑

    使用固定的專案內 flag 檔案，相對於專案根目錄

    Returns:
        Path - flag 檔案的絕對路徑
    """
    project_root = get_project_root()
    return project_root / STOP_FLAG_FILE


def get_session_state_file() -> Path:
    """
    取得 session 狀態檔案路徑

    Returns:
        Path - 狀態檔案路徑
    """
    ppid = os.getppid()
    return Path(STATE_FILE_TEMPLATE.format(ppid=ppid))


def has_been_triggered_this_session(logger) -> bool:
    """
    檢查此 session 是否已觸發過 Stop hook，考慮 flag 過期時間

    如果 flag 檔案存在且未過期（< STOP_FLAG_EXPIRY_SECONDS），則認為已觸發
    如果 flag 已過期，則刪除並回傳 False（視為新 session）

    Returns:
        bool - 是否已觸發（且未過期）
    """
    flag_file = get_session_stop_flag()
    if not flag_file.exists():
        return False

    try:
        with open(flag_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        created_at_str = data.get("created_at")
        if not created_at_str:
            # flag 格式異常，移除它
            flag_file.unlink()
            return False

        created_at = datetime.fromisoformat(created_at_str)
        elapsed = (datetime.now() - created_at).total_seconds()

        if elapsed > STOP_FLAG_EXPIRY_SECONDS:
            # flag 已過期，移除它
            logger.debug(f"Stop flag 已過期 ({elapsed:.1f}s > {STOP_FLAG_EXPIRY_SECONDS}s)，刪除")
            flag_file.unlink()
            return False

        logger.debug(f"Stop flag 仍有效 ({elapsed:.1f}s 內)")
        return True

    except Exception as e:
        logger.warning(f"檢查 stop flag 失敗: {e}")
        return False


def mark_triggered_this_session(logger) -> None:
    """
    標記此 session 已觸發過 Stop hook，並記錄時間戳

    寫入固定 flag 檔案，包含建立時間，用於之後的過期檢查
    """
    flag_file = get_session_stop_flag()
    try:
        # 確保目錄存在
        flag_file.parent.mkdir(parents=True, exist_ok=True)

        # 寫入時間戳
        flag_data = {
            "created_at": datetime.now().isoformat(),
            "reason": "stop_hook_triggered"
        }
        with open(flag_file, 'w', encoding='utf-8') as f:
            json.dump(flag_data, f, ensure_ascii=False)

        logger.debug(f"建立 session stop flag: {flag_file}")
    except Exception as e:
        logger.warning(f"建立 session stop flag 失敗: {e}")


def read_session_state(logger) -> Optional[Dict[str, Any]]:
    """
    讀取 session 狀態檔案

    Returns:
        dict - session 狀態，若檔案不存在則回傳 None
    """
    state_file = get_session_state_file()

    if not state_file.exists():
        logger.debug(f"session 狀態檔案不存在: {state_file}")
        return None

    try:
        with open(state_file, 'r', encoding='utf-8') as f:
            state = json.load(f)
        logger.debug(f"讀取 session 狀態成功: {json.dumps(state)}")
        return state
    except json.JSONDecodeError as e:
        logger.warning(f"解析 session 狀態 JSON 失敗: {e}")
        return None
    except Exception as e:
        logger.warning(f"讀取 session 狀態檔案失敗: {e}")
        return None
