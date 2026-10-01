"""共用隔離索引提交。

``commit_files_isolated`` 供 ``ticket-md-auto-commit-hook.py`` 與
``lifecycle.complete()`` 共用：以 ``GIT_INDEX_FILE`` 指向獨立臨時 index，
全程不觸碰共用 index，提交內容只由呼叫端傳入的 ``paths`` 決定，不受共用
index 任何並行寫入影響（僅核對 --cached 範圍再裸 commit 仍有 TOCTOU 窗口，
實測命中過）。

隔離提交完整性三要件（見 ``.claude/references/bash-tool-usage-details.md``
「規則七詳細」）：
1. 檔案清單來源獨立於共用 index —— 呼叫端必須自帶 ``paths``（如 ticket md
   絕對路徑、worklog 路徑），禁止以 ``git diff --cached --name-only`` 產生
   清單。GIT_INDEX_FILE 只隔離「寫入端」，清單來源若改讀共用 index 的
   staged 狀態，隔離會在入口就已經漏掉。
2. 寫入端使用 ``GIT_INDEX_FILE`` 指向獨立臨時 index。
3. 提交前以 ``git diff --name-only`` 自檢實際變更範圍恰為 ``paths``，
   不符即放棄提交（不 update-ref）。

因不經過 ``git commit``，此路徑不會觸發任何 pre-commit/commit-msg hook
（含 bare-commit-guard-hook）——這是 plumbing 命令的固有行為，非刻意繞過。
guard 存在的目的是攔截「範圍不明的裸 commit」；本函式以自我驗證取代 guard
的把關角色：提交範圍由程式碼結構保證且提交後即時核驗，不依賴 guard 事後
攔截，故豁免 guard 不削弱其防護意圖。

GIT_INDEX_FILE 作用域（查驗結論）：``env`` 為 ``dict(os.environ)`` 的
區域複本，``env["GIT_INDEX_FILE"] = temp_index_path`` 只寫入此複本，從未
寫回 ``os.environ`` 本身，故不存在需要「unset」的全域狀態——僅
read-tree/add/write-tree 三步驟顯式傳入該 ``env``；
commit-tree/diff（自我驗證）/update-ref/後續共用 index 同步皆不帶
``env`` 參數（預設 ``None``），對應行程預設環境與共用 index，範圍分離
不依賴任何時間點的「unset」動作。

update-ref 成功後（HEAD 已推進），以 ``_sync_shared_index_after_commit``
將本次 ``paths`` 同步至共用 index（以新 HEAD 的 tree 為準，逐路徑
``update-index --index-info`` / ``--force-remove``），避免共用 index 對
這些路徑停留在舊 HEAD 狀態並隨時間累積凍結——凍結後任何後續裸 commit
會把這些路徑一併回退。此同步步驟失敗只 WARNING，不影響已完成的提交
（commit 與 HEAD 推進已成功，不應因收尾步驟失敗而讓呼叫端誤判並重試
造成重複提交）；僅動本次 ``paths`` 涉及項目，不做全量 read-tree（避免
覆蓋共用 index 中其他未提交的 staged 內容）。錯誤處理分支
（read-tree/add/write-tree/commit-tree/自我驗證不符/update-ref CAS 失敗）
在 ``_sync_shared_index_after_commit`` 呼叫之前即 ``return``，共用 index
不被觸碰。
"""
from __future__ import annotations

import glob
import os
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple, Union

_GIT_TIMEOUT = 10
# 哨兵：呼叫端未指定 timeout 時，於呼叫當下讀取模組層 _GIT_TIMEOUT（而非定義當下綁定
# 的預設值），使 timeout 可被測試與設定覆寫。None 代表不設 timeout。
_DEFAULT_TIMEOUT = object()
_MAX_RETRIES = 2
_RETRY_WAIT_SECONDS = 1

# git 撞鎖時錯誤文字內的鎖檔路徑一律以單引號包住，例如
# ``fatal: Unable to create '/repo/.git/index.lock': File exists.`` 與
# ``error: cannot lock ref 'HEAD': Unable to create '/repo/.git/refs/heads/main.lock'``。
_LOCK_PATH_RE = re.compile(r"'([^']*\.lock)'")

# 鎖存在超過此秒數即判為崩潰殘骸而非並行活鎖。判準來源：活鎖由持鎖行程在
# 單一 git 操作內建立與釋放，實測約十秒內消失；殘骸的 mtime 停在崩潰時刻，
# 不會自行前進。兩者錯誤輸出完全同形，唯一可程式化的區別是鎖齡。
_STALE_LOCK_AGE_SECONDS = 60

