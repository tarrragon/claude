#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

"""
Session Start Scheduler Hint Hook

SessionStart 事件觸發時，呼叫 `ticket track runqueue` 取得排程提示，
並作為 additionalContext 顯示於新 session 啟動訊息中。

邏輯：
1. 優先呼叫 `ticket track runqueue --context=resume --top 3`
   - 有待恢復 handoff → 用該輸出
2. 若 resume 無結果（輸出含「無可執行 Ticket」標記）→ fallback
   呼叫 `ticket track runqueue --format=list --top 1` 顯示下一個可執行任務
3. 若兩者皆無 → 本節顯示「無排程提示」
4. 另掃描當前版本的 completed ANA spawned pending，若有則追加「Spawned 推進清單」小節
   （W17-041 / W17-036 軸 D 補強；PC-075 下游傳播路徑訊號通道）

失敗模式：
- CLI 執行錯誤 / timeout / 不存在 → logger.error（stderr）+ 靜默
  （規則 4：失敗可見；但 SessionStart hook 不阻塞 session 啟動）
- Spawned 掃描失敗 → logger.warning + 回傳 None，不影響主排程提示

來源：
- W17-011.4 / W17-009 scheduler 缺口 D（motd/login info 類比）
- W17-041 / W17-036 軸 D：session-start 新增 spawned pending 提醒
"""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

# 加入 hook_utils 路徑
sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import (  # noqa: E402
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    get_project_root,
    parse_ticket_frontmatter,
    scan_ticket_files_by_version,
    find_ticket_file,
)

EXIT_SUCCESS = 0

# CLI 超時秒數（SessionStart 不可長等）
CLI_TIMEOUT_SECONDS = 8

# 判斷「無可執行 Ticket」的輸出特徵（與 ticket track runqueue 對齊）
EMPTY_MARKER = "無可執行 Ticket"

# Spawned pending 掃描限制（避免洗版）
SPAWNED_PENDING_DISPLAY_LIMIT = 5

# Terminal 狀態（spawned 視為「已推進完成」的集合，不列入 pending 清單）
# 與 ticket_system.constants.TERMINAL_STATUSES 對齊（uv script 單檔 dependencies=[]，硬編一致副本）
TERMINAL_STATUSES = {"completed", "closed"}

# todolist.yaml active version 偵測 regex
_TODOLIST_ACTIVE_VERSION_RE = re.compile(
    r"-\s*version:\s*[\"']?(\S+?)[\"']?\s*\n\s*status:\s*active",
    re.MULTILINE,
)


def _run_ticket_cli(args: list, logger) -> Optional[str]:
    """執行 `ticket track runqueue ...` 並回傳 stdout；失敗回 None。"""
    cmd = ["ticket", "track", "runqueue"] + args
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=CLI_TIMEOUT_SECONDS,
        )
        if proc.returncode != 0:
            logger.error(
                "ticket track runqueue 非零退出 (rc=%s): stderr=%s",
                proc.returncode, proc.stderr.strip()[:300],
            )
            return None
        return proc.stdout
    except subprocess.TimeoutExpired as e:
        logger.error("ticket track runqueue 逾時 (%ss): %s", CLI_TIMEOUT_SECONDS, e)
        return None
    except FileNotFoundError as e:
        logger.error("ticket CLI 未安裝或不在 PATH: %s", e)
        return None
    except Exception as e:  # noqa: BLE001 — session 啟動不可因任何例外阻塞
        logger.error("ticket track runqueue 執行錯誤: %s", e, exc_info=True)
        return None


def _has_content(output: Optional[str]) -> bool:
    """判斷 runqueue 輸出是否有實質內容（非空清單）。"""
    if not output or not output.strip():
        return False
    return EMPTY_MARKER not in output


def fetch_scheduler_context(logger) -> Optional[str]:
    """
    取得排程提示內容。

    流程：
    1. 試 resume（--context=resume --top 3）
    2. resume 空則 fallback next（--format=list --top 1）
    3. 皆空 → None
    """
    # Step 1: resume
    resume_out = _run_ticket_cli(["--context=resume", "--top", "3"], logger)
    if _has_content(resume_out):
        return resume_out.strip()

    # Step 2: fallback next
    next_out = _run_ticket_cli(["--format=list", "--top", "1"], logger)
    if _has_content(next_out):
        return next_out.strip()

    # Step 3: 皆無內容
    return None


