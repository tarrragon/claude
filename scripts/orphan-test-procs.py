#!/usr/bin/env python3
"""列出（或終止）本專案範圍內的孤兒測試程序。

用法：python3 .claude/scripts/orphan-test-procs.py [--kill]

不帶引數：只列出，不終止，結束碼 0。
--kill：對符合者先 TERM，寬限後仍存活才 KILL；送訊號前會重讀該 PID 的父程序與命令，
        與認定時不同則不送。結束碼：0 全數處理完；1 有目標未能終止；2 ps/git 等外部命令失敗。

認定須四項皆符合：
1. 父程序為 1（已被 launchd 收養）
2. 非殭屍（ps 狀態不以 Z 開頭）
3. 命令屬已知測試執行器：首詞為 RUNNERS 之一，或首詞為直譯器且緊接 -m 模組名／執行器腳本
4. 工作目錄位於專案根目錄或其 git worktree 之下

疑似殘留（只顯示，任何情況下不終止，含 --kill）：父程序為 1、工作目錄在專案範圍內、
本身不是執行器、子孫中有執行器的程序樹。無法確認它不是刻意放在背景執行的。

登記群組（run-with-timeout.py 啟動命令時登記的程序群組；格式與位置見該檔模組說明，
本檔另行實作讀取，兩邊一致由測試確保）：這是唯一依「來源」而非外觀終止的類別。
- 登記的包裝腳本仍存活（PID 存在且啟動時間相符）：略過。
- 包裝腳本已不在、群組領頭程序存在且啟動時間與登記相符、群組仍有成員：可終止，--kill 時先 TERM 後 KILL
  （killpg 只對通過比對的登記群組使用），完成後移除登記。
  終止函式內 TERM 後領頭已退出而群組仍有成員者，視為同一群組繼續送 KILL；領頭仍在但啟動時間不符則不送，
  回報未能終止（結束碼 1）。
- 清理開始時領頭啟動時間與登記不符，或領頭已不在但群組編號仍有成員（編號可能已被重用）：只列出原因、不送訊號，並移除過期登記。
- 群組已無成員：移除過期登記（不論登記的工作目錄是否在專案範圍內）。
- 登記檔無法讀取／格式損壞（含 pgid 非大於 1 的整數、布林、浮點、等於本指令自身群組編號）：回報該筆後繼續，不中斷、不刪除、不送訊號；
  登記的工作目錄在專案範圍外且群組仍有成員者略過。
- ps 查詢失敗：該筆回報錯誤、不終止、保留登記，其餘登記與既有類別照常處理，結束碼 1。啟動時間固定以 UTC 比對。

特殊情形：
- 工作目錄無法取得或已刪除：無法確認屬於本專案，不終止，僅列為「略過」。
- 子程序自行脫離群組但父程序仍存活：父程序非 1，不符合，不列出。
- 首詞為絕對路徑但該檔案不存在（含執行檔已被刪除的程序）：不認定。
- 命令列的詞界無法由 ps 分辨，認定只看首詞（見 is_runner）：執行檔路徑含空白、
  直譯器帶值選項、測試執行器的工作程序皆不支援，寧可漏認，不可誤認。
"""
import argparse
import json
import os
import re
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import List, NamedTuple, Optional

# 已知測試執行器（直接執行時的檔名，或經直譯器啟動時的腳本檔名／-m 模組名）
RUNNERS = frozenset({"flutter_tester", "pytest", "py.test", "jest", "vitest"})
INTERPRETER_RE = re.compile(r"^(python[\d.]*|node|bun|deno)$", re.IGNORECASE)
SCRIPT_EXTS = (".py", ".js", ".mjs", ".cjs", ".ts")
# TERM 後給程序收尾的寬限秒數
GRACE_SECONDS = 3.0
POLL_INTERVAL = 0.05
# KILL 後等待目標消失的期限秒數（機器過載時 KILL 生效可能晚於一個輪詢間隔）
KILL_WAIT_SECONDS = 3.0


class Proc(NamedTuple):
    pid: int
    ppid: int
    stat: str
    command: str
    etime: str = ""  # ps 的存活時間（[[dd-]hh:]mm:ss）；取不到為空字串


class SuspectTree(NamedTuple):
    """被收養且子孫含測試執行器的程序樹；members 含根。"""
    root: Proc
    members: List[Proc]


