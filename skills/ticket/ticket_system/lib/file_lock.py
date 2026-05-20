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

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

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


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()
