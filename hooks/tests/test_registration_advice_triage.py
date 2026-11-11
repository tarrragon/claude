"""W1-135：框架工具輸出的註冊建議句不得要求 consumer 修改 settings.json。

分流說法與 sync-pull.md〈幽靈註冊處置〉（W1-116 定案）一致：
框架 hook 上游已註冊 -> 刪 settings.local.json 重複；上游缺註冊 / 專案自有 hook -> 回報 framework issue。
"""
from __future__ import annotations

import ast
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


def _advice_blocks() -> list[str]:
    """hook 檔內含「建議:」的字串（隱式串接在 AST 已合併；f-string 取常數段）。"""
    tree = ast.parse(HOOK_FILE.read_text(encoding="utf-8"))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            text = "".join(v.value for v in node.values if isinstance(v, ast.Constant))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            text = node.value
        else:
            continue
        if "建議:" in text:
            out.append(text)
    return out


def test_hook_advice_has_no_settings_json_edit_instruction():
    blocks = _advice_blocks()
    assert len(blocks) >= 5
    for block in blocks:
        assert not FORBIDDEN.search(block), block


def test_hook_advice_for_registration_gaps_has_triage():
    # 未註冊 hook / skill hook / 合併版重複 / local 含註冊
    assert sum(TRIAGE_MARKER in b for b in _advice_blocks()) >= 4


def test_project_init_completeness_hint_triage():
    sys.path.insert(0, str(PROJECT_INIT_DIR))
    try:
        import project_init.lib.messages as m  # type: ignore
    finally:
        sys.path.remove(str(PROJECT_INIT_DIR))
    holder = next(
        c for c in vars(m).values()
        if isinstance(c, type) and hasattr(c, "HOOK_COMPLETENESS_HINT")
    )
    hint = holder.HOOK_COMPLETENESS_HINT
    assert not FORBIDDEN.search(hint), hint
    assert TRIAGE_MARKER in hint
