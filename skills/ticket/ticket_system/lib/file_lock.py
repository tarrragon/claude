"""
Per-ticket-file advisory lock 模組（W14-042）

提供跨模組共用的 fcntl.flock 包裝 context manager，給 ticket_builder 等
caller 包圍 `load → modify → save` 三步驟，消除 logical race。

Why（與設計緣由）：
    W14-005 重現實驗確認 ticket_builder.update_parent_children /
    update_source_spawned_tickets 的 load-modify-save 三步存在 logical race
    （lost_rate 55.6%~71.9%）。本模組為共用 utility，由 caller 顯式以
    `with file_lock(ticket_path): ...` 包圍完整序列。

    `save_ticket` 本身不加 lock：單次 f.write 對小 content 已 effectively
    atomic，且若 save_ticket 內部再加 lock 會與 caller 的外層 lock 形成
    巢狀 LOCK_EX（同 process 同 fd 對同 file），導致 self-block。

POSIX-only：fcntl 為 POSIX API；Windows 平台會在實際呼叫 file_lock 時
丟出 NotImplementedError 並指引遷移路徑（portalocker / filelock）。
"""

import sys
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Iterator, Optional

# fcntl is POSIX-only; Windows lacks it. Gate the import so module load
# succeeds cross-platform; raise NotImplementedError on actual invocation.
try:
    import fcntl  # type: ignore[import-not-found]
    _HAS_FCNTL = True
except ImportError:  # pragma: no cover - exercised only on Windows
    fcntl = None  # type: ignore[assignment]
    _HAS_FCNTL = False


@contextmanager
def file_lock(target_path: Path) -> Iterator[None]:
    """Per-file fcntl.LOCK_EX blocking advisory lock。

    使用方式::

        with file_lock(ticket_path):
            data = load_ticket(...)
            data["field"].append(...)
            save_ticket(data, ticket_path)

    禁止巢狀（重要）：
        同一 process 在同一 `with file_lock(p):` 區塊內，禁止再次呼叫
        `file_lock(p)`（同 path 或會 resolve 到同一檔的 path）。fcntl
        在 POSIX 語義下，相同 fd 對同一檔再次 LOCK_EX 會直接 self-block
        死鎖。caller 必須確保 file_lock 在一次 load-modify-save 序列中
        只包圍一層。

    Lock file:
        ``{target_path}{suffix}.lock``，例如 `foo.md` → `foo.md.lock`。
        Crash 後 OS 自動回收 fd 釋鎖；殘留 lock file 不影響後續 reuse
        （已加入 .gitignore）。

    Args:
        target_path: 要保護的目標檔案路徑（不會被開啟，只用於決定 lock
            file 位置）。

    Raises:
        NotImplementedError: 在無 fcntl 的平台（如 Windows）呼叫時。
    """
    if not _HAS_FCNTL:
        # Why: fcntl is POSIX-only. On Windows the advisory-lock semantics
        # cannot be silently dropped (would re-introduce W14-005 race) nor
        # naively replaced (msvcrt.locking has different semantics).
        raise NotImplementedError(
            "file_lock requires POSIX fcntl, which is unavailable on this "
            "platform (likely Windows). Run ticket tooling under WSL/macOS/"
            "Linux, or migrate file_lock to a cross-platform library such "
            "as `portalocker` or `filelock` before invoking update_* code "
            "paths."
        )
    lock_path = target_path.with_suffix(target_path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = open(lock_path, "w")
    try:
        fcntl.flock(fd.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
        finally:
            fd.close()


# ---------------------------------------------------------------------------
# stale lock 收割（W8-017）
# ---------------------------------------------------------------------------


def reap_stale_locks(directory: Path) -> int:
    """非阻塞收割 directory 下殘留的 stale ``*.md.lock``。

    Why（與設計緣由）：
        file_lock context manager 釋鎖後刻意保留 sentinel lock file
        （見 file_lock docstring），每次 load-modify-save 序列殘留一個
        0-byte ``{ticket}.md.lock``。長期累積會讓 PM 誤判有 active 操作
        （W8-017）。本函式於 CLI 安全收尾處呼叫，收割無人持有的殘留。

    安全策略（禁止天真 inline unlink）：
        對每個 ``*.md.lock`` 嘗試 ``flock(LOCK_EX | LOCK_NB)``：
        - 搶到（非阻塞成功）= 無人持鎖 = stale → 在持鎖狀態下 unlink。
        - 搶不到（``BlockingIOError`` / ``OSError``）= 有人持鎖 = active
          → 跳過，絕不誤刪。
        非阻塞特性確保本函式不會卡在 active lock 上，亦不破壞既有
        flock-unlink race 防護（W14-005）：active lock 永不被收割。

    Args:
        directory: 收割起點目錄；遞迴掃描其下所有 ``*.md.lock``。

    Returns:
        int: 實際收割（unlink）的 stale lock 數量。

    Note:
        無 fcntl 平台（Windows）或目錄不存在時 graceful 回傳 0，不丟例外
        （收割屬清理性質，失敗不應阻斷主流程）。
    """
    if not _HAS_FCNTL or not directory.exists():
        return 0

    reaped = 0
    for lock_path in directory.rglob("*.md.lock"):
        if not lock_path.is_file():
            continue
        try:
            fd = open(lock_path, "w")
        except OSError:
            # 開檔失敗（權限/競態刪除）→ 跳過，不阻斷其他收割
            continue
        try:
            try:
                fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                # 搶不到 = active lock（有人持鎖）→ 跳過不刪
                continue
            # 搶到鎖 = stale；在持鎖狀態下 unlink，避免 TOCTOU race
            try:
                lock_path.unlink()
                reaped += 1
            except FileNotFoundError:
                # 已被他者收割 → 視為已處理
                pass
            finally:
                fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
        finally:
            fd.close()
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


def _try_acquire_create_lock(tickets_dir: Path) -> Optional[IO[str]]:
    """嘗試取得 create 序列化 lock；任何失敗皆降級回傳 None（不丟例外）。

    與 file_lock 的平台策略差異：file_lock 在無 fcntl 平台 raise
    NotImplementedError（靜默放行會重新引入 W14-005 lost-update）；本 lock
    改為 warn + 降級，因為單 process create 本身無 race，不應因平台差異
    阻斷基本建票功能（acceptance：不阻斷單 process create）。
    """
    if not _HAS_FCNTL:
        _warn_create_lock_degraded("此平台無 fcntl（可能為 Windows）")
        return None
    lock_path = tickets_dir / CREATE_LOCK_FILENAME
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_file = open(lock_path, "w")
    except OSError as exc:
        _warn_create_lock_degraded(f"lock file 開啟失敗（{exc}）")
        return None
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
    except OSError as exc:
        lock_file.close()
        _warn_create_lock_degraded(f"flock 取得失敗（{exc}）")
        return None
    return lock_file


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
    - file_lock 無 fcntl 平台 raise；本 lock graceful degradation
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
    lock_file = _try_acquire_create_lock(tickets_dir)
    if lock_file is None:
        yield
        return
    try:
        yield
    finally:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        finally:
            lock_file.close()


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()