# 判定「己方歷史版本」時回溯的該路徑提交數上限。凍結型過期 entry 的成因是同步
# 失敗後又發生的後續提交次數；同步失敗屬罕見事件，其後累積的提交數遠低於此值。
# 取 50 使每個未命中路徑最多多花約 50 次 ls-tree（只在 entry 不等於 HEAD／本次
# tree／parent 時才進入，正常路徑零額外成本），並避免長歷史檔案無界掃描。
# 超出上限的凍結 entry 仍視為他方 stage，由 WARNING 的 restore 指令人工處置。
_OWN_HISTORY_LOOKBACK = 50


def _run_git(
    args: List[str],
    cwd: Optional[str] = None,
    env: Optional[dict] = None,
    timeout=_DEFAULT_TIMEOUT,
    input_text: Optional[str] = None,
) -> Tuple[bool, str, str]:
    """執行單次 git 命令，回傳 (success, stdout, stderr)。"""
    if timeout is _DEFAULT_TIMEOUT:
        timeout = _GIT_TIMEOUT
    try:
        result = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
            input=input_text,
        )
    except subprocess.TimeoutExpired:
        return False, "", f"git {' '.join(args[1:2])} 逾時"
    except FileNotFoundError:
        return False, "", "找不到 git"

    if result.returncode == 0:
        return True, result.stdout, ""
    return False, result.stdout, result.stderr.strip()


def _is_lock_contention(err: str) -> bool:
    """判斷錯誤文字是否為撞鎖。

    涵蓋三種形態：``index.lock``（共用 index）、``cannot lock ref``
    （update-ref 撞 ref 鎖）、以及任何被單引號包住的 ``*.lock`` 路徑
    （``refs/heads/*.lock`` 與 ``HEAD.lock`` 皆屬此類）。原實作只比對
    ``index.lock`` 子字串，對 update-ref 的錯誤文字恆為 False。
    """
    if not err:
        return False
    if "index.lock" in err or "cannot lock ref" in err:
        return True
    return bool(_LOCK_PATH_RE.search(err))


def _lock_paths_from_error(err: str, cwd: Optional[str] = None) -> List[str]:
    """自錯誤文字取出鎖檔路徑（相對路徑以 ``cwd`` 補齊為絕對路徑）。"""
    paths = []
    for path in _LOCK_PATH_RE.findall(err or ""):
        if not path:
            continue
        if not os.path.isabs(path):
            path = os.path.join(cwd or os.getcwd(), path)
        paths.append(os.path.normpath(path))
    return list(dict.fromkeys(paths))


def _scan_ref_lock_files(cwd: Optional[str]) -> List[str]:
    """列出 repo 內現存的 ref 鎖檔（``HEAD.lock`` 與 ``refs/heads/**/*.lock``）。

    僅檢視檔案系統，不呼叫 git——本函式在 update-ref 失敗路徑上使用，額外
    的 git 呼叫會在該路徑上再次撞同一把鎖。``.git`` 為檔案時（linked
    worktree）回傳空清單：該情形下鎖位於主倉庫，歸屬判定交由錯誤文字內
    的絕對路徑處理。
    """
    if not cwd:
        return []
    git_dir = os.path.join(cwd, ".git")
    if not os.path.isdir(git_dir):
        return []
    candidates = [os.path.join(git_dir, "HEAD.lock")]
    candidates += glob.glob(
        os.path.join(git_dir, "refs", "heads", "**", "*.lock"), recursive=True
    )
    return [p for p in dict.fromkeys(candidates) if os.path.exists(p)]


def _describe_lock_file(path: str) -> Optional[str]:
    """產出單一鎖檔的診斷字串（mtime／鎖齡／大小／內容）。

    診斷內容是清理責任歸屬的唯一依據：合法的移除判準是「內容可溯源為自己
    崩潰操作的產物且 mtime 停在該時刻」，故三項缺一不可。
    """
    try:
        stat_result = os.stat(path)
    except OSError:
        return None
    try:
        with open(path, "rb") as handle:
            content = handle.read(200).decode("utf-8", "replace").strip()
    except OSError as exc:  # 讀不到內容仍輸出其餘欄位，不讓診斷整段消失
        content = f"<無法讀取：{exc}>"
    mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat_result.st_mtime))
    age = int(time.time() - stat_result.st_mtime)
    return (
        f"{path}（mtime {mtime}、已存在 {age} 秒、大小 {stat_result.st_size} bytes、"
        f"內容 {content!r}）"
    )


