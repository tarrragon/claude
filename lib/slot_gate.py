#!/usr/bin/env python3
"""
本機名額閘門（2026-10-14）

heavy 命令（全套件測試、編譯）以 flock 取得全機名額後才執行，由 run-with-timeout.py 呼叫。

- 名額由持有程序的 flock 綁定其存活期間；正常結束、逾時、被 SIGKILL 皆由核心釋放。
  鎖檔描述符預設不可繼承，子程序殘存不佔用名額。
- 鎖目錄：CLAUDE_SLOT_LOCK_DIR；未設則為 ~/.cache/claude-slot。刻意不用 TMPDIR／XDG_RUNTIME_DIR：
  它們是環境變數，不同 session 的值可能不同，名額會變成每份值一份；固定的共用 /tmp 路徑則可被其他
  本機使用者搶先建立或換成 symlink。
- 目錄以 0o700 建立，並以 lstat 驗證：必須是目錄（非 symlink）、屬於目前使用者、群組與其他人不可寫入
  （mode & 0o077 == 0）；任一不符即略過閘門。鎖檔與 holder 暫存檔以 O_NOFOLLOW 開啟。
- 以 CLAUDE_SLOT_LOCK_DIR 覆寫時，其父目錄須為本人擁有且不可被他人寫入：驗證只涵蓋最末層目錄，
  父目錄若可被他人改名或替換，驗證通過後的路徑仍可能被換掉。
- 排隊依到達順序（先到先得）：進入等待時於鎖目錄建立排隊檔 queue-{序號12位}-{pid}.json（O_EXCL，序號取現有最大值加一，
  撞名重試；內容含 pid、命令、到達時間），只有序號最小且 pid 存活的排隊者可嘗試 flock。排隊檔在取得、放棄、
  逾時、訊號中斷時由本程序刪除；pid 已不存在的排隊檔（被 SIGKILL 或他人清除）由後續排隊者清除，不阻塞後方。
  等待提示含順位與前方筆數。
- 閘門的任何讀寫失敗只對 stderr 寫一行（開頭 run-with-timeout:）後略過閘門，不阻擋命令。
- 孤兒提示：heavy 命令取得名額後、啟動命令前，以子程序執行 orphan-test-procs.py（不帶 --kill，只列出）
  查詢本專案孤兒；有則於 stderr 印出數量與清理指令，無則不輸出；查詢失敗或逾時（ORPHAN_QUERY_TIMEOUT_SECONDS）
  只寫一行 stderr，不阻擋命令。light 命令不經過閘門，故不查詢。CLAUDE_ORPHAN_SCRIPT、
  CLAUDE_ORPHAN_QUERY_TIMEOUT 可覆寫查詢腳本與逾時（測試用）。
- 持有者的子程序不重複取得名額：持有者在持有期間把自己的 pid 放入環境變數 HELD_ENV（export_hold），
  子程序內的 run-with-timeout 經 is_heavy_command 判定為免排隊。標記僅在「該 pid 仍存在且名額確實全被占用」
  時有效（held_by_ancestor），殘留的過期標記不會讓 heavy 命令繞過閘門。
- 預估耗時（2026-10-15）：排隊檔與 holder 檔都記預估持有秒數 estimate（呼叫端傳入 estimate_seconds，
  未傳用 default_estimate_seconds(command)；舊格式無此欄位的檔案同樣以命令預設值計）。佇列總等待不設上限、
  不因預估過長而拒絕（飽和時被拒者不保留位置會飢餓）：進場即輸出一行順位、前方筆數、前方第一筆與預估等待，
  呼叫端自行決定是否中止。順位只計排隊檔，不含持有者（持有者之後第 N 位）；持有者換人是先到者取得名額後
  後方遞補一位，不是插隊。等待上限 CLAUDE_SLOT_WAIT_LIMIT 只用來偵測持有者卡住：持有者已持有秒數超出自身
  estimate 超過上限即以 SLOT_WAIT_EXIT_CODE 結束。例外：環境帶持有標記（HELD_ENV，持有者的子程序）時
  上限仍是總等待上限，兩邊版本不一致時快速失敗。
- 排頭停住偵測：排隊者每輪輪詢更新自己排隊檔的 mtime 作為心跳；前方存活排隊者的心跳超過
  SLOT_STALL_SECONDS 即視同離場（順位不計、不刪其排隊檔，並寫一行 stderr）。恢復後第一輪更新心跳即重新計入，
  與新排頭同時 flock 由核心互斥。
- CLAUDE_SLOT_WAIT_LIMIT、CLAUDE_SLOT_NOTICE_INTERVAL、CLAUDE_SLOT_STALL_SECONDS（秒）可覆寫等待上限、提示間隔與停住門檻（測試用）。
"""
import fcntl
import contextlib
import json
import os
import re
import stat
import subprocess
import sys
import time
from typing import Callable, List, Optional, Tuple

