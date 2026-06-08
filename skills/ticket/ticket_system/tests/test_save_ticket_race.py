"""Phase 2 RED v2 — update_* race condition regression tests.

對應 ticket 0.18.0-W14-042（修正版 Phase 1 spec，saffron 重評後）。

設計變更（v1 → v2）：
-----------------------
v1 RED 失效根因：lock 注入 `save_ticket()` 是錯誤設計。`save_ticket` 的 single
`f.write(content)` 對小 content 已 effectively atomic（OS-level），測試僅 1/7 真紅。

v2 修正：真正 race 發生在 `update_parent_children` / `update_source_spawned_tickets`
的 load → modify → save 三步驟序列（logical read-modify-write）。本測試模擬該層級
race，預期無 lock 時 lost rate ≥ 50%。

對應 spec：Solution「Phase 1 修正版」場景 1/4，acceptance A2-1 / A2-4。
"""

from __future__ import annotations

import inspect
import multiprocessing as mp
import os
import signal
import time
from pathlib import Path
from typing import Tuple

import pytest

from ticket_system.lib import parser, ticket_builder
from ticket_system.lib.parser import parse_frontmatter


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture(scope="module", autouse=True)
def _force_fork_mode():
    """macOS Python 3.13 預設 spawn，顯式切回 fork 以共享 monkeypatch state。

    防護：若無法切到 fork（已 init 過且當前非 fork），必須 fail-fast。
    spawn 模式下 child process 不繼承 monkeypatch 狀態，會導致 race
    regression 測試讀到真實 ticket dir、誤判通過（false GREEN）。
    """
    try:
        mp.set_start_method("fork", force=True)
    except RuntimeError:
        # 已被 init 過：若當前已是 fork 則正常通過；否則 fail-fast
        pass
    current = mp.get_start_method()
    assert current == "fork", (
        f"fork mode required for race tests; current start method = {current!r}. "
        f"spawn/forkserver would yield FALSE GREEN due to process state isolation "
        f"(monkeypatch on ticket_builder.get_ticket_path / load_ticket would not "
        f"propagate to child processes, so workers would touch real ticket dir "
        f"or fail to import the patched paths)."
    )


@pytest.fixture
def tmp_ticket_dir(tmp_path: Path) -> Path:
    d = tmp_path / "tickets"
    d.mkdir()
    return d


def _write_ticket(path: Path, tid: str, *, children=None, spawned=None) -> None:
    """以最小合法 frontmatter 建立 ticket md 檔。"""
    lines = ["---"]
    lines.append(f"id: {tid}")
    lines.append("title: race target")
    lines.append("status: pending")
    lines.append(f"children: {children if children is not None else []}")
    lines.append(f"spawned_tickets: {spawned if spawned is not None else []}")
    lines.append("---")
    lines.append("")
    lines.append("body")
    path.write_text("\n".join(lines), encoding="utf-8")


@pytest.fixture
def parent_ticket(tmp_ticket_dir: Path) -> Tuple[str, Path]:
    """建立一個 parent ticket，回傳 (id, path)。"""
    tid = "0.0.0-W0-PARENT"
    path = tmp_ticket_dir / f"{tid}.md"
    _write_ticket(path, tid, children=[])
    return tid, path


@pytest.fixture
def source_ticket(tmp_ticket_dir: Path) -> Tuple[str, Path]:
    """建立一個 source ticket，回傳 (id, path)。"""
    tid = "0.0.0-W0-SOURCE"
    path = tmp_ticket_dir / f"{tid}.md"
    _write_ticket(path, tid, spawned=[])
    return tid, path


