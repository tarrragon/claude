"""ticket create ID 分配並行 race 防護（IMP-072 方案 A，1.0.0-W1-063）。

來源 Ticket
-----------
1.0.0-W1-063（IMP）：ticket create 的「ID 分配（get_next_seq 掃描 max+1）→
落盤（save_ticket）」之間無鎖，跨 process / 跨 session 並行 create 同讀相同
max seq 配出同一 ID，後寫者靜默覆寫前者（IMP-072，2026-06-11 單日 2 次撞號：
W1-057/W1-059）。

修復設計（指導本測試斷言）
--------------------------
1. lib/file_lock.py 新增 create_id_allocation_lock(tickets_dir)：目錄級
   fcntl.LOCK_EX blocking lock，lock file 為 {tickets_dir}/.ticket-create.lock。
2. create.execute 將 Step 1（ID 分配）至 Step 3（落盤）包進臨界區；
   bulk_create.execute 非 dry_run 路徑同樣持鎖。
3. graceful degradation：無 fcntl 平台 / lock file 開啟失敗 / flock 失敗時
   warn（stderr，quality-baseline 規則 4）後以無鎖模式續行，不阻斷單
   process create。

測試策略
--------
race 測試沿用 test_lifecycle_race.py 慣例：mp fork mode + module top-level
worker。worker 重現 create 臨界區的真實組成（get_next_seq 真實掃描 + 落盤），
並在「分配 ID」與「落盤」之間插入人工 delay 放大撞號時間窗——無鎖時此序列
必然撞號（所有 worker 同讀 max 配同一 ID），有鎖時序列化為各自獨立 ID。
"""

from __future__ import annotations

import multiprocessing as mp
import sys
import time
from pathlib import Path
from typing import List

import pytest

from ticket_system.lib import ticket_builder
from ticket_system.lib.file_lock import (
    CREATE_LOCK_FILENAME,
    create_id_allocation_lock,
)

# W9-005 / issue #1 問題6：fork mode 共享 monkeypatch state（spawn 下不傳遞至
# child 會 false GREEN）。Windows 無 fork，故 win32 整檔 skip（create lock
# 跨平台正確性已由 test_lock_open_failure / test_single_process 等覆蓋）。
pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="fork-based race test；Windows 無 fork，monkeypatch 不傳遞至 spawn child",
)


@pytest.fixture(scope="module", autouse=True)
def _force_fork_mode():
    """macOS Python 3.13 預設 spawn，顯式切回 fork 以共享 monkeypatch state。"""
    try:
        mp.set_start_method("fork", force=True)
    except RuntimeError:
        pass
    current = mp.get_start_method()
    assert current == "fork", (
        f"fork mode required; current={current!r}. "
        f"spawn 模式下 monkeypatch 不傳遞至 child，會 false GREEN"
    )


@pytest.fixture
def tickets_dir(tmp_path: Path) -> Path:
    d = tmp_path / "tickets"
    d.mkdir()
    return d


def _write_seed_ticket(tickets_dir: Path, ticket_id: str) -> None:
    """預置既有 ticket，使 get_next_seq 走正常路徑（local glob 非空，
    不觸發兩來源掃空的降級分支警告，聚焦 race 本身）。"""
    (tickets_dir / f"{ticket_id}.md").write_text(
        f"---\nid: {ticket_id}\ntitle: seed\ntype: IMP\nstatus: pending\n---\n\n# Body\n",
        encoding="utf-8",
    )


# ============================================================
# Worker（module top-level；fork 繼承 monkeypatch state）
# ============================================================

_VERSION = "0.0.0"
_WAVE = 1
# 「分配 ID → 落盤」之間的人工 delay：放大臨界區時間窗，使無鎖版本必然撞號
# （所有 worker 在彼此落盤前完成掃描，同讀 max 配同一 ID）。
_RACE_WINDOW_SECONDS = 0.15


def _allocate_and_persist(tickets_dir: Path) -> str:
    """create 臨界區的最小重現：真實 get_next_seq 掃描 + delay + 落盤。"""
    seq = ticket_builder.get_next_seq(_VERSION, _WAVE)
    time.sleep(_RACE_WINDOW_SECONDS)
    ticket_id = f"{_VERSION}-W{_WAVE}-{seq:03d}"
    path = tickets_dir / f"{ticket_id}.md"
    path.write_text(
        f"---\nid: {ticket_id}\ntitle: worker\ntype: IMP\nstatus: pending\n---\n"
        f"\n# Body of {ticket_id}\n",
        encoding="utf-8",
    )
    return ticket_id


def _worker_create_with_lock(tickets_dir_str: str) -> str:
    """並行 worker：持 create_id_allocation_lock 執行「分配 → 落盤」序列。"""
    tickets_dir = Path(tickets_dir_str)
    with create_id_allocation_lock(tickets_dir):
        return _allocate_and_persist(tickets_dir)


