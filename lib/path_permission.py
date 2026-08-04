"""
路徑權限檢查模組

提供檔案路徑的允許/禁止模式比對和權限判斷。
從 main-thread-edit-restriction-hook.py 提取。
消除 EXCEPTION 層，改為 ALLOWED 優先檢查，每條路徑只匹配一層。

0.2.1-W3-066：ALLOWED_PATTERNS 是 .claude/ 子目錄白名單的建立端（source of truth）。
拒絕訊息（hook_messages.GateMessages.EDIT_BLOCKED_CLAUDE_INVALID_PATH）過去硬編碼一份
獨立清單，兩者結構上可各自演進而漂移（tool-output-trust-rules 規則 6：驗證器/訊息清單
與建立端定義衝突時以建立端為準）。改為訊息清單由 get_allowed_claude_subdirectory_lines()
從 ALLOWED_PATTERNS 動態推導，兩者不可能再漂移。
"""

import os
import re
from collections import namedtuple
from pathlib import Path
from typing import List, Tuple

from lib.hook_messages import GateMessages


# ============================================================================
# 路徑模式定義
# ============================================================================

# _AllowedEntry.dir_label：非 None 時代表這條規則對應一個「.claude/ 子目錄」，
# 會被 get_allowed_claude_subdirectory_lines() 收錄進拒絕訊息的可寫清單；
# None 代表根目錄檔案模式或非 .claude/ 路徑，不屬於「子目錄」語意，訊息不列出。
_AllowedEntry = namedtuple("_AllowedEntry", ["pattern", "dir_label", "description"])

# .claude/ 子目錄的中文說明，僅供拒絕訊息排版用；新增子目錄時只需在下方
# ALLOWED_PATTERN_ENTRIES 補一行，清單與訊息會自動同步，無需手動維護第二份清單。
ALLOWED_PATTERN_ENTRIES: List[_AllowedEntry] = [
    _AllowedEntry(r"^\.claude/[^/]+\.(json|yaml)$", None, None),  # .claude/ 根目錄配置檔
    _AllowedEntry(r"^\.claude/[^/]+\.md$", None, None),  # .claude/ 根目錄 md 檔（README.md, CHANGELOG.md 等；W10-049）
    _AllowedEntry(r"^\.claude/plans/.*", "plans", "計畫檔案"),  # i18n-exempt
    _AllowedEntry(r"^\.claude/rules/.*", "rules", "規則"),  # i18n-exempt
    _AllowedEntry(r"^\.claude/methodologies/.*", "methodologies", "方法論"),  # i18n-exempt
    _AllowedEntry(r"^\.claude/hooks/.*", "hooks", "Hook 系統"),  # i18n-exempt
    _AllowedEntry(r"^\.claude/skills/.*", "skills", "Skill 工具"),  # i18n-exempt
    _AllowedEntry(r"^\.claude/agents/.*", "agents", "代理人定義"),  # i18n-exempt
    _AllowedEntry(r"^\.claude/references/.*", "references", "參考檔案"),  # i18n-exempt
    _AllowedEntry(r"^\.claude/pm-rules/.*", "pm-rules", "PM 流程規則"),  # i18n-exempt
    _AllowedEntry(r"^\.claude/error-patterns/.*", "error-patterns", "錯誤模式"),  # i18n-exempt
    _AllowedEntry(r"^\.claude/hook-specs/.*", "hook-specs", "Hook 規格"),  # i18n-exempt
    _AllowedEntry(r"^\.claude/scripts/.*", "scripts", "腳本"),  # i18n-exempt
    _AllowedEntry(r"^\.claude/handoff/.*", "handoff", "交接檔案"),  # i18n-exempt
    _AllowedEntry(r"^\.claude/analyses/.*", "analyses", "歷史分析報告歸檔（W10-049）"),  # i18n-exempt
    _AllowedEntry(r"^\.claude/templates/.*", "templates", "通用模板檔案（W10-049.3）"),  # i18n-exempt
    _AllowedEntry(r"^\.claude/lib/.*\.md$", "lib", "lib 目錄的 .md 文件（.py 仍由 BLOCKED_PATTERNS 阻擋）"),  # i18n-exempt
    _AllowedEntry(r"^\.claude/output-styles/.*", "output-styles", "output-style 設計檔案（W10-050）"),  # i18n-exempt
    # config 目錄含 presence_profiles.py，為 3 個 hook 的 import 目標；
    # 修改該檔後須跑 .claude/hooks/tests/test_presence_detection_hook.py
    _AllowedEntry(r"^\.claude/config/.*", "config", "框架設定資料（0.2.1-W3-069）"),  # i18n-exempt
    _AllowedEntry(r"^docs/.*", None, None),
    _AllowedEntry(r"^CLAUDE\.md$", None, None),
    _AllowedEntry(r"^CHANGELOG\.md$", None, None),
    _AllowedEntry(r"^package\.json$", None, None),  # 版本發布 bump
    _AllowedEntry(r"^manifest\.json$", None, None),  # Chrome Extension manifest 版本發布 bump
    _AllowedEntry(r"^\.gitignore$", None, None),  # repo 層級忽略清單（W10-033）
    _AllowedEntry(r"^\.gitattributes$", None, None),  # repo 層級檔案屬性（W10-054.1.1）
    _AllowedEntry(r"^\.claude/\.gitattributes$", None, None),  # 框架層級檔案屬性：隨 sync 傳播到其他專案
    _AllowedEntry(r"(^|.*/)README\.md$", None, None),  # 任意層級 README.md
]