@pytest.fixture
def patch_ticket_paths(tmp_ticket_dir: Path, monkeypatch):
    """重導 update_* 內部的 get_ticket_path / load_ticket 至 tmp dir。

    fork 模式下 child 繼承 parent 的 monkeypatch 狀態，故只需在主 process patch。
    """
    def _fake_get_ticket_path(version: str, ticket_id: str) -> Path:
        return tmp_ticket_dir / f"{ticket_id}.md"

    def _fake_load_ticket(version: str, ticket_id: str):
        path = tmp_ticket_dir / f"{ticket_id}.md"
        if not path.exists():
            return None
        content = path.read_text(encoding="utf-8")
        try:
            fm, body = parse_frontmatter(content)
        except Exception:
            return None
        if not fm:
            return None
        fm["_body"] = body
        fm["_path"] = str(path)
        return fm

    # Patch 在 ticket_builder 模組命名空間（update_* 內部解析的目標）
    monkeypatch.setattr(ticket_builder, "get_ticket_path", _fake_get_ticket_path)
    monkeypatch.setattr(ticket_builder, "load_ticket", _fake_load_ticket)

    # extract_version_from_ticket_id 對 "0.0.0-W0-PARENT" 需能回傳 "0.0.0"
    # 真實函式應已支援；若失敗測試會直接顯示
    return _fake_get_ticket_path, _fake_load_ticket


# ============================================================
# Multiprocessing workers（module top-level，fork 可直接繼承 patch）
# ============================================================

def _worker_update_parent(args):
    """並發呼叫 update_parent_children。"""
    parent_id, child_id = args
    return ticket_builder.update_parent_children("0.0.0", parent_id, child_id)


def _worker_update_source(args):
    """並發呼叫 update_source_spawned_tickets。"""
    source_id, new_id = args
    return ticket_builder.update_source_spawned_tickets(source_id, new_id)


def _read_list_field(path: Path, field: str) -> list:
    """直接從 md frontmatter 讀取 list 欄位（旁路 load_ticket 快取）。"""
    content = path.read_text(encoding="utf-8")
    fm, _ = parse_frontmatter(content)
    return list(fm.get(field, []) or [])


# ============================================================
# Tests — 真正 RED：模擬 update_* race
# ============================================================

class TestUpdateParentChildrenRace:
    """場景 1 / A2-1：N=20 並行 update_parent_children，0 lost update。"""

    def test_concurrent_append_no_lost_update(
        self, parent_ticket, patch_ticket_paths
    ):
        parent_id, parent_path = parent_ticket
        N = 20
        N_ROUNDS = 3  # 重複多輪累積 lost rate 樣本

        total_expected = 0
        total_actual_sum = 0
        round_results = []

        for round_idx in range(N_ROUNDS):
            # 每輪重置 children=[]
            _write_ticket(parent_path, parent_id, children=[])

            # 清 process-scoped cache（避免主 process 殘留）
            try:
                parser._ticket_cache.clear()
            except Exception:
                pass

            child_ids = [f"0.0.0-W0-CHILD-{round_idx}-{i:02d}" for i in range(N)]
            args = [(parent_id, cid) for cid in child_ids]

            with mp.Pool(N) as pool:
                results = pool.map(_worker_update_parent, args)

            # 成功 writers：returned True；失敗（False）也是 race 訊號
            # （load_ticket 讀到部分寫入時回 None → update_* 回 False）
            successful_ids = [cid for cid, ok in zip(child_ids, results) if ok]

            final_children = _read_list_field(parent_path, "children")
            unique = set(final_children)
            # 計算 lost update：成功宣稱寫入 (return True) 但最終 children 缺失
            missing = set(successful_ids) - unique

            round_results.append({
                "expected_among_successful": len(successful_ids),
                "actual": len(unique),
                "missing": sorted(missing),
                "returned_false_count": results.count(False),
            })
            total_expected += len(successful_ids)
            total_actual_sum += len(unique & set(successful_ids))

        lost_total = total_expected - total_actual_sum
        lost_rate = lost_total / total_expected if total_expected else 0.0

        # 預期 RED：無 lock 時 lost_rate > 0（W14-005 重現實驗 ~66.5%）
        assert lost_total == 0, (
            f"LOST UPDATE detected (update_parent_children race):\n"
            f"  total_expected={total_expected} total_actual={total_actual_sum}\n"
            f"  lost_total={lost_total} lost_rate={lost_rate*100:.1f}%\n"
            f"  per-round details: {round_results}"
        )


