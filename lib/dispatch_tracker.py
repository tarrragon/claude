"""
Active Dispatch Tracker 共用模組

追蹤背景代理人的派發狀態，防止 PM 重複執行同一 Ticket。

狀態檔案：.claude/dispatch-active.json

公開 API：
- record_dispatch: 記錄新派發
- clear_dispatch: 清理已完成派發（description 比對，非 SubagentStop 路徑）
- mark_turn_ended_by_handle: 依 agent_handle 錨定比對標記回合結束（named
  派發的精準路徑，先於 mark_turn_ended_by_id 呼叫）
- mark_turn_ended_by_id: 標記 agent_id 對應 entry 的回合結束時刻（不刪除，
  未命名派發的既有路徑）
- mark_oldest_active_null_agent_id_entry_turn_ended: 上者的 FIFO fallback
- get_active_dispatches: 取得所有活躍派發
- is_file_under_dispatch: 檢查檔案是否在派發中
- cleanup_expired: 清理超時記錄
- detect_orphan_branches: 偵測 orphan worktree 分支

turn_ended_at 欄位：
  SubagentStop 事件的觸發前提原被假設為「代理人真正停止才觸發」，實測
  不成立——代理人回合結束後轉入 idle 仍存活、仍列於代理人清單、仍可接受
  訊息並繼續工作。`clear_dispatch_by_id` / `clear_oldest_null_agent_id_
  entry` 兩個刪除式函式據此假設在 SubagentStop 觸發時清空記錄，會使唯一
  追蹤存活狀態的資料源在代理人尚未終止時即消失。

  `mark_turn_ended_by_id` / `mark_oldest_active_null_agent_id_entry_turn_
  ended` 取代刪除為標記：entry 保留，僅寫入 `turn_ended_at`（ISO8601，
  初始為 None）記錄「最後一次回合結束」時刻。consumer 讀取
  `get_active_dispatches` 時，entry 存在本身仍代表「該代理人未被確認
  終止」（保守存活語意，供 bare-commit-guard-hook.py 等並行安全防護使
  用）；`turn_ended_at` 是否為 None 則代表「當下是否正在執行某個回合」
  （供需要「真正忙碌中」語意的判斷使用，如本模組使用端的 [WAIT] 廣播）。

  目前無可靠的「代理人已真正終止」訊號（SubagentStop 不是、無 SessionEnd
  等價的 subagent 版本）。刻意不發明時間閾值式的終止判斷（如「idle 超過
  N 分鐘視為終止」）——此類判斷未經驗證，可能與 SubagentStop 前提失準
  同樣的方式錯誤。保留至 `cleanup_expired`（既有 TTL 機制）回收，為目前
  唯一的既定回收路徑；`clear_dispatch_by_id` / `clear_oldest_null_agent_id_
  entry` 兩個舊有刪除式函式保留於本模組（供未來若出現可靠終止訊號時使
  用），但不應再由 SubagentStop 呼叫。

  cleanup_expired 的 TTL 依 turn_ended_at 是否已設定分層（詳見該常數
  `TURN_ENDED_MAX_AGE_HOURS` 定義處的完整依據）：`turn_ended_at` 為 None
  （回合仍在進行中）維持呼叫端傳入的短 TTL（預設 1 小時，起算基準
  `dispatched_at`）不變；`turn_ended_at` 已設定者改用遠長的 TTL、起算
  基準改為 `turn_ended_at` 本身——該 entry 已結束當前回合、不再服務
  「檔案佔用中」的並行安全目的，短 TTL 的理由不再適用，且
  session-registry-start-hook.py 的 SessionStart 掃描依賴這批 entry 存活
  夠久才能被回報；若沿用舊有 1 小時 TTL，長時間閒置（實測樣本上界 17
  小時）的殘留代理人記錄會在掃描讀到之前就被刪除。

agent_handle 欄位（identifier namespace 修復）：
  `mark_turn_ended_by_id` 依賴 `tool_response.agentId` 記錄的 `agent_id`
  做精準比對，實測該欄位 68% 派發缺席，且即使有值也是不同識別碼命名
  空間（未命名派發的純 hex，如 `ac6c923bb6253aa3a`），與 SubagentStop
  自己回報、CC runtime 保證存在的 `agent_id`（named 派發格式為
  `a<handle>-<hex>`，如 `afix-abc123-73070ca5c1d3f849`）對不上。named
  派發（帶 `name` 參數）在平行情境下（同批次派發多個代理人）必然產生
  多筆 `agent_id is None` 的候選，FIFO fallback 依設計於候選 > 1 時
  停用，故 `turn_ended_at` 在此主要情境下永遠不會被設定。

  `agent_handle` 欄位改在 dispatch 當下（`PostToolUse` 觸發時）同步
  擷取派發用的 `name` 參數（可定址短 handle，非 persona），不依賴任何
  非同步 `tool_response` 回應；`mark_turn_ended_by_handle` 以錨定 regex
  `^a<escaped-handle>-[0-9a-f]+$` 比對 SubagentStop 回報的 `agent_id`，
  取代對 named 派發已不可靠的舊路徑。未命名派發（無 `agent_handle`）
  不受影響，繼續走 `mark_turn_ended_by_id` 舊路徑。
"""