def _stale_lock_diagnosis(err: str, cwd: Optional[str]) -> Optional[str]:
    """撞鎖錯誤中若含持久殘骸鎖，回傳診斷字串；否則回傳 None。

    工具**不移除任何鎖**——殘骸與活鎖的錯誤輸出同形，誤刪活鎖會破壞正在
    進行的並行操作。此處只負責停止重試並輸出足夠判斷的事實。
    """
    now = time.time()
    stale: List[str] = []
    candidates = _lock_paths_from_error(err, cwd) + _scan_ref_lock_files(cwd)
    for path in dict.fromkeys(candidates):
        try:
            stat_result = os.stat(path)
        except OSError:
            continue  # 鎖已消失即為活鎖的正常結局，不需診斷
        if now - stat_result.st_mtime < _STALE_LOCK_AGE_SECONDS:
            continue
        description = _describe_lock_file(path)
        if description:
            stale.append(description)
    if not stale:
        return None
    return (
        f"[殘骸診斷] 鎖已持續超過 {_STALE_LOCK_AGE_SECONDS} 秒未更新，判為崩潰殘骸而非"
        "並行活鎖，停止重試。工具不移除任何鎖，須由留下該鎖的執行者依內容溯源後"
        "自行處置：" + "；".join(stale)
    )


def _run_git_with_lock_retry(
    args: List[str],
    cwd: Optional[str] = None,
    env: Optional[dict] = None,
    timeout=_DEFAULT_TIMEOUT,
    max_retries: int = _MAX_RETRIES,
    wait_seconds: int = _RETRY_WAIT_SECONDS,
    input_text: Optional[str] = None,
) -> Tuple[bool, str, str]:
    """遇鎖競爭時等待重試（禁止刪除 lock 檔）。

    重試涵蓋 ``index.lock`` 與 ref 鎖（``refs/heads/*.lock`` / ``HEAD.lock``）。
    重試前先判讀鎖齡：命中持久殘骸即立即放棄並在錯誤文字後附上診斷，避免把
    「立刻失敗」換成「永遠重試」。
    """
    ok, out, err = _run_git(args, cwd=cwd, env=env, timeout=timeout, input_text=input_text)
    attempt = 1
    while not ok and _is_lock_contention(err) and attempt < max_retries:
        diagnosis = _stale_lock_diagnosis(err, cwd)
        if diagnosis:
            return False, out, f"{err}\n{diagnosis}"
        time.sleep(wait_seconds)
        ok, out, err = _run_git(args, cwd=cwd, env=env, timeout=timeout, input_text=input_text)
        attempt += 1
    if not ok and _is_lock_contention(err):
        diagnosis = _stale_lock_diagnosis(err, cwd)
        if diagnosis:
            err = f"{err}\n{diagnosis}"
    return ok, out, err


def _describe_update_ref_failure(
    err: str, commit_sha: str, cwd: Optional[str], locks_before: set
) -> str:
    """組出 update-ref 失敗的錯誤字串：原因 + commit SHA + 鎖殘骸歸屬。

    兩項附加輸出各自對應一個既有失效路徑。commit-tree SHA 未被任何 ref
    指向，錯誤中不帶它等於讓已完成的工作無法被手動 CAS 接續；鎖殘骸歸屬
    以「呼叫前不存在、失敗後存在」判定，因為合法的移除判準是可溯源為自己
    的產物，執行者不知道自己留下了什麼就沒有人有資格清理。
    """
    now_locks = set(_scan_ref_lock_files(cwd))
    now_locks.update(
        p for p in _lock_paths_from_error(err, cwd) if os.path.exists(p)
    )
    residue = sorted(now_locks - locks_before)
    if residue:
        descriptions = [d for d in (_describe_lock_file(p) for p in residue) if d]
        residue_note = "本次 update-ref 留下鎖殘骸（呼叫前不存在），清理責任歸屬本執行者：" + "；".join(
            descriptions or residue
        )
    else:
        residue_note = "本次 update-ref 未留下鎖殘骸（錯誤涉及的鎖在本次呼叫前即存在，或已自行消失）"
    reason = err or "HEAD 於提交期間被並行移動"
    return (
        f"{reason}\n[已建立的 commit-tree SHA] {commit_sha}"
        f"（commit 物件已存在但無 ref 指向，可據此手動完成 CAS）\n[鎖殘骸歸屬] {residue_note}"
    )


def _blob_entries(
    rev: str, paths: List[str], cwd: str
) -> Optional[Dict[str, str]]:
    """讀 ``rev`` 中 ``paths`` 的 ``"<mode> <blob>"``；rev 內不存在的路徑不出現。

    Returns:
        None 表 ls-tree 失敗（呼叫端須視為同步失敗）。
    """
    ok, out, _err = _run_git_with_lock_retry(
        ["git", "ls-tree", "-z", rev, "--"] + paths, cwd=cwd
    )
    if not ok:
        return None
    entries: Dict[str, str] = {}
    # -z：以 NUL 分隔且路徑不跳脫，CJK 檔名才能與 paths 逐字比對
    for line in out.split("\0"):
        meta, _, path = line.partition("\t")
        parts = meta.split()
        if path and len(parts) >= 3:
            entries[path] = f"{parts[0]} {parts[2]}"
    return entries


