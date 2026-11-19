#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Sync 排除兩通道同構檢查 Hook

觸發時機: SessionStart
模式: 提醒為主（不阻擋），一致時靜默

兩條排除通道共用同一套類別、各自實作：
- 框架通道 `.claude/lib/sync_exclude_manifest.py`，作用域是整個 `.claude/`。
- skill-sync 通道 `.claude/skills/skill-sync/skill_sync/cli.py`，作用域是單一 skill 目錄。

skill-sync 是零依賴的獨立 wheel，不能 import 框架模組，所以兩份清單不合併；
一致性原本只寫在兩邊的註解，沒有執行點。本 hook 依類別逐項比對，輸出只在
一側出現的名稱。

比對方式：
- skill-sync 側以 AST 讀 cli.py 的 frozenset 字面與 `_should_exclude_file`
  內 `.endswith("<字面>")`，不 import（避免套件初始化副作用，也不依賴其執行環境）。
- 框架側直接 import manifest 的具名集合。

不告警的兩類：
- runtime state：只在一側出現、但另一側列在 `LOCAL_ONLY_PATTERNS` 的名稱。
  兩邊實際都會排除，只是歸類不同（例：skill-sync 把 hook-logs 歸工具產物，
  框架歸 Session-bound log）。
- 已知分歧：`KNOWN_DIVERGENCES` 列出刻意不同的名稱與理由，輸出時不算差異。
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
from lib import setup_hook_logging, run_hook_safely, get_code_root  # noqa: E402
from lib.sync_exclude_manifest import (  # noqa: E402
    ALL_TOOL_ARTIFACT_PATTERNS,
    LOCAL_ONLY_PATTERNS,
    PER_PROJECT_PATTERNS,
    TOOL_ARTIFACT_DIR_SUFFIXES,
)

HOOK_NAME = "sync-exclusion-channel-parity-check"
SKILL_SYNC_CLI_REL = Path(".claude/skills/skill-sync/skill_sync/cli.py")

CATEGORY_TOOL_DIRS = "工具產物目錄"
CATEGORY_TOOL_SUFFIXES = "工具產物目錄後綴"
CATEGORY_POLICY = "專案專屬目錄"

# (類別, 名稱) -> 刻意分歧的理由。新增前先確認分歧是設計而非漂移。
KNOWN_DIVERGENCES: dict[tuple[str, str], str] = {
    (CATEGORY_TOOL_DIRS, "build"): (
        "框架通道以路徑段比對整個 .claude/，build 是通用目錄名，會誤排除真實目錄；"
        "skill-sync 作用域只到單一 skill 目錄"
    ),
    (CATEGORY_POLICY, ".version-release.yaml"): (
        "專案根目錄的設定檔，不會出現在 skill 目錄內，skill-sync 不需要排除"
    ),
    (CATEGORY_POLICY, "sync-preserve.yaml"): (
        "consumer 的同步宣告，放在 .claude/ 根目錄，不會出現在 skill 目錄內"
    ),
    (CATEGORY_POLICY, "sync-skills.yaml"): (
        "consumer 的同步宣告，放在 .claude/ 根目錄，不會出現在 skill 目錄內"
    ),
    (CATEGORY_POLICY, "sync-base.json"): (
        "同步基準點與版本 pin，放在 .claude/ 根目錄，不會出現在 skill 目錄內"
    ),
}


class SkillSyncSets(NamedTuple):
    tool_dirs: frozenset[str]
    policy_dirs: frozenset[str]
    suffixes: frozenset[str]


class Divergence(NamedTuple):
    category: str
    name: str
    only_in: str  # "skill-sync" 或 "框架"


class ParityReport(NamedTuple):
    divergences: list[Divergence]
    known: list[tuple[str, str, str]]  # (類別, 名稱, 理由)


class ParseError(Exception):
    """cli.py 讀不到或結構不符預期。"""


def _frozenset_literal(node: ast.AST) -> frozenset[str] | None:
    """解析 `frozenset({"a", "b"})` 字面；其他形式回傳 None。"""
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
        return None
    if node.func.id != "frozenset" or len(node.args) != 1:
        return None
    arg = node.args[0]
    if not isinstance(arg, (ast.Set, ast.List, ast.Tuple)):
        return None
    values = [e.value for e in arg.elts if isinstance(e, ast.Constant)]
    if len(values) != len(arg.elts) or not all(isinstance(v, str) for v in values):
        return None
    return frozenset(values)