import json
import os
import re
import subprocess
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .git_utils import get_worktree_list

STATE_FILE_RELATIVE = ".claude/dispatch-active.json"
LOCK_FILE_RELATIVE = ".claude/dispatch-active.lock"

# turn_ended_at 已設定的 entry 的 TTL（小時），見模組 docstring
# 「turn_ended_at 欄位」段完整脈絡。
#
# 數值依據：實測殘留代理人樣本的 idle 時長上界為 17 小時，24 小時在此之上
# 留約 7 小時餘裕（涵蓋「PM 一個工作日未巡查」的情境），同時仍為有限值
# 而非無上限——除本機制外，目前沒有任何一條路徑會刪除已標記 turn_ended_at
# 的 entry（SubagentStop 已改標記不刪除；`clear_dispatch` 雖存在但未被
# 任何呼叫端實際呼叫，見本模組函式 docstring），若不設上限，
# dispatch-active.json 會單調成長，而它被多個防護 hook
# （active-dispatch-tracker-hook.py 的 PostToolUse、
# session-start-sync-exclusion-check-hook.py 的 SessionStart）逐次讀取，
# 成長不設界會拉高持續讀取成本。24 小時的有限視窗讓成長速率有上界；
# session-registry-start-hook.py 新增的 SessionStart 掃描本就會在這個
# 視窗內主動回報候選，本 TTL 只作為掃描未被查看時的最終回收 fallback，
# 不是偵測手段本身——偵測手段是該掃描，不是本 TTL 到期。
TURN_ENDED_MAX_AGE_HOURS = 24

