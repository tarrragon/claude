"""0.4.1-W3-002: DispatchRecommender REGISTRY_PATH 死路徑修復回歸測試。

來源: 0.4.1-W2-009 Solution「重要發現」——REGISTRY_PATH 以 __file__ 相對推算，
解析到 `.claude/skills/ticket/agents/registry.yaml`（不存在），使
DispatchRecommender.agents 恆為空字典，recommend() 恆回傳 []。

測試覆蓋:
1. 預設建構（未傳 registry_path）時，agents 依真實 `.claude/agents/registry.yaml`
   載入且非空（acceptance 1）。
2. registry_path 解析對 CLAUDE_PROJECT_DIR 變動敏感（驗證走 get_project_root()
   而非 import-time 固定路徑）。
3. 顯式傳入 registry_path 時沿用舊行為（向後相容）。
"""
from __future__ import annotations

from pathlib import Path

from ticket_system.lib.dispatch_recommender import DispatchRecommender


def test_default_registry_path_loads_real_registry_agents_non_empty(real_repo_root):
    """acceptance 1: 未指定 registry_path 時，agents 依真實 registry.yaml 載入且非空。"""
    recommender = DispatchRecommender()
    assert recommender.agents != {}
    assert "parsley-flutter-developer" in recommender.agents


def test_registry_path_resolution_follows_claude_project_dir(tmp_path, monkeypatch):
    """registry_path 解析必須走 get_project_root()，對 CLAUDE_PROJECT_DIR 變動敏感。"""
    fake_root = tmp_path / "fake-project"
    registry_dir = fake_root / ".claude" / "agents"
    registry_dir.mkdir(parents=True)
    (registry_dir / "registry.yaml").write_text(
        "schema_version: \"1.0\"\n"
        "agents:\n"
        "  fake-agent:\n"
        "    tdd_phases:\n"
        "      - \"phase3b\"\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(fake_root))

    recommender = DispatchRecommender()

    assert recommender.agents == {"fake-agent": {"tdd_phases": ["phase3b"]}}


def test_cinnamon_tdd_phases_aligned_with_tdd_phases_convention(real_repo_root):
    """acceptance 3 佐證：cinnamon-refactor-owl 的 tdd_phases 使用 TDD_PHASES 慣例值
    "phase4"（tdd_sequence.PHASE_LABELS / ticket_generator._TDD_STAGE_MAP 皆只用
    "phase4"，"phase4a"/"phase4b"/"phase4c" 僅為 TDD_PHASE_DISPLAY 的顯示標籤），
    使 tdd_phase_inference 比對 ticket tdd_stage 時可命中，不再恆為 None。"""
    recommender = DispatchRecommender()
    assert recommender.agents["cinnamon-refactor-owl"]["tdd_phases"] == ["phase4"]


def test_explicit_registry_path_still_supported(tmp_path):
    """顯式傳入 registry_path 時沿用舊行為（向後相容既有呼叫端）。"""
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(
        "schema_version: \"1.0\"\nagents:\n  explicit-agent:\n    tdd_phases: []\n",
        encoding="utf-8",
    )

    recommender = DispatchRecommender(registry_path=registry_path)

    assert recommender.agents == {"explicit-agent": {"tdd_phases": []}}
