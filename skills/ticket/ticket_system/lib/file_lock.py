"""
Per-ticket-file advisory lock 模組（W14-042）

提供跨模組共用的檔案鎖包裝 context manager，給 ticket_builder 等
caller 包圍 `load → modify → save` 三步驟，消除 logical race。

Why（與設計緣由）：
    W14-005 重現實驗確認 ticket_builder.update_parent_children /
    update_source_spawned_tickets 的 load-modify-save 三步存在 logical race
    （lost_rate 55.6%~71.9%）。本模組為共用 utility，由 caller 顯式以
    `with file_lock(ticket_path): ...` 包圍完整序列。

    `save_ticket` 本身不加 lock：單次 f.write 對小 content 已 effectively
    atomic，且若 save_ticket 內部再加 lock 會與 caller 的外層 lock 形成
    巢狀鎖（同 process 對同一 file），導致 self-block。

跨平台（1.0.0-W9-001）：
    改用 filelock 庫取代 POSIX-only 的 fcntl 直接呼叫。

    Why：原版以 `fcntl.flock` 直接實作，fcntl 為 POSIX-only API，在
    Windows 無此模組，故原 file_lock 在 Windows 直接 raise
    NotImplementedError。後果是所有以 `with file_lock(...)` 包圍的
    update_* 命令（claim / complete / close / release / set-* /
    append-log / check-acceptance）在 Windows 全數崩潰，ticket 工具
    實質淪為唯讀（framework issue #1 問題0，P0）。

    解法：filelock 在 POSIX 後端同樣使用 `fcntl.flock`
    （per-open-file-description 語義，與原實作一致，故 reap_stale_locks
    的同 process active-lock 偵測行為不變）、Windows 後端使用
    msvcrt.locking，跨平台語義一致。公開 API
    （file_lock / reap_stale_locks / create_id_allocation_lock /
    CREATE_LOCK_FILENAME）與鎖語義皆不變。
"""

import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from filelock import FileLock, Timeout


