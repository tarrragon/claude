#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Hooks Test Gate Hook（PreToolUse: Bash）

目標式 hooks 測試 gate（0.2.1-W3-189，source ANA 0.2.1-W3-188）。

問題背景：
  0.2.1-W3-181 於 14:52 改動 SKILLS 常數使
  `test_all_seven_skills_covered` 紅燈，W3-181 與 W3-184 兩次 commit 皆無
  提示，潛伏 27 分鐘至 W3-091 代理人碰巧跑全套件才撞見。W3-188 實查六個
  位置（.github/workflows / .pre-commit-config.yaml / .husky / .git/hooks /
  core.hooksPath / settings.json 既有 test hook）後判定：commit 或
  complete 前確無任何機制要求 hooks 測試通過，屬機制缺口。

方案取捨（W3-188 結論，勿重做評估）：
  全套件 84.56s vs 單一目標測試檔 0.21s，差約 400 倍，而多數 hooks
  commit 只動一至兩檔。故採「目標式子集」而非全套件阻擋：commit 觸及
  `.claude/hooks/*.py` 時，僅跑其對應測試檔（依命名慣例推導，實測覆蓋
  47/94）。

Hook Event: PreToolUse
Matcher: Bash
Decision:
  - 未觸及 .claude/hooks/*.py → 無輸出（zero overhead，見下方效能設計）
  - 觸及且對應測試紅燈 → permission_decision="deny"（阻擋 commit）
  - 觸及且無對應測試 → additional_context 提醒（不阻擋，技術債可見化）
  - 觸及且對應測試綠燈 → 無輸出（放行）

============================================================
範疇邊界（刻意不做，非遺漏 —— 務必讀完再修改本檔）
============================================================
本 gate 只驗證「被改動的 hook 檔本身的對應測試」，**不涵蓋跨檔破壞**
（例如改 `lib/git_utils.py` 共用模組導致其他未被本次 commit 觸及的 hook
測試轉紅）。這與全套件 gate 的差異必須在放行 / 阻擋訊息中明示，否則本
機制會成為 `ARCH-BAL-011` 的新實例——名字像「hooks 測試 gate」但實際只
覆蓋單檔，讀者若望文生義會誤以為通過等於全套件安全。

其餘刻意不做：
  - 不掃描 `.claude/lib/` 或 `.claude/skills/*/hooks/` 的改動（範疇僅
    `.claude/hooks/` 下直接子層 `*.py`，與 candidate_tests 慣例一致）。
  - 不嘗試對 `git commit -a/-am/--all`、`git add -A/.`、萬用字元等無法
    靜態列舉的情況做完整推導；僅合併「當下已 staged」與「同指令內明確
    `git add <literal path>`／commit pathspec 提及的 `.claude/hooks/*.py`
    字面路徑」兩個來源。三者皆無法涵蓋的邊界情況（如先在另一個獨立 Bash
    呼叫用 `git add -A` 暫存、再於本次呼叫 commit）仍會被「當下已 staged」
    來源涵蓋，故實務影響有限。
  - 不處理跨 repo（`-C` 指向非本專案 / 子 shell cd 至他處）：偵測到即
    skip（allow），因為本 gate 保護的是本專案的 hooks 測試，與其他 repo
    無關。

============================================================
效能設計（acceptance 4：不觸及 .claude/hooks 的 commit 零額外開銷）
============================================================
`_fast_reject()` 為第一道便宜判斷：純字串 regex 搜尋 "commit" 字樣，
非 commit 類命令（Bash 工具最大宗：ls/cat/flutter test/...）於此短路，
**不執行 `git diff --cached`**。只有偵測到 commit 字樣才會付出後續解析
與 git 呼叫的成本；成本基準見 W3-188 Context Bundle（全套件 84.56s vs
單檔 0.21s）。

============================================================
迴圈防護
============================================================
本 hook 內部以 `subprocess.run(["uv", "run", ...])` 直接呼叫 pytest，
並非透過 Claude Code 的 Bash 工具發出命令 —— PreToolUse 只攔截 Bash
「工具呼叫」，子行程呼叫不會再次觸發本 hook（或任何 PreToolUse hook），
無遞迴風險。

對應 ticket 0.2.1-W3-189（source ANA 0.2.1-W3-188）。
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import (  # noqa: E402
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    emit_hook_output,
    get_project_root,
)
from lib.git_utils import run_git_command  # noqa: E402

HOOK_NAME = "hooks-test-gate"

# 單一目標測試檔基準 0.21s（W3-188 實測），逾時代表測試檔本身有問題
# （如無窮迴圈），非本 gate 職責涵蓋範圍，保守給 30s 容錯空間。
PYTEST_TIMEOUT = 30

# 便宜前置判斷：命令是否含 "commit" 字樣（非 git 相關的 Bash 命令於此短路）
_COMMIT_WORD_RE = re.compile(r"\bcommit\b")

# 命令是否為真實 git commit 呼叫（統一環境變數前綴，供本檔多個 regex共用）
_ENV_PREFIX = r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"

# 命令是否為 git commit 呼叫（statement 邊界版，比照 post-test-hook.py 於
# 0.2.1-W3-066 的修法：要求 "git commit" 位於命令 statement 起頭（^ /
# ;|&(\n / && / ||）之後，可選環境變數前綴。子 shell cd 形式（如
# `(cd dir && git commit ...)`）的 "git commit" 前有 `&&` 邊界字元仍會
# 命中，不需另立子 shell 專用 regex。
#
# 0.2.1-W3-191 修正：舊版對命令任意位置做 substring 搜尋，導致
# `echo '{"command":"git commit ..."}'` 之類的 JSON payload 字面提及被
# 誤判為真實 commit（該字面前為引號字元，非 statement 邊界，加上邊界
# 要求後不再誤觸發）。
_GIT_COMMIT_RE = re.compile(
    r"(?:^|[;|&(\n]|&&|\|\|)\s*" + _ENV_PREFIX + r"git\s+(?:-C\s+\S+\s+)?commit\b"
)

# 目標 repo 提示（-C 形式 / 子 shell cd 形式），用於跨 repo 判斷
_DASH_C_RE = re.compile(r"\bgit\s+-C\s+(?P<repo>\S+)\b")
_SUBSHELL_CD_RE = re.compile(r"\(\s*cd\s+(?P<repo>\S+)\s*(?:&&|;)")

# 命令字面中提及的 .claude/hooks 下直接子層 .py 路徑（不含路徑前綴限定，
# 實際採計位置由 _iter_literal_pathspec_segments 限定於 git add 或 commit
# pathspec 參數位置，見下方，非命令任意位置）。
_HOOK_PY_LITERAL_RE = re.compile(r"\.claude/hooks/([\w.\-]+\.py)\b")

# statement 邊界分隔符，用於切分命令為獨立區段（與 _GIT_COMMIT_RE 共用邊界
# 概念，但這裡切分後逐段判斷區段開頭，而非在整條命令內搜尋）。
_STATEMENT_BOUNDARY_SPLIT_RE = re.compile(r"&&|\|\||;|\n|\|")

_GIT_ADD_STATEMENT_RE = re.compile(r"^" + _ENV_PREFIX + r"git\s+add\b")
_GIT_COMMIT_PATHSPEC_RE = re.compile(
    r"^" + _ENV_PREFIX + r"git\s+(?:-C\s+\S+\s+)?commit\b.*?--\s+(?P<pathspec>.*)$"
)


def _iter_literal_pathspec_segments(command: str):
    """回傳命令中屬於 `git add` 參數，或 `git commit ... -- <pathspec>` 之後
    的區段字串。

    只有這些位置提及的 `.claude/hooks/*.py` 字面才會被 `_touched_hook_filenames`
    採計（0.2.1-W3-191 修正 acceptance 3：字面提及來源限定於 git add 或
    commit pathspec 的參數位置，非命令任意位置）。命令先依 statement 邊界
    （`&&` / `||` / `;` / `|` / 換行）切段，逐段判斷開頭是否為 `git add`
    或 `git commit ... --`，非此二者的區段（如 `echo '...'`、JSON payload
    片段、被管線呼叫的 hook 路徑本身）一律忽略。
    """
    for raw_segment in _STATEMENT_BOUNDARY_SPLIT_RE.split(command):
        segment = raw_segment.strip()
        if not segment:
            continue
        if _GIT_ADD_STATEMENT_RE.match(segment):
            yield segment
            continue
        m = _GIT_COMMIT_PATHSPEC_RE.match(segment)
        if m:
            yield m.group("pathspec")


def _fast_reject(command: str) -> bool:
    """便宜前置判斷：命令連 'commit' 字樣都沒有，直接短路（零額外開銷）。"""
    if not command:
        return True
    return not _COMMIT_WORD_RE.search(command)


def _extract_repo_hint(command: str) -> Optional[str]:
    """取得 -C 或子 shell cd 的目標 repo 提示字串（找不到回傳 None）。"""
    m = _DASH_C_RE.search(command)
    if m:
        return m.group("repo")
    m = _SUBSHELL_CD_RE.search(command)
    if m:
        return m.group("repo")
    return None


def _is_host_repo_commit(command: str, host_root: str) -> bool:
    """判斷此次 commit 是否針對本專案（host_root）。

    無 -C / cd 提示時視為預設 cwd（host_root），返回 True。
    有提示但無法解析為絕對路徑，或解析後與 host_root 不同，返回 False
    （skip，範疇邊界：跨 repo 不干預）。
    """
    repo_hint = _extract_repo_hint(command)
    if repo_hint is None:
        return True
    if not repo_hint.startswith("/"):
        return False
    try:
        return Path(repo_hint).resolve() == Path(host_root).resolve()
    except OSError:
        return False


def _touched_hook_filenames(command: str, host_root: str, logger) -> Set[str]:
    """回傳本次 commit 觸及的 `.claude/hooks/` 直接子層 `*.py` 檔名集合。

    兩來源聯集：
      1. 當下已 staged（`git diff --cached --name-only`）
      2. 同指令內 `git add` 或 commit pathspec 參數位置字面提及的路徑
         （見 `_iter_literal_pathspec_segments`，涵蓋 `git add x && git
         commit` 串接情境，且排除非該參數位置的字面提及，如 JSON payload
         或 echo 字面；見檔頭範疇邊界）
    僅保留 `.claude/hooks/` 下不含更深層路徑分隔符（無巢狀子目錄）的
    `*.py`（與 candidate_tests 命名慣例一致，排除 tests/ 與 lib/ 子目錄）。
    """
    filenames: Set[str] = set()

    success, output = run_git_command(
        ["diff", "--cached", "--name-only"], cwd=host_root
    )
    if success and output:
        for line in output.split("\n"):
            line = line.strip()
            m = re.fullmatch(r"\.claude/hooks/([\w.\-]+\.py)", line)
            if m:
                filenames.add(m.group(1))
    elif not success:
        logger.warning("無法讀取 staged 檔案清單（%s），僅依賴命令字面推導", output)

    for segment in _iter_literal_pathspec_segments(command):
        for m in _HOOK_PY_LITERAL_RE.finditer(segment):
            filenames.add(m.group(1))

    return filenames


def _candidate_tests(hook_filename: str) -> Set[str]:
    """依命名慣例推導 hook 檔對應的候選測試檔名（W3-188 實測覆蓋 47/94）。

    uv-tool-ownership-guard-hook.py -> {test_uv_tool_ownership_guard_hook.py,
                                          test_uv_tool_ownership_guard.py}
    """
    stem = hook_filename[:-3].replace("-", "_")
    return {f"test_{stem}.py", f"test_{stem.replace('_hook', '')}.py"}


def _resolve_test_paths(
    hook_filenames: Set[str], hooks_dir: Path
) -> "tuple[Dict[str, Path], List[str]]":
    """分類：有對應測試（回傳 {hook檔名: 測試絕對路徑}）／無對應測試（清單）。"""
    tests_dir = hooks_dir / "tests"
    tested: Dict[str, Path] = {}
    untested: List[str] = []
    for hook_filename in sorted(hook_filenames):
        found: Optional[Path] = None
        for candidate in sorted(_candidate_tests(hook_filename)):
            candidate_path = tests_dir / candidate
            if candidate_path.exists():
                found = candidate_path
                break
        if found is not None:
            tested[hook_filename] = found
        else:
            untested.append(hook_filename)
    return tested, untested


def _run_pytest(test_paths: List[Path], hooks_dir: Path, logger) -> "tuple[bool, str]":
    """跑指定測試檔清單，回傳 (是否通過, 輸出末段供 deny 訊息附帶)。"""
    cmd = ["uv", "run", "--project", str(hooks_dir), "pytest", "-q"] + [
        str(p) for p in test_paths
    ]
    logger.info("執行目標測試: %s", cmd)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=PYTEST_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        logger.warning("目標測試執行逾時（%ss），保守判定為失敗", PYTEST_TIMEOUT)
        return False, f"測試逾時（{PYTEST_TIMEOUT}s）"
    output_tail = "\n".join((result.stdout + result.stderr).splitlines()[-20:])
    passed = result.returncode == 0
    logger.info("目標測試結果: returncode=%d", result.returncode)
    return passed, output_tail


_BOUNDARY_NOTE = (
    "範疇邊界：本 gate 僅驗證被改動 hook 檔本身的對應測試，"
    "不涵蓋跨檔破壞（如改共用模組導致其他 hook 測試轉紅）。"
)


def _build_deny_message(failing: Dict[str, Path], output_tail: str) -> str:
    files_block = "\n".join(f"  - {f} -> {p}" for f, p in sorted(failing.items()))
    return (
        "Hooks 目標測試 gate：commit 被阻止\n\n"
        "以下被改動的 hook 檔對應測試未通過：\n"
        f"{files_block}\n\n"
        "測試輸出（末段）：\n"
        f"{output_tail}\n\n"
        f"{_BOUNDARY_NOTE}\n"
        "請修正對應測試後再重試 commit。"
    )


def _build_untested_reminder(untested: List[str]) -> str:
    files_block = "\n".join(f"  - {f}" for f in sorted(untested))
    return (
        "[Hooks 測試 gate 提醒] 以下被改動的 hook 檔未受測試保護"
        "（`.claude/hooks/tests/` 下無依命名慣例對應的測試檔）：\n"
        f"{files_block}\n\n"
        f"{_BOUNDARY_NOTE}\n"
        "建議補上對應測試，使其納入本 gate 保護範圍。"
    )


def main() -> int:
    logger = setup_hook_logging(HOOK_NAME)

    input_data = read_json_from_stdin(logger)
    if input_data is None:
        logger.debug("無有效輸入，允許")
        return 0

    tool_name = input_data.get("tool_name", "")
    if tool_name != "Bash":
        logger.debug("工具 %s 不需要 hooks 測試 gate 檢查", tool_name)
        return 0

    tool_input = input_data.get("tool_input") or {}
    command = tool_input.get("command", "")

    if _fast_reject(command):
        logger.debug("命令不含 'commit' 字樣，零開銷短路允許")
        return 0

    if not _GIT_COMMIT_RE.search(command):
        logger.debug("命令含 'commit' 但非 git commit 呼叫，允許")
        return 0

    host_root = str(get_project_root())

    if not _is_host_repo_commit(command, host_root):
        logger.debug("commit 目標非本專案，跳過（範疇邊界：不干預跨 repo）")
        return 0

    touched = _touched_hook_filenames(command, host_root, logger)
    if not touched:
        logger.debug("此次 commit 未觸及 .claude/hooks 下直接子層 *.py，允許")
        return 0

    hooks_dir = Path(host_root) / ".claude" / "hooks"
    tested, untested = _resolve_test_paths(touched, hooks_dir)

    if tested:
        passed, output_tail = _run_pytest(list(tested.values()), hooks_dir, logger)
        if not passed:
            logger.info("目標測試紅燈，阻擋 commit: %s", sorted(tested.keys()))
            emit_hook_output(
                "PreToolUse",
                permission_decision="deny",
                permission_decision_reason=_build_deny_message(tested, output_tail),
                input_data=input_data,
            )
            return 0

    if untested:
        logger.info("以下觸及的 hook 檔無對應測試: %s", sorted(untested))
        emit_hook_output(
            "PreToolUse",
            additional_context=_build_untested_reminder(untested),
            input_data=input_data,
        )
        return 0

    logger.debug("所有觸及的 hook 檔對應測試皆通過，允許")
    return 0


if __name__ == "__main__":
    exit_code = run_hook_safely(main, HOOK_NAME)
    sys.exit(exit_code)