ALLOWED_PATTERNS = [entry.pattern for entry in ALLOWED_PATTERN_ENTRIES]


def get_allowed_claude_subdirectory_lines() -> List[str]:
    """從 ALLOWED_PATTERN_ENTRIES 動態推導「.claude/ 允許子目錄」清單，供拒絕訊息使用。

    回傳格式化好的行清單（`  - .claude/xxx/  (說明)`），與 ALLOWED_PATTERNS
    結構上綁定，新增/移除子目錄規則時訊息自動同步，不需要手動維護第二份清單
    （0.2.1-W3-066，tool-output-trust-rules 規則 6）。
    """
    lines = []
    for entry in ALLOWED_PATTERN_ENTRIES:
        if entry.dir_label is None:
            continue
        lines.append(f"  - .claude/{entry.dir_label}/  ({entry.description})")  # i18n-exempt
    return lines

# 禁止的檔案路徑模式（正則）
# 注意：.claude/hooks/ 和 .claude/skills/ 的 .py 檔案由 ALLOWED_PATTERNS 覆蓋，
# 不在此處列出（消除三層 pattern 互相覆蓋）
BLOCKED_PATTERNS = [
    r"^lib/.*",
    r"^test/.*",
    r".*\.dart$",
    r"^\.claude/lib/.*\.py$",
    r"^backend/.*",
    r".*\.go$",
    r"^go\.mod$",
    r"^go\.sum$",
]


# ============================================================================
# 路徑正規化
# ============================================================================

def normalize_path(file_path: str) -> str:
    """正規化檔案路徑為相對於專案根目錄的路徑"""
    normalized = file_path.replace("\\", "/")

    project_dir = os.getenv("CLAUDE_PROJECT_DIR", str(Path.cwd()))
    project_dir = project_dir.replace("\\", "/")

    if normalized.startswith(project_dir):
        normalized = normalized[len(project_dir):]
        if normalized.startswith("/"):
            normalized = normalized[1:]

    if normalized.startswith("./"):
        normalized = normalized[2:]

    return normalized


# ============================================================================
# 模式比對函式
# ============================================================================

def _matches_any_pattern(file_path: str, patterns: list, logger, label: str) -> bool:
    """檢查路徑是否匹配任一模式"""
    for pattern in patterns:
        if re.match(pattern, file_path):
            logger.debug(f"檔案匹配{label}模式 {pattern}: {file_path}")
            return True
    return False


def is_allowed_path(file_path: str, logger) -> bool:
    """檢查檔案路徑是否在允許清單中"""
    # Claude Code 官方路徑（用戶 home 目錄下，不在專案內）
    normalized_abs = file_path.replace("\\", "/")
    if "/.claude/projects/" in normalized_abs and "/memory/" in normalized_abs:
        logger.debug(f"檔案匹配 Claude Code memory 系統路徑: {normalized_abs}")
        return True
    if "/.claude/plans/" in normalized_abs:
        logger.debug(f"檔案匹配 Claude Code plan 路徑: {normalized_abs}")
        return True

    normalized_path = normalize_path(file_path)
    return _matches_any_pattern(normalized_path, ALLOWED_PATTERNS, logger, "允許")


def is_blocked_path(file_path: str, logger) -> bool:
    """檢查檔案路徑是否在禁止清單中"""
    normalized_path = normalize_path(file_path)
    return _matches_any_pattern(normalized_path, BLOCKED_PATTERNS, logger, "禁止")


# ============================================================================
# 權限判斷
# ============================================================================

def check_file_permission(file_path: str, logger) -> Tuple[bool, str]:
    """
    檢查檔案編輯權限（預設拒絕安全策略）

    檢查順序：允許清單 → 禁止清單 → .claude/ 攔截 → 預設拒絕
    改為 ALLOWED 優先，消除 EXCEPTION 層需求。

    Returns:
        tuple - (is_allowed, reason)
    """
    if not file_path:
        logger.warning("警告: 檔案路徑為空")
        return True, "檔案路徑為空，允許編輯"

    normalized_path = normalize_path(file_path)
    logger.debug(f"檢查檔案路徑: {normalized_path}")

    # 先檢查允許清單（白名單優先，避免需要 EXCEPTION 層覆蓋 BLOCKED）
    if is_allowed_path(normalized_path, logger):
        logger.info(f"允許編輯檔案: {normalized_path}")
        return True, "檔案在允許清單中"

    # 檢查禁止清單
    if is_blocked_path(normalized_path, logger):
        reason = GateMessages.EDIT_BLOCKED_PROGRAM_FILES
        logger.warning(f"拒絕編輯禁止的檔案: {normalized_path}")
        return False, reason

    # .claude/ 非白名單路徑 → 拒絕
    if normalized_path.startswith(".claude/"):
        reason = GateMessages.build_edit_blocked_claude_invalid_path(
            get_allowed_claude_subdirectory_lines()
        )
        logger.warning(f"拒絕編輯非白名單 .claude/ 路徑: {normalized_path}")
        return False, reason

    # 預設拒絕
    reason = GateMessages.EDIT_BLOCKED_DEFAULT_DENY
    logger.warning(f"拒絕編輯非白名單路徑（預設拒絕）: {normalized_path}")
    return False, reason