# 跨平台 file lock：Unix 走 fcntl.flock，Windows 走 msvcrt.locking。
# 目標：_state_lock 的 read-modify-write 互斥保護可在 Windows 執行，
# 不再以 `import fcntl` 直接失敗 (ModuleNotFoundError)。
if sys.platform == "win32":
    import msvcrt

    def _lock_fd(fd) -> None:
        """Windows 檔案鎖：msvcrt.locking 需檔案有內容才能鎖。"""
        try:
            fd.write(" ")
            fd.flush()
            fd.seek(0)
            msvcrt.locking(fd.fileno(), msvcrt.LK_LOCK, 1)
        except OSError:
            # 鎖失敗不阻斷（Hook 非關鍵路徑），容忍極罕見 race
            pass

    def _unlock_fd(fd) -> None:
        try:
            fd.seek(0)
            msvcrt.locking(fd.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
else:
    import fcntl

    def _lock_fd(fd) -> None:
        fcntl.flock(fd, fcntl.LOCK_EX)

    def _unlock_fd(fd) -> None:
        fcntl.flock(fd, fcntl.LOCK_UN)

# 記憶體快取：避免同一 Hook 執行中重複讀取 JSON 檔案
# 使用檔案 mtime 判斷是否需要重新讀取
_state_cache: Dict = {"data": None, "mtime": 0.0}


def reset_cache() -> None:
    """重設記憶體快取（供測試使用）。"""
    _state_cache["data"] = None
    _state_cache["mtime"] = 0.0


def get_state_file_path(project_root: Path) -> Path:
    """取得狀態檔路徑"""
    return project_root / STATE_FILE_RELATIVE


@contextmanager
def _state_lock(project_root: Path):
    """排他鎖保護 read-modify-write 週期，防止並行寫入資料遺失。"""
    lock_file = project_root / LOCK_FILE_RELATIVE
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    fd = lock_file.open("w")
    try:
        _lock_fd(fd)
        yield
    finally:
        _unlock_fd(fd)
        fd.close()


def _read_state(project_root: Path) -> Dict:
    """讀取狀態檔。檔案不存在或格式錯誤時回傳空結構。

    使用檔案 mtime 驅動的記憶體快取：檔案未變更時直接回傳快取，
    避免同一 session 中多次 Edit/Write 觸發重複 JSON 解析。
    """
    state_file = get_state_file_path(project_root)
    if not state_file.exists():
        return {"dispatches": []}
    try:
        current_mtime = state_file.stat().st_mtime
        if _state_cache["data"] is not None and _state_cache["mtime"] == current_mtime:
            return _state_cache["data"]

        content = state_file.read_text(encoding="utf-8")
        data = json.loads(content)
        if not isinstance(data, dict) or "dispatches" not in data:
            return {"dispatches": []}

        _state_cache["data"] = data
        _state_cache["mtime"] = current_mtime
        return data
    except (json.JSONDecodeError, OSError) as e:
        print(f"[dispatch_tracker] _read_state: 狀態檔讀取失敗 ({state_file}): {e}", file=sys.stderr)
        return {"dispatches": []}


def _write_state(project_root: Path, state: Dict) -> None:
    """寫入狀態檔。自動建立父目錄。寫入後使快取失效。

    寫暫存檔 + os.replace 原子替換：無鎖讀端（is_file_under_dispatch 等
    查詢路徑）任何時刻看到的檔案內容只會是完整的舊版或完整的新版，不會
    讀到半寫的中間狀態（torn write）。取代原先的 write_text 直寫（在同一
    檔案系統內非原子，寫入中途崩潰或讀端時間點不巧會讀到截斷/空內容）。

    fsync 失敗不阻斷寫入（os.replace 的原子替換保證仍成立，fsync 只是
    加強持久性——斷電情境下少一層保障，非功能性錯誤），但需可觀測（規則
    4）：寫 stderr 一筆提示，比照本模組 `_read_state` 既有的 stderr 通知
    慣例（本模組無 logger 參數貫穿全公開 API，不新增此依賴面）。
    """
    state_file = get_state_file_path(project_root)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(state, indent=2, ensure_ascii=False) + "\n"
    tmp_path = state_file.with_name(
        state_file.name + ".tmp." + uuid.uuid4().hex[:8]
    )
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError as e:
                print(
                    f"[dispatch_tracker] _write_state: fsync 失敗（不影響本次寫入，"
                    f"僅持久性保障降級） ({tmp_path}): {e}",
                    file=sys.stderr,
                )
        os.replace(tmp_path, state_file)
    except OSError:
        if tmp_path.exists():
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise

    # 寫入後使快取失效，下次 _read_state 會重新讀取
    _state_cache["data"] = None
    _state_cache["mtime"] = 0.0


def record_dispatch(
    project_root: Path,
    agent_description: str,
    tool_use_id: str = "",
    ticket_id: str = "",
    files: Optional[List[str]] = None,
    branch_name: str = "",
    agent_id: Optional[str] = None,
    session_id: str = "",
    name: str = "",
    agent_handle: str = "",
) -> None:
    """記錄一個新的派發。寫入 dispatch-active.json。

    Args:
        project_root: 專案根目錄
        agent_description: 代理人描述（用於比對清理）
        tool_use_id: CC runtime tool_use_id（用於 PostToolUse 補 agent_id）
        ticket_id: 關聯的 Ticket ID
        files: 代理人處理的檔案清單
        branch_name: worktree 分支名稱（用於 orphan 偵測精確比對）
        agent_id: 代理人 ID（可選，通常由 PostToolUse/SubagentStop 補寫）。
            實測 `tool_response.agentId` 68% 派發缺席，且即使有值也與
            SubagentStop 自己回報的 `agent_id` 屬不同識別碼命名空間（見
            `mark_turn_ended_by_handle` docstring）——本欄位對 named
            派發的精準比對已不可靠，named 派發請改用 `agent_handle`。
        session_id: 派發者（PM）的 CC session_id（multi-PM 協調層，
            供 pm-registry 交叉比對「哪個 PM session 派發了哪些工作」）
        name: named agent 的身份識別（如 `subagent_type`，例
            "thyme-python-developer"）。可合法為空——非綁定特定代理人身份
            的派發（如未指定 subagent_type 的通用 Task 呼叫）無此值。
            殘留代理人排查時，此欄位補足 agent-dispatch.jsonl 缺少的
            named-agent 身份資訊。**這是 persona 識別碼，不是可定址的
            派發 handle**——與 `agent_handle` 是兩個不同命名空間，不可
            混用（見 `agent_handle` 說明）。
        agent_handle: 派發時的可定址短 handle（來自 Agent 工具呼叫的
            `name` 參數，與上方 `name`/`subagent_type` 這個 persona
            欄位是兩個不同概念——一次派發可能同時有 handle 與 persona
            兩個值，例如 handle="fix-abc123"、
            persona="thyme-python-developer"）。CC runtime 會把此
            handle 編入 SubagentStop 回報的 `agent_id`，格式為
            `a<handle>-<hex>`（如 `afix-abc123-73070ca5c1d3f849`），
            故此欄位可在 dispatch 當下（`PostToolUse` 觸發時）同步取得，
            不依賴任何非同步 `tool_response` 回應，用於
            `mark_turn_ended_by_handle` 的精準比對。可合法為空——未命名
            派發（無 `name` 參數）無此值，此時 SubagentStop 比對維持
            沿用 `mark_turn_ended_by_id` 的舊路徑。

    Note:
        v1 曾另有 parent_session_id 欄位（恆等 session_id 的冗餘值），
        registry 契約 v2 審查判定其資訊量為零，已移除；nested spawn
        語意分化時再視需要新增，不沿用舊欄位名稱與語意。

        ticket_id / files 可合法為空：呼叫端（active-dispatch-tracker-
        hook.py）在無法從派發 prompt/description 解析出 ticket_id 時
        （例如非綁定特定 ticket 的 code-review 型派發），會以空字串／空
        清單寫入本函式，這是預期行為而非資料錯誤，本模組刻意不在寫入端
        擋下此類記錄——dispatch_count／orphan 偵測等用途仍需要這筆記錄
        存在。下游若需要「已知檔案範圍」語意（如判斷 staged 內容是否與
        某派發宣告範圍不相交），應在該消費端自行過濾空 files 記錄，不應
        依賴本模組事先過濾（見 bare-commit-guard-hook.py 的
        `_staged_scope_is_safe_for_bare_commit`）。
    """
    with _state_lock(project_root):
        state = _read_state(project_root)
        entry = {
            "agent_description": agent_description,
            "tool_use_id": tool_use_id,
            "agent_id": agent_id,
            "ticket_id": ticket_id,
            "files": files or [],
            "branch_name": branch_name,
            "dispatched_at": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "name": name,
            "agent_handle": agent_handle,
            "turn_ended_at": None,
        }
        state["dispatches"].append(entry)
        _write_state(project_root, state)


def clear_dispatch(project_root: Path, agent_description: str) -> bool:
    """清理已完成的派發。依 agent_description 比對。

    Args:
        project_root: 專案根目錄
        agent_description: 要清理的代理人描述

    Returns:
        是否成功找到並清理記錄
    """
    with _state_lock(project_root):
        state = _read_state(project_root)
        original_count = len(state["dispatches"])
        state["dispatches"] = [
            d for d in state["dispatches"]
            if d.get("agent_description") != agent_description
        ]
        if len(state["dispatches"]) < original_count:
            _write_state(project_root, state)
            return True
        return False


def update_dispatch_agent_id(
    project_root: Path, tool_use_id: str, agent_id: str
) -> bool:
    """依 tool_use_id 補寫 agent_id（PostToolUse 觸發時呼叫）。

    Returns:
        是否找到並更新記錄
    """
    with _state_lock(project_root):
        state = _read_state(project_root)
        for entry in state["dispatches"]:
            if entry.get("tool_use_id") == tool_use_id:
                old_id = entry.get("agent_id")
                if old_id is not None and old_id != agent_id:
                    print(
                        f"[dispatch_tracker] update_dispatch_agent_id: "
                        f"覆寫 agent_id (tool_use_id={tool_use_id}, "
                        f"old={old_id}, new={agent_id})",
                        file=sys.stderr,
                    )
                entry["agent_id"] = agent_id
                _write_state(project_root, state)
                return True
        return False


def clear_dispatch_by_id(project_root: Path, agent_id: str) -> bool:
    """依 agent_id 精準清理 dispatch 記錄（刪除式）。

    警告：不應由 SubagentStop 呼叫。SubagentStop 只保證代理人本次回合
    結束，不保證代理人已真正終止（見模組 docstring「turn_ended_at 欄位」
    段）。SubagentStop 路徑請改用 `mark_turn_ended_by_id`（標記不刪除）。
    本函式保留供未來出現可靠終止訊號時使用。

    Returns:
        是否成功找到並清理記錄
    """
    with _state_lock(project_root):
        state = _read_state(project_root)
        original_count = len(state["dispatches"])
        state["dispatches"] = [
            d for d in state["dispatches"]
            if d.get("agent_id") != agent_id
        ]
        removed = original_count - len(state["dispatches"])
        if removed > 1:
            print(
                f"[dispatch_tracker] clear_dispatch_by_id: "
                f"agent_id={agent_id} 重複匹配 {removed} 筆",
                file=sys.stderr,
            )
        if removed > 0:
            _write_state(project_root, state)
            return True
        return False


def mark_turn_ended_by_handle(project_root: Path, agent_id: str) -> bool:
    """依 agent_handle 錨定比對標記回合結束（named 派發的精準路徑，
    SubagentStop 觸發時應先呼叫本函式，失敗才 fallback 到
    `mark_turn_ended_by_id`）。

    比對邏輯：對每筆 `agent_handle` 非空的 entry，建構錨定 regex
    `^a<escaped-handle>-[0-9a-f]+$` 比對傳入的 `agent_id`（SubagentStop
    回報，CC runtime 保證存在）。採錨定 regex 而非單純
    `agent_id.startswith("a" + handle + "-")`，理由：

    - 右端錨定 `$` + `[0-9a-f]+` 限定 hex 字元集到字串結尾，排除
      「handle 是另一個 handle 的 hyphen-token 前綴」的邊界情況（例如
      handle="fix-abc" 與另一 handle="fix-abc-2"，若用前綴比對，
      `startswith("afix-abc-")` 對 `afix-abc-2-<hex>` 會誤判為匹配；
      錨定 regex 因為 `$` 要求整個剩餘部分只能是 hex，`abc-2-<hex>`
      含非 hex 字元 `-` 與可能的非 hex 字母，不會通過）
    - `re.escape(handle)` 防禦 handle 本身含 regex 特殊字元

    空字串 `agent_handle` 明確排除於比對迴圈之外（不嘗試對空 handle
    建 pattern），避免退化成 `^a-[0-9a-f]+$` 誤配未命名派發的純 hex
    `agent_id`（該格式無 `a` 前綴，理論上不會誤配，但顯式排除更穩固，
    不依賴這個觀察維持不變）。

    多筆匹配時的處理比照 `mark_turn_ended_by_id` 對 `agent_id` 重複
    匹配的既定慣例（stderr 提示 + 全部標記，不是拒絕標記）——理由是
    維持一致性優於為這個低機率情境（兩個 entry 使用完全相同的
    `agent_handle`）發明新語意，且「全部標記」對回合結束偵測目的的
    錯誤代價低於「都不標記」（後者會讓兩筆都繼續恆為 None，重現本函式
    要修的問題）。

    Returns:
        bool: 是否找到並標記至少一筆記錄（無 `agent_handle` 可比對，或
            比對無結果時回傳 False，呼叫端應 fallback 到
            `mark_turn_ended_by_id`）
    """
    with _state_lock(project_root):
        state = _read_state(project_root)
        matched = []
        for entry in state["dispatches"]:
            handle = entry.get("agent_handle")
            if not handle:
                continue
            pattern = "^a" + re.escape(handle) + "-[0-9a-f]+$"
            if re.match(pattern, agent_id):
                matched.append(entry)

        if not matched:
            return False

        if len(matched) > 1:
            print(
                f"[dispatch_tracker] mark_turn_ended_by_handle: "
                f"agent_id={agent_id} 比對到 {len(matched)} 筆 agent_handle "
                f"重複匹配",
                file=sys.stderr,
            )

        now = datetime.now(timezone.utc).isoformat()
        for entry in matched:
            entry["turn_ended_at"] = now
        _write_state(project_root, state)
        return True


def mark_turn_ended_by_id(project_root: Path, agent_id: str) -> bool:
    """依 agent_id 標記 dispatch 記錄的回合結束時刻。

    未命名派發（無 `agent_handle`）的比對路徑——SubagentStop 觸發時應
    先呼叫 `mark_turn_ended_by_handle`，該函式回傳 False（無 handle 可
    比對）才呼叫本函式。named 派發請改用 `mark_turn_ended_by_handle`，
    本函式依賴的 `tool_response.agentId` 對 named 派發已證實不可靠（見
    模組 docstring「agent_handle 欄位」段）。

    不刪除 entry：entry 保留，寫入 `turn_ended_at`（ISO8601）記錄本次
    SubagentStop 事件發生時刻。重複呼叫（同一代理人多回合對話）會覆寫
    為最新一次回合結束時刻，屬預期行為（冪等更新，非累加）。

    Returns:
        是否找到並標記記錄
    """
    with _state_lock(project_root):
        state = _read_state(project_root)
        matched = [
            d for d in state["dispatches"]
            if d.get("agent_id") == agent_id
        ]
        if len(matched) > 1:
            print(
                f"[dispatch_tracker] mark_turn_ended_by_id: "
                f"agent_id={agent_id} 重複匹配 {len(matched)} 筆",
                file=sys.stderr,
            )
        if not matched:
            return False
        now = datetime.now(timezone.utc).isoformat()
        for entry in matched:
            entry["turn_ended_at"] = now
        _write_state(project_root, state)
        return True


def clear_dispatch_by_description_fallback(
    project_root: Path, description: str
) -> bool:
    """依 description 清理最早的一筆 dispatch 記錄（fallback 路徑）。

    Returns:
        是否成功找到並清理記錄
    """
    with _state_lock(project_root):
        state = _read_state(project_root)
        candidates = [
            d for d in state["dispatches"]
            if d.get("agent_description") == description
        ]
        if not candidates:
            return False
        oldest = min(candidates, key=lambda d: d.get("dispatched_at", ""))
        state["dispatches"].remove(oldest)
        _write_state(project_root, state)
        return True


def clear_oldest_null_agent_id_entry(project_root: Path) -> bool:
    """清理 agent_id 為 null 且 dispatched_at 最早的一筆（刪除式 FIFO fallback）。

    警告：不應由 SubagentStop 呼叫（理由同 `clear_dispatch_by_id`）。
    SubagentStop 路徑請改用 `mark_oldest_active_null_agent_id_entry_turn_
    ended`（標記不刪除）。本函式保留供未來出現可靠終止訊號時使用。

    Returns:
        是否成功找到並清理記錄
    """
    with _state_lock(project_root):
        state = _read_state(project_root)
        candidates = [
            d for d in state["dispatches"]
            if d.get("agent_id") is None
        ]
        if not candidates:
            return False
        oldest = min(candidates, key=lambda d: d.get("dispatched_at", ""))
        state["dispatches"].remove(oldest)
        _write_state(project_root, state)
        return True


def mark_oldest_active_null_agent_id_entry_turn_ended(project_root: Path) -> bool:
    """標記 agent_id 為 null 且尚未標記過回合結束的最早一筆（FIFO fallback）。

    SubagentStop 觸發時 agent_id 精準匹配失敗後使用。因 SubagentStop
    input 無 description 欄位，改用 FIFO 語義。

    候選限定「尚未標記」（`turn_ended_at` 為 None）：entry 保留不刪除後，
    已標記過回合結束的 null-agent_id entry 會持續留在陣列中，若候選集合
    不排除它們，日後每次 SubagentStop 都會重新把它們計入候選數，使呼叫端
    「候選數 > 1 時停用 FIFO」防護（避免誤標仍在執行中的記錄）永久失效。

    Returns:
        是否找到並標記記錄
    """
    with _state_lock(project_root):
        state = _read_state(project_root)
        candidates = [
            d for d in state["dispatches"]
            if d.get("agent_id") is None and d.get("turn_ended_at") is None
        ]
        if not candidates:
            return False
        oldest = min(candidates, key=lambda d: d.get("dispatched_at", ""))
        oldest["turn_ended_at"] = datetime.now(timezone.utc).isoformat()
        _write_state(project_root, state)
        return True


def get_active_dispatches(project_root: Path) -> List[Dict]:
    """取得所有活躍的派發記錄。

    Returns:
        派發記錄清單
    """
    state = _read_state(project_root)
    return state["dispatches"]


def is_file_under_dispatch(project_root: Path, filepath: str) -> Optional[Dict]:
    """檢查檔案是否正在被派發的代理人處理。

    Args:
        project_root: 專案根目錄
        filepath: 要檢查的檔案路徑

    Returns:
        匹配的 dispatch 記錄，或 None
    """
    dispatches = get_active_dispatches(project_root)
    for dispatch in dispatches:
        if filepath in dispatch.get("files", []):
            return dispatch
    return None


def _is_dispatch_expired(dispatch: Dict, now: datetime, max_age_hours: int) -> bool:
    """判斷單一派發記錄是否已超時。解析失敗視為超時。

    `turn_ended_at` 已設定時改以該欄位為起算基準並套用
    `TURN_ENDED_MAX_AGE_HOURS`（見模組層常數定義），取代呼叫端傳入的
    `max_age_hours`——該 entry 已不再服務並行安全目的，短 TTL 的理由不再
    適用。`turn_ended_at` 為 None（回合仍在進行中）維持原邏輯：以
    `dispatched_at` 起算、套用呼叫端傳入的 `max_age_hours`。
    """
    turn_ended_at_str = dispatch.get("turn_ended_at")
    if turn_ended_at_str:
        anchor_field = "turn_ended_at"
        anchor_str = turn_ended_at_str
        effective_max_age_hours = TURN_ENDED_MAX_AGE_HOURS
    else:
        anchor_field = "dispatched_at"
        anchor_str = dispatch.get("dispatched_at", "")
        effective_max_age_hours = max_age_hours
    try:
        anchor = datetime.fromisoformat(anchor_str)
        if anchor.tzinfo is None:
            anchor = anchor.replace(tzinfo=timezone.utc)
        return (now - anchor).total_seconds() / 3600 > effective_max_age_hours
    except (ValueError, TypeError) as e:
        print(
            f"[dispatch_tracker] cleanup_expired: 時間解析失敗 "
            f"({anchor_field}='{anchor_str}'): {e}",
            file=sys.stderr,
        )
        return True


def cleanup_expired(project_root: Path, max_age_hours: int = 1) -> int:
    """清理超時的派發記錄（防止遺留）。

    Args:
        project_root: 專案根目錄
        max_age_hours: 最大存活時數

    Returns:
        清理的記錄數量
    """
    with _state_lock(project_root):
        state = _read_state(project_root)
        now = datetime.now(timezone.utc)

        kept = [d for d in state["dispatches"] if not _is_dispatch_expired(d, now, max_age_hours)]
        removed_count = len(state["dispatches"]) - len(kept)

        if removed_count > 0:
            state["dispatches"] = kept
            _write_state(project_root, state)

        return removed_count


def _parse_agent_worktree_branches(project_root: Path) -> List[str]:
    """從 git worktree list 解析 agent- 前綴的分支名稱。

    改用 lib.git_utils.get_worktree_list（0.2.1-W3-290）；exclude_main 旗標
    對本函式無意義（agent- 前綴過濾已隱含排除 main/master），故不傳
    exclude_main，僅以 branch 前綴判斷等價於原實作。

    Returns:
        agent- 前綴的 worktree 分支名稱清單，失敗時回傳空清單
    """
    try:
        worktrees = get_worktree_list(cwd=str(project_root))
    except Exception as e:
        print(f"[dispatch_tracker] _parse_agent_worktree_branches: git worktree list 失敗: {e}", file=sys.stderr)
        return []

    return [
        wt["branch"]
        for wt in worktrees
        if wt.get("branch", "").startswith("agent-")
    ]


def detect_orphan_branches(project_root: Path) -> List[str]:
    """偵測 orphan worktree 分支（有 worktree 但無對應 dispatch 記錄）。

    Returns:
        orphan 分支名稱清單
    """
    worktree_branches = _parse_agent_worktree_branches(project_root)
    if not worktree_branches:
        return []

    dispatch_branch_names = {
        d.get("branch_name", "") for d in get_active_dispatches(project_root)
        if d.get("branch_name")
    }

    # 精確比對（子字串比對不可靠）
    return [b for b in worktree_branches if b not in dispatch_branch_names]
