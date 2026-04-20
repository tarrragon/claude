"""
Error Pattern Attribution Filter - 精確歸屬新增 error-pattern 至來源 Ticket

PC-099 防護：acceptance-gate-hook 場景 #17 AUQ 原本僅比對 mtime > ticket.started_at，
會把「同一 session 內其他工作新增的 PC」誤報為「當前 ticket 新增」，造成 false positive。

本模組提供 `filter_error_patterns_by_ticket_scope()`，將 mtime-based 候選清單再依
「是否真正屬於當前 ticket scope」過濾，僅保留與當前 ticket 有明確關聯的 PC 檔案。

歸屬判定順序（短路求值）：

1. PC 檔案含 YAML frontmatter `source_ticket` 欄位：
   - 等於當前 ticket_id → 歸屬（保留）
   - 為空 / null / 其他 ticket_id → 不歸屬（過濾）

2. PC 檔案無 frontmatter（既有 legacy 格式）：
   - 當前 ticket md 內容（where.files / acceptance / solution log）引用該 PC 的
     檔名（basename）或 PC ID（如 `PC-099`）→ 歸屬
   - 完全無引用 → 不歸屬（meta-ticket / 跨 session 保護）

此策略對應 ticket W10-087 how.strategy 的混合方案：(b) source_ticket 前瞻 +
(a) 時間窗 fallback（以 ticket md 引用為近似證據，避免依賴 git log）。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Tuple


# PC ID 正規表達式（如 PC-099、IMP-055、ARCH-019）
_PATTERN_ID_RE = re.compile(r"\b(?:PC|IMP|ARCH|ANA|REF|DOC)-\d+\b", re.IGNORECASE)

# YAML frontmatter 開頭結尾標記
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_pc_frontmatter_source_ticket(
    pc_content: str, logger=None
) -> Tuple[bool, Optional[str]]:
    """解析 PC 檔案的 YAML frontmatter `source_ticket` 欄位。

    Returns:
        (has_frontmatter, source_ticket_value)
        - has_frontmatter: 檔案是否含 `---` YAML frontmatter 區塊
        - source_ticket_value: frontmatter 內 `source_ticket` 的值；無此欄位或值為
          空/null 時為 None
    """
    m = _FRONTMATTER_RE.match(pc_content)
    if not m:
        return False, None

    block = m.group(1)
    for line in block.splitlines():
        stripped = line.strip()
        if stripped.startswith("source_ticket:"):
            value = stripped.split(":", 1)[1].strip()
            # 去除引號
            if (value.startswith('"') and value.endswith('"')) or (
                value.startswith("'") and value.endswith("'")
            ):
                value = value[1:-1]
            # null / 空值視為 None
            if not value or value.lower() in ("null", "~", "none"):
                return True, None
            return True, value

    return True, None


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
        current_ticket_id: 當前 complete 中的 ticket ID（如 `0.18.0-W10-087`）
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
            pc_content = pc_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            if logger:
                logger.warning(
                    "無法讀取 PC 檔案 %s: %s（保守歸屬以避免漏報）", rel_path, e
                )
            attributed.append(rel_path)
            continue

        # 步驟 1：frontmatter source_ticket 優先
        has_fm, source_ticket = _parse_pc_frontmatter_source_ticket(pc_content, logger)

        if has_fm and source_ticket is not None:
            if source_ticket == current_ticket_id:
                if logger:
                    logger.info(
                        "PC %s frontmatter source_ticket=%s 匹配當前 ticket，歸屬",
                        rel_path,
                        source_ticket,
                    )
                attributed.append(rel_path)
            else:
                if logger:
                    logger.info(
                        "PC %s frontmatter source_ticket=%s 不匹配當前 ticket %s，過濾",
                        rel_path,
                        source_ticket,
                        current_ticket_id,
                    )
            continue

        # 步驟 2：無 frontmatter 或 source_ticket 為 null → 回退至 ticket 引用檢查
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
