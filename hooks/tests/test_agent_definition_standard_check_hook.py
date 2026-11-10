"""
Agent Definition Standard Check Hook 測試

驗證 SessionStart 掃描 hook 對 .claude/agents/*.md 的三區塊計數、內容錯置啟發式
WARNING、與 language-agent-template.md 模板同步檢查。

設計依據：1.0.0-W8-016 / agent-definition-standard-details.md
- 三區塊：允許產出 / 禁止行為 / 適用情境，計數須 == 3
- 豁免：AGENT_PRELOAD.md / README.md / 第三方 vendored / DEPRECATED 標記檔
- 內容錯置：步驟化清單 / 品質檢查全文關鍵詞 → WARNING
- 模板同步：language-agent-template.md 須含三區塊存在性
- WARNING 級不阻擋（exit 0）
"""

import importlib.util
import io
import sys
from pathlib import Path

import pytest


_HOOKS_DIR = Path(__file__).parent.parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

_spec = importlib.util.spec_from_file_location(
    "agent_definition_standard_check_hook",
    _HOOKS_DIR / "agent-definition-standard-check-hook.py",
)
_hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hook)


# ---------------------------------------------------------------------------
# helpers: 建立暫存 agents 目錄
# ---------------------------------------------------------------------------

THREE_SECTIONS = """---
name: dummy-agent
description: dummy
---

# Dummy Agent

## 允許產出

可寫測試。

## 禁止行為

禁止改 src。

## 適用情境

測試時。
"""

MISSING_ONE_SECTION = """---
name: broken-agent
description: broken
---

# Broken Agent

## 允許產出

可寫測試。

## 適用情境

測試時。
"""


def _make_agents_dir(tmp_path, files: dict) -> Path:
    agents_dir = tmp_path / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    for name, content in files.items():
        (agents_dir / name).write_text(content, encoding="utf-8")
    return agents_dir


# ---------------------------------------------------------------------------
# 三區塊計數
# ---------------------------------------------------------------------------


class TestCountSections:
    def test_count_three_sections_full(self, tmp_path):
        agents_dir = _make_agents_dir(tmp_path, {"a.md": THREE_SECTIONS})
        count = _hook.count_required_sections(agents_dir / "a.md")
        assert count == 3

    def test_count_three_sections_missing_one(self, tmp_path):
        agents_dir = _make_agents_dir(tmp_path, {"a.md": MISSING_ONE_SECTION})
        count = _hook.count_required_sections(agents_dir / "a.md")
        assert count == 2


# ---------------------------------------------------------------------------
# 豁免判定
# ---------------------------------------------------------------------------


class TestExemption:
    def test_meta_files_exempt(self):
        assert _hook.is_exempt("AGENT_PRELOAD.md", "")
        assert _hook.is_exempt("README.md", "")

    def test_deprecated_marker_exempt(self):
        deprecated = "---\nname: x\ndescription: \"[DEPRECATED] moved\"\n---\n# X [DEPRECATED]\n"
        assert _hook.is_exempt("x.md", deprecated)

    def test_vendored_exempt(self):
        assert _hook.is_exempt("impeccable-manual-edit-applier.md", "")

    def test_normal_agent_not_exempt(self):
        assert not _hook.is_exempt("thyme-python-developer.md", THREE_SECTIONS)


# ---------------------------------------------------------------------------
# 掃描 + 收集違規
# ---------------------------------------------------------------------------


class TestScan:
    def test_scan_collects_violations(self, tmp_path):
        agents_dir = _make_agents_dir(
            tmp_path,
            {
                "good.md": THREE_SECTIONS,
                "bad.md": MISSING_ONE_SECTION,
                "AGENT_PRELOAD.md": "# meta",
            },
        )
        result = _hook.scan_agents(agents_dir)
        names = [v["name"] for v in result["structure_violations"]]
        assert "bad.md" in names
        assert "good.md" not in names
        assert "AGENT_PRELOAD.md" not in names

    def test_scan_top3_limit(self, tmp_path):
        files = {f"bad{i}.md": MISSING_ONE_SECTION for i in range(5)}
        agents_dir = _make_agents_dir(tmp_path, files)
        result = _hook.scan_agents(agents_dir)
        # 全部違規但只輸出 top 3
        assert len(result["structure_violations_top3"]) == 3
        assert result["total_structure_violations"] == 5


# ---------------------------------------------------------------------------
# 內容錯置啟發式
# ---------------------------------------------------------------------------


class TestContentMisplacement:
    def test_quality_checklist_keyword_warns(self):
        content = THREE_SECTIONS + "\n## 品質檢查清單\n- [ ] 測試通過\n- [ ] 命名正確\n- [ ] 無重複\n"
        assert _hook.detect_content_misplacement(content) is not None

    def test_clean_agent_no_warning(self):
        assert _hook.detect_content_misplacement(THREE_SECTIONS) is None


# ---------------------------------------------------------------------------
# 模板同步檢查
# ---------------------------------------------------------------------------


class TestTemplateSync:
    def test_template_has_three_sections(self, tmp_path):
        tpl = tmp_path / "language-agent-template.md"
        tpl.write_text(THREE_SECTIONS, encoding="utf-8")
        missing = _hook.check_template_sections(tpl)
        assert missing == []

    def test_template_missing_section(self, tmp_path):
        tpl = tmp_path / "language-agent-template.md"
        tpl.write_text(MISSING_ONE_SECTION, encoding="utf-8")
        missing = _hook.check_template_sections(tpl)
        assert "禁止行為" in missing

    def test_template_absent_returns_marker(self, tmp_path):
        tpl = tmp_path / "language-agent-template.md"
        missing = _hook.check_template_sections(tpl)
        assert missing == ["<file-not-found>"]


# ---------------------------------------------------------------------------
# main exit code（WARNING 不阻擋）
# ---------------------------------------------------------------------------


class TestMainExitCode:
    def test_main_returns_zero_with_violations(self, tmp_path, monkeypatch):
        agents_dir = _make_agents_dir(tmp_path, {"bad.md": MISSING_ONE_SECTION})
        tpl = agents_dir / "language-agent-template.md"
        tpl.write_text(THREE_SECTIONS, encoding="utf-8")
        monkeypatch.setattr(_hook, "_resolve_agents_dir", lambda: agents_dir)
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        rc = _hook.main()
        assert rc == 0

    def test_main_returns_zero_when_clean(self, tmp_path, monkeypatch):
        agents_dir = _make_agents_dir(tmp_path, {"good.md": THREE_SECTIONS})
        tpl = agents_dir / "language-agent-template.md"
        tpl.write_text(THREE_SECTIONS, encoding="utf-8")
        monkeypatch.setattr(_hook, "_resolve_agents_dir", lambda: agents_dir)
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        rc = _hook.main()
        assert rc == 0