def _shared_index_entries(paths: List[str], cwd: str) -> Optional[Dict[str, str]]:
    """讀共用 index 中 ``paths`` 的 entry（``"<mode> <blob>"``）。

    衝突 stage（非 0）的路徑以 ``"conflict"`` 表示，使其必然被視為他方狀態。
    """
    ok, out, _err = _run_git_with_lock_retry(
        ["git", "ls-files", "-s", "-z", "--"] + paths, cwd=cwd
    )
    if not ok:
        return None
    entries: Dict[str, str] = {}
    for line in out.split("\0"):
        meta, _, path = line.partition("\t")
        parts = meta.split()
        if path and len(parts) >= 3:
            entries[path] = f"{parts[0]} {parts[1]}" if parts[2] == "0" else "conflict"
    return entries


def _path_history_entries(path: str, cwd: str) -> set:
    """該路徑在 HEAD 可達歷史中最近 ``_OWN_HISTORY_LOOKBACK`` 次提交的 entry 集合。

    entry 格式同 ``_blob_entries``（``"<mode> <blob>"``）。步驟失敗時回傳已收集
    部分：少收只會讓更多 entry 被判為他方 stage，方向保守（不覆寫）。
    """
    ok, out, _err = _run_git_with_lock_retry(
        ["git", "rev-list", f"-{_OWN_HISTORY_LOOKBACK}", "HEAD", "--", path], cwd=cwd
    )
    history: set = set()
    if not ok:
        return history
    for commit in out.split():
        entry = (_blob_entries(commit, [path], cwd) or {}).get(path)
        if entry:
            history.add(entry)
    return history


def _warn_sync_failed(paths: List[str], step: str, err: str) -> None:
    """同步最終失敗的 WARNING：列出受影響路徑與補救指令。

    commit 已成功，不回傳錯誤；但 entry 可能停在舊版本，須讓使用者能處置。
    """
    remedy = "；".join(f"git restore --staged -- {p}" for p in paths)
    print(
        f"[WARNING] 共用 index 同步失敗（{step}）：{err}\n"
        f"受影響路徑（共用 index entry 可能比 HEAD 舊）：{', '.join(paths)}\n"
        f"補救指令（確認該路徑無需保留的 staged 內容後執行）：{remedy}",
        file=sys.stderr,
    )


def _sync_shared_index_after_commit(
    paths: List[str], tree_sha: str, cwd: str, old_head: Optional[str] = None
) -> None:
    """提交成功（update-ref 已推進 HEAD）後，將本次 ``paths`` 同步至共用
    index，避免共用 index 對這些路徑停留在舊 HEAD 狀態（凍結累積），日後
    任何裸 commit 回退這些路徑。

    內容取自「呼叫當下的 HEAD」而非本次 ``tree_sha``：並行提交同一檔案時，
    同步順序可能與提交順序相反，晚到的舊同步若寫入本次 tree 的 blob，會把
    entry 覆寫成比 HEAD 舊的版本（路徑 B：並行提交的同步順序顛倒）。

    他方保護：共用 index 該 entry 既不等於本次 commit 的 parent 版本
    （``old_head``），也不等於本次 tree 版本、也不等於當下 HEAD 版本，且其 blob
    未出現在該路徑最近 ``_OWN_HISTORY_LOOKBACK`` 次提交歷史中，代表有人另外
    stage 了內容，不覆寫，改印 WARNING。

    僅動共用 index 中本次 ``paths`` 涉及的項目，不做全量 read-tree（避免
    覆蓋共用 index 中其他未提交的 staged 內容），不刪任何鎖。

    失敗只記錄 WARNING（含路徑與補救指令）、不回傳錯誤——commit 與
    update-ref 已成功，此步驟失敗不應讓呼叫端誤判整體提交失敗（那會導致
    重試造成重複提交）。此函式全程不帶 ``GIT_INDEX_FILE``（env 用行程預設
    環境），寫入對象即共用 index。
    """
    head_entries = _blob_entries("HEAD", paths, cwd)
    if head_entries is None:
        _warn_sync_failed(paths, "ls-tree HEAD", "無法讀取當下 HEAD")
        return
    tree_entries = _blob_entries(tree_sha, paths, cwd) or {}
    parent_entries = (_blob_entries(old_head, paths, cwd) or {}) if old_head else {}
    index_entries = _shared_index_entries(paths, cwd)
    if index_entries is None:
        _warn_sync_failed(paths, "ls-files", "無法讀取共用 index")
        return

    to_sync: List[str] = []
    foreign: List[str] = []
    for path in paths:
        known = {head_entries.get(path), tree_entries.get(path)}
        if old_head:
            known.add(parent_entries.get(path))
        entry = index_entries.get(path)
        # 歷史比對辨認「前次同步失敗而凍結的己方舊版本」；否則凍結 entry 在其後
        # 每次同步都落在 known 之外，被永久當成他方 stage
        is_own = entry in known or (
            entry is not None
            and entry != "conflict"
            and entry in _path_history_entries(path, cwd)
        )
        (to_sync if is_own else foreign).append(path)

    if foreign:
        print(
            "[WARNING] 共用 index 該路徑含他方另外 stage 的內容（既非本次 commit 的 "
            f"parent 版本、也非本次或當下 HEAD 版本），未覆寫：{', '.join(foreign)}\n"
            "若確認不需保留：git restore --staged -- " + " ".join(foreign),
            file=sys.stderr,
        )

    present = [p for p in to_sync if p in head_entries]
    index_info = "".join(
        "{} {} 0\t{}\n".format(*head_entries[p].split(), p) for p in present
    )
    if index_info:
        ok, _, err = _run_git_with_lock_retry(
            ["git", "update-index", "--index-info"], cwd=cwd, input_text=index_info,
            timeout=None,  # 持 index.lock 期間被 timeout 殺掉會殘留鎖，比照 update-ref
        )
        if not ok:
            _warn_sync_failed(present, "update-index", err)

    missing = [p for p in to_sync if p not in head_entries]
    if missing:
        ok, _, err = _run_git_with_lock_retry(
            ["git", "update-index", "--force-remove", "--"] + missing, cwd=cwd,
            timeout=None,  # 同上：持鎖步驟不設會殺行程的 timeout
        )
        if not ok:
            _warn_sync_failed(missing, "force-remove", err)


