"""0.4.1-W2-009: claim --as 自動推導 tdd_phase 接線（整合測試）。

來源: 0.4.1-W2-004 ANA 結論——tdd_phase 推進機制存在但不在熱路徑，
0.4.0 十八票零呼叫。本測試驗證 claim --as 接上 registry agent -> tdd_phases
對應後，tdd_phase 會依 agent 身份自動推進；且 `ticket track phase` 手動
設定過的值不被 claim 重置。

測試覆蓋:
1. claim --as fennel-go-developer -> 自動寫入 phase3b（acceptance 1）
2. tdd_phase_source == manual 時，claim --as 不覆蓋 tdd_phase（acceptance 2）
3. agent 在 registry 無 tdd_phases 對應 -> 靜默略過，tdd_phase 不變
4. 裸 claim（無 --as）-> tdd_phase 不變（向後相容）
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List

import pytest

from ticket_system.lib import ticket_loader
from ticket_system.lib.parser import parse_frontmatter


@pytest.fixture
def tmp_ticket_dir(tmp_path: Path) -> Path:
    d = tmp_path / "tickets"
    d.mkdir()
    return d


def _write_registry(mapping: dict) -> None:
    """在 _isolate_project_root 注入的 CLAUDE_PROJECT_DIR 下寫入最小 registry.yaml。"""
    project_root = Path(os.environ["CLAUDE_PROJECT_DIR"])
    registry_path = project_root / ".claude" / "agents" / "registry.yaml"
    registry_path.parent.mkdir(parents=True, exist_ok=True)

    lines = ["schema_version: \"1.0\"", "agents:"]
    for agent, phases in mapping.items():
        lines.append(f"  {agent}:")
        lines.append("    tdd_phases:")
        for phase in phases:
            lines.append(f"      - \"{phase}\"")
    registry_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_pending_ticket(
    path: Path,
    tid: str,
    tdd_phase: str = "phase1",
    tdd_stage: List[str] | None = None,
    tdd_phase_source_line: str = "",
) -> None:
    stage = tdd_stage if tdd_stage is not None else [
        "phase1",
        "phase2",
        "phase3a",
        "phase3b",
        "phase4",
    ]
    stage_lines = ["tdd_stage:"] + [f"  - {p}" for p in stage]
    lines = [
        "---",
        f"id: {tid}",
        "title: claim tdd_phase auto-infer target",
        "type: IMP",
        "status: pending",
        "assigned: false",
        "started_at: null",
        "acceptance: []",
        f"tdd_phase: {tdd_phase}",
        *stage_lines,
        "children: []",
        "blockedBy: []",
        "who:",
        "  current: pending",
        "  history: {}",
    ]
    if tdd_phase_source_line:
        lines.append(tdd_phase_source_line)
    lines += ["---", "", "body"]
    path.write_text("\n".join(lines), encoding="utf-8")


@pytest.fixture
def patch_ticket_paths(tmp_ticket_dir: Path, monkeypatch):
    """重導 lifecycle / ticket_ops 的 path/load 至 tmp dir（仿 test_claim_as_sets_who）。"""
    from ticket_system.commands import lifecycle as lifecycle_mod
    from ticket_system.lib import ticket_ops

    def _fake_get_ticket_path(version: str, ticket_id: str) -> Path:
        return tmp_ticket_dir / f"{ticket_id}.md"

    def _fake_load_ticket(version: str, ticket_id: str):
        path = tmp_ticket_dir / f"{ticket_id}.md"
        if not path.exists():
            return None
        try:
            fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        if not fm:
            return None
        fm["_body"] = body
        fm["_path"] = str(path)
        return fm

    monkeypatch.setattr(ticket_loader, "get_ticket_path", _fake_get_ticket_path)
    monkeypatch.setattr(ticket_loader, "load_ticket", _fake_load_ticket)
    monkeypatch.setattr(lifecycle_mod, "get_ticket_path", _fake_get_ticket_path)
    monkeypatch.setattr(lifecycle_mod, "load_ticket", _fake_load_ticket)
    monkeypatch.setattr(ticket_ops, "load_ticket", _fake_load_ticket)
    monkeypatch.setattr(ticket_ops, "get_ticket_path", _fake_get_ticket_path)


def _read_frontmatter(path: Path) -> dict:
    fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    return fm


def _claim(tid: str, as_agent=None) -> int:
    from ticket_system.commands.lifecycle import TicketLifecycle

    return TicketLifecycle("0.0.0").claim(tid, as_agent=as_agent)


def test_claim_as_fennel_go_developer_writes_phase3b(
    tmp_ticket_dir: Path, patch_ticket_paths
):
    """acceptance 1: claim --as fennel-go-developer 自動寫入 phase3b。"""
    _write_registry({"fennel-go-developer": ["phase3b"]})

    tid = "0.0.0-W0-TDDPHASE1"
    path = tmp_ticket_dir / f"{tid}.md"
    _write_pending_ticket(path, tid, tdd_phase="phase1")

    assert _claim(tid, as_agent="fennel-go-developer") == 0

    fm = _read_frontmatter(path)
    assert fm["tdd_phase"] == "phase3b"
    assert fm["tdd_phase_source"] == "auto"


def test_manual_tdd_phase_not_reset_by_claim(tmp_ticket_dir: Path, patch_ticket_paths):
    """acceptance 2: phase 子命令（tdd_phase_source=manual）設定過的值不被 claim 重置。"""
    _write_registry({"fennel-go-developer": ["phase3b"]})

    tid = "0.0.0-W0-TDDPHASE2"
    path = tmp_ticket_dir / f"{tid}.md"
    _write_pending_ticket(
        path,
        tid,
        tdd_phase="phase2",
        tdd_phase_source_line="tdd_phase_source: manual",
    )

    assert _claim(tid, as_agent="fennel-go-developer") == 0

    fm = _read_frontmatter(path)
    assert fm["tdd_phase"] == "phase2"
    assert fm["tdd_phase_source"] == "manual"


def test_agent_without_registry_mapping_leaves_tdd_phase_unchanged(
    tmp_ticket_dir: Path, patch_ticket_paths
):
    """agent 在 registry 無 tdd_phases 對應時，靜默略過，tdd_phase 不變。"""
    _write_registry({"fennel-go-developer": ["phase3b"]})

    tid = "0.0.0-W0-TDDPHASE3"
    path = tmp_ticket_dir / f"{tid}.md"
    _write_pending_ticket(path, tid, tdd_phase="phase1")

    assert _claim(tid, as_agent="unregistered-agent") == 0

    fm = _read_frontmatter(path)
    assert fm["tdd_phase"] == "phase1"
    assert fm.get("tdd_phase_source") is None


def test_bare_claim_does_not_touch_tdd_phase(tmp_ticket_dir: Path, patch_ticket_paths):
    """裸 claim（無 --as）-> tdd_phase 不變（向後相容）。"""
    _write_registry({"fennel-go-developer": ["phase3b"]})

    tid = "0.0.0-W0-TDDPHASE4"
    path = tmp_ticket_dir / f"{tid}.md"
    _write_pending_ticket(path, tid, tdd_phase="phase1")

    assert _claim(tid, as_agent=None) == 0

    fm = _read_frontmatter(path)
    assert fm["tdd_phase"] == "phase1"
    assert fm.get("tdd_phase_source") is None


def test_claim_as_fennel_go_developer_writes_phase3b_using_real_registry(
    tmp_ticket_dir: Path, patch_ticket_paths, real_repo_root
):
    """0.4.1-W3-002 acceptance 2: 用真實 `.claude/agents/registry.yaml`（非測試自寫
    的假 registry）驗證 fennel-go-developer -> phase3b 對應確實落地於實際設定檔。"""
    tid = "0.0.0-W0-TDDPHASE5"
    path = tmp_ticket_dir / f"{tid}.md"
    _write_pending_ticket(path, tid, tdd_phase="phase1")

    assert _claim(tid, as_agent="fennel-go-developer") == 0

    fm = _read_frontmatter(path)
    assert fm["tdd_phase"] == "phase3b"
    assert fm["tdd_phase_source"] == "auto"


def test_claim_as_thyme_python_developer_writes_phase3b_using_real_registry(
    tmp_ticket_dir: Path, patch_ticket_paths, real_repo_root
):
    """0.4.1-W3-002 acceptance 2: thyme-python-developer 亦依真實 registry.yaml
    自動寫入 phase3b（實作型代理人補齊驗證）。"""
    tid = "0.0.0-W0-TDDPHASE6"
    path = tmp_ticket_dir / f"{tid}.md"
    _write_pending_ticket(path, tid, tdd_phase="phase1")

    assert _claim(tid, as_agent="thyme-python-developer") == 0

    fm = _read_frontmatter(path)
    assert fm["tdd_phase"] == "phase3b"
    assert fm["tdd_phase_source"] == "auto"