SLOT_WAIT_EXIT_CODE = 125
# 同時執行的 heavy 命令數（全機）；2026-10-14 swap 耗盡事件後定為 1
SLOT_COUNT = 1
# 持有者超出自身預估的容忍秒數：超過代表持有者異常久，與其無限掛起不如回報讓呼叫端決策
SLOT_WAIT_LIMIT_SECONDS = 3600.0
SLOT_NOTICE_INTERVAL_SECONDS = 30.0
SLOT_POLL_INTERVAL = 0.1
# 排頭心跳過期秒數：排隊者每輪輪詢（約 SLOT_POLL_INTERVAL）更新自己排隊檔的 mtime；
# 存活但超過此秒數未更新（SIGSTOP、整個 session 暫停）即判定停住，後方略過。
# 取 30 秒：約為輪詢間隔的 300 倍，高負載下的排程延遲不會誤判；停住時後方最多多等這麼久。
SLOT_STALL_SECONDS = 30.0
# 孤兒查詢的逾時：查詢只是提示，慢於此值寧可放棄也不拖慢 heavy 命令啟動
ORPHAN_QUERY_TIMEOUT_SECONDS = 5.0
ORPHAN_CLEANUP_COMMAND = "python3 .claude/scripts/orphan-test-procs.py --kill"
# 與 orphan-test-procs.py 的機器可讀契約行（SUMMARY_PREFIX）一致；人讀行的字樣不屬契約，不解析
_ORPHAN_SUMMARY_RE = re.compile(
    r"^ORPHAN_SUMMARY matched=(\d+) skipped=(\d+) suspects=(\d+) registered=(\d+)$", re.MULTILINE)
WAITED_REPORT_THRESHOLD = SLOT_POLL_INTERVAL
# 無歷史資料時的預估持有秒數（保守取偏高值，寧可早拒絕也不讓排隊者空等滿上限）。
# 依據 2026-10-15 實測：hooks 套件 160-230 秒、ticket skill 520-580 秒、動到 lib 的合併約 915 秒。
DEFAULT_ESTIMATE_SECONDS = 600.0
_DEFAULT_ESTIMATE_BY_KEYWORD = (
    ("merge-gate", 900.0),  # 合併閘門通常由 merge_gate 傳入日誌中位數；此為無法估算時的後備
    ("flutter", 600.0),
    ("pytest", 300.0),
)


def default_estimate_seconds(command: List[str]) -> float:
    """依命令內容給預設預估持有秒數；無關鍵字符合時回 DEFAULT_ESTIMATE_SECONDS。"""
    joined = " ".join(command)
    for keyword, seconds in _DEFAULT_ESTIMATE_BY_KEYWORD:
        if keyword in joined:
            return seconds
    return DEFAULT_ESTIMATE_SECONDS


def _warn(message: str, label: str = "run-with-timeout") -> None:
    sys.stderr.write(f"{label}: {message}\n")


# 持有名額的程序在持有期間放入環境，其子程序據此免重複取得（否則自我死鎖）
HELD_ENV = "CLAUDE_SLOT_HELD_BY"
# 持有期間子程序的名額等待上限（秒）：子程序認得標記時根本不等待，會等代表兩邊 slot_gate 版本不一致，
# 此時快速失敗，不讓持有者占住全機名額直到預設上限
HELD_CHILD_WAIT_LIMIT_SECONDS = 30


