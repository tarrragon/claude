"""
Ticket metadata 品質驗證模組

遷自 ana-ticket-metadata-validation-hook.py（PC-058）。該 hook 註冊為
PostToolUse + matcher Write，但 ticket 檔案的正常寫入管道是 ticket CLI
（Bash subprocess），從未對真實 ticket 觸發過。本模組將三項驗證邏輯搬入
`ticket create` 流程內部呼叫，使其對每一次真實建票皆生效。

三項驗證：
  1. who.current 是否符合 CLAUDE.md 指定的實作代理人
  2. acceptance 每項 < 100 字元、無「;」/「；」等分隔符分隔多條件
  3. tdd_phase 與 ticket type 的合理性

適用範圍：本專案所有 `ticket create`，不限 ANA 代理人來源（原 hook 的
`is_ana_created_ticket()` 過濾層未隨遷移保留——三項驗證邏輯本身皆非
ANA 專屬判準，且獨立量測顯示非 ANA 來源票的警告率不低於 ANA 來源票，
繼續限縮射程會漏掉多數訊號；量測方法與範圍見遷移紀錄）。

who 欄位檢查的範疇限縮（相對於原 hook 的重要修正）：原 `validate_who_field`
假設「每張 IMP/FEAT/BUG ticket 都該指派給 CLAUDE.md 唯一列出的實作代理人」，
但本專案實際採多代理人依領域分工（`.claude/` 框架基礎設施類 ticket 指派給
thyme-python-developer／basil-hook-architect 等專責代理人，非 CLAUDE.md
的「實作代理人」欄位——該欄位描述的是產品程式碼〔Flutter/Dart〕的語言代理人）。
獨立掃描全庫既有 ticket 發現：套用原判準會標記約半數「不符」，其中絕大多數
的 where.files 命中 `.claude/` 路徑，即專案本身認定為正確分工的框架
ticket。故本模組的 who 檢查新增範疇限縮：where.files 命中任一 `.claude/`
路徑時略過此項檢查（保留 acceptance／tdd_phase 兩項不受影響，兩者判準與
代理人分工無關）。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from ticket_system.lib.checkbox_utils import strip_checkbox_prefix
from ticket_system.lib.command_lifecycle_messages import CreateMessages
from ticket_system.lib.file_conflict import where_files as _where_files

# acceptance 單項長度上限（PC-058 檢測規則，逐字沿用原 hook 常數）
ACCEPTANCE_MAX_LENGTH = 100

# acceptance 多條件分隔符（不應出現於單一 bullet，逐字沿用原 hook 常數）
MULTI_CONDITION_SEPARATORS = ["；", ";", " and ", "&&"]


def get_project_implementation_agent(project_root: Path) -> Optional[str]:
    """從 CLAUDE.md 解析「實作代理人」欄位。

    Args:
        project_root: 專案根目錄

    Returns:
        實作代理人名稱（如 parsley-flutter-developer），或 None
    """
    claude_md = project_root / "CLAUDE.md"
    if not claude_md.is_file():
        return None

    try:
        content = claude_md.read_text(encoding="utf-8")
    except OSError:
        return None

    # 匹配 | **實作代理人** | xxx-yyy-zzz（描述） |
    match = re.search(r"\|\s*\*\*實作代理人\*\*\s*\|\s*([a-z][a-z0-9\-]+)", content)
    return match.group(1) if match else None


def _is_framework_scoped(ticket: Dict[str, Any]) -> bool:
    """where.files 是否命中任一 `.claude/` 路徑（框架/基礎設施範疇）。

    who 欄位檢查的範疇限縮判準——見模組頂部 docstring 的量測依據。
    """
    return any(
        isinstance(f, str) and f.strip().startswith(".claude/")
        for f in _where_files(ticket)
    )


def validate_who_field(
    ticket: Dict[str, Any],
    expected_agent: Optional[str],
) -> Optional[str]:
    """驗證 who.current 是否符合專案實作代理人。

    Returns:
        警告訊息或 None
    """
    if not expected_agent:
        return None  # 無法判斷專案代理人時跳過

    if _is_framework_scoped(ticket):
        return None  # 框架/基礎設施範疇改由專責代理人分工，非本檢查範疇

    who = ticket.get("who") or {}
    if not isinstance(who, dict):
        return None

    current = who.get("current") or ""
    ticket_type = (ticket.get("type") or "").upper()
    # IMP / 實作類 ticket 才檢查 who 是否符合語言代理人
    if ticket_type not in ("IMP", "FEAT", "BUG"):
        return None

    if current and current != expected_agent:
        return CreateMessages.WHO_AGENT_MISMATCH_WARNING.format(
            current=current, expected=expected_agent,
        )
    return None


def validate_acceptance(ticket: Dict[str, Any]) -> List[str]:
    """驗證 acceptance：每項 < 100 字元、無多條件分隔符。

    Returns:
        警告訊息列表
    """
    warnings: List[str] = []
    acceptance = ticket.get("acceptance") or []
    if not isinstance(acceptance, list):
        return warnings

    for idx, item in enumerate(acceptance, 1):
        if not isinstance(item, str):
            continue
        _, body = strip_checkbox_prefix(item)
        if len(body) > ACCEPTANCE_MAX_LENGTH:
            warnings.append(CreateMessages.ACCEPTANCE_TOO_LONG_WARNING.format(
                idx=idx, length=len(body), max_length=ACCEPTANCE_MAX_LENGTH,
            ))
        for sep in MULTI_CONDITION_SEPARATORS:
            if sep in body:
                warnings.append(CreateMessages.ACCEPTANCE_MULTI_CONDITION_WARNING.format(
                    idx=idx, sep=sep.strip(),
                ))
                break
    return warnings


def validate_tdd_phase(ticket: Dict[str, Any]) -> Optional[str]:
    """驗證 tdd_phase 與 ticket type 合理性。

    規則：
      - DOC 類 ticket 不應有 tdd_phase
      - tdd_stage 列出全部 phase1-4 但任務描述短時，提示 PM 評估是否縮減

    Returns:
        警告訊息或 None
    """
    ticket_type = (ticket.get("type") or "").upper()
    tdd_phase = ticket.get("tdd_phase")
    tdd_stage = ticket.get("tdd_stage") or []

    if ticket_type == "DOC" and tdd_phase:
        return CreateMessages.TDD_PHASE_DOC_TYPE_WARNING.format(tdd_phase=tdd_phase)

    # 全 4 phase 預設值警示（提示 PM 評估）
    if isinstance(tdd_stage, list) and len(tdd_stage) >= 4:
        what = (ticket.get("what") or "").strip()
        # what 描述極短（< 30 字元）+ 走完整 4 phase 視為可疑預設
        if what and len(what) < 30:
            return CreateMessages.TDD_PHASE_DEFAULT_SUSPECT_WARNING.format(
                phase_count=len(tdd_stage),
            )
    return None


def validate_ticket_metadata(
    ticket: Dict[str, Any],
    project_root: Path,
) -> List[str]:
    """彙整所有 metadata 品質驗證項目，供 `ticket create` 流程呼叫。

    Args:
        ticket: 新建立的 ticket dict（`create.py` 建立後、儲存前/後的完整結構）
        project_root: 專案根目錄（供讀取 CLAUDE.md）

    Returns:
        警告訊息列表（已含 [WARNING] 前綴，與 detect_srp_violations 等既有
        detect_* 函式同慣例，呼叫端直接 print(format_warning(warning))）
    """
    warnings: List[str] = []

    expected_agent = get_project_implementation_agent(project_root)
    who_warn = validate_who_field(ticket, expected_agent)
    if who_warn:
        warnings.append(who_warn)

    warnings.extend(validate_acceptance(ticket))

    tdd_warn = validate_tdd_phase(ticket)
    if tdd_warn:
        warnings.append(tdd_warn)

    return warnings