class CommandError(Exception):
    """外部命令無法執行或回傳非 0。"""


def _run(cmd: List[str], tolerate_failure: bool = False) -> str:
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
    except OSError as exc:
        raise CommandError(f"無法執行 {cmd[0]}：{exc}")
    if res.returncode != 0 and not tolerate_failure:
        raise CommandError(f"{' '.join(cmd)} 失敗（結束碼 {res.returncode}）：{res.stderr.strip()}")
    return res.stdout


def list_processes() -> List[Proc]:
    out = _run(["ps", "-axo", "pid=,ppid=,stat=,etime=,command="])
    procs = []
    for line in out.splitlines():
        parts = line.split(None, 4)
        if len(parts) == 5 and parts[0].isdigit() and parts[1].isdigit():
            procs.append(Proc(int(parts[0]), int(parts[1]), parts[2], parts[4], parts[3]))
    return procs


def _base(token: str) -> str:
    return os.path.basename(token)


def _script_name(token: str) -> str:
    name = _base(token)
    for ext in SCRIPT_EXTS:
        if name.endswith(ext):
            return name[: -len(ext)]
    return name


def _is_known_executable(token: str) -> bool:
    return _base(token) in RUNNERS or bool(INTERPRETER_RE.match(_base(token)))


def _interpreter_runs_runner(rest: List[str]) -> bool:
    """直譯器之後的第一個引數是否啟動測試執行器（-m 模組名，或執行器腳本）。

    只看緊接在直譯器之後的詞：-m 取模組名，-mNAME 取 NAME；其他選項（含帶值的
    -W、-X、--require 等）一律不認定，因為無法分辨選項的值與腳本詞。
    """
    if not rest:
        return False
    first = rest[0]
    if first == "-m":
        return len(rest) > 1 and rest[1] in RUNNERS
    if first.startswith("-m"):
        return first[2:] in RUNNERS
    if first.startswith("-"):
        return False
    return _script_name(first) in RUNNERS


def _is_regular_file(path: str) -> bool:
    """磁碟上是否存在該一般檔案（獨立成函式，供測試替換）。"""
    return os.path.isfile(path)


def is_runner(command: str) -> bool:
    """只看首詞；後方任何詞都不用來推測被空白切斷的路徑（寧可漏認，不可誤認）。

    首詞為絕對路徑時須為磁碟上存在的一般檔案：被空白切斷的半截路徑不是檔案。
    """
    tokens = command.split()
    if not tokens or not _is_known_executable(tokens[0]):
        return False
    if os.path.isabs(tokens[0]) and not _is_regular_file(tokens[0]):
        return False
    if _base(tokens[0]) in RUNNERS:
        return True
    return _interpreter_runs_runner(tokens[1:])


def process_cwd(pid: int) -> Optional[str]:
    """回傳程序工作目錄；無法取得時回 None（程序已結束時 lsof 回非 0，視為無法取得）。"""
    out = _run(["lsof", "-a", "-d", "cwd", "-Fn", "-p", str(pid)], tolerate_failure=True)
    for line in out.splitlines():
        if line.startswith("n"):
            return line[1:]
    return None


def project_roots(root: Optional[str]) -> List[str]:
    """專案根目錄加上其 git worktree 根目錄（realpath）。

    給定 root 時直接以它為唯一範圍，不展開 worktree（測試與縮小範圍用）。
    """
    if root:
        return [os.path.realpath(root)]
    base = _run(["git", "-C", str(Path(__file__).resolve().parent),
                 "rev-parse", "--show-toplevel"]).strip()
    listing = _run(["git", "-C", base, "worktree", "list", "--porcelain"])
    roots = [os.path.realpath(base)]
    roots += [os.path.realpath(l[len("worktree "):])
              for l in listing.splitlines() if l.startswith("worktree ")]
    return sorted(set(roots))


def under(path: str, roots: List[str]) -> bool:
    real = os.path.realpath(path)
    return any(real == r or real.startswith(r + os.sep) for r in roots)


