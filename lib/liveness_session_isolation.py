"""測試 session 的 liveness 隔離：專屬 session id 與洩漏哨兵。

Why：mark_hook_entry 以 CLAUDE_CODE_SESSION_ID 決定 _liveness 索引檔名；測試沿用
呼叫者的 session id 時，測試特徵記錄會併入真實 session 的索引檔，已失效的 hook
被誤判為存活。測試 session 改用 pytest- 前綴 id，使任何漏網寫入都落在可辨識的
獨立檔，再由哨兵在 session 結束時 fail-closed。

哨兵只判斷 pytest- 前綴檔存不存在，不比對整個目錄：並行的真實 session 也會寫入
同一目錄，整目錄比對會誤判。
"""

import json
import os
import sys
import uuid
from pathlib import Path
from typing import List

ENV_SESSION_ID = "CLAUDE_CODE_SESSION_ID"
SESSION_ID_PREFIX = "pytest-"
LIVENESS_RELATIVE = Path(".claude") / "hook-logs" / "_liveness"


def new_test_session_id() -> str:
    return "{}{}-{}".format(SESSION_ID_PREFIX, os.getpid(), uuid.uuid4().hex[:8])


def find_leaked_liveness_files(real_root: Path) -> List[Path]:
    """回傳真實根 _liveness 下的 pytest- 前綴檔；目錄不存在視為無洩漏。"""
    liveness_dir = real_root / LIVENESS_RELATIVE
    if not liveness_dir.is_dir():
        return []
    return sorted(liveness_dir.glob(SESSION_ID_PREFIX + "*"))


HOOK_LOGS_RELATIVE = Path(".claude") / "hook-logs"
SHARED_PREFIX = "shared:"
SHARED_ROOT_KEY = "__shared_root__"
REAL_ROOT_KEY = "__real_root__"
TEST_RUN_KEY = "__test_run__"
ENV_TEST_RUN = "HOOK_LIVENESS_TEST_RUN"


def _resolve_shared_root(real_root: Path) -> Path:
    """get_shared_state_root 解析出的根（linked worktree 內為主 repo）；解析失敗回 real_root。"""
    try:
        try:
            from lib.hook_base import get_shared_state_root
        except ImportError:
            sys.path.insert(0, str(real_root / ".claude"))
            from lib.hook_base import get_shared_state_root
        return Path(get_shared_state_root(real_root)).resolve()
    except Exception as exc:  # 解析失敗退回單根，並留 stderr 痕跡
        sys.stderr.write("[liveness-leak-sentinel] 共用根解析失敗，只比對單根: {}\n".format(exc))
        return real_root


def _snapshot_one(root: Path, prefix: str) -> dict:
    snap = {}
    logs = root / HOOK_LOGS_RELATIVE
    if not logs.is_dir():
        return snap
    for entry in os.scandir(logs):
        snap[prefix + "hook-logs/" + entry.name] = None
    liveness = logs / "_liveness"
    if liveness.is_dir():
        for entry in os.scandir(liveness):
            try:
                snap[prefix + "_liveness/" + entry.name] = entry.stat().st_size
            except OSError:
                continue
    return snap


def take_snapshot(real_root: Path, shared_root: Path = None, test_run_id: str = None) -> dict:
    """拍快照：real_root 與共用狀態根各一份（兩者相同時只拍一次）。

    只掃第一層：hook-logs 單目錄可達數萬檔，逐檔 stat 不可行。共用根在拍照時
    解析並記入快照，事後比對沿用（結束時環境變數可能已不同）。

    test_run_id 為 None 時產生新的測試執行 id，寫入 ENV_TEST_RUN（子行程繼承，
    mark_hook_entry 據此在紀錄加 test_run 欄位）並記入快照；結束時比對沿用
    快照內的 id，不覆蓋。
    """
    if shared_root is None:
        shared_root = _resolve_shared_root(real_root)
    if test_run_id is None:
        test_run_id = uuid.uuid4().hex
        os.environ[ENV_TEST_RUN] = test_run_id
    snap = _snapshot_one(real_root, "")
    snap[REAL_ROOT_KEY] = str(real_root)
    snap[TEST_RUN_KEY] = test_run_id
    if Path(shared_root).resolve() != Path(real_root).resolve():
        snap.update(_snapshot_one(Path(shared_root), SHARED_PREFIX))
        snap[SHARED_ROOT_KEY] = str(shared_root)
    return snap


_META_KEYS = (SHARED_ROOT_KEY, REAL_ROOT_KEY, TEST_RUN_KEY)