def _all_slots_busy(directory: str) -> bool:
    """每個名額的鎖檔目前都被某程序持有（不符合即立刻放回剛取得的鎖）。"""
    for index in range(SLOT_COUNT):
        try:
            fd = os.open(os.path.join(directory, f"heavy-slot-{index}.lock"), os.O_RDWR | os.O_NOFOLLOW)
        except OSError:
            return False  # 鎖檔不存在或不可開：沒有人持有
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return False
        except BlockingIOError:
            pass  # 此名額有人持有，檢查下一個
        finally:
            os.close(fd)
    return True


def held_by_ancestor() -> bool:
    """環境標記指向仍存在的程序，且名額確實被占用。標記格式錯誤或任何查驗失敗皆視為未持有。"""
    raw = os.environ.get(HELD_ENV)
    if not raw:
        return False
    try:
        return not _pid_gone(int(raw)) and _all_slots_busy(slot_dir())
    except (ValueError, OSError):
        return False  # 標記不是整數或目錄不可查：不免排隊，由正常取得流程處理


# 保存 export_hold 之前的 CLAUDE_SLOT_WAIT_LIMIT；空字串表示當時未設定
_LIMIT_BEFORE_ENV = "CLAUDE_SLOT_WAIT_LIMIT_BEFORE_HOLD"
_LIMIT_ENV = "CLAUDE_SLOT_WAIT_LIMIT"


@contextlib.contextmanager
def export_hold(hold: "SlotHold"):
    """持有期間把本程序 pid 放入環境供直接子層的 run-with-timeout 辨識，並把其等待上限降為
    HELD_CHILD_WAIT_LIMIT_SECONDS；離開時還原原值。

    標記只給直接子層：run-with-timeout 啟動被包裝命令時須以 child_env 去除，不得往下傳。
    """
    names = (HELD_ENV, _LIMIT_ENV, _LIMIT_BEFORE_ENV)
    previous = {n: os.environ.get(n) for n in names}
    os.environ[_LIMIT_BEFORE_ENV] = os.environ.get(_LIMIT_ENV, "")
    os.environ[HELD_ENV] = str(os.getpid())
    os.environ[_LIMIT_ENV] = str(HELD_CHILD_WAIT_LIMIT_SECONDS)
    try:
        yield hold
    finally:
        for n, v in previous.items():
            if v is None:
                os.environ.pop(n, None)
            else:
                os.environ[n] = v


def child_env(env: "os._Environ") -> dict:
    """被包裝命令的環境：去除持有標記，等待上限還原為持有前的值（持有前未設定則移除）。

    沒有持有標記時原樣複製。
    """
    out = dict(env)
    if HELD_ENV not in out:
        return out
    out.pop(HELD_ENV)
    before = out.pop(_LIMIT_BEFORE_ENV, None)
    if before:
        out[_LIMIT_ENV] = before
    elif before is not None:
        out.pop(_LIMIT_ENV, None)
    return out


def is_heavy_command(command: List[str]) -> bool:
    """依 test_command_parse 判定；判定本身失敗時保守視為 heavy（只多排隊）。

    祖先程序已持有名額時回 False：呼叫端據此略過取得，避免對同一名額自我死鎖。
    """
    if held_by_ancestor():
        return False
    try:
        from lib.test_command_parse import WEIGHT_HEAVY, classify_argv_weight
        return classify_argv_weight(command) == WEIGHT_HEAVY
    except Exception as exc:  # 任何判定失敗都不得讓包裝程序以 traceback 結束
        _warn(f"heavy 判定失敗，視為 heavy：{exc}")
        return True


def slot_dir() -> str:
    return os.environ.get("CLAUDE_SLOT_LOCK_DIR") or os.path.join(
        os.path.expanduser("~"), ".cache", "claude-slot")


def _owner_uid() -> int:
    return os.getuid()


def _prepare_dir(directory: str) -> None:
    """建立（0o700）並驗證鎖目錄；不符安全條件拋 PermissionError，呼叫端據此略過閘門。"""
    os.makedirs(directory, mode=0o700, exist_ok=True)
    info = os.lstat(directory)  # lstat 不跟隨 symlink
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise PermissionError(f"{directory} 不是一般目錄（symlink 或其他類型），不使用")
    if info.st_uid != _owner_uid():
        raise PermissionError(f"{directory} 不屬於目前使用者，不使用")
    if info.st_mode & 0o077:
        raise PermissionError(f"{directory} 權限允許群組或其他人存取（{info.st_mode & 0o777:o}），不使用")


