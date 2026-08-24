"""
pm-registry.json 共用模組（multi-PM 協調層 registry 基礎設施，schema v2）

跨 worktree 單一實例的 multi-PM session registry，落於 `git rev-parse
--git-common-dir` 解析出的主 .git/ 目錄下，供同一 repo 上多個並行 PM
session（各自獨立 worktree/branch）互相看見彼此的存活狀態（heartbeat）
與認領範圍（tickets/files，寫入端見本模組 `recompute_lease()`，唯一
寫入路徑；呼叫端見 `ticket_system.lib.lease` 的 claim/complete/release/
reclaim 生命週期事件）。

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
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from .git_utils import run_git_command
except ImportError:
    # 本模組偶被以 bare top-level import 載入（如
    # `sys.path.insert(0, ".claude/lib")` 後直接 `import pm_registry`，
    # 非透過 `lib.` package context），此時無 package 可供相對匯入解析。
    # 降級為絕對匯入（呼叫端已將 .claude/lib 加入 sys.path 的情境下
    # git_utils 為同層可直接匯入的模組）。
    from git_utils import run_git_command  # type: ignore[no-redef]

REGISTRY_FILENAME = "pm-registry.json"
LOCK_FILENAME = "pm-registry.lock"
SCHEMA_VERSION = 2

# read_registry 降級旗標鍵：缺檔/空白/損毀/schema 不合四種降級分支回傳的
# 空骨架皆帶此鍵，供呼叫端區分「registry 讀取失敗」與「registry 有效但目前
# 無任何 session」——後者不會帶此鍵。非 schema 正式欄位，不寫回
# write_registry（呼叫端僅供顯示層判定使用，不應持久化）。
DEGRADED_READ_KEY = "_degraded"

# SessionStart source 值：resume 觸發 merge（繼承既有 lease），其餘一律
# 視為新生 session 觸發 reset（startup/clear/未知值，契約 v2 D4 增補 1）
RESUME_SOURCE = "resume"

# UserPromptSubmit heartbeat 更新的最小間隔（契約指定，免高頻寫入）。
# 與下方 STALE_THRESHOLD_MINUTES 為耦合參數對：debounce 必須遠小於
# stale 門檻（現行 60 秒 << 30 分鐘，約 30 倍餘裕），否則高頻互動場景
# 下心跳更新間隔可能逼近甚至超過 STALE 判定窗口，使活躍 session 被誤判
# 為 STALE。調整任一值時需同時檢視此餘裕比例是否仍合理，不可獨立調整。
HEARTBEAT_DEBOUNCE_SECONDS = 60

# Registry Schema 契約：heartbeat 逾此分鐘數視為 STALE（lease reclaim 沿用
# 同一 TTL）。FRESH/STALE 判準唯一來源，見 `is_fresh()`；
# ticket_system/commands/track_sessions.py 已委派呼叫 `is_fresh()`，不再
# 自帶獨立常數（曾有獨立同值常數，已統一，見該檔模組 docstring）。
STALE_THRESHOLD_MINUTES = 30

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


def get_registry_dir(cwd: Optional[str] = None, logger=None) -> Optional[Path]:
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

    解析失敗需可觀測（規則 4）：`logger` 提供時記一筆 warning——非 git
    環境為預期情境（不需 warning 等級），但 timeout/git 命令不存在等
    非預期失敗可能代表 worktree registry 分裂故障（該 worktree 從此讀
    不到共用 registry），warning 等級便於與「純粹非 git 環境」的常態
    區分。

    改走 `git_utils.run_git_command`（帶 `--no-optional-locks`）：本函式
    原直接呼叫 `subprocess.run`，每次 heartbeat/claim 觸發的
    `git rev-parse` 會與並行 PM session 的其他 git 操作競爭
    `.git/index.lock`（IMP-046 同型風險）；`run_git_command` 已封裝
    `--no-optional-locks` 避免此競爭，且為專案內同類 git rev-parse
    實作中最新、最嚴謹的版本，本函式改為呼叫它而非各自維護一份。
    """
    success, output = run_git_command(
        ["rev-parse", "--git-common-dir"], cwd=cwd, timeout=GIT_COMMON_DIR_TIMEOUT
    )
    if not success:
        if logger:
            logger.warning(
                "git rev-parse --git-common-dir 解析失敗（cwd=%s）: %s；"
                "本次 registry 操作將跳過，若非預期的非 git 環境請檢查 worktree 狀態",
                cwd, output,
            )
        return None

    if not output:
        return None

    common_dir = Path(output)
    if not common_dir.is_absolute():
        base = Path(cwd) if cwd else Path.cwd()
        common_dir = (base / common_dir).resolve()
    return common_dir


