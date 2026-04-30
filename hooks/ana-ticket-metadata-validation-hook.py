#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6.0"]
# ///

"""
ANA-Created Ticket Metadata Validation Hook

防護 PC-058：ANA 代理人（saffron 等）建立 follow-up Ticket 時 metadata 漂移。

觸發時機：PostToolUse (Write/Edit)，當寫入路徑為 docs/work-logs/*/tickets/*.md 時。

驗證項目：
  1. who.current 是否為 CLAUDE.md 指定的語言實作代理人
  2. acceptance 每項 < 100 字元、無「;」分隔多條件
  3. tdd_phase 與 ticket type 合理（小改動/DOC/ANA 不應強走完整 phase1-4）

行為：
  - 偵測到問題輸出 WARNING 到 stderr（不阻擋寫入）
  - 始終 exit 0
  - 僅檢查由 ANA 類代理人建立的 ticket（who.current 為 ANA 類，或 source_ticket 非空）

對應 Ticket: 0.18.0-W11-004.5
對應 Error Pattern: PC-058
"""

import sys
import re
import json
import os
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

# 加入 hook_utils 路徑（相同目錄）
sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import setup_hook_logging, run_hook_safely, read_json_from_stdin

try:
    import yaml
except ImportError:
    yaml = None


# ============================================================================
# 常數定義
# ============================================================================

# ANA 類代理人（產出分析報告 + 建立 follow-up ticket 的代理人）
ANA_AGENT_TYPES = {
    "saffron-system-analyst",
    "sage",
    "saffron",
    "saffron-analyst",
}

# acceptance 單項長度上限（PC-058 檢測規則）
ACCEPTANCE_MAX_LENGTH = 100

# acceptance 多條件分隔符（不應出現於單一 bullet）
MULTI_CONDITION_SEPARATORS = ["；", ";", " and ", "&&"]

# 合法 tdd_phase 值
VALID_TDD_PHASES = {None, "phase0", "phase1", "phase2", "phase3a", "phase3b", "phase4"}


# ============================================================================
# CLAUDE.md 實作代理人解析
# ============================================================================

def get_project_implementation_agent(project_root: Path, logger) -> Optional[str]:
    """
    從 CLAUDE.md 解析「實作代理人」欄位。

    Args:
        project_root: 專案根目錄
        logger: logger

    Returns:
        實作代理人名稱（如 thyme-extension-engineer），或 None
    """
    claude_md = project_root / "CLAUDE.md"
    if not claude_md.exists():
        logger.debug("CLAUDE.md 不存在")
        return None

    try:
        content = claude_md.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"讀取 CLAUDE.md 失敗: {e}")
        return None

    # 匹配 | **實作代理人** | xxx-yyy-zzz（描述） |
    match = re.search(r"\|\s*\*\*實作代理人\*\*\s*\|\s*([a-z][a-z0-9\-]+)", content)
    if match:
        agent = match.group(1)
        logger.debug(f"從 CLAUDE.md 取得實作代理人: {agent}")
        return agent

    logger.debug("CLAUDE.md 未找到實作代理人欄位")
    return None


# ============================================================================
# Frontmatter 解析
# ============================================================================

def is_ticket_file(file_path: Path) -> bool:
    """判斷是否為 ticket 檔案。"""
    return bool(re.search(r"docs/work-logs/[^/]+/tickets/[^/]+\.md$", file_path.as_posix()))


def parse_frontmatter(content: str, logger) -> Optional[Dict[str, Any]]:
    """解析 ticket frontmatter。"""
    if yaml is None:
        logger.error("PyYAML 不可用，無法解析 frontmatter")
        return None

    if not content.startswith("---"):
        return None

    lines = content.split("\n")
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return None

    try:
        return yaml.safe_load("\n".join(lines[1:end_idx]))
    except Exception as e:
        logger.warning(f"frontmatter 解析失敗: {e}")
        return None


# ============================================================================
# ANA 來源偵測
# ============================================================================

def is_ana_created_ticket(frontmatter: Dict[str, Any]) -> bool:
    """
    判斷 ticket 是否由 ANA 代理人建立。

    判斷準則（任一成立即視為 ANA 來源）：
      1. who.current 為 ANA 類代理人
      2. source_ticket 非空（spawned 自其他 ticket）且 dispatch_reason 含 'ANA'
    """
    # 準則 1：who.current
    who = frontmatter.get("who") or {}
    if isinstance(who, dict):
        current = who.get("current") or ""
        if current in ANA_AGENT_TYPES:
            return True
        # 包含 saffron / sage 字根
        if current and any(ana in current for ana in ("saffron", "sage")):
            return True

    # 準則 2：source_ticket + dispatch_reason
    source_ticket = frontmatter.get("source_ticket")
    if source_ticket:
        return True

    return False


# ============================================================================
# 驗證邏輯
# ============================================================================

def validate_who_field(
    frontmatter: Dict[str, Any],
    expected_agent: Optional[str],
) -> Optional[str]:
    """
    驗證 who.current 是否符合專案實作代理人。

    Returns:
        warning 訊息或 None
    """
    if not expected_agent:
        return None  # 無法判斷專案代理人時跳過

    who = frontmatter.get("who") or {}
    if not isinstance(who, dict):
        return None

    current = who.get("current") or ""
    # ANA 類代理人本身（仍在分析階段）不檢查
    if current in ANA_AGENT_TYPES or any(ana in current for ana in ("saffron", "sage")):
        return None

    ticket_type = (frontmatter.get("type") or "").upper()
    # IMP / 實作類 ticket 才檢查 who 是否符合語言代理人
    if ticket_type not in ("IMP", "FEAT", "BUG"):
        return None

    if current and current != expected_agent:
        return (
            f"who.current = '{current}' 與 CLAUDE.md 指定實作代理人 "
            f"'{expected_agent}' 不符（PC-058）"
        )
    return None