@contextmanager
def file_lock(target_path: Path) -> Iterator[None]:
    """Per-file blocking advisory lock（filelock 後端）。

    使用方式::

        with file_lock(ticket_path):
            data = load_ticket(...)
            data["field"].append(...)
            save_ticket(data, ticket_path)

    禁止巢狀（重要）：
        同一 process 在同一 `with file_lock(p):` 區塊內，禁止再次呼叫
        `file_lock(p)`（同 path 或會 resolve 到同一檔的 path）。filelock
        以獨立 FileLock 實例對同一檔再次取鎖，在 POSIX 下屬不同 open
        file description，會 self-block（與原 fcntl LOCK_EX 巢狀死鎖語義
        相同）。caller 必須確保 file_lock 在一次 load-modify-save 序列
        中只包圍一層。

    Lock file:
        ``{target_path}{suffix}.lock``，例如 `foo.md` → `foo.md.lock`。
        Crash 後 OS 自動回收 fd 釋鎖；殘留 lock file 不影響後續 reuse
        （已加入 .gitignore，並由 reap_stale_locks 收割）。

    Args:
        target_path: 要保護的目標檔案路徑（不會被開啟，只用於決定 lock
            file 位置）。
    """
    lock_path = target_path.with_suffix(target_path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    # 預設 timeout=-1（blocking），語義等同原 fcntl.LOCK_EX 阻塞取鎖。
    lock = FileLock(str(lock_path))
    lock.acquire()
    try:
        yield
    finally:
        lock.release()


# ---------------------------------------------------------------------------
# stale lock 收割（W8-017）
# ---------------------------------------------------------------------------


def reap_stale_locks(directory: Path) -> int:
    """非阻塞收割 directory 下殘留的 stale ``*.md.lock``。

    Why（與設計緣由）：
        file_lock context manager 釋鎖後可能保留 sentinel lock file
        （POSIX 後端），每次 load-modify-save 序列殘留一個
        0-byte ``{ticket}.md.lock``。長期累積會讓 PM 誤判有 active 操作
        （W8-017）。本函式於 CLI 安全收尾處呼叫，收割無人持有的殘留。

    安全策略（禁止天真 inline unlink）：
        對每個 ``*.md.lock`` 嘗試 ``FileLock(timeout=0).acquire()``：
        - 搶到（非阻塞成功）= 無人持鎖 = stale → 計數並在持鎖狀態下
          unlink。
        - 搶不到（``Timeout``）= 有人持鎖 = active → 跳過，絕不誤刪。
        非阻塞特性確保本函式不會卡在 active lock 上，亦不破壞既有
        flock-unlink race 防護（W14-005）：active lock 永不被收割。

    Args:
        directory: 收割起點目錄；遞迴掃描其下所有 ``*.md.lock``。

    Returns:
        int: 實際收割的 stale lock 數量（綁定「搶鎖成功」事件，非
            unlink 成功；Windows 後端釋鎖時可能已自行移除 sentinel，
            綁 unlink 會漏計）。

    Note:
        目錄不存在時 graceful 回傳 0，不丟例外（收割屬清理性質，失敗
        不應阻斷主流程）。
    """
    if not directory.exists():
        return 0

    reaped = 0
    for lock_path in directory.rglob("*.md.lock"):
        if not lock_path.is_file():
            continue
        lock = FileLock(str(lock_path), timeout=0)
        try:
            lock.acquire()
        except (Timeout, OSError):
            # Timeout = active（有人持鎖）；OSError = 開檔失敗（權限 / 競態
            # 刪除）→ 皆跳過，不誤刪、不阻斷其他收割。
            continue
        # 搶到鎖 = stale；計數綁定搶鎖成功事件，再 best-effort unlink。
        reaped += 1
        try:
            lock_path.unlink()
        except OSError:
            # Windows 對開啟中 handle 的 unlink 可能 PermissionError，或
            # 已被他者收割（FileNotFoundError）→ best-effort 跳過，計數已
            # 綁搶鎖成功不受影響。
            pass
        finally:
            lock.release()
    return reaped


# ---------------------------------------------------------------------------
# create ID 分配序列化 lock（IMP-072 方案 A）
# ---------------------------------------------------------------------------

CREATE_LOCK_FILENAME = ".ticket-create.lock"


def _warn_create_lock_degraded(reason: str) -> None:
    """lock 降級警告（quality-baseline 規則 4：失敗必須對用戶可見，走 stderr）。"""
    sys.stderr.write(
        f"[WARNING] create_id_allocation_lock: {reason}；"
        f"本次 create 以無鎖模式續行（單 process create 不受影響）。"
        f"並行 create 期間請改為序列執行以避免 ID 撞號（IMP-072）\n"
    )


def _try_acquire_create_lock(tickets_dir: Path) -> Optional[FileLock]:
    """嘗試取得 create 序列化 lock；任何失敗皆降級回傳 None（不丟例外）。

    與 file_lock 的策略差異：file_lock 取鎖失敗會讓 caller 阻塞等待；本
    lock 改為 warn + 降級，因為單 process create 本身無 race，不應因環境
    異常（lock file 無法建立）阻斷基本建票功能（acceptance：不阻斷單
    process create）。

    跨平台（W9-001）：改用 filelock 後不再有「無 fcntl 平台」降級分支
    （filelock 在 Windows 亦提供有效鎖）；僅在 lock file 無法建立 / 取得
    時降級。
    """
    lock_path = tickets_dir / CREATE_LOCK_FILENAME
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        _warn_create_lock_degraded(f"lock file 開啟失敗（{exc}）")
        return None
    lock = FileLock(str(lock_path))
    try:
        lock.acquire()
    except (OSError, Timeout) as exc:
        _warn_create_lock_degraded(f"flock 取得失敗（{exc}）")
        return None
    return lock


@contextmanager
def create_id_allocation_lock(tickets_dir: Path) -> Iterator[None]:
    """目錄級 blocking lock：序列化「ID 分配 → 落盤」臨界區（IMP-072 方案 A）。

    Why：ticket create 的 ID 分配（get_next_seq / get_next_child_seq 掃描
    max+1）與檔案寫入（save_ticket）之間無鎖，跨 process / 跨 session 並行
    create 會同讀相同 max seq、配出同一 ID，後寫者靜默覆寫前者（IMP-072，
    2026-06-11 單日 2 次撞號）。

    與 file_lock 的差異：
    - file_lock 是 per-ticket-file lock（保護單一 ticket 的 load-modify-save）；
      本 lock 是 per-tickets-dir lock（同版本目錄下所有 create 互斥）。
    - file_lock 取鎖失敗阻塞等待；本 lock graceful degradation
      （stderr warn + 無鎖續行），理由見 _try_acquire_create_lock docstring。

    Lock file：``{tickets_dir}/.ticket-create.lock``（`*.lock` 已在 .gitignore；
    crash 後 OS 自動回收 fd 釋鎖，殘留檔不影響 reuse）。

    使用方式::

        with create_id_allocation_lock(get_tickets_dir(version)):
            seq = get_next_seq(version, wave)   # 分配 ID
            ...
            save_ticket(ticket, ticket_path)    # 落盤

    禁止巢狀：同 process 在本 lock 區塊內再呼叫 create_id_allocation_lock
    （同 tickets_dir）會 self-block，語意同 file_lock 的巢狀禁令。
    """
    lock = _try_acquire_create_lock(tickets_dir)
    if lock is None:
        yield
        return
    try:
        yield
    finally:
        lock.release()


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()