def _appended_has_test_run(key: str, before: dict, after: dict) -> bool:
    """呼叫者 id 檔新增內容中，是否有 test_run 等於本次執行 id 的紀錄。

    fail-closed 範圍（回 True 並寫 stderr）：讀檔失敗、缺根／id 資訊、
    以換行結尾的完整行 JSON 解析失敗。末段未以換行結尾 = 寫入者尚未寫完，忽略。
    """
    try:
        root_key = SHARED_ROOT_KEY if key.startswith(SHARED_PREFIX) else REAL_ROOT_KEY
        root = Path(after[root_key])
        run_id = after[TEST_RUN_KEY]
        bare = key[len(SHARED_PREFIX):] if key.startswith(SHARED_PREFIX) else key
        path = root / HOOK_LOGS_RELATIVE / bare
        offset = before.get(key) or 0
        with open(path, "rb") as f:
            f.seek(max(offset - 1, 0))
            raw = f.read()
        if offset > 0:
            # 拍照時呼叫者可能寫到一行中間：offset-1 不是換行，新增內容首段是半行後半截，丟棄
            at_line_start = raw[:1] == b"\n"
            raw = raw[1:]
            if not at_line_start:
                raw = raw.partition(b"\n")[2]
        text = raw.decode("utf-8", errors="replace")
    except (OSError, KeyError, TypeError) as exc:
        sys.stderr.write("[liveness-leak-sentinel] 無法讀取 {} 新增內容，fail-closed 判洩漏: {}\n".format(key, exc))
        return True
    lines = text.split("\n")
    lines.pop()  # 末段：以換行結尾時為空字串，否則為未寫完的半行，皆不處理
    for line in lines:
        if not line.strip():
            continue
        try:
            if json.loads(line).get("test_run") == run_id:
                return True
        except (ValueError, AttributeError) as exc:
            sys.stderr.write("[liveness-leak-sentinel] {} 完整行解析失敗，fail-closed 判洩漏: {}\n".format(key, exc))
            return True
    return False


def diff_snapshots(before: dict, after: dict, real_session_id) -> List[str]:
    """回傳洩漏項：hook-logs 新增第一層項目；_liveness 中屬於測試的新增或增長檔。

    _liveness 屬於測試 = pytest- 前綴；或檔名為呼叫者原始 session id 且新增內容
    含本次測試執行 id 的 test_run 紀錄（呼叫者自身的正常 hook 寫入不計）。
    並行真實 session 的檔案不計，避免誤判。共用根的項目以 shared: 前綴回報。
    """
    leaks = []
    for key, size in sorted(after.items()):
        if key in _META_KEYS or (key in before and before[key] == size):
            continue
        bare = key[len(SHARED_PREFIX):] if key.startswith(SHARED_PREFIX) else key
        if bare.startswith("hook-logs/"):
            # 共用根第一層項目不判定（過渡放寬，後續版本補歸屬標記）：項目無內容標記，
            # 無法歸屬寫入者，他方 session 的 hook 也會新建（如 pre-fix-evaluation-*.json）。
            # 少掉的偵測面：未隔離測試只在共用根新建第一層項目、且未經 run_hook_safely
            # 寫帶 marker 的 _liveness 紀錄時抓不到；經 run_hook_safely 者仍由 _liveness 判紅。
            is_shared = key.startswith(SHARED_PREFIX)
            if key not in before and bare != "hook-logs/_liveness" and not is_shared:
                leaks.append(key)
            continue
        stem = bare[len("_liveness/"):].rsplit(".", 1)[0]
        if stem.startswith(SESSION_ID_PREFIX):
            leaks.append(key)
        elif real_session_id and stem == real_session_id and _appended_has_test_run(key, before, after):
            leaks.append(key)
    return leaks


def apply_snapshot_sentinel(session, real_root: Path, before: dict, real_session_id) -> List[str]:
    """快照差異判紅：有洩漏令套件失敗（exitstatus=1）並寫 stderr。"""
    shared = before.get(SHARED_ROOT_KEY)
    after = take_snapshot(real_root, Path(shared) if shared else real_root, before.get(TEST_RUN_KEY))
    leaks = diff_snapshots(before, after, real_session_id)
    if leaks:
        sys.stderr.write("[liveness-leak-sentinel] 前後快照偵測到洩漏: {}\n".format(leaks))
        session.exitstatus = 1
    return leaks


def apply_leak_sentinel(session, real_root: Path) -> List[Path]:
    """偵測到洩漏時令套件失敗（exitstatus=1）並寫 stderr，回傳洩漏檔清單。"""
    leaked = find_leaked_liveness_files(real_root)
    if leaked:
        sys.stderr.write(
            "[liveness-leak-sentinel] 真實 _liveness 出現測試 session 檔，"
            "有測試繞過重導寫入真實 hook-logs: {}\n".format([p.name for p in leaked])
        )
        session.exitstatus = 1
    return leaked
