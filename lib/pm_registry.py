"""
pm-registry.json 共用模組（multi-PM 協調層 registry 基礎設施，schema v2）

跨 worktree 單一實例的 multi-PM session registry，落於 `git rev-parse
--git-common-dir` 解析出的主 .git/ 目錄下，供同一 repo 上多個並行 PM
session（各自獨立 worktree/branch）互相看見彼此的存活狀態（heartbeat）
與認領範圍（tickets/files，本模組保留欄位，寫入邏輯留待後續階段）。

Registry Schema 契約 v2（單一來源，本模組不得自行變更欄位/結構；發現
契約不可行時回報 PM，不擅自變更）：

    {
      "schema_version": 2,
      "sessions": {
        "<session_id>": {
          "name": "<session 名稱，如 worktree 目錄基名>",
          "project": "<git toplevel 絕對路徑>",
          "registered_at": "<ISO8601 UTC>",
          "heartbeat_ts": "<ISO8601 UTC>",
          "tickets": [],
          "files": []
        }
      }
    }

v2 相對 v1 的變更（重現實驗與三視角審查後定案，五項決策）：

- 釋放時機：由 Stop hook 移除 entry，改為 SessionEnd graceful release（+
  30 分 TTL 兜底異常終止，TTL 判定留待 Phase 3）；handoff 顯式釋放路徑
  保留不變。Stop 每回合觸發非 session 終結，舊機制使 debounce 淪為
  dead code、Phase 2 lease 欄位每回合被清空。
- heartbeat 事件涵蓋面：Stop 職責由「釋放」替換為「心跳更新」（忽略
  `stop_hook_active=true` 的自激回合），與 UserPromptSubmit 並存——
  teammate 訊息驅動的回合不觸發 UserPromptSubmit，僅留單一事件源會使
  代理協作密集的活躍 session 被誤判 STALE（實測 55 分假陰性案例）。
  兩事件缺一不可，不得以「簡化」為由刪減任一方。
- 欄位：移除 `parent_session_id`（恆等 session_id 的冗餘欄位，nested
  spawn 語意分化時再加）——schema_version 因此升為 2。
- 非 git 環境：跳過註冊（不再 fallback 寫入 `<cwd>/.git` 或
  `lib.hook_base.get_project_root()/.git`）——讀端永不讀取的檔案是寫給
  空氣的容錯。
- upsert 語意：register_session 依 SessionStart 的 `source` 欄位分流。
  `source == "resume"` → merge（僅更新 heartbeat_ts/name/project，保留
  tickets/files/registered_at，繼承既有 lease）；其餘（startup/clear/
  未知值）→ 重置為全新 entry（新生 session 不繼承舊 lease，防止
  SessionEnd 漏觸發 + 同 session_id 重開時繼承 zombie lease）。
  update_heartbeat 對既有 entry 一律 merge（同語意，無 source 可辨）。

鎖與寫入模式（已於獨立實驗驗證：兩獨立 process 各 300 輪 flock 保護的
read-modify-write，共 600 輪無損）：同目錄 `pm-registry.lock`，
`fcntl.flock(LOCK_EX)`（Windows: msvcrt.locking）護住整段
read-modify-write（保護寫入端彼此的 read-modify-write 互斥）；寫入本體
採「寫暫存檔 + os.replace 原子替換」（保護無鎖讀端不撞見半寫檔案，即
torn write）。兩者保護的問題面不同、缺一不可：flock 防寫入端互相覆蓋
遺失更新，os.replace 防讀端讀到寫入中途的不完整內容。

本模組獨立實作跨平台鎖 primitive，不 import lib.dispatch_tracker 的私有
函式——dispatch-active.json 與 pm-registry.json 是兩個語意獨立的狀態檔
（前者追蹤派發、後者追蹤 PM session 存活），刻意不耦合。

損毀/缺檔處置：JSON 解析失敗或缺檔即重建空 registry + stderr 通知
（Hook 失敗必須可見原則），不阻擋呼叫端工作。舊版（schema_version=1，
含 parent_session_id 欄位）檔案可正常讀取——混版部署期間（部分 session
仍跑舊碼）容忍其寫入 v1 形狀的資料，讀取時寬鬆接受不視為損毀，下次由
本模組寫入時自然正規化為 v2 形狀（見 `read_registry` 的相容處理）。
"""