def classify(procs: List[Proc], roots: List[str]):
    """回傳 (符合者, 略過者)；略過者為 (Proc, 原因)。"""
    matched, skipped = [], []
    for p in procs:
        if p.ppid != 1 or p.stat.startswith("Z") or not is_runner(p.command):
            continue
        cwd = process_cwd(p.pid)
        if cwd is None:
            skipped.append((p, "無法取得 cwd"))
        elif not os.path.isdir(cwd):
            skipped.append((p, f"cwd 已刪除：{cwd}"))
        elif under(cwd, roots):
            matched.append(p)
    return matched, skipped


def _descendants(root_pid: int, children: dict) -> List[int]:
    """root_pid 的所有子孫 PID（含防環：已走過者不重複）。"""
    seen, stack, order = {root_pid}, [root_pid], []
    while stack:
        for kid in children.get(stack.pop(), []):
            if kid not in seen:
                seen.add(kid)
                order.append(kid)
                stack.append(kid)
    return order


def find_suspect_trees(procs: List[Proc], roots: List[str], cwd_of, is_runner_fn=None):
    """純函式：回傳 SuspectTree 清單。

    根須父程序為 1、非殭屍、本身不是執行器（那屬「符合」類別）、cwd 可取得且在
    專案範圍內，且子孫中有非殭屍的執行器。cwd 取不到者不列出（無法確認屬本專案）。
    """
    runner = is_runner_fn or is_runner
    by_pid = {p.pid: p for p in procs}
    children: dict = {}
    for p in procs:
        if p.pid != p.ppid:
            children.setdefault(p.ppid, []).append(p.pid)
    found = []
    for p in procs:
        if p.ppid != 1 or p.pid == 1 or p.stat.startswith("Z") or runner(p.command):
            continue
        subtree = [by_pid[k] for k in _descendants(p.pid, children)]
        if not any(not d.stat.startswith("Z") and runner(d.command) for d in subtree):
            continue
        cwd = cwd_of(p.pid)
        if cwd is not None and os.path.isdir(cwd) and under(cwd, roots):
            found.append(SuspectTree(p, [p] + subtree))
    return found


def format_age(etime: str) -> str:
    return etime.strip() or "未知"


def render_suspects(trees: List[SuspectTree]) -> List[str]:
    """輸出行：各樹的根、存活時間、成員，並說明為何不終止與如何處理。"""
    lines = []
    for t in trees:
        lines.append(f"疑似殘留 根 {t.root.pid} 存活 {format_age(t.root.etime)}")
        lines += [f"  {m.pid} {m.command}" for m in t.members]
    if trees:
        lines += [
            "以上疑似殘留的程序樹不會被本指令終止（帶 --kill 也一樣）：",
            "無法確認它不是刻意放在背景執行的。要處理請先核對，再以 kill <PID> 逐一個別終止。",
        ]
    return lines


SUMMARY_PREFIX = "ORPHAN_SUMMARY"


def registry_dir() -> str:
    """與 run-with-timeout.py 的同名函式同值（兩端一致由測試鎖住）。"""
    override = os.environ.get("CLAUDE_PROC_REGISTRY_DIR")
    if override:
        return override
    return os.path.join(os.path.expanduser("~"), ".cache", "claude-proc-registry")


def registry_dir_problem(directory: str) -> Optional[str]:
    """登記目錄不可採信的原因；安全或目錄不存在回 None。讀取端不建立目錄。"""
    try:
        info = os.lstat(directory)  # lstat 不跟隨 symlink
    except FileNotFoundError:
        return None
    except OSError as exc:
        return f"無法檢查：{exc}"
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        return "不是一般目錄（symlink 或其他類型）"
    if info.st_uid != os.getuid():
        return "不屬於目前使用者"
    if info.st_mode & 0o077:
        return f"權限允許群組或其他人存取（{info.st_mode & 0o777:o}）"
    return None


REGISTRY_FIELDS = ("pgid", "leader_start", "wrapper_pid", "wrapper_start", "cwd", "command")


class RegEntry(NamedTuple):
    path: str
    pgid: int
    leader_start: str
    wrapper_pid: int
    wrapper_start: str
    cwd: str
    command: list


