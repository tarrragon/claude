"""Tests for file-size-guardian-hook 的 Auto-load 預算量測（1.0.0-W7-004.7）。

涵蓋：
- @ 引用解析（行首 / 行內 / 不存在路徑 graceful skip / email 與裝飾器排除）
- 集合收集（CLAUDE.md + rules/core/*.md + @ 引用鏈遞迴一層、去重）
- Token 估算（int(chars / CHARS_PER_TOKEN)，係數引用 hook 常數，1.0.0-W7-006 校準為 1.3）
- 預算內 / 超標兩路徑輸出斷言（含 top 3 體量檔與差值）
- state 檔首次不存在的初始化路徑與後續差值計算
- 失敗安全：量測異常時 stderr 警告 + 不阻擋（quality-baseline 規則 4 雙通道）
"""

from __future__ import annotations

import importlib.util
import json
import logging
from pathlib import Path
from unittest.mock import patch

import pytest

HOOK_PATH = Path(__file__).resolve().parent.parent / "file-size-guardian-hook.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("file_size_guardian_hook", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def hook_mod():
    return _load_module()


@pytest.fixture
def project_root(tmp_path):
    """建立含 CLAUDE.md + rules/core/ 的最小專案結構"""
    (tmp_path / ".claude" / "rules" / "core").mkdir(parents=True)
    (tmp_path / ".claude" / "references").mkdir(parents=True)
    (tmp_path / "CLAUDE.md").write_text(
        "# CLAUDE.md\n\n@.claude/references/quickref.md\n", encoding="utf-8"
    )
    (tmp_path / ".claude" / "references" / "quickref.md").write_text(
        "quickref content\n", encoding="utf-8"
    )
    (tmp_path / ".claude" / "rules" / "core" / "rule-a.md").write_text(
        "rule a content\n", encoding="utf-8"
    )
    return tmp_path


# ============================================================
# @ 引用解析
# ============================================================


class TestParseAtReferences:
    def test_line_start_reference(self, hook_mod):
        refs = hook_mod.parse_at_references("@.claude/rules/core/quality-baseline.md\n")
        assert refs == [".claude/rules/core/quality-baseline.md"]

    def test_inline_reference(self, hook_mod):
        text = "詳見 @.claude/references/chrome-extension-quickref.md 速查表"
        refs = hook_mod.parse_at_references(text)
        assert refs == [".claude/references/chrome-extension-quickref.md"]

    def test_email_not_matched(self, hook_mod):
        # email 的 @ 前無空白且 domain 非 .md 路徑，不應命中
        refs = hook_mod.parse_at_references("聯絡 user@example.com 取得協助")
        assert refs == []

    def test_decorator_not_matched(self, hook_mod):
        # 程式碼裝飾器不以 .md 結尾，不應命中
        refs = hook_mod.parse_at_references("    @pytest.fixture\n    def foo():")
        assert refs == []

    def test_multiple_references(self, hook_mod):
        text = "@a/b.md\n中段 @c/d.md 引用\n"
        assert hook_mod.parse_at_references(text) == ["a/b.md", "c/d.md"]


class TestResolveAtReferences:
    def test_nonexistent_path_graceful_skip(self, hook_mod, project_root):
        source = project_root / "CLAUDE.md"
        source.write_text("@.claude/references/missing.md\n", encoding="utf-8")
        resolved = hook_mod.resolve_at_references(source, project_root)
        assert resolved == set()

    def test_recursive_one_level(self, hook_mod, project_root):
        # CLAUDE.md → quickref.md → nested.md（遞迴一層應涵蓋）
        nested = project_root / ".claude" / "references" / "nested.md"
        nested.write_text("nested\n", encoding="utf-8")
        (project_root / ".claude" / "references" / "quickref.md").write_text(
            "@.claude/references/nested.md\n", encoding="utf-8"
        )
        resolved = hook_mod.resolve_at_references(project_root / "CLAUDE.md", project_root)
        assert project_root / ".claude" / "references" / "quickref.md" in resolved
        assert nested in resolved

    def test_unreadable_source_returns_empty(self, hook_mod, project_root):
        resolved = hook_mod.resolve_at_references(project_root / "no-such-file.md", project_root)
        assert resolved == set()


# ============================================================
# 集合收集與 token 估算
# ============================================================


class TestCollectAutoLoadFiles:
    def test_collects_claude_md_rules_core_and_at_refs(self, hook_mod, project_root):
        files = hook_mod.collect_auto_load_files(project_root)
        assert project_root / "CLAUDE.md" in files
        assert project_root / ".claude" / "rules" / "core" / "rule-a.md" in files
        assert project_root / ".claude" / "references" / "quickref.md" in files

    def test_deduplicates_rules_core_referenced_by_claude_md(self, hook_mod, project_root):
        # CLAUDE.md @ 引用指向 rules/core 內既有檔案時不重複計入
        (project_root / "CLAUDE.md").write_text(
            "@.claude/rules/core/rule-a.md\n", encoding="utf-8"
        )
        files = hook_mod.collect_auto_load_files(project_root)
        paths = [str(p) for p in files]
        assert len(paths) == len(set(paths))

    def test_missing_claude_md_still_scans_rules_core(self, hook_mod, project_root):
        (project_root / "CLAUDE.md").unlink()
        files = hook_mod.collect_auto_load_files(project_root)
        assert project_root / ".claude" / "rules" / "core" / "rule-a.md" in files


