"""
路徑權限檢查模組

提供檔案路徑的允許/禁止模式比對和權限判斷。
從 main-thread-edit-restriction-hook.py 提取。
消除 EXCEPTION 層，改為 ALLOWED 優先檢查，每條路徑只匹配一層。
"""

import os
import re
from pathlib import Path
from typing import Tuple

from lib.hook_messages import GateMessages


# ============================================================================
# 路徑模式定義
# ============================================================================

# 允許的檔案路徑模式（正則）
# 注意：Ticket 檔案由 ticket-file-access-guard-hook.py 專責處理
ALLOWED_PATTERNS = [
    r"^\.claude/[^/]+\.(json|yaml)$",  # .claude/ 根目錄配置檔
    r"^\.claude/[^/]+\.md$",  # .claude/ 根目錄 md 檔（README.md, CHANGELOG.md 等；W10-049 清理任務支援）
    r"^\.claude/plans/.*",
    r"^\.claude/rules/.*",
    r"^\.claude/methodologies/.*",
    r"^\.claude/hooks/.*",
    r"^\.claude/skills/.*",
    r"^\.claude/agents/.*",
    r"^\.claude/references/.*",
    r"^\.claude/pm-rules/.*",
    r"^\.claude/error-patterns/.*",
    r"^\.claude/hook-specs/.*",
    r"^\.claude/scripts/.*",
    r"^\.claude/handoff/.*",
    r"^\.claude/analyses/.*",  # 歷史分析報告歸檔（W10-049 清理任務支援）
    r"^\.claude/templates/.*",  # 通用模板檔案（W10-049.3 引用更新需求）
    r"^\.claude/lib/.*\.md$",  # lib 目錄的 md 文件（README 等；W10-049.1 引用更新需求；.py 仍由 BLOCKED_PATTERNS 阻擋）
    r"^\.claude/output-styles/.*",  # output-style 設計檔案：主線程可直接編輯（W10-050，PC-066 ARCH-018 教訓）
    r"^docs/.*",
    r"^CLAUDE\.md$",
    r"^CHANGELOG\.md$",
    r"^\.gitignore$",  # repo 層級忽略清單：主線程可直接補 runtime artifact / lock（W10-033）
    r"^\.gitattributes$",  # repo 層級檔案屬性：主線程可直接維護 eol/binary 規範（W10-054.1.1）
    r"^\.claude/\.gitattributes$",  # 框架層級檔案屬性：隨 sync 傳播到其他專案
]

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
        reason = GateMessages.EDIT_BLOCKED_CLAUDE_INVALID_PATH
        logger.warning(f"拒絕編輯非白名單 .claude/ 路徑: {normalized_path}")
        return False, reason

    # 預設拒絕
    reason = GateMessages.EDIT_BLOCKED_DEFAULT_DENY
    logger.warning(f"拒絕編輯非白名單路徑（預設拒絕）: {normalized_path}")
    return False, reason
