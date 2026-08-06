#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

"""
Stop hook: 偵測 worklog 寫了 handoff 段落但 CLI 未執行的雙軌不同步（W17-083 S3）

對應 W17-083 Phase 1 方案 D（A + C 組合）的 A 部分：
session 結束時掃描 worklog 是否含 handoff 關鍵字，比對 .claude/handoff/pending/
現況，列出缺失（worklog 有 / pending 無）與孤立（pending 有 / worklog 無）。

四主情境：
1. 雙軌一致 → 不輸出
2. worklog 有 / pending 無（核心） → 輸出警告 + 建議命令
3. pending 有 / worklog 無（孤立） → 輸出低優先級提示
4. 雙軌皆無 → 不輸出

輸出協議：
- systemMessage via JSON stdout（top-level 欄位，Claude Code Stop event schema
  不允許 additionalContext；handoff-auto-resume-stop-hook 使用 decision/reason
  與 suppressOutput，本 hook 透過 systemMessage 顯示警告，兩者可獨立共存）

ARCH-020 同構雙寫風險：
- HANDOFF_KEYWORDS / TICKET_ID regex 與 ticket_system/lib/worklog_parser.py 重複
- 因 PEP 723 隔離環境（dependencies=[]）無法 import lib，需照搬 SOT
- SOT: .claude/skills/ticket/ticket_system/lib/worklog_parser.py
- 任一處更新時需手動同步另一處（兩處 docstring 互相引用）

來源：W17-083 ANA Phase 3a S3 設計
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional, Set

# 加入 hook_utils 路徑
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))
from lib import (  # noqa: E402
    setup_hook_logging,
    get_project_root,
    scan_ticket_files_by_version,
    parse_ticket_frontmatter,
    PM_ONLY_PREFIX,
)
from datetime import datetime  # noqa: E402

EXIT_SUCCESS = 0

# Stop flag 防重複觸發（W17-176 根因 1）
# 與 handoff-auto-resume-stop-hook 機制對齊但獨立 flag 路徑，避免互相干擾
STOP_FLAG_FILE = ".claude/handoff/.stop-sync-check-blocked"
STOP_FLAG_EXPIRY_SECONDS = 7200  # 2 小時（一個 session 的合理長度）

# In-progress 偵測豁免（W17-176 根因 2）
# 任務進行中提醒 handoff 邏輯倒置：handoff 是 session 結束時的動作
IN_PROGRESS_STATUSES = {"in_progress"}

# todolist active version 偵測（與 session-start-scheduler-hint-hook 同步）
_TODOLIST_ACTIVE_VERSION_RE = re.compile(
    r"-\s*version:\s*[\"']?(\S+?)[\"']?\s*\n\s*status:\s*active",
    re.MULTILINE,
)

# Pending dir 相對路徑（與 ticket_system.constants.HANDOFF_DIR 一致；硬編副本）
HANDOFF_PENDING_RELPATH = ".claude/handoff/pending"

# Terminal 狀態（已 completed 不視為缺失）
TERMINAL_STATUSES = {"completed", "closed"}

# ---------------------------------------------------------------------------
# SOT-mirror: HANDOFF_KEYWORDS / TICKET_ID regex
# 對應 .claude/skills/ticket/ticket_system/lib/worklog_parser.py
# 任一處更新需同步另一處（ARCH-020）
# ---------------------------------------------------------------------------

HANDOFF_KEYWORDS = (
    # 標題式
    "下個 Session 接手 Context",
    "下一 Session 接手",
    "下 Session 接手",
    "接手指引",
    "Handoff Context",
    "Session Handoff",
    "下一站",
    # 建議式
    "下 session 優先建議",
    "下個 session 優先建議",
    "下一 session 優先建議",
    "下 session 優先順序建議",
    "下次 session 建議",
    "建議下 session",
    # 續行式
    "未完成清單",
    "Spawned 推進清單",
)
# 0.2.1-W3-218 補「下一站」（本專案書寫慣例）。SOT-mirror，同步理由見
# worklog_parser.py:HANDOFF_KEYWORDS docstring。

TICKET_ID_FULL_PATTERN = re.compile(
    r"\b(\d+\.\d+\.\d+)-(W\d+-[\d\w]+(?:\.\d+)?)\b"
)
TICKET_ID_SHORT_PATTERN = re.compile(
    r"\b(W\d+-[\d\w]+(?:\.\d+)?)\b"
)


# ---------------------------------------------------------------------------
# 解析輔助函式（SOT-mirror，與 worklog_parser.py 邏輯一致）
# ---------------------------------------------------------------------------


def _detect_handoff_keywords(content: str) -> bool:
    if not content:
        return False
    return any(kw in content for kw in HANDOFF_KEYWORDS)


# 行首錨定容許前綴：關鍵字前只能有 '#' / '*' / 空白，排除句中出現
# （0.2.1-W3-294 根因 1：rfind 未錨定行首，命中自指語料的歷史分析行）
_ANCHOR_PREFIX_PATTERN = re.compile(r"^[#*\s]*$")
_TITLE_LINE_PATTERN = re.compile(r"^#{1,6}\s")
_INLINE_LIST_END_PATTERN = re.compile(r"^- ", re.MULTILINE)
_INLINE_BOLD_END_PATTERN = re.compile(r"^\*\*", re.MULTILINE)


def _iter_anchored_keyword_hits(content: str):
    """找出所有「行首錨定」的 HANDOFF_KEYWORDS 命中位置（SOT-mirror）。"""
    for kw in HANDOFF_KEYWORDS:
        start = 0
        while True:
            idx = content.find(kw, start)
            if idx < 0:
                break
            line_start = content.rfind("\n", 0, idx) + 1
            prefix = content[line_start:idx]
            if _ANCHOR_PREFIX_PATTERN.match(prefix):
                yield idx, line_start
            start = idx + 1


def _extract_handoff_section(content: str) -> str:
    """從 worklog 內容切出 handoff 相關段落（SOT-mirror，0.2.1-W3-294 重設計）。

    策略：只採「行首錨定」的關鍵字命中（關鍵字前僅允許 '#' / '*' / 空白），
    取最後一個（idx 最大）；依關鍵字所在行的形態分派終點界定——標題式
    （`^#{1,6}\\s`）取下一個 H1/H2，行內式取下一個空行 / 行首條列 `- ` /
    `**` 起始行三者取最先。無行首錨定命中回 ""。

    SOT: .claude/skills/ticket/ticket_system/lib/worklog_parser.py:extract_handoff_section
    任一處更新需同步另一處（ARCH-020）。本函式邏輯（S1 段落界定）與 SOT 完全
    一致；hook 端另有 S2 session 增量前置過濾（見 `_extract_session_incremental_content`），
    是呼叫本函式「前」的獨有前處理，非本函式職責差異——CLI --from-worklog 等
    其他呼叫端無 session 概念，不套用該前置過濾，直接以全文呼叫本函式（與 SOT
    docstring 一致）。

    用於 detect_sync_drift 將 ticket ID 掃描範圍限制在 handoff 段落，避免從整個
    worklog 抓到歷史 ticket 造成 false positive（W17-155 ANA / W17-156 修復）。
    """
    if not content:
        return ""

    hits = list(_iter_anchored_keyword_hits(content))
    if not hits:
        return ""

    latest_idx, line_start = max(hits, key=lambda h: h[0])

    line_end = content.find("\n", latest_idx)
    if line_end == -1:
        line_end = len(content)
    line_text = content[line_start:line_end]

    if _TITLE_LINE_PATTERN.match(line_text):
        section_end_pattern = re.compile(r"^(# |## )", re.MULTILINE)
        next_match = section_end_pattern.search(content, latest_idx + 1)
        if next_match:
            return content[line_start : next_match.start()]
        return content[line_start:]

    candidates = []
    blank_idx = content.find("\n\n", line_end)
    if blank_idx != -1:
        candidates.append(blank_idx)
    list_match = _INLINE_LIST_END_PATTERN.search(content, line_end)
    if list_match:
        candidates.append(list_match.start())
    bold_match = _INLINE_BOLD_END_PATTERN.search(content, line_end)
    if bold_match:
        candidates.append(bold_match.start())

    if candidates:
        return content[line_start : min(candidates)]
    return content[line_start:]


def _preceded_by_version_prefix(content: str, start: int) -> bool:
    if start == 0:
        return False
    prefix_start = max(0, start - 12)
    prefix = content[prefix_start:start]
    return bool(re.search(r"\d+\.\d+\.\d+-$", prefix))


def _extract_ticket_ids(content: str, active_version: Optional[str] = None) -> list[str]:
    if not content:
        return []
    seen: list[str] = []
    seen_set: set[str] = set()
    for match in TICKET_ID_FULL_PATTERN.finditer(content):
        full_id = f"{match.group(1)}-{match.group(2)}"
        if full_id not in seen_set:
            seen.append(full_id)
            seen_set.add(full_id)
    if active_version:
        for match in TICKET_ID_SHORT_PATTERN.finditer(content):
            short_id = match.group(1)
            if _preceded_by_version_prefix(content, match.start()):
                continue
            full_id = f"{active_version}-{short_id}"
            if full_id not in seen_set:
                seen.append(full_id)
                seen_set.add(full_id)
    return seen


def _detect_active_version(project_root: Path) -> Optional[str]:
    """偵測 todolist.yaml 中 status=active 的版本字串（不含 v 前綴）。"""
    todolist = project_root / "docs" / "todolist.yaml"
    if not todolist.exists():
        return None
    try:
        content = todolist.read_text(encoding="utf-8")
        m = _TODOLIST_ACTIVE_VERSION_RE.search(content)
        if m:
            return m.group(1).strip().lstrip("v")
    except Exception:
        return None
    return None


def _find_worklog_path(project_root: Path, version: str) -> Path:
    """構建 main worklog 路徑（與 worklog_appender._build_worklog_path 一致）。"""
    bare = version.lstrip("v")
    parts = bare.split(".")
    major = parts[0]
    minor = f"{parts[0]}.{parts[1]}" if len(parts) >= 2 else bare
    return (
        project_root
        / "docs"
        / "work-logs"
        / f"v{major}"
        / f"v{minor}"
        / f"v{bare}"
        / f"v{bare}-main.md"
    )


def _scan_pending_dir(project_root: Path) -> Set[str]:
    """掃描 .claude/handoff/pending/ 下的 ticket ID（檔名 stem）。

    W17-165 L2-C：過濾 from_ticket 處於 terminal 狀態（completed/closed）的
    handoff JSON，避免下游 orphan 比對誤報。設計取捨：
    - 純檔名掃描（O(N) glob）→ 加入 frontmatter 讀取（O(N) read + regex）
    - 在 session stop 時觸發，N 通常 < 20，額外成本可忽略
    - 失敗 fail-open：讀檔/解析失敗時保留原 ID（與 GC 策略一致）
    """
    pending_dir = project_root / HANDOFF_PENDING_RELPATH
    if not pending_dir.exists():
        return set()

    result: Set[str] = set()
    for p in pending_dir.glob("*.json"):
        ticket_id = p.stem
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            # 解析失敗保留原 ID，不誤刪
            result.add(ticket_id)
            continue

        # 優先以 JSON 內 from_ticket / ticket_id 欄位定位實際 ticket（檔名可能與 from_ticket 不一致）
        from_ticket = (
            (data or {}).get("from_ticket")
            or (data or {}).get("ticket_id")
            or ticket_id
        )
        status = _load_ticket_status(project_root, str(from_ticket))
        if status in TERMINAL_STATUSES:
            # from_ticket 已 terminal → 不視為待恢復；交由 handoff-auto-resume GC 路徑清理
            continue
        result.add(ticket_id)
    return result


def _load_ticket_status(project_root: Path, ticket_id: str) -> Optional[str]:
    """從 ticket md frontmatter 輕量解析 status；找不到回 None。

    避免 import ticket_system（PEP 723 dependencies=[]）；用 regex 解析 status: 行。
    """
    # ticket id 格式：<version>-W<wave>-<seq>[.<sub>]
    parts = ticket_id.split("-", 1)
    if len(parts) < 2:
        return None
    version = parts[0]
    bare = version.lstrip("v")
    sub = bare.split(".")
    major = sub[0]
    minor = f"{sub[0]}.{sub[1]}" if len(sub) >= 2 else bare

    # 可能放在 tickets/ 子目錄
    candidates = [
        project_root / "docs" / "work-logs" / f"v{major}" / f"v{minor}" / f"v{bare}" / "tickets" / f"{ticket_id}.md",
        project_root / "docs" / "work-logs" / f"v{major}" / f"v{minor}" / f"v{bare}" / f"{ticket_id}.md",
    ]
    for ticket_path in candidates:
        if not ticket_path.exists():
            continue
        try:
            content = ticket_path.read_text(encoding="utf-8")
        except Exception:
            continue
        # frontmatter 在開頭 --- ... ---
        m = re.search(r"^status:\s*(\S+)\s*$", content, re.MULTILINE)
        if m:
            return m.group(1).strip()
    return None


# ---------------------------------------------------------------------------
# Stop flag 防重複觸發 + in_progress 豁免（W17-176）
# ---------------------------------------------------------------------------


def _get_stop_flag_path(project_root: Path) -> Path:
    """取得 stop flag 檔案路徑（W17-176 根因 1）。"""
    return project_root / STOP_FLAG_FILE


def _is_blocked_this_session(project_root: Path, logger) -> bool:
    """檢查 stop flag 是否存在且未過期（防重複觸發）。

    flag 機制與 handoff-auto-resume-stop-hook 一致：
    - flag 不存在 → False（首次觸發）
    - flag 存在且未過期 → True（本 session 已執行過，跳過）
    - flag 已過期 → 刪除並回傳 False（視為新 session）

    fail-open：解析失敗時刪除 flag 並回傳 False。
    """
    flag_file = _get_stop_flag_path(project_root)
    if not flag_file.exists():
        return False
    try:
        data = json.loads(flag_file.read_text(encoding="utf-8"))
        created_at_str = data.get("created_at")
        if not created_at_str:
            flag_file.unlink()
            return False
        created_at = datetime.fromisoformat(created_at_str)
        elapsed = (datetime.now() - created_at).total_seconds()
        if elapsed > STOP_FLAG_EXPIRY_SECONDS:
            logger.debug("Stop flag 已過期 (%.1fs)，刪除", elapsed)
            flag_file.unlink()
            return False
        logger.debug("Stop flag 仍有效 (%.1fs)，跳過本次觸發", elapsed)
        return True
    except Exception as e:
        logger.warning("檢查 stop flag 失敗: %s", e)
        try:
            flag_file.unlink()
        except Exception:
            pass
        return False


def _mark_blocked_this_session(project_root: Path, logger) -> None:
    """寫入 stop flag 標記本 session 已執行過。"""
    flag_file = _get_stop_flag_path(project_root)
    try:
        flag_file.parent.mkdir(parents=True, exist_ok=True)
        flag_data = {
            "created_at": datetime.now().isoformat(),
            "reason": "stop_worklog_handoff_sync_check_triggered",
        }
        flag_file.write_text(json.dumps(flag_data, ensure_ascii=False), encoding="utf-8")
        logger.debug("建立 stop flag: %s", flag_file)
    except Exception as e:
        logger.warning("建立 stop flag 失敗: %s", e)


def _is_subagent_context(input_data: dict, logger) -> bool:
    """判斷 stdin 是否帶 subagent context 標記（W1-044）。

    Why：本 hook 註冊於 Stop event（主線程停止）。CC hook input schema
    （.claude/references/hook-architect-technical-reference.md）中 SubagentStop
    才帶 agent_id / agent_type，Stop 不帶。若 stdin 出現 agent_id / agent_type，
    代表本次觸發實際處於 subagent context，此時注入 systemMessage 漂移警告會
    劫持 agent 最終訊息（W1-030 判定 worklog-sync-check 為「中」劫持潛力來源）。

    Consequence：subagent context 下不偵測會把雙軌漂移警告注入 agent 回傳值。

    Action：caller（detect_sync_drift）在最前面呼叫；True 時 return None 跳過偵測。
    採 documented schema 欄位（agent_id/agent_type）判別，不用 transcript heuristic。

    SOT: .claude/skills/ticket/hooks/handoff-auto-resume-stop-hook.py:is_subagent_context
    任一處更新需同步另一處（ARCH-020 同構雙寫，PEP 723 隔離無法 import lib）。
    """
    if not isinstance(input_data, dict):
        return False
    has_marker = bool(input_data.get("agent_id")) or bool(input_data.get("agent_type"))
    if has_marker:
        logger.info(
            "偵測到 subagent context（agent_id=%s, agent_type=%s），跳過 sync check",
            input_data.get("agent_id"),
            input_data.get("agent_type"),
        )
    return has_marker


def _has_background_agents(input_data: dict, logger) -> bool:
    """判斷 input_data 是否有背景代理人正在執行（W3-026.3）。

    Why: Claude Code v2.1.145 stdin 提供 background_tasks 欄位，是「目前有
    背景任務」的直接訊號，比現行的 stop flag + in_progress ticket 推斷更精準；
    背景任務執行中時 worklog/CLI 同步通常尚未完成，提醒屬誤報。

    Consequence: 採「弱依賴策略」——只判斷 list 非空，不依賴 task object
    內部 schema。欄位不存在 / 非 list / 空 list / input_data 非 dict 全部
    回 False，caller 自然 fallback 到現行兩道防護邏輯，不影響舊行為。

    Action: caller（detect_sync_drift）在 stop flag 與 in_progress ticket
    防護之後加入本檢查，True 時 return None 跳過 sync drift 偵測。

    SOT: .claude/skills/ticket/hooks/handoff-auto-resume-stop-hook.py:has_background_agents
    任一處更新需同步另一處（ARCH-020 同構雙寫，PEP 723 隔離無法 import lib）。
    """
    if not isinstance(input_data, dict):
        return False
    bg_tasks = input_data.get("background_tasks")
    if not isinstance(bg_tasks, list):
        return False
    has_active = len(bg_tasks) > 0
    if has_active:
        logger.info(
            f"input_data.background_tasks 非空（{len(bg_tasks)} 項），"
            f"跳過 worklog-handoff sync check"
        )
    return has_active


def _has_in_progress_ticket(project_root: Path, version: str, logger) -> bool:
    """偵測 active version 是否有 in_progress ticket（W17-176 根因 2）。

    Fail-open 設計：偵測過程任何異常皆回傳 False（不阻塞 hook 後續邏輯，但
    本 hook 整體 fail-open 走向是「假設無 in_progress→繼續檢查」，可能造成
    一次假陽性，但不會掩蓋真實的 sync drift 問題）。

    根因 2 邏輯：任務進行中提醒 handoff 是邏輯倒置——handoff 是 session 結束
    時的動作，任務未完成不該補 handoff。
    """
    try:
        ticket_files = scan_ticket_files_by_version(project_root, version, logger)
        if not ticket_files:
            return False
        for ticket_path in ticket_files:
            try:
                fm = parse_ticket_frontmatter(ticket_path, logger)
                if not fm:
                    continue
                status = (fm.get("status") or "").strip().lower()
                if status in IN_PROGRESS_STATUSES:
                    logger.debug("偵測到 in_progress ticket: %s", ticket_path.name)
                    return True
            except Exception as e:
                logger.debug("讀取 ticket frontmatter 失敗 (%s): %s", ticket_path.name, e)
                continue
        return False
    except Exception as e:
        logger.warning("掃描 in_progress ticket 失敗（fail-open）: %s", e)
        return False


# ---------------------------------------------------------------------------
# S2：session 增量前置過濾（0.2.1-W3-294，僅 hook 端適用）
# ---------------------------------------------------------------------------


def _resolve_git_base_commit(project_root: Path, session_start: float, logger) -> Optional[str]:
    """找出 session_start 之前最近一個 commit（作 git diff 的 base）。

    fail-open：git 不可用 / 非 git repo / subprocess 失敗 → 回 None。
    """
    since_iso = datetime.fromtimestamp(session_start).isoformat()
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(project_root),
                "rev-list",
                "-1",
                f"--before={since_iso}",
                "HEAD",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except Exception as e:
        logger.debug("S2 git rev-list 失敗（fail-open 全文）: %s", e)
        return None
    if result.returncode != 0:
        logger.debug("S2 git rev-list 非零 exit（fail-open 全文）: %s", result.stderr)
        return None
    base = result.stdout.strip()
    return base or None


def _extract_session_incremental_content(
    project_root: Path, worklog_path: Path, session_start: float, logger
) -> Optional[str]:
    """S2：以 git diff 界定本 session 新增的 worklog 內容（僅 hook 端適用）。

    Why：關鍵字定位法在自指語料必然失效（根因 1/2），但將掃描範圍先限縮到
    本 session 實際新增的文字，可從源頭排除歷史交接段落，與 S1 段落界定
    互補（S1 處理增量內若仍混有雜訊的界定，S2 處理跨 session 歷史雜訊）。

    Consequence：不做此前置過濾時，即使 S1 修好行首錨定，仍可能命中「本
    session 未寫但歷史仍存在」的行內式交接段落（如上個 session 遺留、尚未
    被下一個 H1/H2 或空行截斷的舊交接行），造成非本 session 中斷卻誤報。

    Action：base 取 session_start 前最近 commit，diff 取新增（`+`）行還原
    為純文字。任一步驟失敗（git 不可用 / base 為空 / subprocess 例外 /
    session_start<=0）回 None，caller 須 fallback 至全文讀取（維持修復前
    行為，不因本強化而破壞既有 fail-open 承諾）。

    CLI --from-worklog 無 session 概念，不套用本函式（S3 語意差異，見
    `_extract_handoff_section` docstring 與 SOT `extract_handoff_section`
    docstring 的 S2 差異說明段落）。
    """
    if session_start <= 0:
        return None
    base = _resolve_git_base_commit(project_root, session_start, logger)
    if not base:
        return None
    try:
        rel_path = worklog_path.relative_to(project_root)
    except ValueError:
        rel_path = worklog_path
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(project_root),
                "diff",
                "--unified=0",
                base,
                "--",
                str(rel_path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except Exception as e:
        logger.debug("S2 git diff 失敗（fail-open 全文）: %s", e)
        return None
    if result.returncode != 0:
        logger.debug("S2 git diff 非零 exit（fail-open 全文）: %s", result.stderr)
        return None

    added_lines = [
        line[1:]
        for line in result.stdout.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]
    return "\n".join(added_lines)


# ---------------------------------------------------------------------------
# 第 7 格偵測：雙軌皆空但 session 有交接訊號（0.2.1-W3-219）
# 來源票 0.2.1-W3-178「可用偵測訊號與誤報風險」：S3 閘門 + S1 主訊號 + S4 反向濾除。
# S2（commit body）/ S5（Context Bundle diff）列為後續增強，本函式不實作。
# ---------------------------------------------------------------------------

_COMMIT_CHORE_PREFIX = "chore("
_COMMIT_HANDOFF_KEYWORD = "交接"


def _iso_to_epoch(value: Optional[str]) -> Optional[float]:
    """ISO 時間字串轉 epoch 秒，解析失敗回 None（fail-open）。"""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)).timestamp()
    except Exception:
        return None


def _get_session_active_tickets(
    project_root: Path, version: str, session_start: float, logger
) -> list[str]:
    """S3 閘門：找出 `started_at` / `completed_at` 落在 `session_start` 之後的
    ticket，代表本 session 有實質 ticket 活動（來源票 W3-178 訊號表 S3 列）。

    只證明「有活動」不指向交接目標本身，故僅作前置條件，非交接訊號本身。
    回傳 ticket id 清單，依 timestamp 新到舊排序（第一項作為建議的
    `--from-ticket-id`）。
    """
    if session_start <= 0:
        return []
    try:
        ticket_files = scan_ticket_files_by_version(project_root, version, logger)
    except Exception as e:
        logger.debug("S3 掃描 ticket 檔案失敗: %s", e)
        return []

    active: list[tuple[float, str]] = []
    for ticket_path in ticket_files:
        try:
            fm = parse_ticket_frontmatter(ticket_path, logger)
        except Exception:
            continue
        if not fm:
            continue
        ticket_id = fm.get("id") or ticket_path.stem
        for field in ("completed_at", "started_at"):
            ts = _iso_to_epoch(fm.get(field))
            if ts is not None and ts >= session_start:
                active.append((ts, str(ticket_id)))
                break
    active.sort(key=lambda item: item[0], reverse=True)
    return [ticket_id for _, ticket_id in active]


def _detect_handoff_commit_signal(
    project_root: Path, session_start: float, logger
) -> list[str]:
    """S1 主訊號 + S4 反向濾除：掃 session 時間窗內 commit subject 的交接語意。

    來源票 W3-178 E4 實測：近 9 天 1035 個 commit 中 subject 命中交接語意僅 5 次
    （0.5%），786 筆（75.9%）為 `chore(` 前綴的 append-log auto-commit 噪音，
    須先濾除否則訊號被淹沒。回傳命中的 commit subject 清單，無命中回空 list。
    """
    if session_start <= 0:
        return []
    since_iso = datetime.fromtimestamp(session_start).isoformat()
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(project_root),
                "log",
                f"--since={since_iso}",
                "--pretty=format:%s",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except Exception as e:
        logger.debug("S1 git log 掃描失敗: %s", e)
        return []
    if result.returncode != 0:
        logger.debug("S1 git log 非零 exit: %s", result.stderr)
        return []

    hits: list[str] = []
    for subject in result.stdout.splitlines():
        subject = subject.strip()
        if not subject:
            continue
        if subject.startswith(_COMMIT_CHORE_PREFIX):
            continue
        if _COMMIT_HANDOFF_KEYWORD in subject:
            hits.append(subject)
    return hits


def _format_dual_empty_warning(
    source_id: str, target_ids: list[str], commit_hits: list[str]
) -> str:
    """格式化第 7 格警告輸出：worklog 與 pending 雙軌皆空，但 commit 有交接語意。"""
    lines: list[str] = []
    lines.append("=" * 40)
    lines.append("[Worklog-CLI Handoff Sync Check] 雙軌皆空但偵測到交接訊號")
    lines.append("=" * 40)
    lines.append("")
    lines.append("worklog 無交接段、.claude/handoff/pending/ 亦無 JSON，")
    lines.append("但本 session 的 commit 訊息含交接語意：")
    lines.append("")
    for subject in commit_hits:
        lines.append(f"  - {subject}")
    lines.append("")
    lines.append("建議執行：")
    if target_ids:
        for tid in target_ids:
            lines.append(f"  ticket handoff --next {tid} --from-ticket-id {source_id}")
    else:
        lines.append(
            f"  ticket handoff --next <target-id> --from-ticket-id {source_id}"
            "  # <target-id> 請換成實際下一站 ticket"
        )
    lines.append("")
    lines.append(
        "（0.2.1-W3-178 8 格矩陣第 7 格；session-switching-sop.md"
        "「Worklog 交接與 CLI handoff 同步」強制規則）"
    )
    return "\n".join(lines)


def _check_dual_empty_handoff_signal(
    project_root: Path, version: str, session_start: float, logger
) -> Optional[str]:
    """第 7 格偵測主流程：S3 閘門 -> S1 訊號（已內含 S4 濾除）-> 輸出建議命令。

    任一階段無命中即靜默回 None，維持第 8 格（確實無交接）不受影響。
    """
    active_tickets = _get_session_active_tickets(project_root, version, session_start, logger)
    if not active_tickets:
        logger.debug("S3 閘門未命中（session 無 ticket 活動），跳過第 7 格偵測")
        return None

    commit_hits = _detect_handoff_commit_signal(project_root, session_start, logger)
    if not commit_hits:
        logger.debug("S1 未命中交接語意 commit，跳過第 7 格偵測")
        return None

    source_id = active_tickets[0]
    target_ids: list[str] = []
    for subject in commit_hits:
        for tid in _extract_ticket_ids(subject, active_version=version):
            if tid not in target_ids:
                target_ids.append(tid)

    return _format_dual_empty_warning(source_id, target_ids, commit_hits)


# ---------------------------------------------------------------------------
# 主邏輯
# ---------------------------------------------------------------------------


def _format_warning(missing: list[str], orphan: list[str]) -> str:
    """格式化警告輸出（對應 W17-083 Phase 1 §4 設計）。"""
    lines = []
    lines.append("=" * 40)
    lines.append("[Worklog-CLI Handoff Sync Check]")
    lines.append("=" * 40)
    lines.append("")

    if missing:
        lines.append("worklog 已寫接手段落，但以下 ticket 未產生 CLI handoff：")
        lines.append("")
        lines.append("缺失（worklog 有 / pending 無）：")
        for tid in missing:
            lines.append(f"  - {tid}")
        lines.append("")
        lines.append("建議執行：")
        for tid in missing:
            lines.append(f"  ticket handoff {tid}")
        lines.append("")
        lines.append("或批次執行：")
        lines.append("  ticket handoff --from-worklog")
        lines.append("")

    if orphan:
        lines.append("孤立（pending 有 / worklog 無）：")
        for tid in orphan:
            lines.append(f"  - {tid}  # 考慮 archive 或補寫 worklog")
        lines.append("")

    lines.append("（session-switching-sop.md「Worklog 交接與 CLI handoff 同步」強制規則）")
    return "\n".join(lines)


def detect_sync_drift(
    project_root: Path,
    session_start: float,
    logger,
    input_data: dict | None = None,
) -> Optional[str]:
    """主檢查邏輯：偵測雙軌不同步並回傳警告字串（無問題回 None）。

    W17-176 + W3-026.3 三道防護（在原邏輯前依序檢查）：
    1. Stop flag：本 session 已執行過 → 跳過（防重複觸發）
    2. in_progress ticket 偵測：有 in_progress ticket → 跳過（任務進行中不該提醒 handoff）
    3. background_tasks（v2.1.145 stdin 直接訊號）：執行中時跳過（W3-026.3）
    4. （隱含）_extract_handoff_section 改 rfind 取最新 → 只列當前 session handoff

    input_data 參數設為 Optional 以保持向後相容（caller 不傳時等同 {} fallback）。
    """
    # W1-044：subagent context 偵測。subagent stop 時跳過 sync check，避免
    # systemMessage 漂移警告劫持 agent 最終訊息（W1-030）。置於所有偵測最前面。
    if _is_subagent_context(input_data or {}, logger):
        return None

    # W17-176 根因 1：stop flag 防重複觸發
    if _is_blocked_this_session(project_root, logger):
        return None

    version = _detect_active_version(project_root)
    if not version:
        logger.debug("無 active version，靜默退出")
        return None

    # W17-176 根因 2：in_progress ticket 偵測豁免（fail-open）
    if _has_in_progress_ticket(project_root, version, logger):
        logger.debug("偵測到 in_progress ticket，跳過 handoff sync check")
        return None

    # W3-026.3：background_tasks 直接訊號（v2.1.145）
    if _has_background_agents(input_data or {}, logger):
        logger.debug("偵測到 background_tasks 非空，跳過 sync check")
        return None

    worklog_path = _find_worklog_path(project_root, version)
    if not worklog_path.exists():
        logger.debug("worklog 不存在: %s", worklog_path)
        return None

    # mtime 過濾：本 session 未動 worklog → worklog 軌恆為「無交接段」（A=無）。
    # 0.2.1-W3-219：此情形若 pending 亦空，正是第 7 格候選，須檢查交接訊號
    # 而非直接靜默；pending 非空則維持既有 orphan 邏輯範圍外的靜默（非本票範圍）。
    if session_start > 0 and worklog_path.stat().st_mtime < session_start:
        logger.debug("worklog mtime 早於 session_start，跳過關鍵字偵測")
        if _scan_pending_dir(project_root):
            return None
        return _check_dual_empty_handoff_signal(project_root, version, session_start, logger)

    try:
        full_content = worklog_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning("讀取 worklog 失敗: %s", e)
        return None

    # S2：優先以 session 增量內容偵測（縮小掃描範圍排除跨 session 歷史雜訊）；
    # 無法界定增量時 fail-open 回退全文（維持修復前行為）
    incremental_content = _extract_session_incremental_content(
        project_root, worklog_path, session_start, logger
    )
    content = incremental_content if incremental_content is not None else full_content

    pending_ids = _scan_pending_dir(project_root)
    has_keywords = _detect_handoff_keywords(content)

    # 雙軌皆無 → 檢查第 7 格訊號（S3 閘門 + S1 主訊號 + S4 反向濾除，0.2.1-W3-219）；
    # 無交接訊號時仍靜默（第 8 格：確實無交接）
    if not has_keywords and not pending_ids:
        return _check_dual_empty_handoff_signal(project_root, version, session_start, logger)

    # W17-156: 只掃 handoff 段落而非整份 worklog，避免抓到歷史 ticket 造成 false positive
    if has_keywords:
        handoff_section = _extract_handoff_section(content)
        worklog_ids = _extract_ticket_ids(handoff_section, active_version=version)
    else:
        worklog_ids = []

    # 過濾 worklog 中已 completed 的 ticket
    worklog_active = []
    for tid in worklog_ids:
        status = _load_ticket_status(project_root, tid)
        if status not in TERMINAL_STATUSES:
            worklog_active.append(tid)

    worklog_active_set = set(worklog_active)
    missing = [tid for tid in worklog_active if tid not in pending_ids]
    orphan = sorted(pending_ids - worklog_active_set)

    if not missing and not orphan:
        return None

    return _format_warning(missing, orphan)


def main():
    logger = setup_hook_logging("stop-worklog-handoff-sync-check")
    try:
        # W3-026.3：讀取 stdin 取得 v2.1.145 background_tasks 欄位
        # 解析失敗 / tty / 欄位不存在皆 fallback 到空 dict（沿用既有行為）
        event: dict = {}
        if not sys.stdin.isatty():
            try:
                parsed = json.loads(sys.stdin.read() or "{}")
                if isinstance(parsed, dict):
                    event = parsed
                else:
                    logger.warning(
                        f"stdin JSON 非 dict 型別（{type(parsed).__name__}），fallback"
                    )
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"解析 stdin 失敗，fallback: {e}")

        session_start = float(event.get("session_start_timestamp", 0) or 0)

        project_root = get_project_root()
        warning = detect_sync_drift(project_root, session_start, logger, input_data=event)

        if warning:
            # Stop event schema 不允許 hookSpecificOutput.additionalContext；
            # 改用 top-level systemMessage（W17-158）。
            # 受眾標記（PC-V1-004 防護 C）：Stop event 無 agent_id，程式層無法
            # 過濾 subagent；加 PM-only 前綴讓 AGENT_PRELOAD 忽略規則補位，
            # 與既有 subagent context 偵測（W1-030 / W1-044）互補形成雙層。
            output = {
                "systemMessage": PM_ONLY_PREFIX + warning,
            }
            print(json.dumps(output, ensure_ascii=False))
            # W17-176 根因 1：成功輸出 warning 後標記 stop flag，後續本 session
            # 不再重複觸發。設計取捨：只在「實際輸出」時標記，避免「無 drift
            # 也消耗 flag」造成下次有 drift 時被誤判跳過。
            _mark_blocked_this_session(project_root, logger)
        sys.exit(EXIT_SUCCESS)
    except Exception as e:
        # 規則 4：失敗可見（stderr + 日誌）
        logger.error("stop-worklog-handoff-sync-check 異常: %s", e, exc_info=True)
        print(f"[stop-worklog-handoff-sync-check] 異常: {e}", file=sys.stderr)
        sys.exit(EXIT_SUCCESS)  # 不阻塞 session stop


if __name__ == "__main__":
    main()