import json
import os
import subprocess
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple

REGISTRY_FILENAME = "pm-registry.json"
LOCK_FILENAME = "pm-registry.lock"
SCHEMA_VERSION = 2

# SessionStart source 值：resume 觸發 merge（繼承既有 lease），其餘一律
# 視為新生 session 觸發 reset（startup/clear/未知值，契約 v2 D4 增補 1）
RESUME_SOURCE = "resume"

# UserPromptSubmit heartbeat 更新的最小間隔（契約指定，免高頻寫入）
HEARTBEAT_DEBOUNCE_SECONDS = 60

# git rev-parse 執行逾時（秒）
GIT_COMMON_DIR_TIMEOUT = 5


# ============================================================================
# 跨平台檔案鎖 primitive
# ============================================================================

if sys.platform == "win32":
    import msvcrt

    def _lock_fd(fd) -> None:
        """Windows 檔案鎖：msvcrt.locking 需檔案有內容才能鎖。"""
        try:
            fd.seek(0, os.SEEK_END)
            if fd.tell() == 0:
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


@contextmanager
def _registry_lock(lock_file: Path):
    """排他鎖保護 read-modify-write 週期，防止並行寫入資料遺失。"""
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    fd = open(lock_file, "a+")
    try:
        _lock_fd(fd)
        yield
    finally:
        _unlock_fd(fd)
        fd.close()


# ============================================================================
# 路徑解析
# ============================================================================


