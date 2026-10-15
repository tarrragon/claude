#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
Global Pkill Guard Hook - PreToolUse Hook

功能: 拒絕 Bash 命令位置出現 pkill / killall（以名稱或樣式比對全機程序），
      以及 `orphan-test-procs.py --kill` 搭配 `--root` 的越界用法。

Hook Event: PreToolUse
Matcher: Bash
Decision: DENY（exit 2，stderr 訊息）| allow（無輸出）

Why: 代理人停手時以 pkill 終止全機測試程序，波及其他 worktree 與其他專案
     且未回報。
Consequence: 被擋的一方若不知替代做法會繞道，故訊息必含替代做法。
Action: 孤兒清理改用 `python3 .claude/scripts/orphan-test-procs.py`；
        已知目標改用 `kill <PID>` 或 `kill -- -<PGID>`。

判準: 以 lib.git_command_parse.parse_command_statements 切語句，僅檢查
      「命令位置 token」（跳過 sudo/nohup/time/xargs/env/KEY=VAL 前綴），
      echo / grep 引數中的字面出現不命中。`bash|sh|zsh -c '<script>'` 遞迴
      解析其腳本字串。無法 tokenize（未閉合引號）fail-open。

框架內既有用法盤點（2026-10-14，.claude 下 hooks/scripts/lib/skills/
references/pm-rules/rules/methodologies/agents）:
  - 可執行程式碼中無任何 pkill / killall 呼叫，無須放行例外。
  - hooks/tests/test_post_test_hook.py: 斷言輸出不含 pkill 字樣，非呼叫。
  - skills/dart-test-async-guardian/SKILL.md、references/agent-dispatch-
    template.md: 文件中「禁用」敘述，非呼叫。

範疇邊界（刻意不做）:
  - 僅見 Bash 工具的字面命令；腳本檔或 hook 以程式碼方式（subprocess、
    os.kill 等）執行全機終止，本守衛結構性不可見。該路徑由測試監控 hook
    的零終止斷言承擔（其清單外的 os.spawn / os.exec / asyncio 子程序
    仍屬該 hook 的缺口，不由本守衛承擔）。
  - `xargs kill`、`kill $(pgrep ...)` 形態不攔截（kill 本身以 PID 作用，
    且 pgrep 為唯讀）。
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import setup_hook_logging, run_hook_safely, read_json_from_stdin
from lib.git_command_parse import parse_command_statements, skip_prefix_wrapper_count

_BANNED = frozenset({"pkill", "killall"})
_SHELLS = frozenset({"bash", "sh", "zsh"})
# 非執行者清單：漏收錄的方向是多擋而非放行
_VIEW_PROGS = frozenset({
    "echo", "printf", "grep", "egrep", "fgrep", "rg", "man", "which", "type",
    "ls", "cat", "head", "tail", "less", "whereis", "apropos",
})
_ORPHAN_SCRIPT = "orphan-test-procs.py"
_MAX_DEPTH = 3


# 閱讀類命令中可執行外部命令的選項（exact 為整個 token，prefix 為字首比對）。
# 環境變數（PAGER、LESSOPEN 等）與設定檔內的執行器不在命令文字，屬已知殘留。
_EXEC_OPTS = {
    "rg": {"exact": ("--pre",), "prefix": ("--pre=",)},
    "man": {"exact": ("-P", "--pager"), "prefix": ("-P", "--pager=", "-H", "--html=")},
    "less": {"exact": (), "prefix": ("+",)},
}
_SPLIT_RE = re.compile(r"[\s=]+")


def _has_exec_option(prog: str, rest: List[str]) -> bool:
    spec = _EXEC_OPTS.get(prog)
    if not spec:
        return False
    return any(t in spec["exact"] or t.startswith(spec["prefix"]) for t in rest)


def _expand_tokens(stmt: List[str]) -> List[str]:
    """把含空白、等號的 token 拆成片段，並去掉 less 啟動命令的 +/! 前綴。"""
    out: List[str] = []
    for tok in stmt:
        out.append(tok)
        if _SPLIT_RE.search(tok) or tok.startswith(("+", "!")):
            out.extend(p.lstrip("+!") for p in _SPLIT_RE.split(tok) if p)
        if tok.startswith("-") and not tok.startswith("--") and len(tok) > 2:
            out.append(tok[2:])  # 黏寫短選項值（-Hpkill、-Ppkill）
    return out


def _is_view_statement(prog: str, rest: List[str]) -> bool:
    """命令位置為閱讀類（非執行者）時，其引數中的 pkill 字樣只是文字。"""
    if prog in _VIEW_PROGS:
        return not _has_exec_option(prog, rest)
    if prog != "command":
        return False
    # 只看 command 自身的選項（命令名之前、以 - 開頭），遇第一個非選項即停；
    # 其後的 -v/-V 屬被執行命令（如 pkill -v）的參數，不得豁免。
    for t in rest:
        if not t.startswith("-") or t == "-":
            return False
        if t in ("-v", "-V"):
            return True
    return False