class TestUpdateSourceSpawnedRace:
    """場景 4 / A2-4：N=20 並行 update_source_spawned_tickets，0 lost update。"""

    def test_concurrent_append_no_lost_update(
        self, source_ticket, patch_ticket_paths
    ):
        source_id, source_path = source_ticket
        N = 20
        N_ROUNDS = 3

        total_expected = 0
        total_actual_sum = 0
        round_results = []

        for round_idx in range(N_ROUNDS):
            _write_ticket(source_path, source_id, spawned=[])

            try:
                parser._ticket_cache.clear()
            except Exception:
                pass

            spawned_ids = [f"0.0.0-W0-SPAWN-{round_idx}-{i:02d}" for i in range(N)]
            args = [(source_id, sid) for sid in spawned_ids]

            with mp.Pool(N) as pool:
                results = pool.map(_worker_update_source, args)

            successful_ids = [sid for sid, ok in zip(spawned_ids, results) if ok]

            final_spawned = _read_list_field(source_path, "spawned_tickets")
            unique = set(final_spawned)
            missing = set(successful_ids) - unique

            round_results.append({
                "expected_among_successful": len(successful_ids),
                "actual": len(unique),
                "missing": sorted(missing),
                "returned_false_count": results.count(False),
            })
            total_expected += len(successful_ids)
            total_actual_sum += len(unique & set(successful_ids))

        lost_total = total_expected - total_actual_sum
        lost_rate = lost_total / total_expected if total_expected else 0.0

        assert lost_total == 0, (
            f"LOST UPDATE detected (update_source_spawned_tickets race):\n"
            f"  total_expected={total_expected} total_actual={total_actual_sum}\n"
            f"  lost_total={lost_total} lost_rate={lost_rate*100:.1f}%\n"
            f"  per-round details: {round_results}"
        )


# ============================================================
# 配置型測試（保留 v1 中仍有效項：.gitignore、signature）
# ============================================================

class TestConfiguration:
    """配置層 acceptance（A1 / A4）：與 race 行為解耦的契約檢查。"""

    def test_gitignore_contains_lock_pattern(self):
        """A4: .gitignore 含 generic *.lock pattern。"""
        project_root = Path(parser.__file__).resolve().parents[5]
        gitignore = project_root / ".gitignore"
        assert gitignore.exists(), f"gitignore not found at {gitignore}"
        content = gitignore.read_text(encoding="utf-8")
        import re
        m = re.search(r"^\*+(?:/\*+)?\.lock\s*$", content, re.MULTILINE)
        assert m is not None, ".gitignore missing generic *.lock pattern"

    def test_save_ticket_signature_unchanged(self):
        """A1: save_ticket signature 不變（修正版 spec 不改 save_ticket）。"""
        sig = inspect.signature(parser.save_ticket)
        params = list(sig.parameters.keys())
        assert params[:2] == ["ticket", "ticket_path"], \
            f"signature changed: {params}"

    def test_update_parent_children_signature_unchanged(self):
        """update_parent_children signature 不變（lock 注入應對 caller 透明）。"""
        sig = inspect.signature(ticket_builder.update_parent_children)
        params = list(sig.parameters.keys())
        assert params == ["version", "parent_id", "child_id"], \
            f"signature changed: {params}"

    def test_update_source_spawned_signature_unchanged(self):
        """update_source_spawned_tickets signature 不變。"""
        sig = inspect.signature(ticket_builder.update_source_spawned_tickets)
        params = list(sig.parameters.keys())
        assert params == ["source_ticket_id", "new_ticket_id"], \
            f"signature changed: {params}"