def _detect_active_version(project_root: Path, logger) -> Optional[str]:
    """從 docs/todolist.yaml 偵測 status=active 的版本字串（不含 v 前綴）。

    優先順序：
    1. 解析 todolist.yaml 的 versions: 列表找 status: active
    2. 若找不到 → 回傳 None（掃描降級，上層靜默忽略）

    與 ticket CLI `_parse_todolist_active_version` 行為一致，但改用輕量 regex
    避免引入 yaml 依賴（uv script dependencies=[]）。

    Args:
        project_root: 專案根目錄
        logger: 日誌物件

    Returns:
        版本字串（例如 "0.18.0"）或 None
    """
    todolist = project_root / "docs" / "todolist.yaml"
    if not todolist.exists():
        logger.debug("todolist.yaml 不存在: %s", todolist)
        return None
    try:
        content = todolist.read_text(encoding="utf-8")
        m = _TODOLIST_ACTIVE_VERSION_RE.search(content)
        if m:
            version = m.group(1).strip()
            logger.debug("偵測到 active version: %s", version)
            return version
        logger.debug("todolist.yaml 中未找到 status=active 版本")
        return None
    except Exception as e:  # noqa: BLE001 — 掃描失敗降級不阻塞
        logger.warning("讀取 todolist.yaml 失敗: %s", e)
        return None


def _extract_spawned_list(frontmatter: dict) -> List[str]:
    """從 frontmatter 萃取 spawned_tickets 清單（支援 list 或 YAML 字串格式）。"""
    raw = frontmatter.get("spawned_tickets") or []
    if isinstance(raw, list):
        return [str(s).strip() for s in raw if s]
    if isinstance(raw, str):
        result = []
        for line in raw.split("\n"):
            line = line.strip()
            if line.startswith("-"):
                item = line[1:].strip()
                if item:
                    result.append(item)
        return result
    return []


def scan_spawned_pending(
    project_root: Path, version: str, logger
) -> List[Tuple[str, str, str]]:
    """掃描當前版本的 completed ANA，回傳其 spawned_tickets 中 status 非 terminal 的項目。

    返回：[(spawned_id, spawned_status, source_ana_id), ...]

    行為：
    - 僅掃描當前 version tickets（~500 檔，實測 < 200ms）
    - 僅納入 pending/in_progress/blocked 等非 terminal 狀態（與 TERMINAL_STATUSES 對齊）
    - 失敗靜默降級：單筆 parse 失敗略過，不影響整體

    Args:
        project_root: 專案根目錄
        version: 版本字串（例如 "0.18.0"）
        logger: 日誌物件

    Returns:
        List of (spawned_id, status, source_ana_id) — 可能為空
    """
    try:
        ticket_files = scan_ticket_files_by_version(project_root, version, logger)
    except Exception as e:  # noqa: BLE001
        logger.warning("掃描版本 tickets 失敗 (v%s): %s", version, e)
        return []
    if not ticket_files:
        logger.debug("當前版本無 ticket 檔案: v%s", version)
        return []

    # Step 1：找 type=ANA + status=completed + 有 spawned_tickets 的 ticket
    ana_completed: List[Tuple[str, List[str]]] = []
    for tf in ticket_files:
        try:
            fm = parse_ticket_frontmatter(tf)
        except Exception as e:  # noqa: BLE001
            logger.debug("解析 frontmatter 失敗 %s: %s", tf.name, e)
            continue
        if fm.get("type") != "ANA":
            continue
        if fm.get("status") != "completed":
            continue
        spawned = _extract_spawned_list(fm)
        if not spawned:
            continue
        ana_id = str(fm.get("id") or tf.stem)
        ana_completed.append((ana_id, spawned))

    if not ana_completed:
        logger.debug("無 completed ANA 含 spawned_tickets")
        return []

    # Step 2：對每個 spawned 檢查 status，收集非 terminal
    non_terminal: List[Tuple[str, str, str]] = []
    for ana_id, spawned_ids in ana_completed:
        for sid in spawned_ids:
            spawned_file = find_ticket_file(sid, project_root, logger)
            if not spawned_file:
                logger.debug("找不到 spawned ticket 檔案: %s", sid)
                continue
            try:
                sfm = parse_ticket_frontmatter(spawned_file)
            except Exception as e:  # noqa: BLE001
                logger.debug("解析 spawned frontmatter 失敗 %s: %s", sid, e)
                continue
            status = sfm.get("status", "unknown")
            if status in TERMINAL_STATUSES:
                continue
            non_terminal.append((sid, status, ana_id))

    logger.info(
        "scan_spawned_pending: ANA(completed+spawned)=%d, spawned_non_terminal=%d",
        len(ana_completed), len(non_terminal),
    )
    return non_terminal