@dataclass(frozen=True)
class AppendSpec:
    """``append_lines`` 的進階值：追加文字 + 非超集時的 HEAD 重放方式。

    ``replay(base, text)`` 收 HEAD 版本全文與本次追加文字，回傳插入後的全文。
    僅在工作區缺檔或不是「HEAD + 本次行」的超集時使用；超集時仍依工作區行序投影。
    """

    text: str
    replay: Optional[Callable[[str, str], str]] = None


AppendValue = Union[str, AppendSpec]


def _project_in_worktree_order(work_path: str, base: str, text: str) -> str:
    """依工作區行序取出「base 各行 + text 各行」；缺檔或非超集回傳空字串。"""
    try:
        with open(work_path, encoding="utf-8") as fh:
            work_lines = fh.read().splitlines()
    except (OSError, UnicodeDecodeError):
        return ""  # 缺檔或不可讀：由呼叫端退回 base + text
    needed = Counter(base.splitlines()) + Counter(text.splitlines())
    picked: List[str] = []
    for line in work_lines:
        if needed[line] > 0:
            needed[line] -= 1
            picked.append(line)
    if +needed:  # 仍有未配對的行：工作區不是超集
        return ""
    return "\n".join(picked) + "\n" if picked else ""


def _stage_appended_blob(
    rel_path: str, text: str, old_head: str, cwd: str, env: dict,
    replay: Optional[Callable[[str, str], str]] = None,
) -> Optional[str]:
    """在隔離 index 中設定 ``rel_path`` 的內容：HEAD 各行 + 本次 ``text`` 各行。

    多寫入者 append-only 檔（如 topic-assignments.txt）不可整檔 add：工作區
    版本可能含他人未提交的行。提交內容的行集合恆為「HEAD 各行 + 本次各行」
    （multiset，重複行按次數計），不含他人未提交的行。

    行序契約：工作區檔存在且為該 multiset 的超集（每行出現次數都不少於所需）
    時，依工作區的行序投影，使提交後 HEAD 與工作區行序一致（兩寫入者的提交
    順序與追加順序相反時，工作區不再持續顯示已修改）。工作區缺檔或不是超集
    時，若呼叫端提供 ``replay`` 則在 HEAD 版本上重放插入（行落在呼叫端指定位置），
    否則退回「HEAD 版本 + text」（本次行接在 HEAD 末尾）。HEAD 版本末尾無
    換行時先補一個換行，與寫入端一致。

    Returns:
        None 表成功；字串為失敗原因。
    """
    ok, base, _err = _run_git_with_lock_retry(
        ["git", "show", f"{old_head}:{rel_path}"], cwd=cwd
    )
    base = base if ok else ""  # HEAD 尚無此檔：以空內容為基底
    if base and not base.endswith("\n"):
        base += "\n"
    content = _project_in_worktree_order(os.path.join(cwd, rel_path), base, text)
    if not content:
        content = replay(base, text) if replay else base + text
    ok, blob_out, err = _run_git_with_lock_retry(
        ["git", "hash-object", "-w", "--stdin"], cwd=cwd, input_text=content
    )
    if not ok:
        return err or "hash-object 失敗"
    ok, _, err = _run_git_with_lock_retry(
        ["git", "update-index", "--add", "--cacheinfo",
         f"100644,{blob_out.strip()},{rel_path}"],
        cwd=cwd, env=env,
    )
    return None if ok else (err or "update-index 失敗")


