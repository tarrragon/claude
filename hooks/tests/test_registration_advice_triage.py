"""W1-135：框架工具輸出的註冊建議句不得要求 consumer 修改 settings.json。

分流說法與 sync-pull.md〈幽靈註冊處置〉一致：
框架 hook 上游已註冊 -> 刪 settings.local.json 重複；上游缺註冊 -> 回報 framework issue；
專案自有 hook -> 寫進專案 hook 清冊（.claude/project-integration/hook-registry.yaml）。

建議句為 hook-registration-coverage-check.py 的具名常數（ADVICE_*），本檔直接斷言常數，
不再以 AST 掃描原始碼字串。
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

_HOOKS_DIR = Path(__file__).resolve().parent.parent
_CLAUDE_DIR = _HOOKS_DIR.parent
HOOK_FILE = _HOOKS_DIR / "hook-registration-coverage-check.py"
PROJECT_INIT_DIR = _CLAUDE_DIR / "skills" / "project-init"

# 要求 consumer 動 settings.json 的字樣
FORBIDDEN = re.compile(
    r"移至 settings\.json|在 settings\.json 中註冊|從 settings\.json 移除"
    r"|補充到 settings\.json|修改 settings\.json|搬到 settings\.json"
)
TRIAGE_MARKER = "framework issue"
MANIFEST_MARKER = ".claude/project-integration/hook-registry.yaml"
# 036 落地專案 hook 清冊後已不成立的舊說法
STALE = re.compile(r"無專案自有 hook 的註冊位置|由 sync overlay 自癒")


def _load_hook():
    spec = importlib.util.spec_from_file_location(
        "hook_registration_coverage_check_advice_under_test", HOOK_FILE
    )
    module = importlib.util.module_from_spec(spec)
    if str(_HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(_HOOKS_DIR))
    spec.loader.exec_module(module)
    return module


hook = _load_hook()


def test_patterns_catch_known_bad_wording():
    """正向對照：兩個判準對已知違規句確實命中，避免判準失效時其餘測試假綠。"""
    assert FORBIDDEN.search("建議: 將此 hook 補充到 settings.json")
    assert STALE.search("若屬專案自有 hook，同樣回報 framework issue（框架目前無專案自有 hook 的註冊位置）")
    assert STALE.search("settings.json 內的幽靈由 sync overlay 自癒")


def test_every_advice_constant_is_listed():
    names = sorted(n for n in vars(hook) if n.startswith("ADVICE_") and n != "ADVICE_CONSTANTS")
    assert len(names) == len(hook.ADVICE_CONSTANTS)
    for name in names:
        assert getattr(hook, name) in hook.ADVICE_CONSTANTS, name


def test_advice_has_no_settings_json_edit_instruction():
    for advice in hook.ADVICE_CONSTANTS:
        assert advice.lstrip().startswith("建議:"), advice
        assert not FORBIDDEN.search(advice), advice


def test_advice_has_no_stale_wording():
    for advice in hook.ADVICE_CONSTANTS:
        assert not STALE.search(advice), advice


def test_registration_gap_advice_has_triage():
    for advice in (
        hook.ADVICE_UNREGISTERED_HOOKS,
        hook.ADVICE_UNREGISTERED_SKILL_HOOKS,
        hook.ADVICE_MERGE_VIOLATION,
        hook.ADVICE_LOCAL_REGISTRATION,
    ):
        assert TRIAGE_MARKER in advice, advice


def test_project_hook_advice_points_to_manifest():
    for advice in (
        hook.ADVICE_UNREGISTERED_HOOKS,
        hook.ADVICE_UNREGISTERED_SKILL_HOOKS,
        hook.ADVICE_LOCAL_REGISTRATION,
    ):
        assert MANIFEST_MARKER in advice, advice


def test_main_uses_constants_not_inline_advice():
    """main 內不再出現內嵌的「建議:」字串，避免常數與實際輸出分叉。"""
    source = HOOK_FILE.read_text(encoding="utf-8")
    body = source.split("ADVICE_CONSTANTS = (", 1)[1]
    assert '"建議:' not in body and '"\\n建議:' not in body


def test_project_init_coverage_hint_triage():
    sys.path.insert(0, str(PROJECT_INIT_DIR))
    try:
        import project_init.lib.messages as m  # type: ignore
    finally:
        sys.path.remove(str(PROJECT_INIT_DIR))
    holder = next(
        c for c in vars(m).values()
        if isinstance(c, type) and hasattr(c, "HOOK_COVERAGE_HINT")
    )
    hint = holder.HOOK_COVERAGE_HINT
    assert not FORBIDDEN.search(hint), hint
    assert not STALE.search(hint), hint
    assert TRIAGE_MARKER in hint
    assert MANIFEST_MARKER in hint
