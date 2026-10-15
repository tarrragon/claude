#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///

"""
Bash Write Boundary Guard Hook - PreToolUse Hook

main-thread-edit-restriction-hook.py 僅註冊於 PreToolUse 的 Edit/Write/MultiEdit
matcher，禁止主線程（PM）寫入 test/、lib/、*.dart。該限制可被 Bash 寫入操作
（heredoc / cat > / cat >> / tee / sed -i / python 內嵌腳本 open() / cp / mv）
完全繞過，繞過後無留痕、無法事後偵測（來源分析結論：職責邊界執法類 guard，
繞過後不可事後偵測，須以 PreToolUse 層攔截，不能靠事後補救）。本 hook 是該
缺口的補網。

觸發時機: 執行 Bash 工具時
行為: 偵測到明確寫入 test/、lib/、*.dart 的 Bash 語法 → 轉呼
      lib/path_permission.check_file_permission() 判斷 → 不允許則 DENY（exit 2）；
      未偵測到明確寫入目標 → 一律 ALLOW（保守白名單策略，fail-open）。

範圍與 main-thread-edit-restriction-hook.py 部分一致：
- Subagent 環境跳過（此限制僅約束主線程）
- 開發分支（feat/*、fix/* 等）跳過
- 不含跨專案判斷：Bash command 無單一 file_path，無法用
  find_target_repo() 判斷目標 repo；candidate path 皆以當前
  CLAUDE_PROJECT_DIR 正規化，跨專案 Bash 寫入若剛好命中
  test/lib/dart pattern 仍會被攔（已知的偏保守行為，優先度低於
  漏放）

偵測形態：
- cat > path / cat >> path（含 heredoc 重導向 `cat > path <<'EOF' ... EOF`）
- tee path / tee -a path
- sed -i ... path / sed --in-place ... path（原地編輯目標）
- python -c / python3 heredoc 內嵌腳本中的 open('path', ...) 呼叫
- cp src dst / mv src dst（目的地路徑）
- 一般輸出重導向 > path / >> path（排除檔案描述符重導向 2>、&>）

解析方式：
命令以單趟字元走訪切成「陳述 -> token」，每個字元只看一次，整體 O(n)，
不使用有回溯風險的複合正則（sed 判定用的正則曾兩度因回溯耗時形成逾時繞過）。
- heredoc 正文與引號內文字不是命令：不進入 token 走訪，描述寫入的文字不誤擋
- 例外：陳述的命令為 python* 時，其原文與 heredoc 正文掃描 open() 呼叫；
  命令為 sh/bash/zsh 時，heredoc 正文會被執行，遞迴解析（深度 2）
- bash -c '...' 字串內的寫入不在本 hook 範圍

FP 邊界（fail-open，保守白名單原則）：
抽出候選路徑後僅在正規化後命中 test/、lib/、*.dart 才轉呼判斷邏輯；
未命中或無法辨識寫入語法一律放行，不做「default deny」。
不設命令長度上限：解析為線性，長度上限只會增加誤擋面（大型 heredoc 正文
合法存在），不增加防護。
"""

import re
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent))         # .claude/hooks/
sys.path.insert(0, str(Path(__file__).parent.parent))   # .claude/       (lib.*)

from lib import setup_hook_logging, run_hook_safely, read_json_from_stdin, is_subagent_environment, emit_hook_output
from lib.git_utils import get_current_branch, is_allowed_branch
from lib.path_permission import check_file_permission, normalize_path

EXIT_ALLOW = 0
EXIT_BLOCK = 2

_MAX_HEREDOC_RECURSION = 2


# ============================================================================
# 命令解析：單趟 token 走訪（O(n)）
# ============================================================================

# 無特殊意義的連續字元，整段一次吃掉（字元集互斥，無回溯）
_PLAIN_RUN = re.compile(r"[^'\"\\\s;|&()`<>#]+")

# python open('path', ...) / open("path", ...)
_OPEN_CALL_PATTERN = re.compile(r"open\(\s*(['\"])([^'\"]+)\1")

_PYTHON_NAME = re.compile(r"python[\d.]*")
_SHELL_NAMES = frozenset({"sh", "bash", "zsh"})
_HEREDOC_DELIM_STOP = frozenset(" \t\r\n;|&()<>")


