#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
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
import time
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
from lib.git_utils import parse_name_status_z, run_git_command  # noqa: E402

HOOK_NAME = "hooks-test-gate"

# 逐檔執行：每個對應測試檔各跑一次 pytest，單檔逾時才判失敗。
# 舊設計把本次提交觸及的全部測試合成一次呼叫並套固定 30s 上限，總耗時隨觸及
# hook 數線性增長（consumer 實測 10 支 hook 合併 45.2s），綠燈被報為逾時。
#
# 單檔上限：本 repo 最慢四檔各取樣 5 次（負載下），bash-git-protected-branch-guard
# 分佈 9.2 / 10.4 / 15.2 / 17.2 / 37.5s（最大值為負載尖峰），其餘三檔 <= 17s。
# 取 60s 使負載尖峰不誤擋；超過視為測試檔本身卡住（無窮迴圈等），保守判失敗。
PER_FILE_TIMEOUT = 60

# 總預算（秒）：所有測試檔累計耗時的硬上限，每檔實際逾時 = min(PER_FILE_TIMEOUT, 剩餘預算)。
# 最壞總耗時 = TOTAL_BUDGET + 進入測試前的 git diff 等開銷（實務 < 5s）。
# 平台 hook timeout 為 non-blocking：gate 被平台殺掉等於放行且無訊號，
# 故 settings.json 明示 timeout（單位：秒）必須大於此上界。
TOTAL_BUDGET = 100

# settings.json 中本 hook 註冊的 timeout（單位：秒；測試驗證兩者一致且大於最壞上界）。
PLATFORM_TIMEOUT_SECONDS = 120

_STATUS_PASS = "pass"
_STATUS_RED = "red"
_STATUS_TIMEOUT = "timeout"
_STATUS_SKIPPED = "skipped"

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
      1. 當下已 staged（`git diff --cached --name-status`，依 status 過濾
         已刪除路徑，見下方刪除／改名處理）
      2. 同指令內 `git add` 或 commit pathspec 參數位置字面提及的路徑
         （見 `_iter_literal_pathspec_segments`，涵蓋 `git add x && git
         commit` 串接情境，且排除非該參數位置的字面提及，如 JSON payload
         或 echo 字面；見檔頭範疇邊界）
    僅保留 `.claude/hooks/` 下不含更深層路徑分隔符（無巢狀子目錄）的
    `*.py`（與 candidate_tests 命名慣例一致，排除 tests/ 與 lib/ 子目錄）。

    刪除／改名處理：`--name-status` 每行首欄為 status 字母
    （A/M/D/R100...）。已刪除（`D`）的 hook 檔不存在於工作樹，無對應測試
    可檢查，故略過，否則已刪除的 hook 每次都被誤判為「觸及但無對應測試」
    產生噪音提醒（噪音累積會讓真警告被忽略）。已改名（`R`）行格式為
    `status\told_path\tnew_path`，僅新路徑仍存在，取最後一欄
    （`fields[-1]`）即同時涵蓋 A/M（單欄路徑）與 R（雙欄取新路徑）兩種
    情況，舊路徑不採計。
    """
    filenames: Set[str] = set()

    success, output = run_git_command(
        ["diff", "--cached", "--name-status", "-z"], cwd=host_root
    )
    if success and output:
        for status, _old_path, new_path in parse_name_status_z(output):
            if status.startswith("D"):
                continue
            m = re.fullmatch(r"\.claude/hooks/([\w.\-]+\.py)", new_path)
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


def _run_pytest(
    test_paths: List[Path], hooks_dir: Path, logger, timeout: Optional[float] = None
) -> "tuple[str, str]":
    """跑指定測試檔清單，回傳 (狀態, 輸出末段)。狀態為 pass / red / timeout。"""
    limit = PER_FILE_TIMEOUT if timeout is None else timeout
    cmd = ["uv", "run", "--project", str(hooks_dir), "pytest", "-q"] + [
        str(p) for p in test_paths
    ]
    logger.info("執行目標測試（timeout=%ss）: %s", limit, cmd)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=limit,
        )
    except subprocess.TimeoutExpired:
        logger.warning("目標測試執行逾時（%ss），保守判定為失敗", limit)
        return _STATUS_TIMEOUT, f"測試逾時（{limit:g}s）"
    output_tail = "\n".join((result.stdout + result.stderr).splitlines()[-20:])
    status = _STATUS_PASS if result.returncode == 0 else _STATUS_RED
    logger.info("目標測試結果: returncode=%d", result.returncode)
    return status, output_tail


def _run_all_tests(
    tested: Dict[str, Path], hooks_dir: Path, logger
) -> "Dict[str, tuple[str, str]]":
    """逐檔執行，回傳 {hook檔名: (狀態, 輸出末段)}。

    每檔逾時 = min(PER_FILE_TIMEOUT, 剩餘總預算)；預算耗盡後其餘檔案標記
    skipped（保守方向：視同未通過，不放行）。最壞總耗時 <= TOTAL_BUDGET。
    """
    deadline = time.monotonic() + TOTAL_BUDGET
    results = {}
    for hook_filename, test_path in sorted(tested.items()):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            logger.warning("總預算 %ss 耗盡，未執行: %s", TOTAL_BUDGET, hook_filename)
            results[hook_filename] = (
                _STATUS_SKIPPED,
                f"總預算 {TOTAL_BUDGET}s 耗盡，未執行",
            )
            continue
        timeout = min(PER_FILE_TIMEOUT, remaining)
        results[hook_filename] = _run_pytest([test_path], hooks_dir, logger, timeout)
    return results


_BOUNDARY_NOTE = (
    "範疇邊界：本 gate 僅驗證被改動 hook 檔本身的對應測試，"
    "不涵蓋跨檔破壞（如改共用模組導致其他 hook 測試轉紅）。"
)


_STATUS_LABELS = {
    _STATUS_RED: "測試紅燈（未通過）",
    _STATUS_TIMEOUT: "測試逾時（單檔超過上限，疑似卡住）",
    _STATUS_SKIPPED: "未執行（總預算耗盡，保守視為未通過）",
}


def _build_deny_message(tested: Dict[str, Path], results: dict) -> str:
    """區分測試紅、單檔逾時、總預算耗盡未執行，並指名檔案。"""
    lines = []
    tails = []
    for hook_filename, (status, tail) in sorted(results.items()):
        if status == _STATUS_PASS:
            continue
        lines.append(
            f"  - {hook_filename} -> {tested[hook_filename]} : {_STATUS_LABELS[status]}"
        )
        tails.append(f"[{hook_filename}]\n{tail}")
    return (
        "Hooks 目標測試 gate：commit 被阻止\n\n"
        "以下被改動的 hook 檔對應測試未通過：\n"
        + "\n".join(lines)
        + "\n\n測試輸出（末段）：\n"
        + "\n\n".join(tails)
        + f"\n\n{_BOUNDARY_NOTE}\n"
        "請修正對應測試後再重試 commit。"
        f"（單檔上限 {PER_FILE_TIMEOUT}s，總預算 {TOTAL_BUDGET}s）"
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
        results = _run_all_tests(tested, hooks_dir, logger)
        failing = {f: r[0] for f, r in results.items() if r[0] != _STATUS_PASS}
        if failing:
            logger.info("目標測試未通過，阻擋 commit: %s", sorted(failing.items()))
            emit_hook_output(
                "PreToolUse",
                permission_decision="deny",
                permission_decision_reason=_build_deny_message(tested, results),
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
