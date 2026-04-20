"""Group E：效能測試（AC6 <100ms）。

Phase 2 §3 Group E / Phase 3a §5：
- E1: 真實 tmp git repo end-to-end 執行 30 次，中位 <100ms + p95 <150ms

thyme 先前實測 5 個 subprocess 序列中位 52ms / p95 84ms，應寬鬆通過。

Phase 4 TD1：use_cache 參數本體已刪除（YAGNI），原 E2 接口一致性測試移除。
"""

from __future__ import annotations

import statistics
import subprocess
import time
from pathlib import Path

import pytest

from ticket_system.lib.checkpoint_state import CheckpointState, checkpoint_state


# ---------------------------------------------------------------------------
# E helper：建立真實 tmp git repo + 多個未提交檔
# ---------------------------------------------------------------------------


def _seed_uncommitted_files(repo: Path, count: int = 5) -> None:
    for i in range(count):
        (repo / f"dirty{i}.txt").write_text(f"content {i}\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# E1：中位 <100ms + p95 <150ms
# ---------------------------------------------------------------------------


def test_E1_checkpoint_state_performance_median_under_100ms(
    tmp_git_repo: Path, mock_ticket_query, mock_dispatch_active, mock_handoff_pending,
):
    """真實 subprocess（git）+ mock ticket CLI：中位 <100ms + p95 <150ms。"""
    _seed_uncommitted_files(tmp_git_repo, count=10)
    mock_dispatch_active(active_count=2, completed_count=1, project_root=tmp_git_repo)
    mock_handoff_pending(ticket_id="W10-017.8", project_root=tmp_git_repo)
    mock_ticket_query(ids=["A", "B", "C"])

    n_runs = 30  # sample size 足以取 median / p95，且 CI 不太慢
    durations_ms: list[float] = []
    for _ in range(n_runs):
        start = time.perf_counter()
        state = checkpoint_state(
            ticket_id="W10-017.8",
            log_metrics=False,  # 避免 log I/O 污染量測
            caller="perf-test",
            project_root=tmp_git_repo,
        )
        durations_ms.append((time.perf_counter() - start) * 1000.0)
        assert isinstance(state, CheckpointState)

    median = statistics.median(durations_ms)
    p95 = sorted(durations_ms)[int(0.95 * n_runs) - 1]

    # 寬鬆 assertion：中位 <100ms 為硬 AC；p95 <150ms 為 sage §E1 目標
    assert median < 100.0, (
        f"中位 {median:.2f}ms 超過 AC6 100ms 閾值（樣本: {durations_ms}）"
    )
    assert p95 < 150.0, (
        f"p95 {p95:.2f}ms 超過 sage §E1 150ms 目標（樣本: {durations_ms}）"
    )


# E2 已移除：Phase 4 TD1 刪除 use_cache 參數本體（YAGNI）
