"""
Error Pattern Checker - error-pattern 衝突檢查（Step 2.7）

檢查修改的模組是否與既有 error-pattern 記錄衝突。
"""

import sys
import subprocess
from pathlib import Path
from typing import List

# 加入 hooks 目錄（acceptance_checkers 的上層）
_hooks_dir = Path(__file__).parent.parent
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

# Error-pattern 衝突檢查豁免的 Ticket 類型
ERROR_PATTERN_CONFLICT_EXEMPT_TYPES = {"DOC", "ANA", "REF"}


def check_error_pattern_conflicts(
    frontmatter: dict, project_dir: Path, logger
) -> List[str]:
    """
    檢查修改的模組是否與既有 error-pattern 記錄衝突（Step 2.7）。

    從 Ticket frontmatter 的 where.files 欄位取得修改檔案清單，
    提取模組關鍵詞後搜尋 error-patterns 目錄。

    Args:
        frontmatter: Ticket frontmatter 結構
        project_dir: 專案根目錄
        logger: 日誌物件

    Returns:
        List[str] - 衝突的 error-pattern 檔案路徑清單（空表示無衝突）
    """
    # 豁免檢查：DOC/ANA/REF 類型跳過
    ticket_type = (frontmatter.get("type") or "").upper()
    if ticket_type in ERROR_PATTERN_CONFLICT_EXEMPT_TYPES:
        logger.debug(f"Ticket 類型 {ticket_type} 豁免 error-pattern 衝突檢查")
        return []

    # 從 where.files 取得修改檔案清單
    where = frontmatter.get("where")
    if not isinstance(where, dict):
        logger.debug("frontmatter 無 where 欄位，跳過衝突檢查")
        return []

    files = where.get("files")
    if not files or not isinstance(files, list):
        logger.debug("where.files 為空或不存在，跳過衝突檢查")
        return []

    # 提取模組關鍵詞（檔案名去副檔名、路徑中的目錄名）
    keywords = set()
    for filepath in files:
        if not isinstance(filepath, str):
            continue
        path = Path(filepath)
        # 檔案名（去副檔名）
        stem = path.stem
        if stem and len(stem) > 2:
            keywords.add(stem.lower())
        # 路徑中的目錄名（取最後兩層）
        parts = path.parts
        for part in parts[-3:-1] if len(parts) > 2 else parts[:-1]:
            if part and len(part) > 2 and part not in ("src", "lib", "core", "test", "tests"):
                keywords.add(part.lower())

    if not keywords:
        logger.debug("未提取到有效關鍵詞，跳過衝突檢查")
        return []

    logger.info(f"error-pattern 衝突檢查關鍵詞: {sorted(keywords)}")

    # 用 grep 搜尋 error-patterns 目錄
    error_patterns_dir = project_dir / ".claude" / "error-patterns"
    if not error_patterns_dir.is_dir():
        logger.debug("error-patterns 目錄不存在，跳過衝突檢查")
        return []

    # 構建 grep pattern：用 | 連接所有關鍵詞（不區分大小寫）
    grep_pattern = "|".join(sorted(keywords))
    conflicts = []

    try:
        result = subprocess.run(
            ["grep", "-r", "-l", "-i", "-E", grep_pattern, str(error_patterns_dir)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            matched_files = result.stdout.strip().split("\n")
            # 轉為相對路徑
            for f in matched_files:
                rel = Path(f).relative_to(project_dir)
                conflicts.append(str(rel))
            logger.info(f"發現 {len(conflicts)} 個 error-pattern 衝突")
        else:
            logger.debug("未發現 error-pattern 衝突")
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        logger.info(f"error-pattern 衝突搜尋失敗（不阻擋）: {e}")

    return conflicts
