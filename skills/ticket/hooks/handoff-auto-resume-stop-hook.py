#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///

"""
Handoff 自動恢復 Stop Hook (v2.5.0)

在對話終止時，檢查是否有未完成的 handoff 任務並判斷是否阻止退出。

功能:
1. 檢查 stop flag 檔案是否存在且未過期（防重複觸發）
2. 讀取 session 狀態，若有 locked_ticket_id，提示用戶恢復
3. 掃描 .claude/handoff/pending/ 查找未恢復任務
   - GC：自動刪除已完成 Ticket 的 stale pending JSON
   - GC 例外：to-sibling / to-parent / to-child 類型保留（來源完成是預期狀態）
   - 新增：區分「待恢復任務」和「最近任務」
4. 根據任務類型決定行為：
   - 有待恢復任務（遺留） → 阻止退出，提示恢復
   - 只有最近任務（可能有代理人執行） → 輸出 INFO 提示，允許退出
   - 無任務 → 靜默通過
5. 建立 stop flag 防止同一 session 重複觸發

v2.5.0 變更:
    - next-wave direction 加入非阻塞方向類型（與 auto 同級）
    - 修正 next-wave handoff 在非 Ticket 工作時反覆阻止退出的問題
    - stop flag 過期時間從 5 分鐘延長到 2 小時（一個 session 的合理長度）
    - 重構 direction 判斷：從單一 "auto" 判斷改為 non_blocking_directions 集合

v2.4.0 變更:
    - 新增「最近任務」判斷邏輯，區分「遺留任務」和「正在執行任務」
    - 檢查 in_progress Ticket 的 started_at 時間，若在最近 N 分鐘內開始執行
      → 視為「可能有代理人正在執行」，不阻止對話終止
    - started_at 超過 N 分鐘的 in_progress Ticket → 視為遺留任務，正常阻止
    - 新增常數 RECENT_TASK_THRESHOLD_MINUTES = 30（可配置）
    - 新增函式 is_ticket_recently_started() 檢查任務是否最近開始執行
    - 修改 scan_pending_handoff_tasks() 回傳 tuple (pending_tasks, recent_tasks)
    - 遵循雙通道原則：對最近任務輸出 INFO 到 stderr，允許對話終止

v2.3.0 變更:
    - 修正 reason 欄位內容：從 "/ticket resume {id}" 改為說明文字
    - 原問題：reason 文字被 Claude 當作斜線命令自動執行，違反 handoff 設計
    - 修正後：reason 明確指示 Claude 告知用戶手動執行，不自動 resume

v2.2.0 變更:
    - 修復 GC bug：to-sibling / to-parent / to-child 類型的 handoff，
      來源 Ticket completed 是預期狀態，不應被 GC 刪除
    - 新增 should_preserve_pending_json() 函式判斷是否保留
    - 改善 GC 日誌訊息，區分保留和刪除的原因

v2.1.0 變更:
    - 移除 scan_in_progress_tickets（不再主動建立 pending JSON）
    - 新增 GC：掃描時自動刪除已完成 Ticket 的 stale pending JSON
    - pending JSON 只由 /ticket handoff 明確建立

防重複觸發:
    使用固定的 flag 檔案路徑 .claude/handoff/.stop-blocked
    flag 檔案內容包含時間戳，過期時間為 300 秒（5 分鐘）
    同一 session 內的多次觸發在 5 分鐘內被抑制，新 session 時 flag 已過期
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# 加入 hook_utils 路徑（相同目錄）
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from lib import (
    setup_hook_logging,
    run_hook_safely,
    parse_ticket_frontmatter,
    get_project_root,
    scan_ticket_files_by_version,
    find_ticket_file,
    PM_ONLY_PREFIX,
)

# W3-039: session 管理 domain 已抽出為獨立模組（與本檔同目錄，合法識別符可直接 import）。
# 本檔上方 sys.path.insert(.../"hooks") 已涵蓋 handoff_session_mgmt 的 hook_utils 依賴；
# 本檔目錄因 hook 以絕對路徑執行不在 sys.path 上，故補加 __file__ 父目錄。
sys.path.insert(0, str(Path(__file__).resolve().parent))
from handoff_session_mgmt import (  # noqa: E402
    get_session_stop_flag,
    get_session_state_file,
    has_been_triggered_this_session,
    mark_triggered_this_session,
    read_session_state,
)

# 加入 ticket_system lib 路徑以引用 handoff_utils.is_handoff_stale（W17-095.2）
# 同時加入 skills/ticket 父路徑以解析 handoff_utils 內部的 `from ticket_system.lib.*` import
_TICKET_SKILL_PATH = Path(__file__).resolve().parents[1]
_TICKET_LIB_PATH = _TICKET_SKILL_PATH / "ticket_system" / "lib"
for _p in (_TICKET_SKILL_PATH, _TICKET_LIB_PATH):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    from handoff_utils import is_handoff_stale  # type: ignore
except Exception as _import_err:  # pragma: no cover - fallback：lib 不可用時退化為原邏輯（保留任務鏈）
    # PC-135 防護：silent fallback 改 noisy。lib import 失敗代表 hook 子進程環境
    # 缺少必要依賴（如 pyyaml 經 ticket_system.lib.__init__ → ticket_loader 鏈），
    # 退化邏輯會讓 stale 判定永遠回 False，造成 GC 行為靜默退化。
    # 寫 stderr 讓 PM/開發者立即看到，不要讓退化路徑長時間生效。
    sys.stderr.write(
        f"[handoff-auto-resume-stop-hook][PC-135] handoff_utils import failed, "
        f"using degraded is_handoff_stale fallback (always returns False). "
        f"Cause: {type(_import_err).__name__}: {_import_err}\n"
    )
    def is_handoff_stale(record, project_root=None):  # type: ignore
        direction = (record or {}).get("direction", "") or ""
        direction_type = direction.split(":")[0]
        # 任務鏈方向預設不視為 stale（保留語義與原 should_preserve_pending_json 一致）
        if direction_type in {"to-sibling", "to-parent", "to-child"}:
            return False, ""
        return False, ""

# W17-181.2: delegate is_ticket_terminal 至 lib SSOT，消除跨進程同構邏輯（ARCH-020）。
try:
    from handoff_utils import is_ticket_terminal as _lib_is_ticket_terminal  # type: ignore
except Exception as _import_err:  # pragma: no cover
    # PC-135 防護：silent fallback 改 noisy。退化為「永遠非 terminal」會讓 GC 保留所有 pending
    # （偏安全側），但仍須讓 PM 立即看見以便診斷 lib 不可達根因。
    sys.stderr.write(
        f"[handoff-auto-resume-stop-hook][PC-135] handoff_utils.is_ticket_terminal import failed, "
        f"using degraded fallback (always returns False; pending will not be GC'd by terminal check). "
        f"Cause: {type(_import_err).__name__}: {_import_err}\n"
    )
    def _lib_is_ticket_terminal(ticket_id, project_root=None):  # type: ignore
        return False

EXIT_SUCCESS = 0

# 常數定義
# W3-039: STOP_FLAG_FILE / STOP_FLAG_EXPIRY_SECONDS / STATE_FILE_TEMPLATE
# 隨 session 管理 domain 一併移至 handoff_session_mgmt 模組。
PENDING_DIR_NAME = ".claude/handoff/pending"
LOG_DIR_NAME = ".claude/hook-logs/handoff-auto-resume"
LOG_FILE_PREFIX = "stop-hook"
RECENT_TASK_THRESHOLD_MINUTES = 30  # 30 分鐘內視為「最近任務」（可能有代理人正在執行）
RECENT_HANDOFF_WINDOW_SECONDS = 300  # W17-118: 最近 N 秒內建立的 handoff 視為下 session 接手點，不計入 pending

# W17-181.2: Terminal 狀態集合已上移至 lib `handoff_utils.is_ticket_terminal`
# （透過 ticket_system.constants.TERMINAL_STATUSES 引用），消除跨進程同構邏輯（ARCH-020）。

def _load_frontmatter_cached(
    cache: Optional[Dict[str, Optional[dict]]],
    ticket_id: str,
    project_root: Path,
    logger,
) -> Optional[dict]:
    """單次請求內 ticket frontmatter 採集點（PC-097 / single-source-io-collection-rules）。

    Why：scan_pending_handoff_tasks 對同一 ticket_id 可能在 is_handoff_stale /
    is_ticket_completed / is_ticket_recently_started 三處重複讀檔。本 helper 提供
    請求生命週期內的快取（dict 由呼叫端建立並傳入），同一 ticket 只解析一次 frontmatter。

    Args:
        cache: 呼叫端持有的快取 dict（key=ticket_id, value=frontmatter dict or None）；
               傳 None 表示不快取（向後相容單一查詢場景）。
        ticket_id: Ticket ID
        project_root: 專案根目錄
        logger: 日誌記錄器

    Returns:
        frontmatter dict；無法定位或解析失敗時為 None。
    """
    if cache is not None and ticket_id in cache:
        return cache[ticket_id]

    ticket_path = find_ticket_file(ticket_id, project_root, logger)
    if not ticket_path:
        result: Optional[dict] = None
    else:
        result = parse_ticket_frontmatter(ticket_path, logger)
        if not result:
            result = None

    if cache is not None:
        cache[ticket_id] = result
    return result


def is_ticket_recently_started(
    project_root: Path,
    ticket_id: str,
    logger,
    frontmatter_cache: Optional[Dict[str, Optional[dict]]] = None,
) -> bool:
    """
    檢查 Ticket 是否在最近 N 分鐘內開始執行（started_at 時間戳）

    用於判斷是否有背景代理人可能正在執行此 Ticket。
    如果 Ticket 的 started_at 在最近 RECENT_TASK_THRESHOLD_MINUTES 內，
    則視為「最近任務」。

    Args:
        project_root: 專案根目錄
        ticket_id: Ticket ID
        logger: 日誌記錄器
        frontmatter_cache: 單次請求內 ticket frontmatter 快取（PC-097 防護）；
            scan loop 應傳入共用 dict 以避免同一 ticket 重複讀檔。
            未傳則維持單次讀檔行為（向後相容單一查詢場景）。

    Returns:
        bool - 是否在最近 N 分鐘內開始執行
    """
    try:
        frontmatter = _load_frontmatter_cached(
            frontmatter_cache, ticket_id, project_root, logger
        )
        if not frontmatter:
            return False

        # 檢查 started_at 時間戳
        started_at_str = frontmatter.get('started_at')
        if not started_at_str:
            return False

        try:
            started_at = datetime.fromisoformat(started_at_str)
            elapsed_minutes = (datetime.now() - started_at).total_seconds() / 60
            # 使用 < 比較（含容差 0.5 分鐘，以防浮點誤差）
            # elapsed_minutes < THRESHOLD 表示「已消耗的分鐘數少於閾值」
            is_recent = elapsed_minutes < RECENT_TASK_THRESHOLD_MINUTES + 0.5

            if is_recent:
                logger.debug(
                    f"Ticket {ticket_id} 在最近 {elapsed_minutes:.1f} 分鐘內開始執行 "
                    f"(閾值: {RECENT_TASK_THRESHOLD_MINUTES} 分鐘)"
                )
            else:
                logger.debug(
                    f"Ticket {ticket_id} 在 {elapsed_minutes:.1f} 分鐘前開始執行 "
                    f"(超過閾值 {RECENT_TASK_THRESHOLD_MINUTES} 分鐘，視為遺留任務)"
                )

            return is_recent
        except ValueError as e:
            logger.warning(f"解析 started_at 時間戳失敗 ({ticket_id}): {e}")
            return False

    except Exception as e:
        logger.warning(f"檢查 Ticket 是否最近開始執行失敗 ({ticket_id}): {e}")
        return False


def is_ticket_completed(project_root: Path, ticket_id: str, logger) -> bool:
    """
    檢查 Ticket 是否處於 terminal 狀態（completed 或 closed）。

    W17-181.2：delegate 至 lib `handoff_utils.is_ticket_terminal`（單一 SSOT），
    消除 ARCH-020 跨進程同構邏輯。函式名保持 is_ticket_completed 以維持
    呼叫端 (project_root, ticket_id, logger) 簽名相容；語義為 terminal
    狀態判定（W17-165 L2-C 既有設計）。

    Args:
        project_root: 專案根目錄
        ticket_id: Ticket ID
        logger: 日誌記錄器（保留參數，異常時記錄）

    Returns:
        bool - 是否處於 terminal 狀態
    """
    try:
        return _lib_is_ticket_terminal(ticket_id, project_root)
    except Exception as e:
        logger.warning(f"檢查 Ticket 完成狀態失敗 ({ticket_id}): {e}")
        return False


def should_preserve_pending_json(record: dict, logger, project_root: Optional[Path] = None) -> bool:
    """
    判斷是否應保留 pending JSON，即使來源 Ticket 已完成。

    W17-095.2 改造：對齊 CLI stale 規則，引用 handoff_utils.is_handoff_stale(record)。
    回傳值定義為「非 stale → 應保留」，與原本的「任務鏈類型 → 保留」相比，
    新增「任務鏈目標已 in_progress/completed → 視為 stale → 不保留（GC）」分支，
    修正 W17-095 根因：原邏輯任務鏈一律 return True，導致目標已啟動的 stale handoff
    反覆誤觸發 Stop hook block。

    record 必要欄位（由 handoff_utils.is_handoff_stale 解析）：
    - direction: "to-sibling[:TARGET_ID]" / "to-parent[:TARGET_ID]" / "to-child[:TARGET_ID]" / 其他
    - from_ticket / ticket_id: 來源 ticket（向後相容）
    - from_status: 可選

    Args:
        record: 從 handoff/pending/*.json 載入的 dict
        logger: 日誌記錄器

    Returns:
        bool - 是否應保留 pending JSON（True=保留，False=GC）
    """
    is_stale, reason = is_handoff_stale(record or {}, project_root)
    direction = (record or {}).get("direction", "") or ""
    if is_stale:
        logger.debug(f"handoff direction='{direction}' 視為 stale（{reason}），不保留")
        return False
    logger.debug(f"handoff direction='{direction}' 非 stale，保留 pending JSON")
    return True


def is_handoff_recently_created(record: dict, logger) -> bool:
    """
    判斷 handoff record 是否在 RECENT_HANDOFF_WINDOW_SECONDS 內建立（W17-118）

    剛建立的 handoff 為「下 session 接手點」，當前 session Stop hook 不應將其
    視為待恢復任務阻塞退出。timestamp 欄位由 /ticket handoff CLI 寫入，格式為
    `datetime.now().isoformat()`。

    Args:
        record: handoff/pending/*.json 載入的 dict
        logger: 日誌記錄器

    Returns:
        bool - 是否在豁免窗口內。timestamp 缺失或解析失敗時保守回傳 False
               （走原路徑，視為非剛建）。
    """
    timestamp_str = (record or {}).get("timestamp")
    if not timestamp_str:
        return False
    try:
        created_at = datetime.fromisoformat(timestamp_str)
        elapsed = (datetime.now() - created_at).total_seconds()
        is_recent = 0 <= elapsed < RECENT_HANDOFF_WINDOW_SECONDS
        if is_recent:
            logger.debug(
                f"handoff timestamp={timestamp_str} 在 {elapsed:.1f}s 前建立 "
                f"(< {RECENT_HANDOFF_WINDOW_SECONDS}s)，視為下 session 接手點"
            )
        return is_recent
    except (ValueError, TypeError) as e:
        logger.warning(f"解析 handoff timestamp 失敗 ({timestamp_str}): {e}")
        return False


def is_subagent_context(input_data: Dict[str, Any], logger) -> bool:
    """判斷 stdin 是否帶 subagent context 標記（W1-044）。

    Why：本 hook 註冊於 Stop event（主線程停止）。CC hook input schema
    （.claude/references/hook-architect-technical-reference.md）中 SubagentStop
    才帶 agent_id / agent_type，Stop 不帶。若 stdin 出現 agent_id / agent_type，
    代表本次觸發實際處於 subagent context（CC 版本路由變更或誤註冊 SubagentStop），
    此時注入 decision:block + 恢復指令會劫持 agent 最終訊息（W1-024 / W1-030 證實）。

    Consequence：subagent context 下不偵測會把 PM 用的恢復指令注入 agent 回傳值，
    覆寫 agent 真實最終訊息（W1-024 實證 basil 回傳值遺失）。

    Action：caller 在 generate_hook_output 開頭呼叫；True 時回 {"suppressOutput": True}
    跳過所有注入。採 documented schema 欄位（agent_id/agent_type）判別，
    不用 transcript 長度等不可靠 heuristic（ticket W1-044 防護要求）。

    與 subagent-stop-dispatch-cleanup-hook.py 的 agent_id 依賴形成一致慣例。
    """
    if not isinstance(input_data, dict):
        return False
    has_marker = bool(input_data.get("agent_id")) or bool(input_data.get("agent_type"))
    if has_marker:
        logger.info(
            "偵測到 subagent context（agent_id=%s, agent_type=%s），跳過 handoff 注入",
            input_data.get("agent_id"),
            input_data.get("agent_type"),
        )
    return has_marker


def has_background_agents(input_data: Dict[str, Any], logger) -> bool:
    """
    判斷 input_data 是否有背景代理人正在執行。

    W3-026.1：用 Claude Code v2.1.145 新欄位 background_tasks 取代
    started_at 30 分鐘閾值推斷。採「弱依賴策略」——只判斷 list 非空，
    不依賴 task object 內部 schema，避免 schema 不確定風險。

    Args:
        input_data: Stop hook stdin JSON
        logger: 日誌記錄器

    Returns:
        bool - 是否有背景代理人執行中。
        欄位不存在 / 非 list / 空 list 皆回 False，
        由 caller fallback 到 started_at 推斷。
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
            f"偵測到背景代理人執行中"
        )
    else:
        logger.debug("input_data.background_tasks 為空 list，無背景代理人")
    return has_active


def scan_pending_handoff_tasks(
    project_root: Path,
    logger,
    input_data: Optional[Dict[str, Any]] = None,
) -> tuple:
    """
    掃描待恢復的 handoff 任務（resumed_at == null 的任務）

    過濾已完成的 Ticket（status: completed），並自動清理 stale JSON。

    新增邏輯：檢查 in_progress Ticket 是否在最近 N 分鐘內開始執行。
    如果是，則視為「可能有代理人正在執行」，回傳到單獨的清單。

    GC 機制：
    - resumed_at 不為 null → 已接手，跳過
    - Ticket 已 completed + direction 不是 to-sibling/to-parent/to-child
      → 刪除 pending JSON（GC）
    - Ticket 已 completed + direction 是任務鏈類型
      → 保留 pending JSON（來源完成是預期狀態）
    - Ticket 未完成且 direction 為 auto 類型（auto 或 auto:TARGET_ID）
      → 收集為「最近任務」（建議性任務，不阻塞退出）
    - Ticket 未完成且非 auto + 在最近 N 分鐘開始執行
      → 收集為「最近任務」（可能有代理人正在執行）
    - Ticket 未完成且非 auto + 超過 N 分鐘未開始
      → 收集為「待恢復任務」（可能被遺忘）

    Args:
        project_root: 專案根目錄
        logger: 日誌記錄器

    Returns:
        tuple - (待恢復任務列表, 最近任務列表)
               各列表元素為 dict，含 ticket_id、title、direction
    """
    pending_dir = project_root / PENDING_DIR_NAME
    pending_tasks = []
    recent_tasks = []

    # PC-097 / single-source-io-collection-rules：單次掃描內 ticket frontmatter
    # 採集快取。is_ticket_recently_started 可能與其他 predicate 重複讀同一 ticket，
    # 透過共用 dict 確保每個 ticket_id 在本次 scan 內只解析一次 frontmatter。
    frontmatter_cache: Dict[str, Optional[dict]] = {}

    if not pending_dir.exists():
        logger.debug(f"pending 目錄不存在: {pending_dir}")
        return pending_tasks, recent_tasks

    # W3-036：has_background_agents 屬 loop-invariant——其唯一輸入 input_data
    # 在整個迴圈中固定不變。提升至迴圈外一次性計算，消除 O(n) 重複呼叫與重複日誌。
    bg_active = has_background_agents(input_data or {}, logger)

    try:
        for file_path in sorted(pending_dir.glob("*.json")):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # 只收集未恢復的任務
                if data.get("resumed_at") is None:
                    ticket_id = data.get("ticket_id", file_path.stem)
                    title = data.get("title", "無標題")
                    direction = data.get("direction", "unknown")

                    # W17-118 Phase 2: 剛建 handoff 視為下 session 接手點，不阻塞
                    # 即使 stale (任務鏈目標已啟動) 也不在當前 session 阻擋退出
                    recently_created = is_handoff_recently_created(data, logger)
                    if recently_created:
                        recent_tasks.append({
                            "ticket_id": ticket_id,
                            "title": title,
                            "direction": direction,
                        })
                        logger.info(
                            f"剛建 handoff (< {RECENT_HANDOFF_WINDOW_SECONDS}s)，"
                            f"視為下 session 接手點不阻塞: {ticket_id}"
                        )
                        continue

                    # W17-118 Phase 1: 計數前先 stale 過濾（與 ticket resume --list 對齊）
                    # stale 條件包含「任務鏈目標已啟動 / 已完成」「來源 ticket 已 completed」
                    # 對齊既有 GC 行為：刪除檔案不計入 pending_tasks
                    is_stale, stale_reason = is_handoff_stale(data, project_root)
                    if is_stale:
                        try:
                            file_path.unlink()
                            logger.info(
                                f"GC: 刪除 stale handoff pending JSON "
                                f"({ticket_id}, direction={direction}, reason={stale_reason})"
                            )
                        except Exception as e:
                            logger.warning(f"刪除 stale handoff JSON 失敗 ({file_path.name}): {e}")
                        continue

                    # 檢查對應 Ticket 是否已完成
                    if is_ticket_completed(project_root, ticket_id, logger):
                        # GC：檢查 direction，判斷是否應保留
                        if should_preserve_pending_json(data, logger, project_root):
                            pending_tasks.append({
                                "ticket_id": ticket_id,
                                "title": title,
                                "direction": direction
                            })
                            logger.debug(
                                f"保留任務鏈類型 handoff 的 pending JSON "
                                f"({ticket_id}, direction={direction})"
                            )
                        else:
                            # 刪除已完成 Ticket 的 stale pending JSON
                            file_path.unlink()
                            logger.info(
                                f"GC: 刪除已完成 Ticket 的 pending JSON "
                                f"({ticket_id}, direction={direction})"
                            )
                    else:
                        # Ticket 未完成，根據 direction 類型判斷分類
                        direction_type = direction.split(":")[0]

                        # 建議性方向類型：提醒但不阻塞退出
                        non_blocking_directions = {"auto", "next-wave"}
                        if direction_type in non_blocking_directions:
                            # 建議性 handoff，不阻塞退出
                            recent_tasks.append({
                                "ticket_id": ticket_id,
                                "title": title,
                                "direction": direction
                            })
                            logger.info(
                                f"建議性 handoff ({direction_type})，不阻塞退出: {ticket_id}"
                            )
                        elif bg_active:
                            # W3-026.1：v2.1.145 background_tasks 直接判斷，
                            # 優先於 started_at 30 分鐘閾值推斷
                            recent_tasks.append({
                                "ticket_id": ticket_id,
                                "title": title,
                                "direction": direction
                            })
                            logger.info(
                                f"background_tasks 非空，視為最近任務: {ticket_id}"
                            )
                        elif is_ticket_recently_started(
                            project_root, ticket_id, logger, frontmatter_cache
                        ):
                            # Fallback：background_tasks 不可用或為空時，
                            # 退化到 started_at 30 分鐘閾值推斷
                            recent_tasks.append({
                                "ticket_id": ticket_id,
                                "title": title,
                                "direction": direction
                            })
                            logger.info(
                                f"找到最近執行的任務（可能有代理人正在處理）: {ticket_id}"
                            )
                        else:
                            pending_tasks.append({
                                "ticket_id": ticket_id,
                                "title": title,
                                "direction": direction
                            })
                            logger.debug(f"找到待恢復任務（可能被遺忘）: {ticket_id}")

            except Exception as e:
                logger.warning(f"讀取 handoff 檔案失敗 ({file_path.name}): {e}")

    except Exception as e:
        logger.error(f"掃描 pending 目錄失敗: {e}")

    return pending_tasks, recent_tasks


def format_pending_tasks_list(pending_tasks: list) -> str:
    """
    格式化待恢復任務清單供 stderr 輸出

    Args:
        pending_tasks: 待恢復任務列表 (dict with ticket_id, title, direction)

    Returns:
        str - 格式化的任務清單
    """
    if not pending_tasks:
        return ""

    message = "\n" + "=" * 70 + "\n"
    message += "[Handoff] 偵測到多個未完成任務，請選擇要恢復的任務：\n"
    message += "=" * 70 + "\n\n"

    for i, task in enumerate(pending_tasks, 1):
        ticket_id = task.get("ticket_id", "unknown")
        title = task.get("title", "無標題")
        direction = task.get("direction", "unknown")

        message += f"{i}. [{ticket_id}] {title}\n"
        message += f"   方向: {direction}\n"
        message += f"   恢復命令: /ticket resume {ticket_id}\n\n"

    message += "=" * 70 + "\n"
    message += "請執行上述恢復命令之一以選擇要恢復的任務。\n"
    message += "=" * 70 + "\n"

    return message


def generate_hook_output(
    logger, input_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    生成 Hook 輸出

    邏輯:
    1. 若此 session 已觸發過，直接跳過（防重複）
    2. 讀取 session 狀態，若有 locked_ticket_id，提示恢復
    3. 掃描 pending 目錄，找未恢復任務（含 GC 清理已完成 Ticket）
       並區分「待恢復任務」和「最近任務」
    4. 處理結果：
       - 有待恢復任務 → 阻止並提示恢復
       - 只有最近任務（無待恢復） → 輸出 INFO 提示，不阻止（允許對話終止）
       - 無任務 → 靜默通過
    5. 建立 stop flag

    新增邏輯（w.r.t. IMP-041）：
    - 區分「待恢復任務」（超過 30 分鐘未執行，可能被遺忘）
      和「最近任務」（最近 30 分鐘內開始，可能有代理人執行）
    - 只阻止待恢復任務，最近任務只輸出 INFO 提示

    注意: pending JSON 只由 /ticket handoff 明確建立，
    Stop hook 不主動建立（避免為不相關的 in_progress Ticket 產生假陽性）。

    Returns:
        dict - Hook 輸出 JSON
    """
    try:
        # Step 0: subagent context 偵測（W1-044）。subagent stop 時跳過所有注入，
        # 避免恢復指令劫持 agent 最終訊息（W1-024 / W1-030）。
        if is_subagent_context(input_data or {}, logger):
            return {"suppressOutput": True}

        # Step 1: 防重複觸發
        if has_been_triggered_this_session(logger):
            logger.info("此 session 已觸發過 Stop hook，跳過")
            return {"suppressOutput": True}

        project_root = get_project_root()
        logger.debug(f"專案根目錄: {project_root}")

        # Step 2: 讀取 session 狀態
        session_state = read_session_state(logger)
        pending_tasks = None
        recent_tasks = []

        if session_state and session_state.get("locked_ticket_id"):
            ticket_id = session_state["locked_ticket_id"]
            logger.info(f"從 session 狀態找到鎖定任務: {ticket_id}")
            pending_tasks = [{"ticket_id": ticket_id, "title": "", "direction": ""}]
        else:
            # Step 3: 掃描 pending 目錄（含 GC 清理已完成 Ticket 的 stale JSON）
            # 並區分待恢復任務和最近任務
            pending_tasks, recent_tasks = scan_pending_handoff_tasks(
                project_root, logger, input_data=input_data
            )
            if pending_tasks:
                logger.info(f"掃描 pending 目錄找到 {len(pending_tasks)} 個待恢復任務")
            if recent_tasks:
                logger.info(f"掃描 pending 目錄找到 {len(recent_tasks)} 個最近任務（可能有代理人執行中）")

        # Step 4: 決策
        # 4a: 有待恢復任務（遺留的任務，需要阻止）
        if pending_tasks:
            logger.info(f"偵測到 {len(pending_tasks)} 個待恢復任務，阻止對話終止")
            mark_triggered_this_session(logger)

            # 單任務時行為不變（向後相容）
            if len(pending_tasks) == 1:
                task = pending_tasks[0]
                ticket_id = task.get("ticket_id")
                logger.info(f"單任務，提示恢復: {ticket_id}")
                # reason 會被注入給主線程 PM（恢復指令屬 PM 專屬動作）。
                # Stop event 無 agent_id，程式層偵測（Step 0 的 W1-044 路徑）
                # 涵蓋不到的環境由前綴 + AGENT_PRELOAD 忽略規則補位（PC-V1-004）。
                return {
                    "decision": "block",
                    "reason": (
                        f"{PM_ONLY_PREFIX}[Handoff] 偵測到未完成的 handoff 任務：{ticket_id}\n"
                        f"請執行以下步驟：\n"
                        f"1. 檢查本 session 中是否有待辦工作尚未建立對應 Ticket（若有，先建立）\n"
                        f"2. 確認所有變更已 commit\n"
                        f"3. 通知用戶可以執行 /clear，然後 /ticket resume {ticket_id}\n"
                        f"請勿自動執行 resume，必須等待用戶手動操作。"
                    )
                }
            else:
                # 多任務時：列出清單到 stderr，exit 2 阻止停止
                tasks_list = format_pending_tasks_list(pending_tasks)
                logger.warning(f"多任務清單:\n{tasks_list}")

                # 輸出到 stderr（exit 2）
                print(tasks_list, file=sys.stderr)

                # 同單任務路徑：reason 屬 PM 專屬注入，加受眾標記前綴（PC-V1-004）。
                return {
                    "decision": "block",
                    "reason": PM_ONLY_PREFIX + "多個待恢復任務，請選擇要恢復的任務"
                }
        # 4b: 只有最近任務，無待恢復任務（可能有代理人在執行）
        elif recent_tasks:
            logger.info(
                f"偵測到 {len(recent_tasks)} 個最近任務（最近 {RECENT_TASK_THRESHOLD_MINUTES} 分鐘內開始），"
                f"推測有背景代理人可能正在執行，允許對話終止並輸出提示"
            )

            # 輸出提示訊息到 stderr（INFO 級別，不阻止）
            recent_info = (
                f"\n{'=' * 70}\n"
                f"[Handoff] 偵測到最近的執行任務（可能有背景代理人正在處理）：\n"
                f"{'=' * 70}\n\n"
            )
            for task in recent_tasks:
                ticket_id = task.get("ticket_id", "unknown")
                title = task.get("title", "無標題")
                direction = task.get("direction", "unknown")
                recent_info += f"- [{ticket_id}] {title}\n"
                recent_info += f"  方向: {direction}\n"
            recent_info += f"\n{'=' * 70}\n"
            recent_info += f"若代理人仍在執行，請勿強制中止。\n"
            recent_info += f"若確認任務已完成，可執行 /ticket resume {recent_tasks[0].get('ticket_id')} 回顧結果。\n"
            recent_info += f"{'=' * 70}\n"

            logger.info(f"最近任務提示:\n{recent_info}")
            print(recent_info, file=sys.stderr)

            # 允許對話終止（suppressOutput），但已輸出提示到 stderr
            return {"suppressOutput": True}
        # 4c: 無任何任務
        else:
            logger.info("無未完成任務，允許對話終止")
            return {"suppressOutput": True}

    except Exception as e:
        logger.critical(f"Stop hook 執行錯誤: {e}", exc_info=True)
        return {"suppressOutput": True}


def main() -> int:
    """
    主入口點

    Returns:
        int - Exit code (0 = 成功)
    """
    logger = setup_hook_logging("handoff-auto-resume-stop")

    try:
        logger.info("Handoff 自動恢復 Stop Hook 啟動")

        # W3-026.1: 讀取 stdin 取得 input_data.background_tasks（v2.1.145 新欄位）
        # 解析失敗 / tty / 欄位不存在皆 fallback 到 started_at 推斷
        input_data: Dict[str, Any] = {}
        if not sys.stdin.isatty():
            try:
                input_data = json.load(sys.stdin)
                if not isinstance(input_data, dict):
                    logger.warning(
                        f"stdin JSON 非 dict 型別（{type(input_data).__name__}），"
                        f"fallback 到 started_at 推斷"
                    )
                    input_data = {}
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"解析 stdin 失敗，fallback 到 started_at 推斷: {e}")
                input_data = {}

        hook_output = generate_hook_output(logger, input_data=input_data)
        print(json.dumps(hook_output, ensure_ascii=False, indent=2))

        logger.info("Hook 執行完成")
        return EXIT_SUCCESS

    except Exception as e:
        logger.critical(f"Hook 主程序執行錯誤: {e}", exc_info=True)
        print(json.dumps({"suppressOutput": True}, ensure_ascii=False, indent=2))
        return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "handoff-auto-resume-stop"))
