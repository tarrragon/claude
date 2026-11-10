"""
狀態檔管理（自 wrap-decision-tripwire-hook.py 拆出，行為不變）。

含：時間注入點、狀態檔路徑解析、載入、原子寫入、過期清理、cooldown、換票重置。
`_now` 是全套件唯一的時鐘注入點（signals.py 以 `state._now()` 屬性存取，
測試只需 patch 本模組一處）。
"""

import json
import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


# ============================================================================
# 時間注入點（測試可 monkeypatch）
# ============================================================================

def _now() -> datetime:
    """返回當前時間。測試可透過 monkeypatch 此函式凍結時間。"""
    return datetime.now()


# ============================================================================
# State 載入與 atomic 寫入
# ============================================================================

def _initial_state() -> Dict[str, Any]:
    return {
        "version": "1.0.0",
        "current_ticket": None,
        "last_updated": None,
        "signals": {},
    }


def load_state(state_path: Path, logger) -> Dict[str, Any]:
    """讀取 state.json。不存在或 parse 失敗時返回初始狀態。"""
    if not state_path.exists():
        logger.info("state file does not exist; returning initial state: %s", state_path)
        return _initial_state()
    try:
        raw = json.loads(state_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            logger.info("state file root not mapping; reinitializing")
            return _initial_state()
        logger.info("state loaded: %s", state_path)
        return raw
    except (json.JSONDecodeError, OSError) as e:
        logger.info("state load failed (%s); reinitializing", e)
        return _initial_state()


def resolve_state_path(base_path: Path, event: Dict[str, Any], logger) -> Path:
    """依 stdin payload 的 session_id 把狀態檔分檔；缺值時退回共用檔（fail-open）。

    分檔命名：<stem>-<session_id><suffix>（session_id 經檔名消毒，僅保留
    英數、底線、連字號）。只讀 stdin payload，不 fallback 環境變數：
    環境變數屬 hook 行程自身而非事件來源，與 payload 不一致時會造成同一
    事件寫入不同檔。
    """
    raw = event.get("session_id")
    sid = re.sub(r"[^A-Za-z0-9_-]", "_", raw) if isinstance(raw, str) else ""
    if not sid:
        logger.info("payload 無可用 session_id；退回共用狀態檔: %s", base_path)
        return base_path
    return base_path.with_name("%s-%s%s" % (base_path.stem, sid, base_path.suffix))


# 他 session 狀態檔的保留天數：S1/cooldown 狀態只在 session 存活期間有意義，
# 長時間 session 偶爾閒置數日，取 7 天以避免誤刪仍在使用的 session 檔。
STALE_STATE_DAYS = 7


def prune_stale_state_files(base_path: Path, current_path: Path, logger) -> int:
    """刪除狀態目錄下 mtime 超過 STALE_STATE_DAYS 的他 session 分檔，回傳刪除數。

    不刪當下 session 檔與共用檔；任何失敗只記日誌（fail-open）。
    不節流：目錄僅含 session 分檔，清理後規模受 7 天內 session 數限制，glob 成本可忽略。
    """
    removed = 0
    try:
        cutoff = _now().timestamp() - STALE_STATE_DAYS * 86400
        for p in base_path.parent.glob("%s-*%s" % (base_path.stem, base_path.suffix)):
            if p == current_path or p == base_path:
                continue
            try:
                if p.stat().st_mtime < cutoff:
                    p.unlink()
                    removed += 1
                    logger.info("stale state file removed: %s", p)
            except OSError as exc:
                logger.info("stale state cleanup failed for %s: %s", p, exc)
    except Exception as exc:  # fail-open：清理不得影響主流程
        logger.info("stale state cleanup aborted: %s", exc)
    return removed


def save_state_atomic(state_path: Path, state: Dict[str, Any], logger) -> None:
    """原子寫入 state.json（tmp + os.replace）。失敗僅記錄不 raise。"""
    try:
        parent = state_path.parent
        parent.mkdir(parents=True, exist_ok=True)
        state["last_updated"] = _now().isoformat()
        fd, tmp_name = tempfile.mkstemp(
            dir=str(parent), prefix=".state-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                json.dump(state, tmp, ensure_ascii=False, indent=2)
                tmp.flush()
                os.fsync(tmp.fileno())
            os.replace(tmp_name, state_path)
            logger.info("state saved atomically: %s", state_path)
        except Exception:
            # 清理 tmp
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
    except Exception as e:
        # 規則 4：雙通道
        sys.stderr.write("[WRAP Tripwire] state write error: {}\n".format(e))
        logger.info("state write failed: %s", e)


# ============================================================================
# Cooldown / 重置輔助
# ============================================================================

def in_cooldown(state: Dict[str, Any], signal_id: str, cooldown_seconds: int) -> bool:
    sig_state = state.get("signals", {}).get(signal_id, {})
    last_warned = sig_state.get("last_warned_at")
    if not last_warned:
        return False
    try:
        last_dt = datetime.fromisoformat(last_warned)
    except (TypeError, ValueError):
        return False
    elapsed = (_now() - last_dt).total_seconds()
    if elapsed < 0:
        # 時鐘倒退 → 視為已過 cooldown
        return False
    return elapsed < cooldown_seconds


def mark_warned(state: Dict[str, Any], signal_id: str) -> Dict[str, Any]:
    sig_state = state.setdefault("signals", {}).setdefault(signal_id, {})
    sig_state["last_warned_at"] = _now().isoformat()
    return state


def apply_ticket_switch_reset(state: Dict[str, Any], current_ticket: Optional[str]) -> Dict[str, Any]:
    """若 ticket 變化則全訊號歸零。current_ticket 為 None 時不動。"""
    if current_ticket is None:
        return state
    prev = state.get("current_ticket")
    if prev != current_ticket:
        state["current_ticket"] = current_ticket
        state["signals"] = {}
    return state


def reset_all_signals(state: Dict[str, Any]) -> Dict[str, Any]:
    state["signals"] = {}
    return state