def get_registry_paths(
    cwd: Optional[str] = None, logger=None
) -> Optional[Tuple[Path, Path]]:
    """回傳 (registry_file, lock_file) 路徑 tuple；非 git 環境回傳 None。"""
    registry_dir = get_registry_dir(cwd=cwd, logger=logger)
    if registry_dir is None:
        return None
    return registry_dir / REGISTRY_FILENAME, registry_dir / LOCK_FILENAME


# ============================================================================
# 讀寫原語
# ============================================================================


def _empty_registry() -> Dict:
    return {"schema_version": SCHEMA_VERSION, "sessions": {}}


def _degraded_registry() -> Dict:
    """`read_registry` 四個降級分支專用：空骨架 + DEGRADED_READ_KEY 旗標，
    與「有效但目前無任何 session」的一般空 registry（僅 `_empty_registry()`
    本身，不帶旗標）區分。"""
    registry = _empty_registry()
    registry[DEGRADED_READ_KEY] = True
    return registry


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
    """讀取 registry 檔。缺檔或損毀時重建空結構並雙通道通知（不阻擋），
    回傳的空結構帶 `DEGRADED_READ_KEY` 旗標，與「有效但目前無任何 session」
    的一般空 registry 區分（呼叫端須自行判斷是否要把降級讀取等同「無法
    判定」處理，本模組不預設呼叫端語意）；偵測到舊版 schema（v1）時
    graceful 正規化，不視為損毀。
    """
    if not registry_file.exists():
        return _degraded_registry()
    try:
        content = registry_file.read_text(encoding="utf-8")
        if not content.strip():
            return _degraded_registry()
        data = json.loads(content)
        if not isinstance(data, dict) or "sessions" not in data:
            raise ValueError("registry 結構缺少 sessions 欄位")
        if not isinstance(data.get("sessions"), dict):
            raise ValueError("sessions 欄位非 dict 型別")
        data = _normalize_legacy_schema(data, logger=logger)
        # 自我修復：成功讀取的合法檔案不應帶 DEGRADED_READ_KEY。此鍵僅
        # 應由本函式的降級分支即時附加、且不得流向磁碟（write_registry
        # 已剝除）；若仍在磁碟內容中出現，代表檔案由本次修正前的舊碼
        # 誤寫入（旗標曾為 in-band、隨 read-modify-write 落盤），屬歷史
        # 污染而非本次讀取真的失敗，讀取當下原地剝除即完成修復，不需
        # 額外遷移步驟。
        data.pop(DEGRADED_READ_KEY, None)
        return data
    except (json.JSONDecodeError, ValueError, OSError) as e:
        message = "[pm_registry] registry 損毀或格式錯誤，重建空 registry ({}): {}".format(
            registry_file, e
        )
        sys.stderr.write(message + "\n")
        if logger:
            logger.warning(message)
        return _degraded_registry()