def build_spawned_pending_section(
    non_terminal: List[Tuple[str, str, str]],
) -> Optional[str]:
    """將 spawned non-terminal 清單格式化為 markdown 小節。

    設計要點：
    - 獨立小節 `## Spawned 推進清單`，與主排程提示區分
    - 明示「衍生自 ANA」語意，讓 PM 不會誤認為一般 pending
    - 限制 SPAWNED_PENDING_DISPLAY_LIMIT 項避免洗版；其餘計數顯示
    - 依 source ANA 分組，避免同源 spawned 散落

    Returns:
        markdown 字串（有 pending 時）或 None（無 pending）
    """
    if not non_terminal:
        return None

    # 依 source ANA 分組保留原順序
    by_ana: Dict[str, List[Tuple[str, str]]] = {}
    order: List[str] = []
    for sid, status, ana_id in non_terminal:
        if ana_id not in by_ana:
            by_ana[ana_id] = []
            order.append(ana_id)
        by_ana[ana_id].append((sid, status))

    total = len(non_terminal)
    displayed = 0
    lines: List[str] = [
        "## Spawned 推進清單（來源為 completed ANA 的衍生 IMP/DOC，非原生 pending）",
        "",
        f"共 {total} 筆待推進；下列依 source ANA 分組顯示（最多 {SPAWNED_PENDING_DISPLAY_LIMIT} 筆）：",
        "",
    ]
    for ana_id in order:
        if displayed >= SPAWNED_PENDING_DISPLAY_LIMIT:
            break
        items = by_ana[ana_id]
        lines.append(f"- source ANA: `{ana_id}`")
        for sid, status in items:
            if displayed >= SPAWNED_PENDING_DISPLAY_LIMIT:
                lines.append(f"  - …（其餘 {total - displayed} 筆省略）")
                break
            lines.append(f"  - `{sid}` [status={status}]")
            displayed += 1

    if total > SPAWNED_PENDING_DISPLAY_LIMIT and displayed == SPAWNED_PENDING_DISPLAY_LIMIT:
        # 若迴圈自然結束時剛好達上限，補一行省略提示（上方分支未觸發時）
        if not lines[-1].startswith("  - …"):
            lines.append(f"  - …（其餘 {total - displayed} 筆省略）")

    lines.append("")
    lines.append("建議動作：依 priority 繼承規則挑最高優先處理；若已決策延後，於 handoff 明示排程。")
    return "\n".join(lines)


def fetch_spawned_pending_context(logger) -> Optional[str]:
    """取得 spawned pending markdown 小節（整合 detect + scan + format）。

    失敗靜默降級：任何步驟失敗回傳 None，不影響主排程提示輸出。
    """
    try:
        project_root = get_project_root()
    except Exception as e:  # noqa: BLE001
        logger.warning("取得 project_root 失敗: %s", e)
        return None

    version = _detect_active_version(project_root, logger)
    if not version:
        logger.debug("active version 未偵測到，跳過 spawned pending 掃描")
        return None

    try:
        non_terminal = scan_spawned_pending(project_root, version, logger)
    except Exception as e:  # noqa: BLE001
        logger.warning("scan_spawned_pending 異常（降級為無 spawned 提示）: %s", e)
        return None

    return build_spawned_pending_section(non_terminal)


def build_hook_output(
    scheduler_context: Optional[str],
    spawned_pending_section: Optional[str] = None,
) -> Dict[str, Any]:
    """組裝 SessionStart hook 的 JSON 輸出。

    兩個區塊獨立存在：
    - scheduler_context → `## 排程提示` 區塊（原排程 hint）
    - spawned_pending_section → `## Spawned 推進清單` 區塊（W17-041 新增）

    兩者皆無時回傳 suppressOutput=True；任一有內容即輸出 additionalContext。
    """
    sections: List[str] = []
    if scheduler_context:
        sections.append(
            "## 排程提示（scheduler hint）\n\n"
            "```\n"
            f"{scheduler_context}\n"
            "```"
        )
    if spawned_pending_section:
        sections.append(spawned_pending_section)

    if not sections:
        return {"suppressOutput": True}

    message = "\n\n".join(sections) + "\n"
    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": message,
        },
        "suppressOutput": False,
    }


def main() -> int:
    """主入口：讀 stdin（可忽略內容）→ 取 context → 輸出 JSON。"""
    logger = setup_hook_logging("session-start-scheduler-hint-hook")
    logger.info("scheduler hint hook 啟動")

    try:
        # SessionStart 可能無 stdin 或給簡短 JSON；不阻塞
        read_json_from_stdin(logger)
    except Exception as e:  # noqa: BLE001
        logger.warning("讀取 stdin 失敗（忽略）: %s", e)

    scheduler_context = fetch_scheduler_context(logger)
    spawned_pending_section = fetch_spawned_pending_context(logger)
    output = build_hook_output(scheduler_context, spawned_pending_section)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    logger.info(
        "scheduler hint hook 完成（scheduler=%s, spawned_pending=%s）",
        scheduler_context is not None,
        spawned_pending_section is not None,
    )
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "session-start-scheduler-hint"))
