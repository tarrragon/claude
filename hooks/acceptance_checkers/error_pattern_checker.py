"""
Error Pattern Checker - error-pattern 衝突檢查（Step 2.7）

檢查修改的模組是否與既有 error-pattern 記錄衝突。

2026-11-12 收斂：關鍵詞排除通用目錄名（原本單一 hook 檔即命中全庫約六成），
底線與連字號互通，結果依相關度排序（命中關鍵詞數、pattern 檔名含關鍵詞加權）；
清單長度上限由呼叫端套用。

呼叫端有兩處：complete 時的 acceptance-gate-hook（Step 2.7），以及 2026-11-13
起 ticket claim 成功後的候選清單（lifecycle.py 的 _print_error_pattern_candidates）。
修改本函式的回傳形狀或豁免規則時，兩端一併確認。
"""

import re
import sys
import subprocess
from pathlib import Path
from typing import Dict, List, Set

# 加入 hooks 目錄（acceptance_checkers 的上層）
_hooks_dir = Path(__file__).parent.parent
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

from acceptance_checkers.ticket_parser import extract_where_files

# Error-pattern 衝突檢查豁免的 Ticket 類型
ERROR_PATTERN_CONFLICT_EXEMPT_TYPES = {"DOC", "ANA", "REF"}

# 不作為比對關鍵詞的通用路徑名（容器目錄、慣用檔名），出現在多數 pattern 內文中
_GENERIC_PATH_TOKENS: frozenset = frozenset({
    ".claude", "claude", "src", "lib", "core", "test", "tests", "docs",
    "hooks", "skills", "scripts", "commands", "references", "rules",
    "pm-rules", "agents", "methodologies", "error-patterns", "templates",
    "__init__", "main", "utils", "common", "config", "settings", "readme",
})

# pattern 檔名含關鍵詞時的加權（檔名命中比內文提及更直接相關）
_FILENAME_HIT_WEIGHT = 2

# 關鍵詞來源權重：被修改檔的檔名比所在目錄名更能指認對象
_STEM_KEYWORD_WEIGHT = 2
_DIR_KEYWORD_WEIGHT = 1


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

    # 從 where.files 取得修改檔案清單（改用 extract_where_files
    # 正規化，避免 parse_ticket_frontmatter 對巢狀列表產出換行字串時被
    # isinstance(files, list) 靜默判定為空，依稽核結論）
    files = extract_where_files(frontmatter, logger)
    if not files:
        logger.debug("where.files 為空或不存在，跳過衝突檢查")
        return []

    keywords = extract_conflict_keywords(files)
    if not keywords:
        logger.debug("未提取到有效關鍵詞，跳過衝突檢查")
        return []

    logger.info(f"error-pattern 衝突檢查關鍵詞: {sorted(keywords)}")

    error_patterns_dir = project_dir / ".claude" / "error-patterns"
    if not error_patterns_dir.is_dir():
        logger.debug("error-patterns 目錄不存在，跳過衝突檢查")
        return []

    # 逐關鍵詞 grep，彙整每個 pattern 檔命中的關鍵詞，供相關度排序
    hits_by_file: Dict[Path, Set[str]] = {}
    for keyword in sorted(keywords):
        try:
            result = subprocess.run(
                ["grep", "-r", "-l", "-i", "-E", _keyword_regex(keyword), str(error_patterns_dir)],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            logger.info(f"error-pattern 衝突搜尋失敗（不阻擋）: {e}")
            return []
        if result.returncode != 0 or not result.stdout.strip():
            continue
        for line in result.stdout.strip().split("\n"):
            path = Path(line)
            if path.name.lower() == "readme.md":
                continue  # 索引檔列出全部 pattern，不是 pattern 本身
            hits_by_file.setdefault(path, set()).add(keyword)

    if not hits_by_file:
        logger.debug("未發現 error-pattern 衝突")
        return []

    ranked = sorted(
        hits_by_file.items(),
        key=lambda item: (-_relevance_score(item[0], item[1], keywords), str(item[0])),
    )
    conflicts = [str(path.relative_to(project_dir)) for path, _ in ranked]
    logger.info(f"發現 {len(conflicts)} 個 error-pattern 衝突（已依相關度排序）")
    return conflicts


def extract_conflict_keywords(files: List[str]) -> Dict[str, int]:
    """由 where.files 提取比對關鍵詞與權重：檔名（去副檔名）權重 2，後兩層目錄名權重 1。

    通用目錄名（hooks、skills 等）幾乎出現在每個 error-pattern 的內文裡，
    納入會讓單一 hook 檔的比對命中全庫多數檔案，故排除。檔名比目錄名更能
    指認被修改的對象，權重較高，使「只提到檔名」的 pattern 排在「只提到
    所在目錄」的 pattern 之前。
    """
    keywords: Dict[str, int] = {}
    for filepath in files:
        if not isinstance(filepath, str):
            continue
        path = Path(filepath)
        stem = path.stem.lower()
        if len(stem) > 2 and stem not in _GENERIC_PATH_TOKENS:
            keywords[stem] = _STEM_KEYWORD_WEIGHT
        parts = path.parts
        for part in parts[-3:-1] if len(parts) > 2 else parts[:-1]:
            token = part.lower()
            if len(token) > 2 and token not in _GENERIC_PATH_TOKENS:
                keywords.setdefault(token, _DIR_KEYWORD_WEIGHT)
    return keywords


def _keyword_regex(keyword: str) -> str:
    """關鍵詞轉 grep 樣式：底線與連字號互通（檔名慣例不同仍可命中）。"""
    return "[-_]".join(re.escape(part) for part in re.split(r"[-_]", keyword))


def _relevance_score(
    pattern_path: Path, matched_keywords: Set[str], weights: Dict[str, int]
) -> int:
    """相關度：命中關鍵詞的權重和；pattern 檔名本身含關鍵詞者再加權。"""
    name = pattern_path.name.lower().replace("_", "-")
    in_name = sum(1 for kw in matched_keywords if kw.replace("_", "-") in name)
    return sum(weights[kw] for kw in matched_keywords) + _FILENAME_HIT_WEIGHT * in_name