def write_registry(registry_file: Path, data: Dict, logger=None) -> None:
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

    fsync 失敗不阻斷寫入（os.replace 的原子替換保證仍成立，fsync 只是
    加強持久性——斷電情境下少一層保障，非功能性錯誤），但需可觀測（規則
    4）：`logger` 提供時記一筆 debug（非 warning，因不影響本次寫入正確
    性，只是持久性保障降級，過度告警會製造噪音）。
    """
    registry_file.parent.mkdir(parents=True, exist_ok=True)
    # DEGRADED_READ_KEY 是 read_registry 降級分支的 in-band 顯示層旗標，
    # 非 schema 正式欄位，不得持久化（否則首次啟動等正常讀寫回路徑會把
    # 旗標固化進磁碟，此後每次讀取皆誤判為降級，見本模組 docstring 契約
    # 說明與該常數定義處註解）。write_registry 是四個 session 生命週期
    # 函式（register_session/update_heartbeat/release_session/
    # recompute_lease）共用的唯一寫入路徑，於此單點剝除即可涵蓋全部
    # 呼叫端，不需逐一在呼叫端各自處理。不就地 mutate 呼叫端傳入的
    # dict（呼叫端在同一鎖範圍內可能於寫入後續用該物件）。
    if DEGRADED_READ_KEY in data:
        data = {k: v for k, v in data.items() if k != DEGRADED_READ_KEY}
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
            except OSError as e:
                if logger:
                    logger.debug("registry fsync 失敗（不影響本次寫入，僅持久性保障降級）: %s", e)
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

        write_registry(registry_file, data, logger=logger)


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
            write_registry(registry_file, data, logger=logger)
            return True

        elapsed = _elapsed_seconds_since(entry.get("heartbeat_ts", ""), now_dt)
        if elapsed is not None and elapsed < HEARTBEAT_DEBOUNCE_SECONDS:
            return False

        _merge_entry(entry, name, project, now_dt.isoformat())
        write_registry(registry_file, data, logger=logger)
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
            write_registry(registry_file, data, logger=logger)
            return True
        return False


def is_fresh(heartbeat_ts: Optional[str], now: Optional[datetime] = None) -> bool:
    """判定 heartbeat 是否仍在 STALE_THRESHOLD_MINUTES 內（lease Phase 3 起
    的正式 FRESH/STALE 判準，本模組為 Registry Schema 契約權威來源）。

    heartbeat 缺失或無法解析一律視為 STALE（回傳 False），不可靜默呈現
    「新鮮」假象（可觀測性規則 4）。ticket_system 的 track_sessions.py 已
    改為呼叫本函式（Phase 4 審查修正 4），為 FRESH/STALE 判準唯一來源，
    不再自帶獨立常數。
    """
    now = now or datetime.now(timezone.utc)
    elapsed = _elapsed_seconds_since(heartbeat_ts or "", now)
    if elapsed is None:
        return False
    return elapsed <= STALE_THRESHOLD_MINUTES * 60


def recompute_lease(
    registry_file: Path,
    lock_file: Path,
    session_id: str,
    *,
    add_ticket_id: Optional[str] = None,
    remove_ticket_id: Optional[str] = None,
    files_loader,
    logger=None,
) -> bool:
    """claim/complete/release/reclaim 共用的唯一 lease 寫入路徑。

    `files` 欄位不是獨立累積狀態，是 `tickets` 的推導物化值：每次呼叫皆以
    「調整後 tickets 清單目前的 where.files 聯集」整組重算覆蓋（replace），
    不做增量 append/merge。理由：append 語意下票面 where.files 若改窄後
    重跑 claim，registry.files 會殘留舊路徑，使 track_conflicts 的
    registry/票面交叉比對產生假陰性。

    tickets 依 `add_ticket_id`（claim，若已在清單中不重複加入）或
    `remove_ticket_id`（complete/release/reclaim，若在清單中則移除）調整；
    兩者互斥語意下只需其一，皆為 None 時等同純粹重算現有 tickets 的 files
    （不改動 tickets 本身）。

    `files_loader` 由呼叫端注入（`Callable[[str], List[str]]`，輸入
    ticket_id、輸出其 where.files）——本模組不認識 ticket md 結構，刻意
    不耦合（同本模組 docstring 對 dispatch_tracker 的既有取捨）。在鎖內
    呼叫以確保 tickets 快照與 files 重算之間一致，無 TOCTOU 視窗。

    鎖內 IO 效能量化門檻（獨立量測分析定案，方法：scratchpad 假
    registry + 真實票面體量 626 檔 median 9.4KB / max 27.1KB + 真實
    `files_loader`，冷/暖快取 N=1/5/10/30/60 曲線 trials=20）：鎖內時長
    對持票數線性，本機斜率約 1.05ms/票、審查基線保守值 2.6ms/票（機器
    差異範圍）；門檻定為單次 p95 < 100ms（感知預算慣用值），以保守斜率
    換算持票安全上限約 38 票；實際工作流單 session 持票數通常 < 10，
    距門檻 3 倍以上餘裕，現狀不構成需修復的效能問題。三個緩解選項（
    where.files 快取 / 持票硬上限 / 鎖外預載鎖內驗證）評估後均不採用：
    快取的一致性成本（防票面改窄後 registry 殘留舊路徑的假陰性風險，見
    上段）換取的收益（省 1-3ms/票）為負淨值；硬上限會約束合法批量工作
    流卻無對應效能收益；鎖外預載鎖內驗證不消除 TOCTOU 視窗。若未來單
    session 持票數逼近 38 票門檻，應以本段量測方法重新評估（可查證判
    準，非無 trigger 延後）。

    entry 不存在時回傳 False（理論上不應發生——SessionStart 已註冊該
    session；仍防禦以符合規則 4 可觀測性，呼叫端負責 stderr 告知並跳過）。

    Returns:
        bool: 是否成功寫入（entry 存在且已更新）
    """
    with _registry_lock(lock_file):
        data = read_registry(registry_file, logger=logger)
        sessions = data.setdefault("sessions", {})
        entry = sessions.get(session_id)
        if entry is None:
            return False

        tickets = list(entry.get("tickets") or [])
        if add_ticket_id and add_ticket_id not in tickets:
            tickets.append(add_ticket_id)
        if remove_ticket_id and remove_ticket_id in tickets:
            tickets = [t for t in tickets if t != remove_ticket_id]

        files: List[str] = []
        for t in tickets:
            for f in files_loader(t):
                if f not in files:
                    files.append(f)

        entry["tickets"] = tickets
        entry["files"] = files
        write_registry(registry_file, data, logger=logger)
        return True


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
