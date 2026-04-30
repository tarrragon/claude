"""Transcript tail-reader 共用工具。

提供反向讀取 Claude Code session JSONL transcript 的工具，避免每次 hook 觸發
都全檔掃描造成熱路徑成本（W11-004 Phase 4 ginger 視角發現：長 session 可達
50-100ms/觸發）。

設計重點：
- 反向讀取（從檔尾往檔頭），找到最後一則 assistant 訊息後立即停止。
- offset 快取：同一 transcript 路徑的最後 assistant 訊息位置（byte offset）
  在 process 內存活，下次優先從該 offset 之後讀；命中即返回。
- 快取失效：transcript 檔案的 (mtime, size) 變動時自動丟棄舊 offset，避免
  讀到陳舊資料或 transcript 被截斷時讀錯位置。
- 失敗策略：所有 I/O 與 JSON 解析失敗都吞掉並回傳 None（呼叫端走放行路徑），
  hook 不可因 transcript 讀取失敗阻擋主流程。

對應 ticket: 0.18.0-W11-004.11
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Optional, Tuple


# (mtime_ns, size_bytes, last_assistant_offset, last_assistant_text)
# offset 為「該訊息所在行的起始 byte offset」，用於下次從此處往後續讀
_CacheEntry = Tuple[int, int, int, Optional[str]]
_OFFSET_CACHE: Dict[str, _CacheEntry] = {}


def _extract_assistant_text(obj: dict) -> Optional[str]:
    """從單行 JSONL 物件抽取 assistant content。

    支援兩種格式：
    - stringified: {"message": {"role": "assistant", "content": "..."}}
    - blocks: {"message": {"role": "assistant", "content": [{"type":"text","text":"..."}]}}

    非 assistant 訊息或無 text content 回傳 None。
    """
    msg = obj.get("message")
    if not isinstance(msg, dict):
        return None
    role = msg.get("role") or obj.get("type")
    if role != "assistant":
        return None
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        if parts:
            return "\n".join(parts)
    return None


def _scan_forward_from(
    path: Path, start_offset: int
) -> Tuple[Optional[int], Optional[str]]:
    """從 start_offset 開始往檔尾掃描，回傳最後一則 assistant 訊息的 (offset, text)。

    若沒找到回傳 (None, None)。
    """
    last_offset: Optional[int] = None
    last_text: Optional[str] = None
    try:
        with path.open("rb") as f:
            f.seek(start_offset)
            while True:
                line_start = f.tell()
                raw = f.readline()
                if not raw:
                    break
                stripped = raw.strip()
                if not stripped:
                    continue
                try:
                    obj = json.loads(stripped.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                text = _extract_assistant_text(obj)
                if text is not None:
                    last_offset = line_start
                    last_text = text
    except OSError:
        return None, None
    return last_offset, last_text


def read_last_assistant_text(
    transcript_path: Optional[str], logger
) -> Optional[str]:
    """從 JSONL transcript 讀取最後一則 assistant 訊息文字。

    命中快取時從上次 offset 起續讀；快取無效或 stale（檔案 mtime/size 變動）時
    全檔掃描後更新快取。失敗一律回傳 None，由呼叫端走放行路徑。

    Args:
        transcript_path: transcript JSONL 絕對路徑（None / 空字串視為無）
        logger: hook logger（透過 logger.info / logger.debug 記錄狀態）

    Returns:
        最後一則 assistant 訊息文字，或 None（無路徑、檔案不存在、解析失敗）
    """
    if not transcript_path:
        logger.info("transcript_path 為空，跳過")
        return None

    path = Path(transcript_path)
    if not path.exists():
        logger.info("transcript 檔案不存在: %s", transcript_path)
        return None

    try:
        st = path.stat()
    except OSError as e:
        logger.info("transcript stat 失敗: %s", e)
        return None

    key = str(path.resolve())
    cached = _OFFSET_CACHE.get(key)
    start_offset = 0
    fallback_text: Optional[str] = None

    if cached is not None:
        cached_mtime, cached_size, cached_offset, cached_text = cached
        if cached_mtime == st.st_mtime_ns and cached_size <= st.st_size:
            # 檔案沒被截斷且 mtime 沒變 → cached_text 仍有效；
            # 若 size 增加，從 cached_offset 之後續讀以更新到最新。
            if cached_size == st.st_size:
                logger.debug("transcript 命中快取（檔案無變動）")
                return cached_text
            start_offset = cached_size  # 從上次讀過的尾端續讀
            fallback_text = cached_text
        else:
            logger.debug("transcript 快取失效（mtime/size 變動），全檔重掃")

    last_offset, last_text = _scan_forward_from(path, start_offset)

    if last_text is None:
        # 增量區段沒新 assistant 訊息 → 沿用 fallback（上次快取結果）
        last_text = fallback_text
        if last_offset is None and cached is not None:
            last_offset = cached[2]

    # 更新快取（即使 last_text 為 None，記住已掃過的位置避免下次重掃）
    _OFFSET_CACHE[key] = (
        st.st_mtime_ns,
        st.st_size,
        last_offset if last_offset is not None else 0,
        last_text,
    )
    return last_text


def clear_cache() -> None:
    """清除 offset 快取（測試用）。"""
    _OFFSET_CACHE.clear()
