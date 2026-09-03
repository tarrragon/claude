"""worklog_appender.append_worklog_progress 併發安全測試（0.2.1-W3-554.1）。

驗證重點：N 個 process 併發對「同一份」main worklog 呼叫
`append_worklog_progress`（各自代表不同 ticket 的 `complete` 併發完成），
`file_lock` 序列化 read-modify-write 後，所有 ticket 的進度行皆完整落地，
無 lost update（後寫者以舊內容覆寫先寫者剛插入的行）。

範圍聲明（PC-BAL-037：測試涵蓋範圍須明記，禁止暗示測試證明了未實測的
保證）：

- 本測試證明的是「N 個 process 併發呼叫、正常完成（無 crash）情境下
  無 lost update」。
- 本測試 **不涵蓋**：
  1. crash 原子性——鎖持有者於 read-modify-write 中途被強制終止時，
     `filelock` 依 OS 層 flock/msvcrt 語意於 process 結束時自動釋鎖，
     但寫入是否已完成（`write_text` 是否為 crash-safe 的原子替換）未經
     本測試驗證；`worklog_appender.py` 目前為直接 `write_text` 覆寫，
     非「暫存檔 + os.replace」模式（對照 `pm_registry.write_registry`
     的原子寫入設計），crash-safe 落盤非本票範圍。
  2. 跨 process 間系統時鐘偏移對「今天日期」判定的影響。
  3. 遠超本測試併發度（N=10）之外的高併發場景（如數百併發）下的
     效能與 flock 佇列行為。
  4. 鎖檔案本身的清理/殘留（`file_lock` 的 lock file 生命週期已由
     `reap_stale_locks` 另行覆蓋，見 `test_reap_stale_locks.py`）。
"""

from __future__ import annotations

import multiprocessing as mp
import sys
from pathlib import Path

import pytest

WORKLOG_REL = "docs/work-logs/v0/v0.31/v0.31.1/v0.31.1-main.md"

WORKLOG_TEMPLATE = """# v0.31.1 main worklog

### 2026-06-08

- 2026-06-08: 0.31.1-W8-040 完成 -- 既有記錄

---
"""

# fork 模式必需（同 test_lifecycle_race.py）：spawn 下 monkeypatch/patch
# state 不傳遞至 child，會 false GREEN。
pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="fork-based 併發測試；Windows 無 fork，改由單元測試層覆蓋。",
)


@pytest.fixture(scope="module", autouse=True)
def _force_fork_mode():
    try:
        mp.set_start_method("fork", force=True)
    except RuntimeError:
        pass
    current = mp.get_start_method()
    assert current == "fork", (
        f"fork mode required; current={current!r}. "
        f"spawn 模式下 patch 不傳遞至 child，會 false GREEN"
    )


def _setup_worklog(root: Path) -> Path:
    worklog = root / WORKLOG_REL
    worklog.parent.mkdir(parents=True, exist_ok=True)
    worklog.write_text(WORKLOG_TEMPLATE, encoding="utf-8")
    return worklog


def _count_lines_for(worklog: Path, ticket_id: str) -> int:
    content = worklog.read_text(encoding="utf-8")
    return sum(1 for line in content.splitlines() if f"{ticket_id} 完成" in line)


# ============================================================
# Worker（module top-level；fork 繼承 patch）
# ============================================================

def _worker_append(args) -> bool:
    """並發呼叫 append_worklog_progress。回傳是否無例外完成。"""
    version, ticket_id, title, root = args
    import io
    from unittest.mock import patch

    saved = sys.stdout
    sys.stdout = io.StringIO()
    try:
        from ticket_system.lib import worklog_appender as wa

        with patch.object(wa, "get_ticket_state_root", return_value=root):
            wa.append_worklog_progress(version, ticket_id, title)
        return True
    except Exception:
        return False
    finally:
        sys.stdout = saved


# ============================================================
# Tests
# ============================================================


class TestWorklogAppendConcurrency:
    """N 個 process 併發 append 不同 ticket → 全部進度行皆完整落地。"""

    def test_concurrent_append_distinct_tickets_no_lost_update(self, tmp_path):
        root = tmp_path
        N = 10
        N_ROUNDS = 3

        for round_idx in range(N_ROUNDS):
            worklog = _setup_worklog(root)

            args = [
                ("0.31.1", f"0.31.1-W8-{200 + round_idx * 100 + i}", f"round{round_idx}-t{i}", root)
                for i in range(N)
            ]
            with mp.Pool(N) as pool:
                results = pool.map(_worker_append, args)

            assert all(results), f"round {round_idx}: 部分 worker 例外退出，results={results}"

            missing = [
                tid for (_v, tid, _t, _r) in args
                if _count_lines_for(worklog, tid) != 1
            ]
            assert not missing, (
                f"round {round_idx}: lost update 偵測——以下 ticket 的進度行缺失或"
                f"重複（應恰為 1 行）: {missing}。無 flock 保護時，後寫 process 以"
                f"自己讀到的舊內容覆寫檔案，會使先寫 process 剛插入的行消失。"
            )

    def test_concurrent_append_same_ticket_stays_idempotent(self, tmp_path):
        """N 個 process 併發對同一 ticket_id 重複呼叫 → 仍只有 1 行（冪等性
        在鎖保護下亦不因併發而破壞，鎖內完成的存在性檢查看到彼此的寫入結果）。
        """
        root = tmp_path
        worklog = _setup_worklog(root)
        N = 8
        ticket_id = "0.31.1-W8-999"

        args = [("0.31.1", ticket_id, f"attempt{i}", root) for i in range(N)]
        with mp.Pool(N) as pool:
            results = pool.map(_worker_append, args)

        assert all(results)
        assert _count_lines_for(worklog, ticket_id) == 1