class _Statement:
    """一個以 | ; & 換行 ( ) 切出的陳述。"""

    __slots__ = ("tokens", "targets", "bodies", "start", "end")

    def __init__(self, start: int) -> None:
        self.tokens: List[str] = []    # 引號已剝除的 token（不含重導向目標）
        self.targets: List[str] = []   # 輸出重導向目標
        self.bodies: List[str] = []    # 此陳述宣告的 heredoc 正文
        self.start = start
        self.end = start


def _read_heredoc_delimiter(command: str, i: int):
    """從 i 讀 heredoc 結束標記（去引號與反斜線），回傳 (word, 下一位置)。"""
    n = len(command)
    word: List[str] = []
    while i < n and command[i] not in _HEREDOC_DELIM_STOP:
        c = command[i]
        if c not in "'\"\\":
            word.append(c)
        i += 1
    return "".join(word), i


def _read_heredoc_bodies(command: str, pos: int, pending):
    """自 pos（換行後）依序讀取每個 pending heredoc 的正文，回傳 (bodies, 新位置)。"""
    n = len(command)
    bodies: List[str] = []
    for strip_tabs, word in pending:
        lines: List[str] = []
        while pos <= n:
            eol = command.find("\n", pos)
            if eol == -1:
                eol = n
            line = command[pos:eol]
            pos = eol + 1
            if (line.lstrip("\t") if strip_tabs else line) == word:
                break
            lines.append(line)
            if eol == n:
                break
        bodies.append("\n".join(lines))
    return bodies, min(pos, n)


def _parse_statements(command: str) -> List[_Statement]:
    """單趟走訪，把命令切成陳述與 token；每個字元至多處理一次。"""
    n = len(command)
    stmts: List[_Statement] = []
    cur = _Statement(0)
    buf: List[str] = []
    has_tok = False
    redirect: Optional[str] = None  # None / 'write' / 'skip'
    pending: list = []
    i = 0

    def flush() -> None:
        nonlocal buf, has_tok, redirect
        if not has_tok:
            return
        text = "".join(buf)
        if redirect == "write":
            cur.targets.append(text)
        elif redirect != "skip":
            cur.tokens.append(text)
        redirect = None
        buf = []
        has_tok = False

    def end_statement(end_pos: int, next_start: int) -> None:
        nonlocal cur, redirect
        flush()
        cur.end = end_pos
        if cur.tokens or cur.targets or cur.bodies:
            stmts.append(cur)
        cur = _Statement(next_start)
        redirect = None

    while i < n:
        c = command[i]
        m = _PLAIN_RUN.match(command, i)
        if m:
            buf.append(m.group())
            has_tok = True
            i = m.end()
        elif c == "'":
            j = command.find("'", i + 1)
            j = n if j == -1 else j
            buf.append(command[i + 1:j])
            has_tok = True
            i = j + 1
        elif c == '"':
            j = i + 1
            while j < n and command[j] != '"':
                j += 2 if command[j] == "\\" else 1
            buf.append(command[i + 1:min(j, n)])
            has_tok = True
            i = j + 1
        elif c == "\\":
            if i + 1 < n and command[i + 1] != "\n":
                buf.append(command[i + 1])
                has_tok = True
            i += 2
        elif c == "\n":
            if pending:
                bodies, nxt = _read_heredoc_bodies(command, i + 1, pending)
                cur.bodies.extend(bodies)
                pending = []
                end_statement(i, nxt)
                i = nxt
            else:
                end_statement(i, i + 1)
                i += 1
        elif c in " \t\r":
            flush()
            i += 1
        elif c == "#" and not has_tok:
            j = command.find("\n", i)
            i = n if j == -1 else j
        elif c == ">":
            is_fd = has_tok and "".join(buf).isdigit()
            if is_fd:
                buf = []
                has_tok = False
            else:
                flush()
            i += 2 if command.startswith(">>", i) else 1
            skip = is_fd
            if i < n and command[i] in "&|":
                skip = skip or command[i] == "&"
                i += 1
            redirect = "skip" if skip else "write"
        elif c == "<":
            if command.startswith("<<<", i):
                flush()
                i += 3
            elif command.startswith("<<", i):
                flush()
                i += 2
                strip_tabs = i < n and command[i] == "-"
                i += 1 if strip_tabs else 0
                while i < n and command[i] in " \t":
                    i += 1
                word, i = _read_heredoc_delimiter(command, i)
                pending.append((strip_tabs, word))
            else:
                flush()
                redirect = "skip"
                i += 1
        elif c == "&" and command.startswith("&>", i):
            flush()
            i += 3 if command.startswith("&>>", i) else 2
            redirect = "skip"
        else:
            # ; | & ( ) `：陳述邊界
            end_statement(i, i + 1)
            i += 1

    end_statement(n, n)
    return stmts