def _endswith_literals(func: ast.FunctionDef) -> frozenset[str]:
    found = set()
    for node in ast.walk(func):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "endswith"
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            found.add(node.args[0].value)
    return frozenset(found)


def parse_skill_sync_sets(source: str) -> SkillSyncSets:
    """從 cli.py 原始碼取出兩個排除集合與後綴字面。"""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise ParseError(f"cli.py 語法錯誤：{exc}") from exc

    assigned: dict[str, frozenset[str]] = {}
    suffixes: frozenset[str] | None = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                value = _frozenset_literal(node.value)
                if value is not None:
                    assigned[target.id] = value
        elif isinstance(node, ast.FunctionDef) and node.name == "_should_exclude_file":
            suffixes = _endswith_literals(node)

    missing = [n for n in ("TOOL_ARTIFACT_DIRS", "POLICY_EXCLUDE_DIRS") if n not in assigned]
    if missing:
        raise ParseError(f"cli.py 找不到 frozenset 字面：{', '.join(missing)}")
    if suffixes is None:
        raise ParseError("cli.py 找不到 _should_exclude_file")
    return SkillSyncSets(
        tool_dirs=assigned["TOOL_ARTIFACT_DIRS"],
        policy_dirs=assigned["POLICY_EXCLUDE_DIRS"],
        suffixes=suffixes,
    )


def compare(
    skill_sync: SkillSyncSets,
    framework_tool_dirs: frozenset[str],
    framework_suffixes: frozenset[str],
    framework_policy: frozenset[str],
    runtime_state: frozenset[str],
) -> ParityReport:
    """逐類別比對；runtime state 與已知分歧不列為差異。"""
    pairs = [
        (CATEGORY_TOOL_DIRS, skill_sync.tool_dirs, framework_tool_dirs),
        (CATEGORY_TOOL_SUFFIXES, skill_sync.suffixes, framework_suffixes),
        (CATEGORY_POLICY, skill_sync.policy_dirs, framework_policy),
    ]
    divergences: list[Divergence] = []
    known: list[tuple[str, str, str]] = []
    for category, ours, theirs in pairs:
        for name, only_in in [(n, "skill-sync") for n in sorted(ours - theirs)] + [
            (n, "框架") for n in sorted(theirs - ours)
        ]:
            reason = KNOWN_DIVERGENCES.get((category, name))
            if reason is not None:
                known.append((category, name, reason))
            elif only_in == "skill-sync" and name in runtime_state:
                continue
            else:
                divergences.append(Divergence(category, name, only_in))
    return ParityReport(divergences, known)


def format_warning(report: ParityReport) -> str:
    lines = [
        "[WARNING] sync 排除兩通道不一致（skill-sync cli.py 與 .claude/lib/sync_exclude_manifest.py）：",
    ]
    for d in report.divergences:
        lines.append(f"  - {d.category}：`{d.name}` 只在{d.only_in}側排除")
    lines.append(
        "處置：兩邊補齊同一名稱；若分歧是刻意的，寫進本 hook 的 KNOWN_DIVERGENCES 並附理由。"
    )
    return "\n".join(lines)


def _emit(context: str | None) -> None:
    if context is None:
        print(json.dumps({"suppressOutput": True}, ensure_ascii=False))
        return
    print(context, file=sys.stderr)  # debug 副本，非注入通道
    output = {
        "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context + "\n"},
        "suppressOutput": False,
    }
    print(json.dumps(output, ensure_ascii=False))


def main() -> int:
    logger = setup_hook_logging(HOOK_NAME)
    cli_path = get_code_root() / SKILL_SYNC_CLI_REL

    try:
        sets = parse_skill_sync_sets(cli_path.read_text(encoding="utf-8"))
    except (OSError, ParseError) as exc:
        message = f"[WARNING] sync 排除兩通道同構檢查未執行：{exc}（{cli_path}）"
        logger.warning(message)
        _emit(message)
        return 0

    report = compare(
        sets,
        framework_tool_dirs=ALL_TOOL_ARTIFACT_PATTERNS,
        framework_suffixes=TOOL_ARTIFACT_DIR_SUFFIXES,
        framework_policy=PER_PROJECT_PATTERNS,
        runtime_state=LOCAL_ONLY_PATTERNS,
    )
    known_desc = ", ".join(f"{c}:{n}" for c, n, _ in report.known) or "無"
    if not report.divergences:
        logger.info("兩通道一致；已知分歧基準：%s", known_desc)
        _emit(None)
        return 0

    warning = format_warning(report)
    logger.warning("%s\n已知分歧基準：%s", warning, known_desc)
    _emit(warning)
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
