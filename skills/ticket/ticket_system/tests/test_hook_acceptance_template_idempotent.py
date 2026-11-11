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


# 3.2.0-W1-030：建票端對盤點表格式問題輸出警告（與 gate 判定一致）
OK_TABLE = "| 產生路徑 | 是否覆蓋 | 未覆蓋原因 |\n|---|---|---|\n| a | 是 | |"
FAILED_TABLE = "| 產生路徑 | 是否覆蓋 | 未覆蓋原因 |\n|---|---|---|\n| a | 部分 | |"
NO_PATH_HEADER_TABLE = "| 端點 | 本票覆蓋 |\n|---|---|\n| a | 是 |"


def _stderr_of(capsys, strategy):
    apply_hook_acceptance_template(HOOK_FILES, list(BASE), strategy)
    return capsys.readouterr().err


def test_failed_table_warns_with_format(capsys):
    err = _stderr_of(capsys, FAILED_TABLE)
    assert "[WARNING] 產生路徑盤點表" in err
    assert "| 產生路徑 | 是否覆蓋 |" in err
    assert "「是」或「否」" in err


def test_table_without_path_header_warns(capsys):
    err = _stderr_of(capsys, NO_PATH_HEADER_TABLE)
    assert "表頭缺「產生路徑」" in err


def test_valid_table_differs_from_failed_table(capsys):
    # E2 對照：同形表格僅覆蓋值不同，合格者不警告、不合格者警告
    ok_err = _stderr_of(capsys, OK_TABLE)
    failed_err = _stderr_of(capsys, FAILED_TABLE)
    assert "產生路徑盤點表" not in ok_err
    assert "產生路徑盤點表" in failed_err


def test_no_table_no_format_warning(capsys):
    assert "產生路徑盤點表" not in _stderr_of(capsys, "純文字策略")
