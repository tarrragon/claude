"""
Error Pattern Attribution Filter - 精確歸屬新增 error-pattern 至來源 Ticket

PC-099 防護：acceptance-gate-hook 場景 #17 AUQ 原本僅比對 mtime > ticket.started_at，
會把「同一 session 內其他工作新增的 PC」誤報為「當前 ticket 新增」，造成 false positive。

本模組提供 `filter_error_patterns_by_ticket_scope()`，將 mtime-based 候選清單再依
「是否真正屬於當前 ticket scope」過濾，僅保留與當前 ticket 有明確關聯的 PC 檔案。

歸屬判定順序（短路求值）：

1. PC 檔案讀取失敗 → 保守歸屬（避免漏報）

2. 當前 ticket md 內容（where.files / acceptance / solution log）引用該 PC 的
   檔名（basename）或 PC ID（如 `PC-099`）→ 歸屬
   完全無引用 → 不歸屬（meta-ticket / 跨 session 保護）

不讀取 PC frontmatter 的任何欄位：error-pattern 會隨同步擴散到其他專案，
歸屬證據只放在當前 ticket md（以 ticket md 引用為證據，避免依賴 git log）。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List, Optional

# Pattern ID 正規表達式收斂為單一 SSOT。
# PATTERN_ID_RE 涵蓋全 category（PC/IMP/ARCH/...）並支援 Model 1 來源前綴格式
# （PC-V1-001）。新增 category 前綴時只需改 lib/pattern_id.py 一處。
_hooks_dir = Path(__file__).resolve().parent.parent  # .claude/hooks
_claude_dir = _hooks_dir.parent  # .claude/
if str(_claude_dir) not in sys.path:
    sys.path.insert(0, str(_claude_dir))
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

from lib.pattern_id import PATTERN_ID_RE as _PATTERN_ID_RE  # noqa: E402

def _extract_pc_id(pc_filename: str) -> Optional[str]:
    """從 PC 檔名提取 Pattern ID（如 PC-099-meta-....md → PC-099）。"""
    m = _PATTERN_ID_RE.search(pc_filename)
    return m.group(0).upper() if m else None


def _ticket_references_pc(
    ticket_content: str, pc_file_path: str, pc_id: Optional[str]
) -> bool:
    """檢查 ticket md 內容是否引用指定 PC（以 basename 或 PC ID）。"""
    basename = Path(pc_file_path).name
    # basename 直接出現
    if basename and basename in ticket_content:
        return True
    # PC ID 出現（大小寫不敏感）
    if pc_id and re.search(rf"\b{re.escape(pc_id)}\b", ticket_content, re.IGNORECASE):
        return True
    return False


def filter_error_patterns_by_ticket_scope(
    candidate_files: List[str],
    current_ticket_id: str,
    ticket_content: str,
    project_dir: Path,
    logger=None,
) -> List[str]:
    """將 mtime-based 候選 PC 檔案清單過濾為「真正歸屬當前 ticket」者。

    Args:
        candidate_files: `check_error_patterns_changed` 回傳的候選檔案相對路徑清單
        current_ticket_id: 當前 complete 中的 ticket ID（格式 `{VERSION}-W{WAVE}-{SEQ}`）
        ticket_content: 當前 ticket md 完整內容（含 frontmatter + body）
        project_dir: 專案根目錄
        logger: 日誌物件（可選）

    Returns:
        過濾後的檔案清單（僅保留歸屬當前 ticket 者）
    """
    if not candidate_files:
        return []

    attributed: List[str] = []

    for rel_path in candidate_files:
        pc_path = project_dir / rel_path
        try:
            pc_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            if logger:
                logger.warning(
                    "無法讀取 PC 檔案 %s: %s（保守歸屬以避免漏報）", rel_path, e
                )
            attributed.append(rel_path)
            continue

        # 歸屬只看 ticket md 是否引用該 PC
        pc_id = _extract_pc_id(Path(rel_path).name)
        if _ticket_references_pc(ticket_content, rel_path, pc_id):
            if logger:
                logger.info(
                    "PC %s (id=%s) 被 ticket %s md 引用，歸屬",
                    rel_path,
                    pc_id,
                    current_ticket_id,
                )
            attributed.append(rel_path)
        else:
            if logger:
                logger.info(
                    "PC %s (id=%s) 無 frontmatter 歸屬且 ticket %s md 未引用，過濾（PC-099 保護）",
                    rel_path,
                    pc_id,
                    current_ticket_id,
                )

    return attributed