# ---------------------------------------------------------------------------
# reference-transaction 預驗證
#
# update-ref 持有 ref 鎖期間會執行 reference-transaction hook，hook 內啟動 python
# 掃描內容佔了持鎖時間的一半以上。本模組在取鎖之前先以「同一份 guard」對同一個
# commit 試跑；只在無任何發現、非合併時，才於該次 update-ref 的環境帶
# GUARD_PREVALIDATED=<new>:<old>:<ref>，由 hook shim 以 sh 比對 stdin 全等後放行。
# 唯一危險方向是錯誤命中，故任何不確定（deny、WARN、載入失敗、合併中、detached
# HEAD）都不設 env，退回 hook 的完整掃描。
# ---------------------------------------------------------------------------
GUARD_PREVALIDATED_ENV = "GUARD_PREVALIDATED"
_GUARD_PREVALIDATE_ONLY_ENV = "GIT_REF_GUARD_PREVALIDATE_ONLY"
_GUARD_PREVALIDATE_CLEAN_TOKEN = "PREVALIDATE_CLEAN"
_GUARD_RELPATH = ".claude/hooks/git-ref-transaction-content-guard.py"
_GUARD_BLOCK_EXIT_CODE = 87  # 須與 guard 的 EXIT_BLOCK 一致
_GUARD_PREVALIDATE_TIMEOUT = 300
_PREVALIDATE_LOG_DIR = os.path.join(".claude", "hook-logs", "git-ops-prevalidate")


def _run_guard_prevalidate(repo_root: str, stdin_text: str) -> Tuple[int, str, str]:
    """以 shim 相同的方式（uv run）在預驗證模式執行 guard，回傳 (rc, stdout, stderr)。"""
    env = dict(os.environ)
    env.pop(GUARD_PREVALIDATED_ENV, None)
    env[_GUARD_PREVALIDATE_ONLY_ENV] = "1"
    result = subprocess.run(
        ["uv", "run", "--quiet", os.path.join(repo_root, _GUARD_RELPATH), "prepared"],
        input=stdin_text,
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=_GUARD_PREVALIDATE_TIMEOUT,
    )
    return result.returncode, result.stdout, result.stderr


def _report_prevalidate_failure(repo_root: str, reason: str) -> None:
    """預驗證失敗必須可見：stderr 與日誌檔雙通道；呼叫端隨後退回完整掃描。"""
    message = f"預驗證失敗，本次 update-ref 退回 hook 完整掃描：{reason}"
    print(f"[WARNING] {message}", file=sys.stderr)
    try:
        log_dir = os.path.join(repo_root, _PREVALIDATE_LOG_DIR)
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "prevalidate-" + time.strftime("%Y%m%d") + ".log")
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] WARNING - {message}\n")
    except OSError as exc:
        print(f"[WARNING] 預驗證日誌寫入失敗：{exc}", file=sys.stderr)


def _prevalidate_guard_env(repo_root: str, commit_sha: str, old_head: str) -> Optional[str]:
    """回傳 GUARD_PREVALIDATED 的值；任何條件不成立回傳 None（不設 env）。

    分支以 ``repo_root`` 的 symbolic-ref HEAD 取得（寫入發生的 checkout），不讀
    CLAUDE_PROJECT_DIR——worktree 情境該變數可能指向別的 checkout。
    """
    ok, sym, _err = _run_git(["git", "symbolic-ref", "-q", "HEAD"], cwd=repo_root)
    ref = sym.strip() if ok else ""
    if not ref.startswith("refs/heads/"):
        return None  # detached HEAD 或非分支：hook 自行判定
    merging, _, _ = _run_git(["git", "rev-parse", "-q", "--verify", "MERGE_HEAD"], cwd=repo_root)
    if merging:
        return None  # 合併中兩端判定不同，一律完整掃描
    if not os.path.isfile(os.path.join(repo_root, _GUARD_RELPATH)):
        return None  # 未安裝 guard：shim 本身也不會掃描
    try:
        rc, out, err = _run_guard_prevalidate(repo_root, f"{old_head} {commit_sha} {ref}\n")
    except (OSError, subprocess.TimeoutExpired) as exc:
        _report_prevalidate_failure(repo_root, f"{type(exc).__name__}: {exc}")
        return None
    if rc == _GUARD_BLOCK_EXIT_CODE:
        return None  # 有 deny：不預驗證，由 hook 阻擋並輸出訊息
    if rc != 0 or (rc == 0 and "內部錯誤" in err):
        _report_prevalidate_failure(repo_root, f"guard rc={rc}：{err.strip()[:300]}")
        return None
    if out.strip() != _GUARD_PREVALIDATE_CLEAN_TOKEN:
        return None  # 有 WARN（或其他非乾淨結果）：不命中，由 hook 輸出提醒
    return f"{commit_sha}:{old_head}:{ref}"


