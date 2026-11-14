#!/usr/bin/env -S uv run --quiet --script
# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
Analysis-Before-Edit Checkpoint Hook - PreToolUse (Edit|Write)

功能:
  「先分析、後修改」原本只寫在派發 prompt，沒有可觀測的檢查點。本 hook 在執行者
  寫產品檔前讀票面，對應章節仍為 placeholder 時介入（僅 IMP 票；DOC／ANA 放行並記 info）：
    - 形態 T（IMP 且 requires_red_run 為真）：讀 Test Results，要求先貼紅燈輸出
    - 形態 P（其餘 IMP）：讀 Problem Analysis，要求先寫問題根因與修改點
  判定前先移除 CLI 自動寫入的子節（查重紀錄、派發日誌、Commit 規範），
  子節清單沿用 track_acceptance 的既有定義。

對應票的方式:
  1. payload 有 agent_id：經 dispatch-active.json 映射（agent_id 精確比對，或
     agent_handle 錨定正規式 ^a<handle>-<hex>$）取得 ticket_id -> 章節為 placeholder 時 deny
  2. 無 agent_id（線 session／PM）：以 in_progress 票的 where.files（write 意圖）比對
     寫入目標，唯一命中才以 additionalContext 提醒；命中零張或多張時放行並記 info

受眾宣告: deny 理由與 additionalContext 給模型；info 日誌給營運。

排除（一律放行）: 測試檔、docs/（含票面）、/tmp 與 scratchpad 路徑。

fail-open: 映射缺失、票面找不到、章節不存在 -> 放行並記 info。
hook 自身例外 -> 放行，寫 stderr 與日誌（檢查點屬流程提醒，故障時不擋下所有寫入）。

已知缺口（不涵蓋）: NotebookEdit；Bash 重導向／sed／python 寫檔。
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import (  # noqa: E402
    setup_hook_logging,
    read_json_from_stdin,
    run_hook_safely,
    get_project_root,
    emit_hook_output,
)
from lib import dispatch_tracker  # noqa: E402
from lib.hook_ticket import (  # noqa: E402
    find_ticket_file,
    parse_ticket_frontmatter,
    extract_where_files_from_frontmatter,
)

_TICKET_SKILL_DIR = Path(__file__).resolve().parent.parent / "skills" / "ticket"
if str(_TICKET_SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(_TICKET_SKILL_DIR))
from ticket_system.lib.dispatch_skeleton import RED_RUN_LINE, requires_red_run  # noqa: E402
from ticket_system.lib.section_locator import find_section  # noqa: E402
from ticket_system.lib.ticket_validator import _is_placeholder  # noqa: E402
from ticket_system.lib.managed_subsections import (  # noqa: E402
    CLI_MANAGED_H3_HEADINGS,
    CREATE_GENERATED_H3_HEADINGS,
    find_h3_subsection,
)

HOOK_NAME = "analysis-before-edit-checkpoint-hook"
EXIT_SUCCESS = 0
TICKET_TYPE_IMP = "IMP"

FILE_TOOLS = ("Edit", "Write")
SECTION_TEST_RESULTS = "Test Results"
SECTION_PROBLEM_ANALYSIS = "Problem Analysis"
WORKTREES_SEGMENT = os.sep + ".claude" + os.sep + "worktrees"

_TEMP_PREFIXES = ("/tmp/", "/private/tmp/")
_TEST_DIR_NAMES = {"test", "tests", "__tests__", "spec"}
_TEST_FILE_PATTERNS = (
    re.compile(r"^test_.*\.py$"),
    re.compile(r"^conftest\.py$"),
    re.compile(r"_test\.[A-Za-z0-9]+$"),
    re.compile(r"\.(test|spec)\.[A-Za-z0-9]+$"),
)
_IN_PROGRESS_LINE = re.compile(r"^status:\s*['\"]?in_progress['\"]?\s*$", re.MULTILINE)
_FRONTMATTER_HEAD_BYTES = 4096

GUIDANCE_T = "先實跑新增測試，把紅燈輸出寫入 Test Results。" + RED_RUN_LINE
GUIDANCE_P = "先讀票面與相關程式碼，把問題根因與預計修改點寫入 Problem Analysis。"