def _scan_any_position(stmt: List[str], depth: int) -> Optional[str]:
    """語句內任何 token 的 basename 為 pkill/killall 即命中；shell -c 遞迴。"""
    for i, tok in enumerate(stmt):
        base = os.path.basename(tok)
        if base in _BANNED:
            return base
        if base in _SHELLS and depth < _MAX_DEPTH:
            rest = stmt[i + 1:]
            for j, t in enumerate(rest[:-1]):
                if t.startswith("-") and not t.startswith("--") and "c" in t:
                    found = _find_violation(rest[j + 1], depth + 1)
                    if found:
                        return found
                    break
    return None


def _find_violation(command: str, depth: int = 0) -> Optional[str]:
    """回傳違規類別（'pkill'／'killall'／'orphan-root'）或 None。"""
    statements = parse_command_statements(command)
    if not statements:
        return None
    for stmt in statements:
        idx = skip_prefix_wrapper_count(stmt)
        if idx >= len(stmt):
            continue
        prog = os.path.basename(stmt[idx])
        vidx = skip_prefix_wrapper_count(stmt, extended=True)
        if vidx >= len(stmt):
            vidx = idx
        vprog = os.path.basename(stmt[vidx])
        if not _is_view_statement(vprog, stmt[vidx + 1:]):
            found = _scan_any_position(stmt, depth)
            if not found and vprog in _EXEC_OPTS:
                found = _scan_any_position(_expand_tokens(stmt), depth)
            if found:
                return found
        # 直接或經 python 直譯器呼叫孤兒清理腳本
        args = stmt[idx:]
        if any(os.path.basename(t) == _ORPHAN_SCRIPT for t in args):
            has_kill = "--kill" in args
            has_root = any(t == "--root" or t.startswith("--root=") for t in args)
            if has_kill and has_root:
                return "orphan-root"
    return None


def _message(kind: str, command: str) -> str:
    head = f"被攔截的命令：{command[:200]}\n\n"
    if kind == "orphan-root":
        why = ("理由：`orphan-test-procs.py --kill` 搭配 `--root` 會終止指定目錄下"
               "所有符合條件的程序，指向專案以外的目錄即波及其他專案。\n\n")
    else:
        why = (f"理由：`{kind}` 以名稱或樣式比對全機程序，會終止其他 worktree 與"
               "其他專案的測試程序。\n\n")
    alt = (
        "替代做法：\n"
        "  1. 清理本專案逾時或中斷留下的孤兒測試程序：\n"
        "     python3 .claude/scripts/orphan-test-procs.py        # 預設只列出\n"
        "     python3 .claude/scripts/orphan-test-procs.py --kill # 只終止本專案範圍\n"
        "     （不帶 --root；--root 僅供測試縮小範圍）\n"
        "  2. 已知目標：`kill <PID>`，或終止整個程序群組 `kill -- -<PGID>`。\n"
        "  3. 逾時控制：python3 .claude/scripts/run-with-timeout.py\n"
        "誤擋時的改寫方式（守衛掃描語句內任何位置的 pkill/killall token）：\n"
        "  - 閱讀類命令（echo/printf/grep/rg/man/which/type/ls/cat/command -v）已放行，無須改寫。\n"
        "    例外：帶執行類選項（rg --pre、man -P/--pager/-H/--html=、less +）時，"
        "上述放行不適用，選項值會被當成執行器掃描。\n"
        "  - 只是把字樣當參數（如 git log --grep pkill）：改寫成不含完整字樣的樣式，如 p[k]ill。\n"
        "  - 遠端或容器內執行（ssh/docker exec/kubectl exec）：改 `kill <PID>`，或在目標端另行處理。\n"
    )
    return "[全機 pkill/killall 被阻擋]\n\n" + head + why + alt


def main() -> int:
    logger = setup_hook_logging("global-pkill-guard")
    try:
        input_data = read_json_from_stdin(logger)
    except (json.JSONDecodeError, EOFError):
        logger.info("無法解析 stdin JSON，放行")
        return 0
    if not input_data or input_data.get("tool_name") != "Bash":
        return 0
    command = (input_data.get("tool_input") or {}).get("command", "") or ""
    if not command or not any(k in command for k in ("pkill", "killall", _ORPHAN_SCRIPT)):
        return 0
    kind = _find_violation(command)
    if kind is None:
        logger.debug("無違規命令位置 token，放行")
        return 0
    logger.warning("全機終止命令被阻擋（%s）：%s", kind, command[:200])
    print(_message(kind, command), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "global-pkill-guard"))