def _basename(token: str) -> str:
    return token.rsplit("/", 1)[-1]


def _skip_empty_or_suffix(toks: List[str], j: int) -> int:
    """BSD 形式 `-i ''` / `-i .bak`：略過 -i 之後的備份後綴 token。"""
    if j < len(toks) and (toks[j] == "" or toks[j].startswith(".")):
        return j + 1
    return j


def _scan_sed(toks: List[str], j: int, out: List[str]) -> int:
    """從 sed 之後的 token 起走訪一次，原地編輯時收集檔案目標，回傳結束位置。"""
    m = len(toks)
    inplace = False
    has_script_opt = False
    end_opts = False
    positionals: List[str] = []
    while j < m:
        t = toks[j]
        j += 1
        if end_opts or t == "" or t[0] != "-" or t == "-":
            positionals.append(t)
        elif t == "--":
            end_opts = True
        elif t.startswith("--"):
            if t.startswith("--in-place"):
                inplace = True
            elif t in ("--expression", "--file"):
                has_script_opt = True
                j += 1
            elif t.startswith(("--expression=", "--file=")):
                has_script_opt = True
        else:
            k = 1
            while k < len(t):
                ch = t[k]
                if ch == "i":
                    inplace = True
                    if t == "-i":
                        j = _skip_empty_or_suffix(toks, j)
                    break
                if ch in "ef":
                    has_script_opt = True
                    if k == len(t) - 1:
                        j += 1
                    break
                k += 1
    if inplace:
        out.extend(positionals if has_script_opt else positionals[1:])
    return m


def _scan_cp_mv(toks: List[str], j: int, out: List[str]) -> int:
    """cp / mv：略過旗標，最後一個位置參數為目的地（至少需要來源與目的地）。"""
    positionals = [t for t in toks[j:] if t == "" or t[0] != "-"]
    if len(positionals) >= 2:
        out.append(positionals[-1])
    return len(toks)


def _scan_tee(toks: List[str], j: int, out: List[str]) -> int:
    out.extend(t for t in toks[j:] if t == "" or t[0] != "-")
    return len(toks)


def _scan_statement_tokens(toks: List[str], out: List[str]) -> None:
    j = 0
    while j < len(toks):
        name = _basename(toks[j])
        if name == "sed":
            j = _scan_sed(toks, j + 1, out)
        elif name in ("cp", "mv"):
            j = _scan_cp_mv(toks, j + 1, out)
        elif name == "tee":
            j = _scan_tee(toks, j + 1, out)
        else:
            j += 1


def _collect_candidates(command: str, depth: int) -> List[str]:
    candidates: List[str] = []
    for stmt in _parse_statements(command):
        candidates.extend(stmt.targets)
        _scan_statement_tokens(stmt.tokens, candidates)
        names = [_basename(t) for t in stmt.tokens]
        if any(_PYTHON_NAME.fullmatch(name) for name in names):
            for text in [command[stmt.start:stmt.end]] + stmt.bodies:
                candidates.extend(m.group(2) for m in _OPEN_CALL_PATTERN.finditer(text))
        if depth < _MAX_HEREDOC_RECURSION and any(name in _SHELL_NAMES for name in names):
            for body in stmt.bodies:
                candidates.extend(_collect_candidates(body, depth + 1))
    return candidates


def _extract_candidate_paths(command: str) -> List[str]:
    """
    從 Bash 命令抽取所有候選寫入目標路徑（單趟 token 走訪，O(n)）。

    heredoc 正文與引號內文字不當命令解析（描述寫入的文字不誤擋）；
    python 陳述的 open() 呼叫與 sh/bash/zsh 的 heredoc 正文因會被執行而納入。

    Returns:
        List[str] - 候選路徑清單（未去重、未正規化）
    """
    return _collect_candidates(command, 0)