def _env_seconds(name: str, default: float) -> float:
    try:
        return float(os.environ[name])
    except (KeyError, ValueError):
        return default


def _holder_path(directory: str, index: int) -> str:
    return os.path.join(directory, f"heavy-slot-{index}.holder.json")


def _pid_gone(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except (PermissionError, OSError):
        return False  # EPERM 表示程序存在
    return False


def _current_load() -> str:
    """當下 load（每次印出時重新取，不沿用持有者記錄的值）。"""
    try:
        return "/".join(f"{x:.2f}" for x in os.getloadavg())
    except OSError:
        return "不可得"


def describe_holder(directory: str) -> str:
    """讀出第一個可讀的持有者資訊；持有者 pid 已不存在時標示資訊過期。"""
    for index in range(SLOT_COUNT):
        try:
            with open(_holder_path(directory, index)) as fh:
                info = json.load(fh)
            text = (f"持有者 pid={info['pid']} cwd={info['cwd']} 命令={' '.join(info['command'])} "
                    f"開始={info['started']} ｜ 目前負載={_current_load()}")
            if _pid_gone(int(info["pid"])):
                text += "（資訊過期：該 pid 已不存在，名額應很快釋放）"
            return text
        except (OSError, ValueError, KeyError, TypeError):
            continue  # 持有者剛取得、尚未寫出資訊，或資訊檔已隨持有者結束移除
    return "持有者資訊暫不可讀"


def _write_holder(directory: str, index: int, command: List[str], estimate: float) -> Optional[str]:
    path = _holder_path(directory, index)
    tmp = f"{path}.{os.getpid()}.tmp"
    try:
        entry = {"pid": os.getpid(), "cwd": os.getcwd(), "command": command,
                 "started": time.strftime("%Y-%m-%d %H:%M:%S"),
                 "started_epoch": time.time(), "estimate": estimate,
                 "load": "/".join(f"{x:.2f}" for x in os.getloadavg())}
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as fh:
            json.dump(entry, fh)
        os.replace(tmp, path)
        return path
    except OSError as exc:
        _warn(f"無法寫入名額持有者資訊（不影響命令）：{exc}")
        try:
            os.unlink(tmp)
        except OSError:
            pass  # 暫存檔未建立或已改名，無需清理
        return None


def _remove_stale_tmp(directory: str) -> None:
    """刪除持有者 pid 已不存在的 holder 暫存檔（寫入中途被 SIGKILL 的殘留）。"""
    try:
        names = os.listdir(directory)
    except OSError:
        return
    for name in names:
        if not (name.startswith("heavy-slot-") and name.endswith(".tmp")):
            continue
        try:
            pid = int(name[:-len(".tmp")].rsplit(".", 1)[1])
        except (ValueError, IndexError):
            continue
        if _pid_gone(pid):
            try:
                os.unlink(os.path.join(directory, name))
            except OSError:
                pass  # 已被他方清除


_QUEUE_RE = re.compile(r"^queue-(\d{12})-(\d+)\.json$")


def _live_queue(directory: str) -> List[Tuple[int, str]]:
    """依序號排序的存活排隊檔 [(序號, 檔名)]；pid 已不存在者順手清除。"""
    entries = []
    for name in os.listdir(directory):
        m = _QUEUE_RE.match(name)
        if m is None:
            continue
        if _pid_gone(int(m.group(2))):
            try:
                os.unlink(os.path.join(directory, name))
            except OSError:
                pass  # 已被他方清除
            continue
        entries.append((int(m.group(1)), name))
    entries.sort()
    return entries


def _enqueue(directory: str, command: List[str], estimate: float) -> str:
    """建立自己的排隊檔，回檔名；序號 = 現有最大序號 + 1，撞名即重試。"""
    while True:
        seq = max([s for s, _ in _live_queue(directory)] + [0]) + 1
        name = f"queue-{seq:012d}-{os.getpid()}.json"
        try:
            fd = os.open(os.path.join(directory, name), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        except FileExistsError:
            continue  # 他人同時取得同一序號
        with os.fdopen(fd, "w") as fh:
            json.dump({"pid": os.getpid(), "command": command, "estimate": estimate,
                       "arrived": time.strftime("%Y-%m-%d %H:%M:%S")}, fh)
        return name


def _dequeue(directory: str, name: str) -> None:
    try:
        os.unlink(os.path.join(directory, name))
    except OSError:
        pass  # 已被他方清除


def _heartbeat(directory: str, name: str) -> None:
    """更新自己排隊檔的 mtime 作為心跳；檔案已被清除時不處理（由順位判定重新排隊）。"""
    try:
        os.utime(os.path.join(directory, name))
    except OSError:
        pass  # 排隊檔已不在，_queue_position 回 0 後會重新排隊


def _is_stalled(directory: str, entry: str, stall_seconds: float) -> bool:
    try:
        return time.time() - os.stat(os.path.join(directory, entry)).st_mtime > stall_seconds
    except OSError:
        return False  # 檔案剛被清除：交由 _live_queue 的後續輪詢處理


def _queue_position(directory: str, name: str, stall_seconds: Optional[float] = None,
                    reported: Optional[set] = None, label: str = "run-with-timeout") -> int:
    """自己的順位（1 起算）；排隊檔已不在（被他人清除）時回 0。

    stall_seconds 不為 None 時，前方心跳過期的存活排隊者視同離場不計入順位（不刪除其排隊檔：
    它恢復後第一輪更新心跳即重新計入，與新排頭同時嘗試 flock 由核心互斥，輸者繼續等待）。
    略過時對 stderr 寫一行，同一筆只寫一次（以 reported 去重）。
    """
    position = 0
    for _seq, entry in _live_queue(directory):
        if entry == name:
            return position + 1
        if stall_seconds is not None and _is_stalled(directory, entry, stall_seconds):
            if reported is not None and entry not in reported:
                reported.add(entry)
                _warn(f"排頭排隊者 {entry} 存活但超過 {stall_seconds:g} 秒未更新心跳，判定停住，略過"
                      f"（恢復後自動重新計入）", label)
            continue
        position += 1
    return 0


def _number(value, fallback: float) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0 else fallback


def _entry_estimate(directory: str, name: str) -> float:
    """排隊檔的預估秒數；欄位缺漏、檔案不可讀（舊格式、剛被清除）以命令預設值或預設常數計。"""
    try:
        with open(os.path.join(directory, name)) as fh:
            info = json.load(fh)
        return _number(info.get("estimate"), default_estimate_seconds(info.get("command") or []))
    except (OSError, ValueError, AttributeError, TypeError):
        return DEFAULT_ESTIMATE_SECONDS


def _holder_remaining(directory: str) -> float:
    """目前持有者的剩餘預估秒數（估計值減已持有秒數，下限 0）；持有者 pid 已不存在或資訊不可讀計 0。"""
    for index in range(SLOT_COUNT):
        try:
            with open(_holder_path(directory, index)) as fh:
                info = json.load(fh)
            if _pid_gone(int(info["pid"])):
                continue
            estimate = _number(info.get("estimate"), default_estimate_seconds(info.get("command") or []))
            elapsed = max(time.time() - float(info["started_epoch"]), 0.0) if "started_epoch" in info else 0.0
            return max(estimate - elapsed, 0.0)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            continue  # 持有者剛取得、尚未寫出資訊，或資訊檔已移除：不計入
    return 0.0


def _holder_overrun(directory: str) -> Optional[Tuple[float, float]]:
    """存活持有者 (已持有秒數, 預估秒數)；無存活持有者或資訊不可讀回 None。"""
    for index in range(SLOT_COUNT):
        try:
            with open(_holder_path(directory, index)) as fh:
                info = json.load(fh)
            if _pid_gone(int(info["pid"])) or "started_epoch" not in info:
                continue
            estimate = _number(info.get("estimate"), default_estimate_seconds(info.get("command") or []))
            return max(time.time() - float(info["started_epoch"]), 0.0), estimate
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            continue  # 持有者剛取得、尚未寫出資訊，或資訊檔已移除：不判定
    return None


def _first_ahead_text(directory: str, name: str) -> str:
    """前方第一筆排隊者的命令（無則空字串）。"""
    for _seq, entry in _live_queue(directory):
        if entry == name:
            return ""
        try:
            with open(os.path.join(directory, entry)) as fh:
                return " ".join(str(x) for x in (json.load(fh).get("command") or [])) or "命令不明"
        except (OSError, ValueError, AttributeError, TypeError):
            return "命令不明"
    return ""


def _queue_text(directory: str, name: str, position: int) -> str:
    """順位說明：順位不含持有者，並指名前方第一筆。"""
    ahead = max(position - 1, 0)
    first = _first_ahead_text(directory, name)
    tail = f"前方第一筆：{first}" if first else "前方無排隊者（只需等持有者，若有）"
    return f"順位 {position}（持有者之後第 {position} 位，順位不含持有者），前方 {ahead} 筆，{tail}"


def estimate_wait(directory: str, name: str) -> Tuple[int, float]:
    """回 (前方存活排隊筆數, 預估等待秒數)；等待 = 持有者剩餘 + 前方各筆 estimate。"""
    ahead = []
    for _seq, entry in _live_queue(directory):
        if entry == name:
            break
        ahead.append(entry)
    return len(ahead), _holder_remaining(directory) + sum(_entry_estimate(directory, e) for e in ahead)


def _try_acquire(directory: str) -> Optional[Tuple[int, int]]:
    """依序嘗試各名額；回 (fd, index) 或 None。"""
    for index in range(SLOT_COUNT):
        fd = os.open(os.path.join(directory, f"heavy-slot-{index}.lock"), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fd, index
        except BlockingIOError:
            os.close(fd)
    return None


class SlotHold:
    """持有中的名額；release 先移除持有者資訊再關閉鎖檔描述符。"""

    def __init__(self, fd: int, holder_path: Optional[str]) -> None:
        self.fd = fd
        self.holder_path = holder_path

    def release(self) -> None:
        if self.holder_path is not None:
            try:
                os.unlink(self.holder_path)
            except OSError:
                pass  # 資訊檔已不存在；鎖由 close 釋放，不影響正確性
        os.close(self.fd)


def acquire_slot(command: List[str],
                 interrupted: Callable[[], Optional[int]],
                 label: str = "run-with-timeout",
                 estimate_seconds: Optional[float] = None) -> Tuple[Optional[SlotHold], Optional[int]]:
    """排隊取得名額；回 (SlotHold 或 None, 提前結束碼或 None)。

    interrupted 回傳等待期間收到的訊號編號（無則 None）。label 為提示行前綴，讓不同呼叫端的等待提示可區分來源。estimate_seconds 為本次預計持有秒數（未傳用命令預設值），供後方排隊者估算等待。持有者為 None 且無結束碼表示閘門失效而略過。
    """
    directory = slot_dir()
    limit = _env_seconds("CLAUDE_SLOT_WAIT_LIMIT", SLOT_WAIT_LIMIT_SECONDS)
    interval = _env_seconds("CLAUDE_SLOT_NOTICE_INTERVAL", SLOT_NOTICE_INTERVAL_SECONDS)
    estimate = _number(estimate_seconds, default_estimate_seconds(command))
    waited_since = time.monotonic()
    next_notice = waited_since
    queue_name = None  # type: Optional[str]
    try:
        _prepare_dir(directory)
        queue_name = _enqueue(directory, command, estimate)
        ahead_count, expected = estimate_wait(directory, queue_name)
        if ahead_count or expected > 0:  # 進場即告知順位與預估；佇列總等待不設上限，由呼叫端決定是否放棄
            _warn(f"進場排隊：{_queue_text(directory, queue_name, ahead_count + 1)}；預估等待 {expected:.0f} 秒"
                  f"（不設總等待上限，可自行中止）；{describe_holder(directory)}", label)
        capped = bool(os.environ.get(HELD_ENV))  # 持有者的子程序：上限仍是總等待上限
        stall = _env_seconds("CLAUDE_SLOT_STALL_SECONDS", SLOT_STALL_SECONDS)
        stalled_reported = set()  # type: set
        while True:
            try:
                _prepare_dir(directory)
                _heartbeat(directory, queue_name)
                position = _queue_position(directory, queue_name, stall, stalled_reported, label)
                if position == 0:  # 排隊檔被他人清除：重新排到隊尾
                    queue_name = _enqueue(directory, command, estimate)
                    position = _queue_position(directory, queue_name, stall, stalled_reported, label)
                got = _try_acquire(directory) if position == 1 else None
            except OSError as exc:
                _warn(f"名額閘門無法使用，略過排隊（不影響命令）：{exc}", label)
                return None, None
            if got is not None:
                fd, index = got
                waited = time.monotonic() - waited_since
                if waited >= WAITED_REPORT_THRESHOLD:
                    _warn(f"取得名額，已等待 {waited:.1f} 秒", label)
                _remove_stale_tmp(directory)
                return SlotHold(fd, _write_holder(directory, index, command, estimate)), None
            signum = interrupted()
            if signum is not None:
                return None, 128 + signum
            now = time.monotonic()
            if capped and now - waited_since >= limit:
                _warn(f"等待名額超過 {limit:g} 秒，放棄執行。{describe_holder(directory)}", label)
                return None, SLOT_WAIT_EXIT_CODE
            running = _holder_overrun(directory)
            if running is not None and running[0] - running[1] > limit:
                _warn(f"持有者已持有 {running[0]:.0f} 秒，超出自身預估 {running[1]:.0f} 秒逾 {limit:g} 秒，"
                      f"疑似卡住，放棄等待。{describe_holder(directory)}", label)
                return None, SLOT_WAIT_EXIT_CODE
            if now >= next_notice:
                _, remaining = estimate_wait(directory, queue_name)
                _warn(f"等待名額：{_queue_text(directory, queue_name, position)}；{describe_holder(directory)}；"
                      f"已等待 {now - waited_since:.0f} 秒，預估剩餘 {remaining:.0f} 秒", label)
                next_notice = now + interval
            time.sleep(SLOT_POLL_INTERVAL)
    except OSError as exc:
        _warn(f"名額閘門無法使用，略過排隊（不影響命令）：{exc}", label)
        return None, None
    finally:
        if queue_name is not None:
            _dequeue(directory, queue_name)  # 取得、放棄、逾時、訊號中斷、例外皆清除


def _orphan_script() -> str:
    return os.environ.get("CLAUDE_ORPHAN_SCRIPT") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "orphan-test-procs.py")


def count_orphans() -> Tuple[int, int]:
    """列出本專案孤兒，回 (可清理, 疑似殘留)；可清理 = 符合 + 可終止的登記群組。

    疑似殘留不會被 --kill 處理，故分開計數。任何失敗拋 RuntimeError 並附原因。
    """
    timeout = _env_seconds("CLAUDE_ORPHAN_QUERY_TIMEOUT", ORPHAN_QUERY_TIMEOUT_SECONDS)
    try:
        res = subprocess.run([sys.executable, _orphan_script()], capture_output=True, text=True,
                             timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"查詢逾時（{timeout:g} 秒）")
    except OSError as exc:
        raise RuntimeError(f"無法執行查詢：{exc}")
    found = _ORPHAN_SUMMARY_RE.findall(res.stdout)
    if res.returncode not in (0, 1) or not found:
        raise RuntimeError(f"查詢失敗（結束碼 {res.returncode}，無法解析輸出）")
    matched, _skipped, suspects, registered = (int(x) for x in found[-1])
    return matched + registered, suspects


def report_orphans() -> None:
    """有孤兒則印出數量；可清理者附清理指令，疑似殘留者要求人工核對。永不拋例外。"""
    try:
        cleanable, suspects = count_orphans()
    except Exception as exc:  # 提示性查詢，任何失敗都不得影響命令
        _warn(f"孤兒程序查詢失敗，略過提示（不影響命令）：{exc}")
        return
    parts = []
    if cleanable:
        parts.append(f"可清理 {cleanable} 個孤兒測試程序（會佔用記憶體），清理：{ORPHAN_CLEANUP_COMMAND}")
    if suspects:
        parts.append(f"疑似殘留 {suspects} 棵程序樹，清理指令不會處理，需人工核對後逐一終止"
                     "（列表見 orphan-test-procs.py 不帶參數的輸出）")
    if parts:
        _warn("偵測到" + "；".join(parts))