def get_registry_dir(cwd: Optional[str] = None) -> Optional[Path]:
    """解析 registry 落點目錄（主 .git/，跨 worktree 單一實例，契約指定）。

    `git rev-parse --git-common-dir`：worktree 內執行時解析回主 repo 的
    .git/，同一 repo 的所有 worktree 因而共見同一份 registry（已實證此
    共見性）。

    解析失敗（非 git 環境、逾時）時回傳 None，不再 fallback 寫入
    `<cwd>/.git` 或 `lib.hook_base.get_project_root()/.git`（契約 v2 D3：
    這兩層 fallback 寫的檔案讀端從未讀取——`get_registry_dir` 本身即讀寫
    共用的路徑解析函式，非 git 環境下沒有任何讀端會查詢一個臨時決定的
    路徑，寫入純屬寫給空氣）。呼叫端收到 None 應跳過本次 registry 操作，
    不阻擋工作（見各 hook 的 stderr 一次性提示）。
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=GIT_COMMON_DIR_TIMEOUT,
        )
        if result.returncode == 0 and result.stdout.strip():
            common_dir = Path(result.stdout.strip())
            if not common_dir.is_absolute():
                base = Path(cwd) if cwd else Path.cwd()
                common_dir = (base / common_dir).resolve()
            return common_dir
    except (subprocess.TimeoutExpired, OSError):
        pass

    return None


def get_registry_paths(cwd: Optional[str] = None) -> Optional[Tuple[Path, Path]]:
    """回傳 (registry_file, lock_file) 路徑 tuple；非 git 環境回傳 None。"""
    registry_dir = get_registry_dir(cwd=cwd)
    if registry_dir is None:
        return None
    return registry_dir / REGISTRY_FILENAME, registry_dir / LOCK_FILENAME


# ============================================================================
# 讀寫原語
# ============================================================================


def _empty_registry() -> Dict:
    return {"schema_version": SCHEMA_VERSION, "sessions": {}}


def _normalize_legacy_schema(data: Dict, logger=None) -> Dict:
    """v1 檔案（schema_version=1，session entry 含 parent_session_id）的
    graceful 降級讀取：不視為損毀，正規化為 v2 形狀後回傳。

    混版部署期間（舊碼仍在跑）可能寫入 v1 形狀的資料；新碼讀到時原地
    剝除已廢棄的 `parent_session_id` 欄位、schema_version 更新為 2，
    不觸發「重建空 registry」（那會刪光其他 session 的合法 entry，
    blast radius 過大）。正規化後的結果不立即寫回，待下次任何一個
    session 生命週期函式（register_session/update_heartbeat/
    release_session）呼叫 write_registry 時自然落地。
    """
    if data.get("schema_version") == SCHEMA_VERSION:
        return data

    for entry in data.get("sessions", {}).values():
        if isinstance(entry, dict):
            entry.pop("parent_session_id", None)
    data["schema_version"] = SCHEMA_VERSION

    message = "[pm_registry] 偵測到舊版 registry（schema_version != {}），已正規化為當前 schema".format(
        SCHEMA_VERSION
    )
    if logger:
        logger.info(message)
    return data


def read_registry(registry_file: Path, logger=None) -> Dict:
    """讀取 registry 檔。缺檔或損毀時重建空結構並雙通道通知（不阻擋）；
    偵測到舊版 schema（v1）時 graceful 正規化，不視為損毀。
    """
    if not registry_file.exists():
        return _empty_registry()
    try:
        content = registry_file.read_text(encoding="utf-8")
        if not content.strip():
            return _empty_registry()
        data = json.loads(content)
        if not isinstance(data, dict) or "sessions" not in data:
            raise ValueError("registry 結構缺少 sessions 欄位")
        if not isinstance(data.get("sessions"), dict):
            raise ValueError("sessions 欄位非 dict 型別")
        return _normalize_legacy_schema(data, logger=logger)
    except (json.JSONDecodeError, ValueError, OSError) as e:
        message = "[pm_registry] registry 損毀或格式錯誤，重建空 registry ({}): {}".format(
            registry_file, e
        )
        sys.stderr.write(message + "\n")
        if logger:
            logger.warning(message)
        return _empty_registry()


def write_registry(registry_file: Path, data: Dict) -> None:
    """寫入 registry 檔（呼叫端須已持有 `_registry_lock`）。

    寫暫存檔 + os.replace 原子替換：讀端（`ticket track sessions` 等無鎖
    查詢）任何時刻看到的檔案內容只會是完整的舊版或完整的新版，不會讀到
    半寫的中間狀態（torn write）。`os.replace` 在同一檔案系統內為原子
    操作（POSIX rename(2) / Windows MoveFileEx，Python stdlib 已跨平台
    封裝），取代原先的 in-place seek(0)+truncate()+write（該模式僅保護
    寫入端彼此的 read-modify-write 互斥，未保護讀端不撞見半寫檔案）。

    暫存檔建立失敗或 replace 失敗時清理殘留暫存檔並重新拋出，呼叫端
    （register_session / update_heartbeat / release_session）已在
    `_registry_lock` 保護下呼叫，異常會沿呼叫鏈往上冒出，由 hook 主流程
    的 try/except 決定是否記錄且不阻擋（見各 hook 的 dual-channel 通知）。
    """
    registry_file.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    tmp_path = registry_file.with_name(
        registry_file.name + ".tmp." + uuid.uuid4().hex[:8]
    )
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        os.replace(tmp_path, registry_file)
    except OSError:
        if tmp_path.exists():
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_entry(name: str, project: str, now: str) -> Dict:
    return {
        "name": name,
        "project": project,
        "registered_at": now,
        "heartbeat_ts": now,
        "tickets": [],
        "files": [],
    }


def _merge_entry(entry: Dict, name: str, project: str, now: str) -> None:
    """就地合併：僅更新 heartbeat_ts/name/project，保留 tickets/files/
    registered_at（契約 v2 D4：既有 lease 不被生命週期事件覆蓋）。
    """
    entry["heartbeat_ts"] = now
    entry["name"] = name
    entry["project"] = project


# ============================================================================
# 公開 API：session 生命週期
# ============================================================================


def register_session(
    registry_file: Path,
    lock_file: Path,
    session_id: str,
    name: str,
    project: str,
    source: str = "",
    logger=None,
) -> None:
    """SessionStart 註冊：依 `source` 分流 merge 或 reset（契約 v2 D4 增補 1）。

    `source == "resume"` 且既有同 session_id entry 存在時 merge（僅更新
    heartbeat_ts/name/project，保留 tickets/files/registered_at，繼承
    既有 lease——顯式恢復語意）；其餘情況（startup/clear/未知值，或
    entry 不存在）一律 reset 為全新 entry（新生 session 不繼承舊 lease，
    防止 SessionEnd 漏觸發 + 同 session_id 重開時繼承 zombie lease 並靠
    新 heartbeat 續命使 TTL 永不回收）。
    """
    with _registry_lock(lock_file):
        data = read_registry(registry_file, logger=logger)
        sessions = data.setdefault("sessions", {})
        now = _now_iso()
        entry = sessions.get(session_id)

        if source == RESUME_SOURCE and entry is not None:
            _merge_entry(entry, name, project, now)
        else:
            sessions[session_id] = _new_entry(name, project, now)

        write_registry(registry_file, data)


def update_heartbeat(
    registry_file: Path,
    lock_file: Path,
    session_id: str,
    name: str,
    project: str,
    logger=None,
) -> bool:
    """UserPromptSubmit / Stop 心跳更新（debounce >= 60s，避免高頻寫入）。

    雙事件源（契約 v2 D1b）：UserPromptSubmit 蓋回合開頭、Stop 蓋回合
    結尾，長回合（teammate 訊息驅動、無 UserPromptSubmit 觸發）期間仍有
    心跳覆蓋；兩者共用本函式與同一 debounce 視窗，行為完全一致。

    既有 entry 一律 merge（僅更新 heartbeat_ts/name/project，保留
    tickets/files/registered_at——契約 v2 D4，防止心跳把 Phase 2 lease
    寫入覆蓋掉）。entry 缺失時（registry 曾損毀重建、或 SessionStart
    註冊失敗）自我修復：以本次可得資訊補建全新 entry，避免永久缺席直到
    下次 SessionStart。

    Returns:
        bool: 是否實際寫入（debounce 命中時回傳 False，供呼叫端記日誌用）
    """
    with _registry_lock(lock_file):
        data = read_registry(registry_file, logger=logger)
        sessions = data.setdefault("sessions", {})
        now_dt = datetime.now(timezone.utc)
        entry = sessions.get(session_id)

        if entry is None:
            sessions[session_id] = _new_entry(name, project, now_dt.isoformat())
            write_registry(registry_file, data)
            return True

        elapsed = _elapsed_seconds_since(entry.get("heartbeat_ts", ""), now_dt)
        if elapsed is not None and elapsed < HEARTBEAT_DEBOUNCE_SECONDS:
            return False

        _merge_entry(entry, name, project, now_dt.isoformat())
        write_registry(registry_file, data)
        return True


def release_session(
    registry_file: Path,
    lock_file: Path,
    session_id: str,
    logger=None,
) -> bool:
    """SessionEnd / handoff 時移除自身 entry（graceful release，契約 v2 D1）。

    Stop 不再呼叫本函式——Stop 每回合觸發非 session 終結，v1 掛在 Stop
    的釋放邏輯已整支移除（含隨之消失的 background_tasks 守衛）。
    SessionEnd 涵蓋 /clear、正常結束等 graceful 路徑；kill/crash 不觸發
    SessionEnd，由 30 分 TTL 兜底（stale 判定留待後續階段）。

    Returns:
        bool: entry 是否存在並被移除
    """
    with _registry_lock(lock_file):
        data = read_registry(registry_file, logger=logger)
        sessions = data.setdefault("sessions", {})
        if session_id in sessions:
            del sessions[session_id]
            write_registry(registry_file, data)
            return True
        return False


def _elapsed_seconds_since(ts_str: str, now_dt: datetime) -> Optional[float]:
    """計算 ts_str 距 now_dt 的秒數；解析失敗回傳 None（呼叫端視為需要更新）。"""
    if not ts_str:
        return None
    try:
        ts_dt = datetime.fromisoformat(ts_str)
        if ts_dt.tzinfo is None:
            ts_dt = ts_dt.replace(tzinfo=timezone.utc)
        return (now_dt - ts_dt).total_seconds()
    except (ValueError, TypeError):
        return None