DENY_TEMPLATE = (
    "[分析先行檢查點] 票 {ticket_id} 的 {section} 仍是 placeholder，這次寫入的產品檔（{target}）已擋下。"
    "{guidance}寫入命令：ticket track append-log {ticket_id} --section \"{section}\" \"<內容>\"。"
    "章節填好後重試同一寫入即可。"
)
REMIND_TEMPLATE = (
    "[分析先行檢查點] 提醒（不阻擋）：這次寫入的檔案（{target}）列在 in_progress 票 {ticket_id} 的 where.files，"
    "該票的 {section} 仍是 placeholder。{guidance}寫入命令：ticket track append-log {ticket_id} "
    "--section \"{section}\" \"<內容>\"。"
)


def main_root_from(root: Path) -> Path:
    """若 root 位於 <main>/.claude/worktrees/<name>，回傳 <main>，否則原樣回傳。"""
    s = str(root)
    idx = s.find(WORKTREES_SEGMENT)
    return Path(s[:idx]) if idx >= 0 else root


def is_excluded_path(target: str) -> bool:
    """測試檔、docs/（含票面）、/tmp 與 scratchpad 路徑不屬產品檔。"""
    if target.startswith(_TEMP_PREFIXES):
        return True
    parts = Path(target).parts
    if "docs" in parts or "scratchpad" in parts:
        return True
    if any(p in _TEST_DIR_NAMES for p in parts[:-1]):
        return True
    name = parts[-1] if parts else ""
    return any(p.search(name) for p in _TEST_FILE_PATTERNS)


def mapped_ticket_id(agent_id: str, root: Path, logger) -> Optional[str]:
    """依 agent_id 經 dispatch-active.json 映射取得 ticket_id；無映射回傳 None。"""
    for d in dispatch_tracker.get_active_dispatches(root):
        hit = d.get("agent_id") == agent_id
        handle = d.get("agent_handle") or ""
        if not hit and handle:
            hit = re.match("^a" + re.escape(handle) + "-[0-9a-f]+$", agent_id) is not None
        if hit:
            ticket_id = d.get("ticket_id") or None
            if ticket_id is None:
                logger.info("映射命中但無 ticket_id，放行: %s", agent_id)
            return ticket_id
    logger.info("agent_id 無映射，放行: %s", agent_id)
    return None


def _in_progress_ticket_paths(root: Path) -> List[Path]:
    work_logs = root / "docs" / "work-logs"
    if not work_logs.is_dir():
        return []
    result = []
    for path in work_logs.glob("v*/**/tickets/*.md"):
        lowered = {p.lower() for p in path.parts}
        if "archive" in lowered or "backup" in lowered:
            continue
        try:
            with open(path, encoding="utf-8") as f:
                head = f.read(_FRONTMATTER_HEAD_BYTES)
        except OSError:
            continue
        if _IN_PROGRESS_LINE.search(head):
            result.append(path)
    return result


def _target_matches(target: str, where_file: str) -> bool:
    # 只去掉 "./" 前綴；lstrip("./") 會連 ".claude/" 開頭的點一起剝掉，使框架路徑永不命中
    rel = where_file.strip().removeprefix("./").split("::", 1)[0]
    return bool(rel) and (target == rel or target.endswith(os.sep + rel))


def matching_tickets(target: str, root: Path, logger) -> List[Tuple[Path, Dict]]:
    """回傳 where.files（write 意圖）含 target 的 in_progress 票。"""
    hits = []
    for path in _in_progress_ticket_paths(root):
        fm = parse_ticket_frontmatter(path, logger)
        if not fm or fm.get("status") != "in_progress":
            continue
        files = extract_where_files_from_frontmatter(fm, logger, intent="write", canonical=True)
        if any(_target_matches(target, f) for f in files):
            hits.append((path, fm))
    return hits


