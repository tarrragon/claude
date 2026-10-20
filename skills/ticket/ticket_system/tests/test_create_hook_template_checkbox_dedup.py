"""0.5.0-W1-379：hook 模板去重不受核取框前綴影響。"""

from ticket_system.commands.create import (
    _HOOK_ACCEPTANCE_TEMPLATES,
    apply_hook_acceptance_template,
)

HOOK_FILES = [".claude/hooks/foo.py"]
TEMPLATES = [t for _, t in _HOOK_ACCEPTANCE_TEMPLATES]


def _strip_box(item: str) -> str:
    return item.removeprefix("[ ] ")


def test_unboxed_templates_not_duplicated():
    """E2：不帶核取框傳入四條模板，各只出現一次。"""
    unboxed = [_strip_box(t) for t in TEMPLATES]
    result, touched = apply_hook_acceptance_template(HOOK_FILES, list(unboxed))
    assert touched is True
    assert len(result) == len(unboxed)
    for item in unboxed:
        assert sum(1 for r in result if _strip_box(r) == item) == 1


def test_boxed_templates_not_duplicated():
    """E1：帶 [ ] 傳入，行為不變。"""
    result, _ = apply_hook_acceptance_template(HOOK_FILES, list(TEMPLATES))
    assert result == TEMPLATES


def test_not_passed_appends_all_templates():
    """E1：完全未傳入，四條模板全數追加。"""
    result, _ = apply_hook_acceptance_template(HOOK_FILES, None)
    assert result == TEMPLATES
