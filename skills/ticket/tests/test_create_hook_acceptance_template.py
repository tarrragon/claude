"""0.5.0-W1-276.1：where 觸及 hook 本體時，create / set-where 帶入 acceptance 模板。

E1 對照：同一批 fixture，觸及 hook 本體 vs 不觸及，斷言 acceptance 結構化欄位
與提醒函式是否被呼叫（不比對輸出子字串）。
"""

import argparse

import pytest
import yaml

from ticket_system.commands import create as create_mod
from ticket_system.commands.create import (
    _HOOK_ACCEPTANCE_TEMPLATES,
    apply_hook_acceptance_template,
)
from ticket_system.commands.fields import execute_set_where

HOOK_FILES = [".claude/hooks/foo.py", "src/a.py"]
PLAIN_FILES = ["src/a.py", "lib/b.dart"]
TEMPLATES = [t for _, t in _HOOK_ACCEPTANCE_TEMPLATES]
BASE = ["[ ] 既有條件"]


def test_templates_carry_placeholder_and_no_gate_keywords():
    checker = create_mod._load_hook_protection_checker()
    assert all("<待填" in t for t in TEMPLATES)
    # 未填模板本身不得讓 gate 的三類關鍵詞通過
    assert len(checker._missing_categories("\n".join(TEMPLATES))) == 3


def test_create_touching_hook_appends_four_templates():
    result, touched = apply_hook_acceptance_template(HOOK_FILES, list(BASE))
    assert touched is True
    assert result == BASE + TEMPLATES


def test_read_marked_hook_path_adds_no_template_e2():
    result, touched = apply_hook_acceptance_template(
        [".claude/hooks/foo-hook.py::read"], list(BASE)
    )
    assert touched is False
    assert result == list(BASE)


def test_unmarked_hook_path_still_adds_template_e1():
    result, touched = apply_hook_acceptance_template(
        [".claude/hooks/foo-hook.py"], list(BASE)
    )
    assert touched is True
    assert len(result) > len(BASE)


def test_write_marked_hook_path_still_adds_template_e1():
    result, touched = apply_hook_acceptance_template(
        [".claude/hooks/x.py::write"], list(BASE)
    )
    assert touched is True
    assert len(result) > len(BASE)


def test_escaped_read_marker_still_adds_template():
    result, touched = apply_hook_acceptance_template(
        [".claude/hooks/foo-hook.py\\::read"], list(BASE)
    )
    assert touched is True
    assert len(result) > len(BASE)


def test_create_not_touching_hook_unchanged():
    result, touched = apply_hook_acceptance_template(PLAIN_FILES, list(BASE))
    assert touched is False
    assert result == BASE


def test_existing_category_not_duplicated():
    existing = BASE + ["[ ] liveness 驗證：已確認"]
    result, _ = apply_hook_acceptance_template(HOOK_FILES, existing)
    labels_added = [t for t in result if t in TEMPLATES]
    assert len(labels_added) == 3
    assert TEMPLATES[1] not in result


INVENTORY_TABLE = (
    "盤點如下\n"
    "| 產生路徑 | 是否覆蓋 | 未覆蓋原因 |\n"
    "|---------|---------|-----------|\n"
    "| 路徑 A | 是 | |\n"
)


@pytest.mark.parametrize(
    "how_strategy,expect_inventory_template",
    [(INVENTORY_TABLE, False), ("一般策略，無表", True)],
)
def test_inventory_template_follows_how_strategy_e1_contrast(
    how_strategy, expect_inventory_template
):
    result, touched = apply_hook_acceptance_template(
        HOOK_FILES, list(BASE), how_strategy
    )
    assert touched is True
    assert (TEMPLATES[3] in result) is expect_inventory_template
    assert result[: len(BASE)] == BASE


# ---- set-where ----


def _make_ticket(tmp_path, monkeypatch, how_strategy=None):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    tdir = tmp_path / "docs/work-logs/v0/v0.1/v0.1.0/tickets"
    tdir.mkdir(parents=True)
    fm = {
        "id": "0.1.0-W1-001", "title": "T", "type": "IMP", "status": "in_progress",
        "version": "0.1.0", "wave": 1, "priority": "P2", "acceptance": list(BASE),
    }
    if how_strategy is not None:
        fm["how"] = {"task_type": "Implementation", "strategy": how_strategy}
    path = tdir / "0.1.0-W1-001.md"
    path.write_text(
        "---\n" + yaml.dump(fm, allow_unicode=True) + "---\n\n# Execution Log\n",
        encoding="utf-8",
    )
    return path


def _run_set_where(path, value, monkeypatch):
    calls = []
    monkeypatch.setattr(create_mod, "print_hook_ticket_reminder", lambda: calls.append(1))
    args = argparse.Namespace(ticket_id="0.1.0-W1-001", value=value, version=None)
    execute_set_where(args, "0.1.0")
    # 表格分隔列含 "---"，不可用 split("---") 切 frontmatter
    fm = next(yaml.safe_load_all(path.read_text(encoding="utf-8")))
    return fm["acceptance"], len(calls)


