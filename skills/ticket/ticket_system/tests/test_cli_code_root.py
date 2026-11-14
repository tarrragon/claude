"""get_cli_code_root 與三處讀取點（204.1.4.3）：框架設定取 CLI 程式碼所在 checkout。

情境 A：env=cwd=code checkout；B：未設 env、cwd=code checkout；
C：env=MAIN、cwd=WT，程式碼在 WT（舊版讀 MAIN，程式碼與設定分屬不同 checkout）。
"""
from __future__ import annotations

import pytest

from ticket_system.lib import claude_lib_loader, paths
from ticket_system.lib.dispatch_recommender import DispatchRecommender
from ticket_system.lib.tdd_phase_inference import _load_agent_tdd_phases


def _make_checkout(root, agent):
    (root / ".claude" / "lib").mkdir(parents=True)
    (root / ".claude" / "lib" / "pm_registry.py").write_text("", encoding="utf-8")
    (root / ".claude" / "agents").mkdir(parents=True)
    (root / ".claude" / "agents" / "registry.yaml").write_text(
        f'schema_version: "1.0"\nagents:\n  {agent}:\n    tdd_phases:\n      - "phase3b"\n',
        encoding="utf-8",
    )
    code = root / ".claude" / "skills" / "ticket" / "ticket_system" / "lib"
    code.mkdir(parents=True)
    return code / "paths.py"


@pytest.fixture
def trees(tmp_path):
    main, wt = tmp_path / "main", tmp_path / "wt"
    return main, wt, _make_checkout(main, "main-agent"), _make_checkout(wt, "wt-agent")


def _read_all(agent):
    return (
        set(DispatchRecommender().agents),
        _load_agent_tdd_phases(agent),
        claude_lib_loader.find_claude_dir("pm_registry.py"),
    )


def test_scenario_c_all_three_follow_code_checkout(trees, monkeypatch):
    main, wt, _, wt_code = trees
    monkeypatch.setattr(paths, "_CODE_FILE", wt_code)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(main))
    monkeypatch.chdir(wt)
    agents, phases, claude_dir = _read_all("wt-agent")
    assert agents == {"wt-agent"}
    assert phases == ["phase3b"]
    assert claude_dir == wt / ".claude"
    assert _load_agent_tdd_phases("main-agent") == []


def test_e1_env_and_code_checkout_both_exist_code_wins_old_env_wins(trees, monkeypatch):
    """E1 對照：env 指向 MAIN、程式碼在 WT，兩者皆有 .claude/lib。
    新碼取 code checkout（WT）；舊碼（env 優先）取 MAIN。"""
    main, wt, _, wt_code = trees
    monkeypatch.setattr(paths, "_CODE_FILE", wt_code)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(main))
    monkeypatch.chdir(wt)
    new = claude_lib_loader.find_claude_dir("pm_registry.py")
    old = main / ".claude"  # 舊優先序：env 的 .claude（marker 存在）
    assert (old / "lib" / "pm_registry.py").is_file()
    assert new == wt / ".claude"
    assert new != old


def test_scenario_a_env_equals_code_checkout(trees, monkeypatch):
    main, _, main_code, _ = trees
    monkeypatch.setattr(paths, "_CODE_FILE", main_code)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(main))
    monkeypatch.chdir(main)
    agents, phases, claude_dir = _read_all("main-agent")
    assert (agents, phases, claude_dir) == ({"main-agent"}, ["phase3b"], main / ".claude")


def test_scenario_b_no_env_cwd_in_code_checkout(trees, monkeypatch):
    main, _, main_code, _ = trees
    monkeypatch.setattr(paths, "_CODE_FILE", main_code)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.chdir(main)
    agents, phases, claude_dir = _read_all("main-agent")
    assert (agents, phases, claude_dir) == ({"main-agent"}, ["phase3b"], main / ".claude")


def test_no_checkout_install_falls_back_to_cwd_git_toplevel(tmp_path, monkeypatch):
    """uv tool 安裝副本：__file__ 上方無 .claude/lib，退回 cwd 的 git 頂層。"""
    site = tmp_path / "site" / "ticket_system" / "lib"
    site.mkdir(parents=True)
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(paths, "_CODE_FILE", site / "paths.py")
    monkeypatch.setattr(paths, "_git_toplevel", lambda: repo)
    assert paths.get_cli_code_root() == repo


def test_no_checkout_no_git_falls_back_to_project_root(tmp_path, monkeypatch):
    site = tmp_path / "site" / "lib"
    site.mkdir(parents=True)
    monkeypatch.setattr(paths, "_CODE_FILE", site / "paths.py")
    monkeypatch.setattr(paths, "_git_toplevel", lambda: None)
    monkeypatch.setattr(paths, "get_project_root", lambda: tmp_path / "root")
    assert paths.get_cli_code_root() == tmp_path / "root"