def _find_boundary_violation(command: str, logger) -> Optional[str]:
    """
    掃描命令的所有候選寫入路徑，回傳第一個命中 test/、lib/、*.dart 且
    check_file_permission 判定不允許的正規化路徑；無命中回傳 None。

    Args:
        command: Bash 命令
        logger: hook logger

    Returns:
        Optional[str] - 命中的正規化路徑，或 None
    """
    for raw_path in _extract_candidate_paths(command):
        normalized = normalize_path(raw_path)

        # 窄化門檻：僅 test/、lib/、*.dart 才進一步判斷（本票範圍，
        # 避免抽取雜訊觸發 check_file_permission 的 default-deny 分支）
        is_target_scope = (
            normalized.startswith("test/")
            or normalized.startswith("lib/")
            or normalized.endswith(".dart")
        )
        if not is_target_scope:
            continue

        is_allowed, reason = check_file_permission(raw_path, logger)
        if not is_allowed:
            logger.warning(
                "偵測到 Bash 寫入職責邊界違規: path=%s reason=%s command=%s",
                normalized, reason, command,
            )
            return normalized

    return None


def _allow_and_exit(logger, reason: str) -> int:
    emit_hook_output("PreToolUse", permission_decision="allow", permission_decision_reason=reason)
    return EXIT_ALLOW


def main() -> int:
    """
    主入口點

    流程: 初始化 → 讀取輸入 → 工具/subagent/分支/跨專案過濾 → 候選路徑抽取
          → 命中則轉呼 check_file_permission → 輸出
    """
    logger = setup_hook_logging("bash-write-boundary-guard")

    logger.info("Bash Write Boundary Guard Hook 啟動")

    input_data = read_json_from_stdin(logger)
    if not input_data:
        logger.debug("輸入為空或解析失敗，返回預設允許")
        return _allow_and_exit(logger, "輸入為空，預設允許")

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input") or {}

    if tool_name != "Bash":
        logger.debug(f"跳過: 工具類型 {tool_name} 不是 Bash")
        return _allow_and_exit(logger, f"工具 {tool_name} 不在檢查範圍")

    # Subagent 跳過：此 Hook 是 main-thread-edit-restriction 的 Bash 補網，
    # 僅限制主線程
    if is_subagent_environment(input_data):
        logger.info(f"subagent 環境（agent_id={input_data.get('agent_id')}），跳過 Bash 寫入邊界限制")
        return _allow_and_exit(logger, "subagent 不受主線程 Bash 寫入邊界限制")

    command = tool_input.get("command", "")
    if not command:
        return _allow_and_exit(logger, "command 為空，允許")

    # 開發分支跳過（feat/*, fix/* 等），與 main-thread-edit-restriction 一致
    current_branch = get_current_branch()
    if current_branch and is_allowed_branch(current_branch):
        logger.info(f"開發分支 '{current_branch}' 上，跳過 Bash 寫入邊界限制")
        return _allow_and_exit(logger, f"開發分支 '{current_branch}' 不受主線程 Bash 寫入邊界限制")

    violation_path = _find_boundary_violation(command, logger)

    if violation_path is None:
        logger.debug("未偵測到明確的 test/lib/dart 寫入目標，允許（fail-open）")
        return _allow_and_exit(logger, "未偵測到職責邊界違規的 Bash 寫入形態")

    reason = (
        f"偵測到 Bash 寫入職責邊界違規（path={violation_path}）。"
        "主線程禁止透過 Bash（cat/tee/sed -i/python open()/cp/mv/heredoc 等）"
        "寫入 test/、lib/、*.dart，等同繞過 main-thread-edit-restriction-hook.py "
        "的職責邊界執法。請改派代理人執行此寫入。"
    )
    emit_hook_output(
        "PreToolUse",
        permission_decision="deny",
        permission_decision_reason=reason,
    )
    logger.info("Hook 檢查完成，exit code: %d", EXIT_BLOCK)
    return EXIT_BLOCK


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "bash-write-boundary-guard"))