def _valid_pgid(value) -> int:
    """群組編號須為大於 1 的整數（布林、浮點、字串不接受），且不等於本指令自身的群組編號。

    killpg(0) 會作用於呼叫者自己的群組，1 為 init；不合者視為損壞登記，不送任何訊號。
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"pgid 不是整數：{value!r}")
    if value <= 1:
        raise ValueError(f"pgid 必須大於 1：{value}")
    if value == os.getpgrp():
        raise ValueError(f"pgid 等於清理指令自身的群組編號：{value}")
    return value


def read_registry(directory: str):
    """回傳 (有效登記清單, 無法讀取者 [(路徑, 原因)])；目錄不存在視為空。"""
    entries, bad = [], []
    try:
        names = sorted(n for n in os.listdir(directory)
                       if n.startswith("wrapper-") and n.endswith(".json"))
    except FileNotFoundError:
        return entries, bad
    except OSError as exc:
        return entries, [(directory, str(exc))]
    for name in names:
        path = os.path.join(directory, name)
        try:
            with open(path) as fh:
                data = json.load(fh)
            if not all(k in data for k in REGISTRY_FIELDS):
                raise ValueError("缺少欄位")
            entries.append(RegEntry(path, _valid_pgid(data["pgid"]), str(data["leader_start"]),
                                    int(data["wrapper_pid"]), str(data["wrapper_start"]),
                                    str(data["cwd"]), list(data["command"])))
        except (OSError, ValueError, TypeError) as exc:
            bad.append((path, f"{type(exc).__name__}：{exc}"))
    return entries, bad


def process_start(pid: int) -> Optional[str]:
    """ps 的 lstart（固定 UTC，與 run-with-timeout.py 一致）；程序不存在回 None，查詢失敗拋 CommandError。"""
    cmd = ["ps", "-o", "lstart=", "-p", str(pid)]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True,
                             env={**os.environ, "LC_ALL": "C", "TZ": "UTC"})
    except OSError as exc:
        raise CommandError(f"無法執行 ps：{exc}")
    if res.returncode != 0 and (res.returncode != 1 or res.stderr.strip()):
        raise CommandError(f"{' '.join(cmd)} 失敗（結束碼 {res.returncode}）：{res.stderr.strip()}")
    return res.stdout.strip() or None


def group_members(pgid: int) -> List[int]:
    """程序群組內非殭屍成員的 PID。"""
    out = _run(["ps", "-axo", "pid=,pgid=,stat="])
    found = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit() \
                and int(parts[1]) == pgid and not parts[2].startswith("Z"):
            found.append(int(parts[0]))
    return found


def judge_entry(e: RegEntry, wrapper_start_now, leader_start_now, members: List[int]):
    """純函式：回傳 (判定, 原因)。判定：wrapper_alive／killable／unsafe／stale。"""
    if wrapper_start_now is not None and wrapper_start_now == e.wrapper_start:
        return "wrapper_alive", "包裝腳本仍存活"
    if not members:
        return "stale", "群組已無成員"
    if leader_start_now is None:
        return "unsafe", f"領頭程序 {e.pgid} 已不在但群組編號仍有成員，可能已被重用"
    if leader_start_now != e.leader_start:
        return "unsafe", (f"領頭程序啟動時間不符（登記 {e.leader_start}，"
                          f"現在 {leader_start_now}），群組編號可能已被重用")
    return "killable", "包裝腳本已不在，群組領頭與登記相符"


def _killpg(pgid: int, sig: int) -> bool:
    """對群組送訊號；群組已不存在或無權送訊號視為正常（是否存活由存活檢查回報）。
    其他作業系統錯誤回 False。"""
    try:
        os.killpg(pgid, sig)
    except (ProcessLookupError, PermissionError):
        pass
    except OSError as exc:
        sys.stderr.write(f"錯誤：killpg({pgid}, {sig}) 失敗：{exc}\n")
        return False
    return True


def _wait_group_empty(pgid: int, seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while group_members(pgid) and time.monotonic() < deadline:
        time.sleep(POLL_INTERVAL)


def terminate_registered(e: RegEntry, grace: float = GRACE_SECONDS) -> str:
    """終止登記的群組。回傳 terminated／changed（送任何訊號前領頭啟動時間不符）／
    changed_after_term（TERM 後領頭仍在但啟動時間不符，未送 KILL）／wrapper_alive／error／survived。

    TERM 後領頭程序查無而群組仍有成員：視為同一群組繼續送 KILL（群組有成員期間其編號
    不會配發給新程序；新群組的領頭會以該編號存在並使比對不符）。
    """
    if process_start(e.pgid) != e.leader_start:
        return "changed"
    if not _killpg(e.pgid, signal.SIGTERM):
        return "error"
    _wait_group_empty(e.pgid, grace)
    if group_members(e.pgid):
        leader_now = process_start(e.pgid)
        if leader_now is not None and leader_now != e.leader_start:
            return "changed_after_term"
        if process_start(e.wrapper_pid) == e.wrapper_start:
            return "wrapper_alive"
        if not _killpg(e.pgid, signal.SIGKILL):
            return "error"
        _wait_group_empty(e.pgid, KILL_WAIT_SECONDS)
    return "survived" if group_members(e.pgid) else "terminated"


def _drop_entry(path: str) -> None:
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
    except OSError as exc:
        sys.stderr.write(f"警告：無法移除登記 {path}：{exc}\n")


def _handle_entry(e: RegEntry, roots: List[str], kill: bool, killable: List[str]) -> int:
    """處理單筆登記並印出結果；回傳 1 表示未能終止／出錯，0 表示正常。判為可終止者的登記檔路徑加入 killable。"""
    wrapper_now = process_start(e.wrapper_pid)
    members = group_members(e.pgid)
    in_scope = under(e.cwd, roots)
    if not in_scope and (members or wrapper_now == e.wrapper_start):
        return 0
    verdict, reason = judge_entry(e, wrapper_now, process_start(e.pgid), members)
    label = f"群組 {e.pgid} cwd {e.cwd} 命令 {' '.join(e.command)}"
    if verdict == "wrapper_alive":
        print(f"登記略過 {label}（{reason}）")
    elif verdict == "stale":
        print(f"登記已過期 {label}（{reason}），移除登記")
        _drop_entry(e.path)
    elif verdict == "unsafe":
        print(f"登記不終止 {label}（{reason}），移除登記")
        _drop_entry(e.path)
    else:
        killable.append(e.path)
        if kill:
            return _kill_entry(e, label)
        print(f"登記可終止 {label}（{reason}）")
    return 0


def _kill_entry(e: RegEntry, label: str) -> int:
    result = terminate_registered(e)
    if result == "terminated":
        print(f"登記已終止 {label}")
        _drop_entry(e.path)
        return 0
    if result == "changed":
        print(f"登記未終止 {label}（送訊號前領頭啟動時間已變，不處理）")
        _drop_entry(e.path)
        return 0
    reasons = {
        "changed_after_term": "已送出 TERM，TERM 後領頭啟動時間不符，未送 KILL",
        "wrapper_alive": "送 KILL 前包裝腳本已存活，未送 KILL",
        "error": "killpg 失敗",
    }
    print(f"登記未能終止 {label}（{reasons.get(result, '送出 KILL 後仍有成員')}）")
    return 1


def process_registry(roots: List[str], kill: bool, killable: Optional[List[str]] = None) -> int:
    """處理登記，印出結果；回傳未能終止或出錯的筆數。單筆出錯不中止其餘登記。

    登記目錄不安全（symlink、非本人擁有、群組或其他人可寫）時不讀取、不終止，只印一行原因。"""
    killable = [] if killable is None else killable
    directory = registry_dir()
    unsafe = registry_dir_problem(directory)
    if unsafe:
        print(f"登記目錄不安全，略過（{unsafe}）")
        return 0
    entries, bad = read_registry(directory)
    for path, reason in bad:
        print(f"登記無法讀取 {path}（{reason}）")
    failed = 0
    for e in entries:
        try:
            failed += _handle_entry(e, roots, kill, killable)
        except CommandError as exc:
            failed += 1
            print(f"登記查詢失敗 群組 {e.pgid}（{exc}），不終止，保留登記")
    return failed


def _send(pid: int, sig: int) -> None:
    try:
        os.kill(pid, sig)
    except ProcessLookupError:
        pass  # 已結束
    except PermissionError:
        # macOS 對殭屍送訊號回 EPERM；他人程序亦同。是否仍存活由 terminate 的存活檢查回報
        pass


def _ps_query(pid: int, fields: str) -> str:
    """查詢單一 PID 的 ps 欄位。找不到該 PID（結束碼 1 且無 stderr）回空字串；其餘失敗拋 CommandError。"""
    cmd = ["ps", "-o", fields, "-p", str(pid)]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
    except OSError as exc:
        raise CommandError(f"無法執行 ps：{exc}")
    if res.returncode != 0 and (res.returncode != 1 or res.stderr.strip()):
        raise CommandError(f"{' '.join(cmd)} 失敗（結束碼 {res.returncode}）：{res.stderr.strip()}")
    return res.stdout.strip()


def _is_alive(pid: int) -> bool:
    out = _ps_query(pid, "stat=")
    return bool(out) and not out.startswith("Z")


def _same_identity(p: Proc) -> bool:
    """該 PID 目前仍是認定時的那個程序（父程序為 1 且命令未變）。"""
    parts = _ps_query(p.pid, "ppid=,command=").split(None, 1)
    return len(parts) == 2 and parts[0] == "1" and parts[1] == p.command


def _wait_gone(pid: int, seconds: float) -> bool:
    """在期限內輪詢；回傳是否已消失。"""
    deadline = time.monotonic() + seconds
    while _is_alive(pid):
        if time.monotonic() >= deadline:
            return False
        time.sleep(POLL_INTERVAL)
    return True


def terminate(p: Proc, grace: float = GRACE_SECONDS) -> str:
    """回傳 terminated／gone（未送訊號即已不存在）／changed（送訊號前身份已變）／
    changed_after_term（TERM 後仍存活但身份已變，未送 KILL）／survived。"""
    if not _same_identity(p):
        return "gone" if not _is_alive(p.pid) else "changed"
    _send(p.pid, signal.SIGTERM)
    if _wait_gone(p.pid, grace):
        return "terminated"
    if not _same_identity(p):
        return "changed_after_term"
    _send(p.pid, signal.SIGKILL)
    return "terminated" if _wait_gone(p.pid, KILL_WAIT_SECONDS) else "survived"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="列出或終止本專案範圍的孤兒測試程序",
        epilog="不支援（會漏認，不會誤認）：執行檔路徑含空白；直譯器帶值選項"
               "（python 的 -W、-X，node 的 -r、--require、--import、--loader）；"
               "測試執行器的工作程序（如 jest、vitest 的 worker）。")
    ap.add_argument("--kill", action="store_true", help="終止符合者（先 TERM 後 KILL）")
    ap.add_argument("--root", help=argparse.SUPPRESS)  # 測試用，不列入說明
    args = ap.parse_args(argv)
    try:
        procs = list_processes()
        roots = project_roots(args.root)
        matched, skipped = classify(procs, roots)
        suspects = find_suspect_trees(procs, roots, process_cwd)
    except CommandError as exc:
        sys.stderr.write(f"錯誤：{exc}\n")
        return 2
    for p in matched:
        print(f"符合 {p.pid} {p.command}")
    for p, reason in skipped:
        print(f"略過 {p.pid} {p.command}（{reason}）")
    for line in render_suspects(suspects):
        print(line)
    failed = 0
    killable: List[str] = []
    try:
        failed += process_registry(roots, args.kill, killable)
    except CommandError as exc:
        sys.stderr.write(f"錯誤：{exc}\n")
        return 2
    if args.kill:
        for p in matched:
            try:
                result = terminate(p)
            except CommandError as exc:
                sys.stderr.write(f"錯誤：{exc}\n")
                return 2
            if result == "terminated":
                print(f"已終止 {p.pid}")
            elif result == "gone":
                print(f"已不存在 {p.pid}（未送訊號時即已結束）")
            elif result == "changed":
                print(f"未終止 {p.pid}（送訊號前身份已變，不處理）")
            elif result == "changed_after_term":
                failed += 1
                print(f"未終止 {p.pid}（已送出 TERM，TERM 後身份已變，未送 KILL）")
            else:
                failed += 1
                print(f"未能終止 {p.pid}（送出 KILL 後仍存活）")
    if args.kill and suspects:
        print(f"疑似殘留 {len(suspects)} 棵未處理（本指令不對其送訊號）")
    print(f"符合 {len(matched)} 略過 {len(skipped)} 疑似殘留 {len(suspects)}")
    # 機器可讀契約行（slot_gate.count_orphans 只解析此行）；欄位順序與名稱變動須同步 slot_gate 與測試
    print(f"{SUMMARY_PREFIX} matched={len(matched)} skipped={len(skipped)} "
          f"suspects={len(suspects)} registered={len(killable)}")
    if not args.kill:
        print("僅列出，未終止任何程序；加 --kill 才終止")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