def validate_acceptance(frontmatter: Dict[str, Any]) -> List[str]:
    """
    驗證 acceptance：每項 < 100 字元、無多條件分隔符。

    Returns:
        warning 訊息列表
    """
    warnings = []
    acceptance = frontmatter.get("acceptance") or []
    if not isinstance(acceptance, list):
        return warnings

    for idx, item in enumerate(acceptance, 1):
        if not isinstance(item, str):
            continue
        # 去除 "[ ]" / "[x]" 前綴後計算長度
        body = re.sub(r"^\[[ xX]\]\s*", "", item).strip()
        if len(body) > ACCEPTANCE_MAX_LENGTH:
            warnings.append(
                f"acceptance[{idx}] 長度 {len(body)} > {ACCEPTANCE_MAX_LENGTH} 字元"
                f"（建議拆分為獨立條件，PC-058）"
            )
        for sep in MULTI_CONDITION_SEPARATORS:
            if sep in body:
                warnings.append(
                    f"acceptance[{idx}] 含多條件分隔符 '{sep.strip()}'，"
                    f"違反 1-item-1-check 原則（PC-058）"
                )
                break
    return warnings


def validate_tdd_phase(frontmatter: Dict[str, Any]) -> Optional[str]:
    """
    驗證 tdd_phase 與 ticket type 合理性。

    規則：
      - DOC 類 ticket 不應有 tdd_phase
      - tdd_stage 列出全部 phase1-4 但任務描述短時，提示 PM 評估是否縮減
    """
    ticket_type = (frontmatter.get("type") or "").upper()
    tdd_phase = frontmatter.get("tdd_phase")
    tdd_stage = frontmatter.get("tdd_stage") or []

    if ticket_type == "DOC" and tdd_phase:
        return (
            f"DOC 類 ticket 不應指定 tdd_phase（目前: {tdd_phase}），"
            f"文件變更不適用 TDD 流程（PC-058）"
        )

    # 全 4 phase 預設值警示（提示 PM 評估）
    if isinstance(tdd_stage, list) and len(tdd_stage) >= 4:
        what = (frontmatter.get("what") or "").strip()
        # what 描述極短（< 30 字元）+ 走完整 4 phase 視為可疑預設
        if what and len(what) < 30:
            return (
                f"tdd_stage 涵蓋 {len(tdd_stage)} 個 phase 但 what 描述極短，"
                f"建議評估是否為預設值未調整（PC-058）"
            )
    return None


def validate_ana_ticket(
    frontmatter: Dict[str, Any],
    expected_agent: Optional[str],
) -> List[str]:
    """彙整所有驗證項目。"""
    warnings: List[str] = []

    who_warn = validate_who_field(frontmatter, expected_agent)
    if who_warn:
        warnings.append(who_warn)

    warnings.extend(validate_acceptance(frontmatter))

    tdd_warn = validate_tdd_phase(frontmatter)
    if tdd_warn:
        warnings.append(tdd_warn)

    return warnings


# ============================================================================
# 主入口
# ============================================================================

def main() -> int:
    logger = setup_hook_logging("ana-ticket-metadata-validation")

    input_data = read_json_from_stdin(logger)
    if input_data is None:
        return 0

    tool_input = input_data.get("tool_input", {})
    file_path_str = tool_input.get("file_path")
    if not file_path_str:
        logger.debug("無 file_path")
        return 0

    file_path = Path(file_path_str)
    if not is_ticket_file(file_path):
        logger.debug(f"非 ticket 檔案: {file_path}")
        return 0

    # 取得內容（Write 提供 content，Edit 後檔案已寫入需重讀）
    content = tool_input.get("content")
    if not isinstance(content, str) or not content.startswith("---"):
        # Edit 工具：讀取磁碟內容
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.debug(f"讀取 ticket 檔案失敗: {e}")
            return 0

    frontmatter = parse_frontmatter(content, logger)
    if not frontmatter:
        logger.debug("frontmatter 解析失敗或不存在")
        return 0

    # 僅驗證 ANA 來源 ticket
    if not is_ana_created_ticket(frontmatter):
        logger.debug(f"非 ANA 來源 ticket，跳過: {frontmatter.get('id')}")
        return 0

    # 取得專案實作代理人
    project_root = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).resolve()
    expected_agent = get_project_implementation_agent(project_root, logger)

    # 執行驗證
    warnings = validate_ana_ticket(frontmatter, expected_agent)

    if warnings:
        ticket_id = frontmatter.get("id", file_path.name)
        header = (
            f"[ANA Ticket Metadata Warning] {ticket_id}（PC-058 防護）"
        )
        logger.warning(f"{ticket_id}: {len(warnings)} 項警告")
        # 寫入 stderr 確保 PM 可見（規則 4）
        print(header, file=sys.stderr)
        for w in warnings:
            print(f"  - {w}", file=sys.stderr)
            logger.warning(f"  - {w}")
        print("  PM 派發前請複檢並修正 metadata。", file=sys.stderr)
    else:
        logger.info(f"ANA ticket {frontmatter.get('id')} metadata 檢查通過")

    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "ana-ticket-metadata-validation"))