def commit_files_isolated(
    paths: List[str],
    message: str,
    cwd: Optional[str] = None,
    append_lines: Optional[Dict[str, AppendValue]] = None,
) -> Dict[str, Optional[str]]:
    """在獨立臨時 index 中精確 stage ``paths`` 後以 plumbing 提交。

    Args:
        paths: 欲提交的檔案路徑清單，須獨立於共用 index（見 module docstring
            要件 1），呼叫端自帶（如 ticket md 絕對路徑）。須逐檔列出：目錄路徑
            會被明確拒絕（failed）；刪除或改名時舊路徑與新路徑都要列入（範圍
            自檢關閉 rename 偵測、逐路徑比對）；主路徑（第一個）須為存在的檔案。
        message: commit message。
        cwd: git 命令執行目錄，預設為目前工作目錄所屬 repo。
        append_lines: 路徑 -> 本次追加文字。這些檔案不整檔 stage，提交內容為
            「HEAD 各行 + 追加各行」（行序依工作區，非超集或缺檔時
            退回 HEAD 版本 + 追加文字），不帶入工作區內他人未提交的內容；
            用於多寫入者 append-only 檔。值為 ``str`` 或 ``AppendSpec``，
            後者的 ``replay`` 取代非超集時「接在 HEAD 末尾」的退回。與 ``paths`` 重疊的路徑以整檔為準。

    Returns:
        dict，含三個鍵：

        - ``status``：``"committed"``（已產生 commit）/
          ``"empty"``（paths 內容與 HEAD 相同，空 tree 短路，未提交）/
          ``"failed"``（任一步驟失敗或範圍自我驗證不符，未提交）
        - ``commit_sha``：``status == "committed"`` 時為新 commit SHA，否則 None
        - ``error``：``status == "failed"`` 時為失敗原因，否則 None
    """
    raw_deduped: List[str] = list(dict.fromkeys(p for p in paths if p))
    if not raw_deduped:
        return {"status": "empty", "commit_sha": None, "error": None}

    ok, root_out, err = _run_git_with_lock_retry(
        ["git", "rev-parse", "--show-toplevel"], cwd=cwd
    )
    if not ok:
        return {"status": "failed", "commit_sha": None, "error": err or "取得 repo root 失敗"}
    repo_root = root_out.strip()
    # git diff --name-only 一律回傳 repo-relative 路徑；呼叫端傳入的
    # paths 可能是絕對路徑（如 lifecycle.complete() 傳入 ticket_path 絕對
    # 路徑），此處統一正規化為 repo-relative，讓提交範圍自我驗證（要件 3）
    # 得以正確比對，避免絕對路徑輸入下恆判定不符而 commit 恆失敗。
    base_dir = cwd or os.getcwd()

    def _to_repo_relative(path: str) -> str:
        abs_path = path if os.path.isabs(path) else os.path.join(base_dir, path)
        return os.path.relpath(os.path.abspath(abs_path), repo_root).replace(os.sep, "/")

    dir_paths = [
        p for p in raw_deduped
        if os.path.isdir(p if os.path.isabs(p) else os.path.join(base_dir, p))
    ]
    if dir_paths:
        return {
            "status": "failed",
            "commit_sha": None,
            "error": (
                f"paths 含目錄路徑 {dir_paths}：範圍自我驗證逐檔比對，"
                "目錄會展開為多個檔案而判定不符，請改列各檔案路徑"
            ),
        }

    deduped: List[str] = list(dict.fromkeys(_to_repo_relative(p) for p in raw_deduped))
    appended: Dict[str, str] = {}
    replays: Dict[str, Callable[[str, str], str]] = {}
    for raw_path, value in (append_lines or {}).items():
        spec = value if isinstance(value, AppendSpec) else AppendSpec(value)
        rel = _to_repo_relative(raw_path)
        if rel not in deduped and spec.text:
            appended[rel] = appended.get(rel, "") + spec.text
            if spec.replay:
                replays[rel] = spec.replay
    expected_changes: List[str] = deduped + list(appended)
    cwd = repo_root

    ok, old_head_out, err = _run_git_with_lock_retry(
        ["git", "rev-parse", "HEAD"], cwd=cwd
    )
    if not ok:
        return {"status": "failed", "commit_sha": None, "error": err or "rev-parse HEAD 失敗"}
    old_head = old_head_out.strip()

    fd, temp_index_path = tempfile.mkstemp(prefix="ticket-commit-isolated-index-")
    os.close(fd)
    os.remove(temp_index_path)  # read-tree 會依需要建立獨立 index 檔
    env = dict(os.environ)
    env["GIT_INDEX_FILE"] = temp_index_path

    try:
        ok, _, err = _run_git_with_lock_retry(
            ["git", "read-tree", old_head], cwd=cwd, env=env
        )
        if not ok:
            return {"status": "failed", "commit_sha": None, "error": err}

        ok, _, err = _run_git_with_lock_retry(
            ["git", "add", "--"] + deduped, cwd=cwd, env=env
        )
        if not ok:
            return {"status": "failed", "commit_sha": None, "error": err}

        for rel, text in appended.items():
            stage_err = _stage_appended_blob(
                rel, text, old_head, cwd, env, replays.get(rel)
            )
            if stage_err is not None:
                return {"status": "failed", "commit_sha": None, "error": stage_err}

        ok, tree_out, err = _run_git_with_lock_retry(
            ["git", "write-tree"], cwd=cwd, env=env
        )
        if not ok:
            return {"status": "failed", "commit_sha": None, "error": err}
        tree_sha = tree_out.strip()

        # 空 tree 短路：write-tree 產出的 tree 與 HEAD 現有 tree 相同，代表
        # deduped 內容與 HEAD 無差異，不產生空 commit。
        ok, old_tree_out, _err = _run_git_with_lock_retry(
            ["git", "rev-parse", f"{old_head}^{{tree}}"], cwd=cwd
        )
        if ok and old_tree_out.strip() == tree_sha:
            return {"status": "empty", "commit_sha": None, "error": None}

        ok, commit_out, err = _run_git_with_lock_retry(
            ["git", "commit-tree", tree_sha, "-p", old_head, "-m", message],
            cwd=cwd,
        )
        if not ok:
            return {"status": "failed", "commit_sha": None, "error": err}
        commit_sha = commit_out.strip()

        # 提交範圍自我驗證（要件 3）：不符即放棄，不 update-ref。
        ok, diff_out, err = _run_git_with_lock_retry(
            ["git", "diff", "--no-renames", "--name-only", "-z", old_head, commit_sha], cwd=cwd
        )
        if not ok:
            return {"status": "failed", "commit_sha": None, "error": err}
        changed = {line for line in diff_out.split("\0") if line}
        # 子集比對：列出但淨變更為零的路徑合法；清單外的變更才是越界。
        # changed 為空已由上方空 tree 短路回報 empty。
        out_of_scope = changed - set(expected_changes)
        if out_of_scope:
            return {
                "status": "failed",
                "commit_sha": None,
                "error": (
                    f"提交範圍自我驗證失敗，預期 {sorted(expected_changes)} 實得 "
                    f"{sorted(changed)}（範圍外 {sorted(out_of_scope)}）"
                ),
            }

        # 預驗證在取 ref 鎖之前完成；env 只隨這一次 update-ref 傳遞（不寫入
        # os.environ，其餘 git 呼叫不帶）。
        prevalidated = _prevalidate_guard_env(cwd, commit_sha, old_head)
        update_ref_env = None
        if prevalidated:
            update_ref_env = dict(os.environ)
            update_ref_env[GUARD_PREVALIDATED_ENV] = prevalidated
        locks_before_update_ref = set(_scan_ref_lock_files(cwd))
        # update-ref 持有 HEAD.lock／<branch>.lock 期間會執行 reference-transaction
        # hook；高負載下 hook 可超過 _GIT_TIMEOUT，逾時會殺掉 git，鎖即殘留，其後
        # 每次提交撞鎖失敗（實測根因，見 CHANGELOG 2.44.6）。故此步驟不設 timeout：
        # 寧可等待，不可在持鎖中殺行程。其餘持鎖步驟（read-tree／add／write-tree 作用於
        # 私有臨時 index；共用 index 同步為毫秒級且不觸發 hook）不同型，維持預設 timeout。
        ok, _, err = _run_git_with_lock_retry(
            ["git", "update-ref", "HEAD", commit_sha, old_head],
            cwd=cwd,
            env=update_ref_env,
            timeout=None,
        )
        if not ok:
            return {
                "status": "failed",
                "commit_sha": None,
                "error": _describe_update_ref_failure(
                    err, commit_sha, cwd, locks_before_update_ref
                ),
            }

        _sync_shared_index_after_commit(expected_changes, tree_sha, cwd, old_head)
        return {"status": "committed", "commit_sha": commit_sha, "error": None}
    finally:
        try:
            if os.path.exists(temp_index_path):
                os.remove(temp_index_path)
        except OSError:
            pass