def _run_create_e2e(tmp_path, monkeypatch, where_files):
    """走 create 命令入口（execute），真實落盤到 tmp，讀回 acceptance 與提醒次數。"""
    from tests.test_create_portable_issue_gate import _install_common_mocks, _make_args

    real_build = create_mod._build_and_save_ticket
    _install_common_mocks(monkeypatch)
    monkeypatch.setattr(create_mod, "_build_and_save_ticket", real_build)
    tickets_dir = tmp_path / "tickets"
    monkeypatch.setattr(create_mod, "get_tickets_dir", lambda v: tickets_dir)
    monkeypatch.setattr(
        create_mod, "get_ticket_path", lambda v, tid: tickets_dir / f"{tid}.md"
    )
    calls = []
    monkeypatch.setattr(create_mod, "print_hook_ticket_reminder", lambda: calls.append(1))

    args = _make_args(where_files=where_files, dedup_checked="none", dedup_keywords=["測試佔位"], acceptance=list(BASE))
    assert create_mod.execute(args) == 0
    (path,) = tickets_dir.glob("*.md")
    fm = yaml.safe_load(path.read_text(encoding="utf-8").split("---", 2)[1])
    return fm["acceptance"], len(calls)


@pytest.mark.parametrize(
    "where_files,expect_templates",
    [(",".join(HOOK_FILES), True), (",".join(PLAIN_FILES), False)],
)
def test_create_command_e2e_e1_contrast(tmp_path, monkeypatch, where_files, expect_templates):
    acceptance, reminder_calls = _run_create_e2e(tmp_path, monkeypatch, where_files)
    if expect_templates:
        assert acceptance == BASE + TEMPLATES
        assert reminder_calls == 1
    else:
        assert acceptance == BASE
        assert reminder_calls == 0


@pytest.mark.parametrize(
    "how_strategy,expect_inventory_template",
    [(INVENTORY_TABLE, False), ("一般策略，無表", True)],
)
def test_set_where_inventory_follows_ticket_how_strategy(
    tmp_path, monkeypatch, how_strategy, expect_inventory_template
):
    path = _make_ticket(tmp_path, monkeypatch, how_strategy)
    acceptance, reminder_calls = _run_set_where(path, ",".join(HOOK_FILES), monkeypatch)
    assert (TEMPLATES[3] in acceptance) is expect_inventory_template
    assert TEMPLATES[:3] == [t for t in acceptance if t in TEMPLATES[:3]]
    assert reminder_calls == 1


@pytest.mark.parametrize(
    "value,expect_templates",
    [(",".join(HOOK_FILES), True), (",".join(PLAIN_FILES), False)],
)
def test_set_where_e1_contrast(tmp_path, monkeypatch, value, expect_templates):
    path = _make_ticket(tmp_path, monkeypatch)
    acceptance, reminder_calls = _run_set_where(path, value, monkeypatch)
    if expect_templates:
        assert acceptance == BASE + TEMPLATES
        assert reminder_calls == 1
    else:
        assert acceptance == BASE
        assert reminder_calls == 0


# ---- 0.5.0-W1-394：佔位符寫明 set-acceptance --edit 改寫 ----

# 389 實例：代理人改寫條目時刪掉前綴中的說明性括號
REWRITTEN_389 = "[ ] 載入與執行的確認方式：已貼 hook-logs 引文"


def _prefix(template):
    return template.split("<待填")[0]


def test_placeholder_points_to_set_acceptance_edit():
    for t in TEMPLATES:
        placeholder = t[t.index("<待填"):]
        assert "set-acceptance" in placeholder and "--edit" in placeholder


def test_prefix_has_no_explanatory_parentheses():
    for t in TEMPLATES:
        assert "（" not in _prefix(t) and "(" not in _prefix(t)


def test_gate_still_treats_new_placeholder_as_unfilled_e2():
    checker = create_mod._load_hook_protection_checker()
    for t in TEMPLATES:
        assert checker._is_template_placeholder(t)
    filled = _prefix(TEMPLATES[0]) + "已貼 hook-logs/x.log 引文"
    assert not checker._is_template_placeholder(filled)


def test_rewritten_entry_keeps_prefix_and_is_not_readded_e1():
    result, _ = apply_hook_acceptance_template(
        HOOK_FILES, BASE + [REWRITTEN_389]
    )
    assert TEMPLATES[1] not in result
    assert result.count(REWRITTEN_389) == 1


def test_dispatch_readiness_counts_rewritten_389_entry_as_template_e1():
    from ticket_system.commands.track_dispatch_readiness import (
        _count_hook_template_items,
    )

    with_rewritten = BASE + [
        REWRITTEN_389 if t == TEMPLATES[1] else t for t in TEMPLATES
    ]
    assert _count_hook_template_items(BASE + TEMPLATES) == 4
    assert _count_hook_template_items(with_rewritten) == 4
    assert _count_hook_template_items(BASE) == 0