class TestMeasureAutoLoadBudget:
    def test_token_estimation_uses_chars_per_token_constant(self, hook_mod, project_root):
        # 固定內容驗證 int(chars / CHARS_PER_TOKEN) 估算（引用常數而非硬編碼係數）
        (project_root / "CLAUDE.md").write_text("x" * 300, encoding="utf-8")
        (project_root / ".claude" / "rules" / "core" / "rule-a.md").write_text(
            "y" * 90, encoding="utf-8"
        )
        total, per_file = hook_mod.measure_auto_load_budget(project_root)
        expected_claude_md = int(300 / hook_mod.CHARS_PER_TOKEN)
        expected_rule_a = int(90 / hook_mod.CHARS_PER_TOKEN)
        assert total == expected_claude_md + expected_rule_a
        # 由大到小排序
        assert per_file[0] == ("CLAUDE.md", expected_claude_md)

    def test_empty_project_returns_zero(self, hook_mod, tmp_path):
        total, per_file = hook_mod.measure_auto_load_budget(tmp_path)
        assert total == 0
        assert per_file == []


# ============================================================
# State 檔
# ============================================================


class TestBudgetState:
    def test_first_run_no_state_returns_none(self, hook_mod, project_root):
        state_path = hook_mod._get_budget_state_path(project_root)
        assert not state_path.exists()
        assert hook_mod.load_previous_budget_total(state_path) is None

    def test_save_then_load_roundtrip(self, hook_mod, project_root):
        state_path = hook_mod._get_budget_state_path(project_root)
        hook_mod.save_budget_state(state_path, 12345)
        assert hook_mod.load_previous_budget_total(state_path) == 12345
        data = json.loads(state_path.read_text(encoding="utf-8"))
        assert "measured_at" in data

    def test_corrupted_state_returns_none(self, hook_mod, project_root):
        state_path = hook_mod._get_budget_state_path(project_root)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text("not-json", encoding="utf-8")
        assert hook_mod.load_previous_budget_total(state_path) is None


# ============================================================
# 輸出路徑（預算內 / 超標）
# ============================================================


@pytest.fixture
def quiet_logger():
    logger = logging.getLogger("test-file-size-guardian-budget")
    logger.addHandler(logging.NullHandler())
    logger.propagate = False
    return logger


class TestBudgetReportOutput:
    def test_under_budget_single_line(self, hook_mod, project_root, quiet_logger, capsys):
        hook_mod.report_auto_load_budget(project_root, quiet_logger)
        out = capsys.readouterr().out
        assert "[Auto-load 預算]" in out
        assert "WARNING" not in out
        # 預算內只輸出一行摘要
        assert len(out.strip().splitlines()) == 1

    def test_over_budget_warning_with_top_files(
        self, hook_mod, project_root, quiet_logger, capsys
    ):
        # 寫入超過 45k tokens（> 45k * CHARS_PER_TOKEN ≈ 58.5k chars）的內容
        (project_root / "CLAUDE.md").write_text("x" * 200_000, encoding="utf-8")
        hook_mod.report_auto_load_budget(project_root, quiet_logger)
        out = capsys.readouterr().out
        assert "[WARNING]" in out
        assert "Top 3 體量檔" in out
        assert "CLAUDE.md" in out

    def test_over_budget_shows_delta_on_second_run(
        self, hook_mod, project_root, quiet_logger, capsys
    ):
        (project_root / "CLAUDE.md").write_text("x" * 200_000, encoding="utf-8")
        hook_mod.report_auto_load_budget(project_root, quiet_logger)
        capsys.readouterr()
        # 第二次量測（總量不變）應顯示差值 +0
        hook_mod.report_auto_load_budget(project_root, quiet_logger)
        out = capsys.readouterr().out
        assert "與上次量測差值: +0 tokens" in out

    def test_first_run_over_budget_no_delta(
        self, hook_mod, project_root, quiet_logger, capsys
    ):
        (project_root / "CLAUDE.md").write_text("x" * 200_000, encoding="utf-8")
        hook_mod.report_auto_load_budget(project_root, quiet_logger)
        out = capsys.readouterr().out
        assert "與上次量測差值" not in out

    def test_state_saved_after_report(self, hook_mod, project_root, quiet_logger, capsys):
        hook_mod.report_auto_load_budget(project_root, quiet_logger)
        capsys.readouterr()
        state_path = hook_mod._get_budget_state_path(project_root)
        assert state_path.exists()


# ============================================================
# 失敗安全（quality-baseline 規則 4 雙通道）
# ============================================================


class TestFailureSafety:
    def test_measurement_exception_writes_stderr_and_does_not_raise(
        self, hook_mod, project_root, quiet_logger, capsys
    ):
        with patch.object(
            hook_mod, "measure_auto_load_budget", side_effect=RuntimeError("boom")
        ):
            # 不阻擋 session：不得拋出例外
            hook_mod.report_auto_load_budget(project_root, quiet_logger)
        captured = capsys.readouterr()
        assert "Auto-load 預算量測異常" in captured.err
        assert "boom" in captured.err

    def test_measurement_exception_logged(self, hook_mod, project_root, capsys, caplog):
        logger = logging.getLogger("test-budget-caplog")
        logger.propagate = True
        with caplog.at_level(logging.ERROR, logger="test-budget-caplog"):
            with patch.object(
                hook_mod, "measure_auto_load_budget", side_effect=RuntimeError("boom")
            ):
                hook_mod.report_auto_load_budget(project_root, logger)
        assert any("Auto-load 預算量測異常" in r.message for r in caplog.records)
        capsys.readouterr()