def _strip_cli_generated(content: str) -> str:
    """移除 CLI 自動寫入的子節（查重紀錄、派發日誌、Commit 規範）。

    這些子節由 ticket create／dispatch 寫入，不代表執行者已做分析；不先移除，
    分析未填的票會被判成已填而放行。子節清單取自 ticket_system 的單一定義。
    """
    for heading in (*CLI_MANAGED_H3_HEADINGS, *CREATE_GENERATED_H3_HEADINGS):
        sub = find_h3_subsection(content, heading)
        if sub:
            content = content[: sub[0]] + content[sub[2]:]
    return content


def pending_section(path: Path, fm: Dict, logger) -> Optional[Tuple[str, str]]:
    """回傳 (章節名, 補寫指引)；章節已填、不存在或非 IMP 時回傳 None。"""
    ticket_type = fm.get("type")
    if ticket_type != TICKET_TYPE_IMP:
        # 證據只來自實作票；DOC／ANA 的分析章節為選填，且 .claude/**/*.md 皆屬產品檔
        logger.info("非 IMP 票（%s），放行: %s", ticket_type, path.name)
        return None
    form_t = requires_red_run(ticket_type, fm.get("acceptance"))
    section, guidance = (
        (SECTION_TEST_RESULTS, GUIDANCE_T) if form_t else (SECTION_PROBLEM_ANALYSIS, GUIDANCE_P)
    )
    match = find_section(path.read_text(encoding="utf-8"), section)
    if not match.found:
        logger.info("票面無 %s 章節，放行: %s", section, path.name)
        return None
    if not _is_placeholder(_strip_cli_generated(match.content)):
        return None
    return section, guidance


def evaluate(input_data: dict, root: Path, logger) -> Tuple[Optional[str], Optional[str]]:
    """回傳 (決定, 訊息)：決定為 "deny"、"remind" 或 None（放行）。"""
    if input_data.get("tool_name") not in FILE_TOOLS:
        return None, None
    target = (input_data.get("tool_input") or {}).get("file_path")
    if not target:
        logger.info("缺 file_path，放行")
        return None, None
    target = os.path.normpath(target)
    if is_excluded_path(target):
        return None, None

    agent_id = input_data.get("agent_id")
    if agent_id:
        ticket_id = mapped_ticket_id(agent_id, root, logger)
        if ticket_id is None:
            return None, None
        path = find_ticket_file(ticket_id, root, logger)
        if path is None:
            logger.info("找不到票面，放行: %s", ticket_id)
            return None, None
        fm = parse_ticket_frontmatter(path, logger) or {}
        pending = pending_section(path, fm, logger)
        if pending is None:
            logger.info("章節已填，放行: %s %s", ticket_id, target)
            return None, None
        section, guidance = pending
        logger.info("分析章節仍為 placeholder，deny: %s %s %s", ticket_id, section, target)
        return "deny", DENY_TEMPLATE.format(
            ticket_id=ticket_id, section=section, target=target, guidance=guidance
        )

    hits = matching_tickets(target, root, logger)
    if len(hits) != 1:
        logger.info("where.files 命中 %d 張 in_progress 票，放行: %s", len(hits), target)
        return None, None
    path, fm = hits[0]
    ticket_id = fm.get("id") or path.stem
    pending = pending_section(path, fm, logger)
    if pending is None:
        return None, None
    section, guidance = pending
    logger.info("分析章節仍為 placeholder，提醒: %s %s %s", ticket_id, section, target)
    return "remind", REMIND_TEMPLATE.format(
        ticket_id=ticket_id, section=section, target=target, guidance=guidance
    )


def main() -> int:
    logger = setup_hook_logging(HOOK_NAME)
    input_data = read_json_from_stdin(logger)
    if not input_data:
        return EXIT_SUCCESS
    try:
        decision, message = evaluate(input_data, main_root_from(Path(get_project_root())), logger)
    except Exception as e:  # 檢查點屬流程提醒：例外時放行，stderr 與日誌皆留紀錄
        logger.critical("hook 例外，已放行: %s", e, exc_info=True)
        sys.stderr.write("[%s] 例外，已放行: %s\n" % (HOOK_NAME, e))
        return EXIT_SUCCESS
    if decision == "deny":
        emit_hook_output("PreToolUse", permission_decision="deny", permission_decision_reason=message)
    elif decision == "remind":
        emit_hook_output("PreToolUse", additional_context=message)
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
