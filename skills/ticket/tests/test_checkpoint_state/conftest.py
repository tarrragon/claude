"""Group B fixtures：5 層資料來源隔離 + 時間凍結 + metrics log 隔離。

設計依據：Phase 2 §4 Mock 與 Fixture 設計。

Sociable Unit Tests 原則：
- Mock：subprocess.run（git）、檔案系統 I/O（透過 tmp_path）、ticket CLI
- 不 Mock：CheckpointState / PendingCheck / datetime / json / pathlib
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import pytest


# ---------------------------------------------------------------------------
# Fixture 1: tmp_git_repo — 建立真實臨時 git repo
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_git_repo(tmp_path: Path) -> Path:
    """在 tmp_path 建立最小化真實 git repo（clean tree）。

    回傳 repo 根目錄。可由 test case 自行 `git add`/commit/touch 調整狀態。
    """
    subprocess.run(
        ["git", "init", "-q", "-b", "main"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@local"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "test"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    # 建立初始 commit 讓 git status 可正常運作
    (tmp_path / "README.md").write_text("init\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "README.md"], cwd=tmp_path, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-q", "-m", "init"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    return tmp_path


# ---------------------------------------------------------------------------
# Fixture 2: mock_dispatch_active — 建立/清空 dispatch-active.json
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_dispatch_active(tmp_path: Path) -> Callable[..., Path]:
    """工廠 fixture：回傳 writer(active_count=..., completed_count=...) 生成檔。

    用法：
        path = mock_dispatch_active(active_count=2, project_root=tmp_git_repo)

    project_root 未指定時使用 tmp_path。
    """

    def _writer(
        active_count: int = 0,
        completed_count: int = 0,
        project_root: Optional[Path] = None,
        content: Optional[Dict[str, Any]] = None,
    ) -> Path:
        root = project_root or tmp_path
        state_dir = root / ".claude" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        path = state_dir / "dispatch-active.json"

        if content is not None:
            payload = content
        else:
            dispatches: List[Dict[str, Any]] = []
            for i in range(active_count):
                dispatches.append({"id": f"a{i}", "status": "running"})
            for i in range(completed_count):
                dispatches.append({"id": f"c{i}", "status": "completed"})
            payload = {"dispatches": dispatches}

        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    return _writer


# ---------------------------------------------------------------------------
# Fixture 3: mock_handoff_pending — 建立/清空 handoff pending json
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_handoff_pending(tmp_path: Path) -> Callable[..., Path]:
    """工廠 fixture：在 .claude/handoffs/pending/ 產出 json 檔。"""

    def _writer(
        ticket_id: str = "W10-017.8",
        project_root: Optional[Path] = None,
        filename: str = "handoff.json",
        extra: Optional[Dict[str, Any]] = None,
    ) -> Path:
        root = project_root or tmp_path
        pending_dir = root / ".claude" / "handoffs" / "pending"
        pending_dir.mkdir(parents=True, exist_ok=True)
        payload = {"ticket_id": ticket_id, "direction": "to-self"}
        if extra:
            payload.update(extra)
        path = pending_dir / filename
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    return _writer


# ---------------------------------------------------------------------------
# Fixture 4: mock_ticket_query — monkey-patch subprocess.run 的 ticket CLI 分支
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_ticket_query(monkeypatch):
    """工廠 fixture：回傳 setter(ids=[...]) 或 setter(raises=exc) 控制 ticket CLI 行為。

    實作：patch `ticket_system.lib.checkpoint_state` 中的 subprocess.run。
    只攔截 ticket CLI（argv[0] == "ticket"），其他 subprocess 呼叫透傳。
    """

    import ticket_system.lib.checkpoint_state as mod

    real_run = subprocess.run
    state: Dict[str, Any] = {"ids": [], "raises": None}

    def fake_run(cmd, *args, **kwargs):
        if isinstance(cmd, (list, tuple)) and len(cmd) > 0 and cmd[0] == "ticket":
            if state["raises"] is not None:
                raise state["raises"]
            # 模擬 ticket CLI 回傳 JSON list-of-dict
            payload = [{"id": tid} for tid in state["ids"]]
            return subprocess.CompletedProcess(
                args=list(cmd), returncode=0,
                stdout=json.dumps(payload), stderr="",
            )
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    def _setter(
        ids: Optional[List[str]] = None,
        raises: Optional[BaseException] = None,
    ):
        state["ids"] = ids if ids is not None else []
        state["raises"] = raises

    return _setter


# ---------------------------------------------------------------------------
# Fixture 5: mock_metrics_log — 隔離 .claude/logs/pm-automation-metrics.jsonl
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_metrics_log(tmp_path: Path) -> Path:
    """回傳臨時 metrics log 檔案路徑（尚未建立，由 Group D 測試寫入）。"""
    logs_dir = tmp_path / ".claude" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir / "pm-automation-metrics.jsonl"


# ---------------------------------------------------------------------------
# Fixture 6: frozen_time — 凍結 datetime（不依賴 freezegun）
# ---------------------------------------------------------------------------


@pytest.fixture
def frozen_time(monkeypatch) -> str:
    """凍結 checkpoint_state._utc_now_iso 回傳固定 ISO 字串。

    回傳凍結的時間字串，測試可用於斷言。
    """

    import ticket_system.lib.checkpoint_state as mod

    fixed = "2026-04-19T12:00:00+00:00"
    monkeypatch.setattr(mod, "_utc_now_iso", lambda: fixed)
    return fixed