# ============================================================
# Tests：並行 create 不撞號（acceptance 1）
# ============================================================

class TestParallelCreateNoCollision:
    """N 並行 create 臨界區 → N 個互異 ID，無覆寫。"""

    def test_parallel_creates_allocate_distinct_ids(
        self, tickets_dir: Path, monkeypatch
    ):
        # get_next_seq 內部經 get_tickets_dir 解析路徑、list_ticket_files_from_main
        # 掃 main ref；皆重導至 tmp / 停用，使掃描來源只剩本地 glob（聚焦 race）。
        monkeypatch.setattr(
            ticket_builder, "get_tickets_dir", lambda v: tickets_dir
        )
        monkeypatch.setattr(
            ticket_builder, "list_ticket_files_from_main", lambda v: []
        )
        _write_seed_ticket(tickets_dir, f"{_VERSION}-W{_WAVE}-001")

        N = 4
        with mp.Pool(N) as pool:
            allocated_ids: List[str] = pool.map(
                _worker_create_with_lock, [str(tickets_dir)] * N
            )

        # 核心斷言 1：所有 worker 分配到互異 ID（無鎖時必同讀 max=1 而全配 002）
        assert len(set(allocated_ids)) == N, (
            f"並行 create 撞號：allocated_ids={allocated_ids}。"
            f"重複 ID 表示「分配 → 落盤」臨界區未被序列化（IMP-072）"
        )

        # 核心斷言 2：檔案系統有 seed + N 個檔（無覆寫遺失）
        md_files = sorted(p.name for p in tickets_dir.glob("*.md"))
        assert len(md_files) == N + 1, (
            f"預期 {N + 1} 個 .md（seed + {N} workers），實得 {md_files}。"
            f"檔案數不足表示後寫者覆寫了前者"
        )

        # 核心斷言 3：每個 worker 的內容落在自己的 ID 檔內（內容歸屬正確）
        for ticket_id in allocated_ids:
            content = (tickets_dir / f"{ticket_id}.md").read_text(encoding="utf-8")
            assert f"# Body of {ticket_id}" in content, (
                f"{ticket_id}.md 內容歸屬錯誤（被其他 worker 覆寫）"
            )

    def test_lock_file_created_at_expected_path(self, tickets_dir: Path):
        with create_id_allocation_lock(tickets_dir):
            assert (tickets_dir / CREATE_LOCK_FILENAME).exists(), (
                "lock file 未建立於 {tickets_dir}/.ticket-create.lock"
            )


# ============================================================
# Tests：graceful degradation（acceptance 2）
# ============================================================

class TestGracefulDegradation:
    """lock 失敗時 warn + 無鎖續行，不阻斷單 process create。"""

    # 註（W9-001）：原 test_no_fcntl_platform_degrades_with_warning 已移除。
    # 該測試 monkeypatch file_lock._HAS_FCNTL=False 以模擬「Windows 無 fcntl →
    # 無鎖降級」。改用跨平台 filelock 後，Windows 亦取得有效鎖，「無 fcntl
    # 平台」場景不復存在（_HAS_FCNTL 符號亦移除），故該測試前提失效而移除。
    # 真正的環境異常降級（lock file 無法建立）仍由下方
    # test_lock_open_failure_degrades_with_warning 覆蓋。

    def test_lock_open_failure_degrades_with_warning(
        self, tmp_path: Path, monkeypatch, capsys
    ):
        """lock file 開啟失敗（tickets_dir 路徑被檔案佔據 → mkdir OSError）：
        warn 後無鎖續行。"""
        blocked_dir = tmp_path / "not-a-dir"
        blocked_dir.write_text("occupied", encoding="utf-8")

        executed = False
        with create_id_allocation_lock(blocked_dir):
            executed = True

        assert executed, "lock file 開啟失敗時必須降級續行"
        captured = capsys.readouterr()
        assert "lock file 開啟失敗" in captured.err

    def test_single_process_create_unaffected(self, tickets_dir: Path, monkeypatch):
        """單 process 序列執行兩次臨界區：lock 正常取得/釋放，ID 遞增不撞。"""
        monkeypatch.setattr(
            ticket_builder, "get_tickets_dir", lambda v: tickets_dir
        )
        monkeypatch.setattr(
            ticket_builder, "list_ticket_files_from_main", lambda v: []
        )
        _write_seed_ticket(tickets_dir, f"{_VERSION}-W{_WAVE}-001")

        first = _worker_create_with_lock(str(tickets_dir))
        second = _worker_create_with_lock(str(tickets_dir))

        assert first == f"{_VERSION}-W{_WAVE}-002"
        assert second == f"{_VERSION}-W{_WAVE}-003"
