"""0.5.0-W1-340：hook 模板帶入冪等（create 後 set-where 不重複帶入）。"""

from ticket_system.commands.create import (
    _HOOK_ACCEPTANCE_TEMPLATES,
    apply_hook_acceptance_template,
)

HOOK_FILES = [".claude/hooks/foo.py"]
TEMPLATES = [t for _, t in _HOOK_ACCEPTANCE_TEMPLATES]
BASE = ["[ ] 既有條件"]


def test_second_apply_keeps_same_count():
    first, _ = apply_hook_acceptance_template(HOOK_FILES, list(BASE))
    second, touched = apply_hook_acceptance_template(HOOK_FILES, list(first))
    assert touched is True
    assert len(first) == len(BASE) + len(TEMPLATES)
    assert len(second) == len(first)


def test_filled_item_preserved_and_not_duplicated():
    first, _ = apply_hook_acceptance_template(HOOK_FILES, list(BASE))
    prefix = TEMPLATES[0].split("<待填>")[0]
    filled = prefix + "已實測通過"
    first[first.index(TEMPLATES[0])] = filled
    second, _ = apply_hook_acceptance_template(HOOK_FILES, list(first))
    assert second == first
    assert filled in second


def test_not_touching_hooks_adds_nothing():
    result, touched = apply_hook_acceptance_template(["src/a.py"], list(BASE))
    assert touched is False
    assert result == BASE
