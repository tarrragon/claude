#!/usr/bin/env python3
"""
Git 命令解析共用工具

提供 Bash PreToolUse git 守衛共用的「什麼算一次 git 呼叫」定義。三個既有
守衛（bare-commit-guard-hook.py / bash-git-protected-branch-guard-hook.py /
bash-git-add-broad-guard-hook.py）各自獨立解析 Bash 命令字串找出 git 呼叫，
各自對「一次 git 呼叫」的定義不同，各自留下不同的破口（heredoc 內文誤判、
廣域 add 形式無法列舉而放棄處理、前綴包裹與全域選項一律看不見）。本模組
把「找出 git 呼叫」這一步收斂為單一定義，各守衛的判決邏輯（是否為廣域
add、是否命中保護分支、是否為 index-discarding commit 等）不受影響，仍
各自保留。

主要功能:
- strip_heredoc_bodies: 移除 heredoc 本體，含找不到收尾界線時的保底還原
- normalize_newlines_to_separators: 把不在引號內的換行轉為顯式語句分隔符
- is_literal_pathspec_token: 判斷 token 是否為可靜態列舉的具體檔案路徑
- is_shell_redirection_token: 判斷 token 是否為 shell 重導向符號
- find_git_invocations: 解析命令字串，回傳指定子命令的結構化呼叫記錄
- GitInvocation: 單次 git 呼叫的結構化記錄

失敗語意（供呼叫端做出各自的 fail-open / fail-closed 決策，見下方
`find_git_invocations` docstring 的「回傳值」段）：
- `None`：命令字串無法安全解析（shlex 遇未閉合引號），呼叫端須自行決定
  如何處置——本模組不替呼叫端決定，因為三個守衛的誤報/漏報代價不同。
- `[]`（空清單）：命令字串可正常解析，但其中沒有符合條件的 git 呼叫。

兩者刻意不可互相混淆：`None` 與 `[]` 在 Python 的布林語境下都是 falsy，
呼叫端必須用 `is None` 明確區分，不可只寫 `if not invocations:`。
"""

import logging
import os
import re
import shlex
import subprocess
import time
from dataclasses import dataclass, field, replace
from typing import FrozenSet, Iterable, List, Optional, Tuple


# ===== 便宜前置判斷 =====

_GIT_WORD_RE = re.compile(r"\bgit\b")


def contains_git_word(command: str) -> bool:
    """判斷命令字串是否含獨立的 `git` 字樣。

    供各守衛在呼叫較昂貴的 `find_git_invocations` 之前先行短路：非 git
    命令（Bash 工具最大宗）可在此便宜判斷後直接放行，不需承擔 heredoc
    剝離 + tokenize 的完整解析成本。三個既有守衛皆各自維護過相同的一行
    正則判斷，此處收斂為單一來源。
    """
    if not command:
        return False
    return bool(_GIT_WORD_RE.search(command))


# ===== heredoc 本體剝離 =====

# heredoc 起始標記：`<<DELIM` / `<<'DELIM'` / `<<"DELIM"` / `<<-DELIM`
_HEREDOC_START_RE = re.compile(r"<<-?\s*(['\"]?)(\w+)\1")


def strip_heredoc_bodies(command: str) -> str:
    """移除 heredoc 內文，避免文件/ticket 撰寫內容的命令字面被誤判為實際命令。

    保底：若掃描到命令結尾仍找不到對應的結束界線行（heredoc 起始標記可能
    只是引號內文字恰好長得像該語法，並非真正的 heredoc），視為無法安全
    判定內文範圍，直接還原整段原始命令、不做任何剝離——避免誤報修正本身
    反過來吞掉起始標記之後的所有真實內容而造成漏報。剝離失敗方向刻意
    偏向「不剝離」而非「過度剝離」：前者最壞情況是誤判未消除，後者最壞
    情況是把真實命令吞掉造成漏放。
    """
    if "<<" not in command:
        return command

    lines = command.split("\n")
    result: List[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        result.append(line)
        match = _HEREDOC_START_RE.search(line)
        if match:
            delimiter = match.group(2)
            j = i + 1
            while j < len(lines) and lines[j].strip() != delimiter:
                j += 1
            if j >= len(lines):
                # 找不到結束界線：無法安全判定範圍，還原原文（保底）
                return command
            i = j + 1  # 跳過內文與結束界線本身
            continue
        i += 1
    return "\n".join(result)


# ===== 換行正規化 =====


def normalize_newlines_to_separators(command: str) -> str:
    """把不在引號內的換行字元轉為顯式 `;` 分隔符。

    shlex 預設把換行當空白吞掉，使多行命令攤平成單一 token 流，若判定邏輯
    只看語句開頭第一個 token，會使非首行的 git 呼叫完全逃逸。此函式在
    tokenize 之前先行正規化，讓後續的語句切分機制自然涵蓋多行情境。
    未處理跳脫引號等複雜情境，與本模組其餘函式的引號處理深度一致。
    """
    result: List[str] = []
    in_single = False
    in_double = False
    for ch in command:
        if ch == "'" and not in_double:
            in_single = not in_single
            result.append(ch)
        elif ch == '"' and not in_single:
            in_double = not in_double
            result.append(ch)
        elif ch == "\n" and not in_single and not in_double:
            result.append(" ; ")
        else:
            result.append(ch)
    return "".join(result)


# ===== 註解剝除 =====

# `#` 位於這些字元之後（或行首）才是詞首，才開啟 shell 註解
_COMMENT_BOUNDARY_CHARS = frozenset(" \t\n;&|(")


def strip_line_comments(command: str) -> str:
    """剝除 shell 註解：詞首的 `#` 起至行尾（不含換行）。

    引號內的 `#` 與詞中的 `#`（如 `a#b`）不是註解，與 bash 語意一致。
    必須在換行正規化之前執行：換行轉成分號後，shlex 的註解處理會把該行
    起至命令結尾全部丟棄，使其後語句的 git 呼叫漏判。
    """
    result: List[str] = []
    in_single = False
    in_double = False
    in_comment = False
    escaped = False
    prev = "\n"
    prev_before_backslash = "\n"
    for ch in command:
        if in_comment:
            if ch == "\n":
                in_comment = False
                result.append(ch)
                prev = ch
            continue
        if escaped:
            escaped = False
            if ch == "\n":
                # 行接續（單引號外的反斜線加換行）：bash 先合併再判斷註解，
                # 彈出已加入的反斜線並略過換行，prev 還原為反斜線之前的字元
                result.pop()
                prev = prev_before_backslash
                continue
        elif ch == "\\" and not in_single:
            escaped = True
            prev_before_backslash = prev
        elif ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double and prev in _COMMENT_BOUNDARY_CHARS:
            in_comment = True
            continue
        result.append(ch)
        prev = ch
    return "".join(result)


# ===== 反引號命令替換 =====


def extract_backtick_bodies(command: str) -> List[str]:
    """取出反引號命令替換的本體（單引號內不算；雙引號內仍會執行，算）。

    本體另成語句掃描，原命令字串不改動，使 `git -C `pwd`/x commit` 這類
    「反引號是參數」的寫法仍保有原本的判讀。未閉合的反引號不取。
    """
    bodies: List[str] = []
    in_single = False
    in_double = False
    buf: Optional[List[str]] = None
    prev = ""
    for ch in command:
        if buf is not None:
            if ch == "`" and prev != "\\":
                bodies.append("".join(buf))
                buf = None
            else:
                buf.append(ch)
        elif ch == "'" and not in_double and prev != "\\":
            in_single = not in_single
        elif ch == '"' and not in_single and prev != "\\":
            in_double = not in_double
        elif ch == "`" and not in_single and prev != "\\":
            buf = []
        prev = ch
    return bodies


# ===== 括號正規化 =====

_logger = logging.getLogger("git_command_parse")


def space_shell_parens(command: str) -> str:
    """在不在引號內、未被反斜線跳脫的 `(` `)` 兩側補空白，使其成為獨立 token。

    shlex（punctuation_chars 模式）會把相鄰的標點合併成單一 token，`);` 因此
    黏成一個非分隔符 token，子 shell 閉合後的語句被併進前一個語句，其中的
    git 呼叫漏抓。補空白後 `(` `)` 各自獨立，交由 `_split_statements` 當語句
    邊界。引號內文字不動（引號內括號維持字面）。

    括號無法配對（開閉數量不等）時不拋例外、不改變處理流程，僅寫 debug 日誌：
    語句切分本就把每個括號當獨立邊界，不需配對資訊。
    """
    out: List[str] = []
    quote = ""
    prev = ""
    depth = 0
    unmatched_close = False
    for ch in command:
        if quote:
            if ch == quote and prev != "\\":
                quote = ""
            out.append(ch)
        elif ch in ("'", '"') and prev != "\\":
            quote = ch
            out.append(ch)
        elif ch in "()" and prev != "\\":
            if ch == "(":
                depth += 1
            elif depth > 0:
                depth -= 1
            else:
                unmatched_close = True
            out.append(" " + ch + " ")
        else:
            out.append(ch)
        prev = ch
    if depth > 0 or unmatched_close:
        _logger.debug("命令括號無法配對（未閉合=%d，多餘右括號=%s），照常切分", depth, unmatched_close)
    return "".join(out)


# ===== token 分類 =====

# 廣域 pathspec 特殊字面（目錄列舉 / 全 worktree 語意）
_BROAD_PATHSPEC_LITERALS = frozenset({".", "./", ":/"})

# 萬用字元（含即視為無法靜態列舉）
_GLOB_CHARS = ("*", "?", "[")

# shell 重導向 token（>、>>、<、N>、N>&M、&>）不是路徑
_REDIRECTION_TOKEN_RE = re.compile(r"^&?\d*(>>?|<)&?\d*$")


def is_literal_pathspec_token(token: str) -> bool:
    """判斷 token 是否為可靜態列舉的具體檔案路徑。

    以下情況視為「不可列舉」（廣域）：`.` / `./` / `:/` 等特殊 pathspec、
    含萬用字元、以 `/` 結尾的目錄 pathspec（內容未知，無法列舉具體檔案）。

    本函式是三個守衛「廣域 pathspec」定義的單一來源（SSOT）。統一前
    `bash-git-protected-branch-guard-hook.py` 的對應判斷只檢查字面 `.`，
    未涵蓋 `./` / `:/` / 尾斜線目錄，統一後這三類會改為正確 fail-closed
    （行為變化，非本模組職責延伸——沿用即修正，詳見呼叫端 ticket Solution）。
    """
    if token in _BROAD_PATHSPEC_LITERALS:
        return False
    if any(c in token for c in _GLOB_CHARS):
        return False
    if token.endswith("/"):
        return False
    return True


def is_shell_redirection_token(tok: str) -> bool:
    """判斷 token 是否為 shell 重導向符號（>、>>、<、2>、2>&1 等）。

    這些 token 是 shell 重導向語法的一部分，不是路徑；解析 add/commit
    引數時應略過，避免誤列為非豁免檔案污染 deny 訊息。
    已知殘留：不含與路徑黏在一起無空格的形式（如 `2>/dev/null`），
    該形式仍會被當作路徑列出（多報不漏報，方向安全）。
    """
    return bool(_REDIRECTION_TOKEN_RE.match(tok))


# ===== 前綴包裹與 git 全域選項穿透 =====

# 語句開頭的前綴包裹命令：跳過後繼續尋找 git（不消耗任何選項值）
_PREFIX_COMMANDS_SIMPLE = frozenset({"sudo", "nohup", "time", "xargs"})

# 僅 git 呼叫定位（extended=True）額外跳過；其他呼叫端各有自己的 launcher 剝除
# （test_command_parse 自行處理 timeout／sudo／env 選項），不受此集合影響
_PREFIX_COMMANDS_EXTENDED_SIMPLE = frozenset({"builtin"})
# 帶選項的前綴包裹：選項值（消耗下一個 token）與選項後固定個數的位置參數
# （timeout 的 DURATION）。選項判斷錯誤的最壞結果是找不到 git（漏報），不會誤報。
_WRAPPER_VALUE_OPTIONS = {
    "sudo": frozenset({
        "-u", "-g", "-h", "-p", "-C", "-r", "-t", "-U", "-D", "-R", "-T",
        "--user", "--group", "--host", "--prompt", "--close-from", "--chdir",
    }),
    "env": frozenset({"-u", "-C", "--unset", "--chdir"}),
    "nice": frozenset({"-n", "--adjustment"}),
    "timeout": frozenset({"-s", "-k", "--signal", "--kill-after"}),
    "stdbuf": frozenset({"-i", "-o", "-e", "--input", "--output", "--error"}),
    "caffeinate": frozenset({"-t", "-w"}),
    "time": frozenset(),
    "doas": frozenset({"-u", "-C"}),
    "chronic": frozenset(),
    "flock": frozenset({"-w", "-E", "--timeout", "--wait", "--conflict-exit-code"}),
}
_WRAPPER_POSITIONALS = {"timeout": 1, "flock": 1}  # flock 的位置參數是鎖檔

# 把字串當命令執行的包裹（env -S／flock -c／watch）：不跳過，改交 _wrapper_script 取腳本遞迴解析
_STRING_COMMAND_WRAPPERS = frozenset({"env", "flock", "watch"})
_WATCH_VALUE_OPTIONS = frozenset({"-n", "--interval"})

# 環境變數賦值前綴（如 `FOO=bar git commit ...`），env 本身另外處理
_ENV_ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$")

# git 全域選項：不消耗值
_GIT_GLOBAL_NO_VALUE = frozenset(
    {
        "--no-pager", "--paginate", "-p", "--no-replace-objects",
        "--literal-pathspecs", "--glob-pathspecs", "--noglob-pathspecs",
        "--icase-pathspecs", "--no-optional-locks", "--bare",
    }
)

# git 全域選項：消耗下一個 token 作為值
_GIT_GLOBAL_WITH_VALUE = frozenset(
    {"-c", "--git-dir", "--work-tree", "--namespace", "--super-prefix", "--config-env"}
)

# 子命令別名：SUBCOMMAND_ALIASES[canonical] = 該 canonical 名稱涵蓋的所有字面 token
SUBCOMMAND_ALIASES: dict = {
    "add": frozenset({"add", "stage"}),
}


def _canonical_subcommand(token: str) -> str:
    """把子命令字面 token 正規化為 canonical 名稱（如 `stage` -> `add`）。

    未命中任何別名時原樣回傳（如 `commit` 本身即 canonical，無別名）。
    """
    for canonical, aliases in SUBCOMMAND_ALIASES.items():
        if token in aliases:
            return canonical
    return token


def _expand_subcommand_aliases(subcommands: Iterable[str]) -> FrozenSet[str]:
    """把呼叫端要求的 canonical 子命令集合展開為所有可能的字面 token 集合。"""
    requested = frozenset(subcommands)
    expanded = set(requested)
    for canonical, aliases in SUBCOMMAND_ALIASES.items():
        if canonical in requested:
            expanded |= aliases
    return frozenset(expanded)


def _wrapper_script(tokens: List[str], idx: int) -> Optional[str]:
    """env -S／flock -c／watch 攜帶的命令字串；該包裹沒有字串命令時回 None。

    watch 會把全部引數合併後交給 sh -c，因此一律回合併字串（無引數為空字串）。
    """
    name = tokens[idx]
    value_options = _WATCH_VALUE_OPTIONS if name == "watch" else _WRAPPER_VALUE_OPTIONS.get(name, frozenset())
    i = idx + 1
    while i < len(tokens):
        tok = tokens[i]
        if name == "env":
            if tok in ("-S", "--split-string"):
                return " ".join(tokens[i + 1:])
            if tok.startswith("--split-string="):
                return " ".join([tok.split("=", 1)[1]] + tokens[i + 1:])
            if tok.startswith("-S") and not tok.startswith("--"):
                return " ".join([tok[2:]] + tokens[i + 1:])
            if _ENV_ASSIGNMENT_RE.match(tok):
                i += 1
                continue
        if name == "flock" and tok in ("-c", "--command"):
            return " ".join(tokens[i + 1:])
        if tok == "--":
            i += 1
            break
        if not tok.startswith("-") or tok == "-":
            break
        i += 2 if tok in value_options else 1
    if name == "watch":
        return " ".join(tokens[i:])
    if name == "flock" and i + 1 < len(tokens) and tokens[i + 1] in ("-c", "--command"):
        return " ".join(tokens[i + 2:])  # `flock <鎖檔> -c <字串>`
    return None


def _skip_wrapper_options(tokens: List[str], idx: int, wrapper: str) -> int:
    """跳過 wrapper 之後的選項（含選項值）與其固定位置參數，回傳下一個 token 位置。

    `env` 的 `KEY=VALUE` 賦值不在此處理，交回呼叫端迴圈（與裸賦值同一條路徑）。
    """
    value_options = _WRAPPER_VALUE_OPTIONS[wrapper]
    while idx < len(tokens):
        tok = tokens[idx]
        if tok == "--":
            idx += 1
            break
        if not tok.startswith("-") or tok == "-":
            break
        idx += 2 if tok in value_options else 1
    idx += _WRAPPER_POSITIONALS.get(wrapper, 0)
    return min(idx, len(tokens))


def skip_prefix_wrapper_count(tokens: List[str], extended: bool = False) -> int:
    """計算語句開頭需跳過的前綴包裹與環境變數賦值 token 數，供索引位移用。

    預設涵蓋：`sudo` / `nohup` / `time` / `xargs`（只跳過命令本身，不消耗
    選項值；後面若接該命令自身的選項而非 `git`，後續檢查自然判定為不匹配）、
    `env`（跳過自身與其後任意數量的 `KEY=VALUE`）、裸的 `KEY=VALUE` 賦值前綴。

    `extended=True`（git 呼叫定位用）：`sudo` / `env` / `nice` / `timeout` /
    `stdbuf` / `caffeinate` 連同選項與選項值一併跳過（`timeout` 另含 DURATION），
    並加跳 `builtin`。預設值維持舊行為，其他呼叫端的語意不變。
    """
    idx = 0
    while idx < len(tokens):
        tok = tokens[idx]
        if extended and tok in _STRING_COMMAND_WRAPPERS and _wrapper_script(tokens, idx) is not None:
            break
        if extended and tok in _WRAPPER_VALUE_OPTIONS:
            idx = _skip_wrapper_options(tokens, idx + 1, tok)
            continue
        if tok in _PREFIX_COMMANDS_SIMPLE or (extended and tok in _PREFIX_COMMANDS_EXTENDED_SIMPLE):
            idx += 1
            continue
        if tok == "env":
            idx += 1
            while idx < len(tokens) and _ENV_ASSIGNMENT_RE.match(tokens[idx]):
                idx += 1
            continue
        if _ENV_ASSIGNMENT_RE.match(tok):
            idx += 1
            continue
        break
    return idx


_skip_prefix_wrapper_count = skip_prefix_wrapper_count  # 舊私有名稱別名，供既有匯入沿用


@dataclass(frozen=True)
class GitInvocation:
    """單次 git 呼叫的結構化記錄。

    Attributes:
        statement: 該呼叫所在語句的完整 token 清單（含前綴包裹，供訊息
            顯示用，如 `" ".join(inv.statement)` 還原「被攔截的命令」）。
        subcommand: canonical 子命令名稱（別名已正規化，如 `stage` -> `add`）。
        subcommand_index: `subcommand` 在 `statement` 中的索引位置。
        dash_c_path: `-C <path>` 指定的目標路徑；未使用 `-C` 時為 None。
            僅捕捉第一個 `-C`（多個 `-C` 的相對路徑組合語意不處理，三個
            既有守衛皆未處理此情境，沿用既有範疇邊界）。
        global_options: 消耗掉的 git 全域選項 token（不含其值），供除錯用。
        args: `subcommand` 之後的所有 token（即該子命令自身的旗標與引數）。
        dash_c_paths: 全部 `-C <path>`，依出現順序；預設空 tuple。
            `dash_c_path` 語意不變（仍只取第一個）。
        effective_dir: git 實際作用的目錄：基準目錄（`base_dir` 參數，預設
            None）依語句前的 `cd` 與全部 `-C` 依 git 語意串接（絕對路徑取代、
            相對路徑接續）。無 base_dir 且無 cd/-C 時為 None；基準為 None 時
            相對路徑以相對字串回傳；`dir_unknown` 為真時為 None。
        dir_unknown: 目錄含變數、命令替換、`cd -`、`||` 之後的 cd、`popd`，
            或經由 shell 別名取得時為 True，此時 effective_dir 不可信。預設 False。
        via_scan: 僅 scan 模式的任意位置掃描才命中（命令位置判定找不到）時為
            True；位置命中或未開 scan 時為 False。預設 False。
        dash_c_dirs: 每個已知 `-C` 套用後的累積目錄（`-C a -C b` 為 a、a/b），
            遇動態值即停止；供需要「全部 -C 目標」的呼叫端使用。預設空 tuple。
        經別名展開的呼叫，`statement` 為展開後的 token 序列。
    """

    statement: List[str]
    subcommand: str
    subcommand_index: int
    dash_c_path: Optional[str]
    global_options: List[str] = field(default_factory=list)
    dash_c_paths: Tuple[str, ...] = ()
    effective_dir: Optional[str] = None
    dir_unknown: bool = False
    via_scan: bool = False
    dash_c_dirs: Tuple[str, ...] = ()

    @property
    def args(self) -> List[str]:
        return self.statement[self.subcommand_index + 1:]


# ===== 語句切分 =====

_STATEMENT_SEPARATORS = frozenset({"&&", "||", ";", "|", "&", "(", ")"})


def _tokenize(command: str) -> Optional[List[str]]:
    """以 shlex 保留引號語意做 token 化，運算子（&&/;/|/( )）成為獨立 token。

    回傳 None 表示無法安全解析（未閉合引號等）——與空清單明確區分，見
    模組 docstring「失敗語意」段。
    """
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        lexer.commenters = ""  # 註解已由 strip_line_comments 按行剝除；shlex 會吞掉詞中 `#` 之後內容
        return _merge_fd_duplication(list(lexer))
    except ValueError:
        return None


def _tokenize_command(command: str) -> Optional[List[str]]:
    """完整前處理管線：heredoc 剝離 -> 換行正規化 -> 括號補空白 -> tokenize。

    `parse_command_statements` 與 `find_git_invocations` 共用，確保兩者對同一
    命令字串切出相同的 token 流。
    """
    stripped = strip_line_comments(strip_heredoc_bodies(command))
    bodies = extract_backtick_bodies(stripped)
    if bodies:
        stripped = "\n".join([stripped] + bodies)  # 原文保留（-C `pwd` 等仍可判讀），本體另成語句
    normalized = normalize_newlines_to_separators(stripped)
    return _tokenize(space_shell_parens(normalized))


def _merge_fd_duplication(tokens: List[str]) -> List[str]:
    """把 punctuation_chars 切開的 fd 複製重導向（2>&1）還原為單一 token。

    shlex 將 `2>&1` 切成 `2` / `>&` / `1`，後兩個數字會被下游誤當路徑。
    僅在「數字 + `>&`（或 `<&`）+ 數字」三段成形時合併。
    """
    merged: List[str] = []
    i = 0
    while i < len(tokens):
        if (
            i + 2 < len(tokens)
            and tokens[i].isdigit()
            and tokens[i + 1] in (">&", "<&")
            and tokens[i + 2].isdigit()
        ):
            merged.append(tokens[i] + tokens[i + 1] + tokens[i + 2])
            i += 3
            continue
        merged.append(tokens[i])
        i += 1
    return merged


def _split_statements(tokens: List[str]) -> List[List[str]]:
    """依 shell 語句分隔符切出獨立語句。

    `(` / `)` 亦視為分隔符（而非巢狀範圍邊界）：子 shell 內容因此被攤平為
    獨立語句，可正確找到其中的 git 呼叫，但不保留「哪些呼叫同屬一個子
    shell」的範圍資訊。需要子 shell 範圍隔離的呼叫端（目前僅
    bash-git-protected-branch-guard-hook.py 的 add+commit 同範圍關聯）
    應在呼叫本模組前，先用自己的子 shell 內容擷取邏輯切出範圍字串，再對
    每個範圍字串個別呼叫 `find_git_invocations`——本模組刻意不處理巢狀
    範圍，避免單一 API 同時服務「不需要範圍隔離」與「需要範圍隔離」兩種
    不同需求而增加所有呼叫端的複雜度。
    """
    statements: List[List[str]] = []
    current: List[str] = []
    for token in tokens:
        if token in _STATEMENT_SEPARATORS:
            if current:
                statements.append(current)
            current = []
        else:
            current.append(token)
    if current:
        statements.append(current)
    return statements


def _consume_global_options(
    statement: List[str], start_idx: int
) -> Optional[Tuple[int, Optional[str], List[str], Tuple[str, ...], dict]]:
    """從 `start_idx`（緊接在 `git` 之後）開始，逐一消耗 git 全域選項。

    回傳 `(下一個未消耗的 idx, 第一個 -C 路徑, global_options, 全部 -C 路徑,
    行內別名 {名稱: 展開值})`；行內別名來自 `-c alias.X=值`。
    回傳 None 表示 `-C` 後無值（語句不完整，非可辨識的 git 呼叫）。
    """
    idx = start_idx
    dash_c_paths: List[str] = []
    global_options: List[str] = []
    inline_aliases: dict = {}
    while idx < len(statement):
        tok = statement[idx]
        if tok == "-c" and idx + 1 < len(statement):
            _record_inline_alias(statement[idx + 1], inline_aliases)
        if tok.startswith("-c") and len(tok) > 2 and not tok.startswith("--"):
            _record_inline_alias(tok[2:], inline_aliases)  # `-c<key=value>` 黏寫
            global_options.append(tok)
            idx += 1
            continue
        if tok.startswith("-C") and len(tok) > 2:
            dash_c_paths.append(tok[2:])  # `-C<path>` 黏寫
            global_options.append(tok)
            idx += 1
            continue
        if tok == "-C":
            if idx + 1 >= len(statement):
                return None  # -C 後無值，語句不完整，非可辨識的 git 呼叫
            dash_c_paths.append(statement[idx + 1])
            global_options.append(tok)
            idx += 2
            continue
        if tok in _GIT_GLOBAL_WITH_VALUE:
            global_options.append(tok)
            idx += 2
            continue
        # `--option=value` 單一 token 形式（git 支援兩種寫法皆合法）
        opt_name = tok.split("=", 1)[0] if "=" in tok else tok
        if opt_name in _GIT_GLOBAL_WITH_VALUE and opt_name != tok:
            global_options.append(tok)
            idx += 1
            continue
        if tok in _GIT_GLOBAL_NO_VALUE:
            global_options.append(tok)
            idx += 1
            continue
        break
    first = dash_c_paths[0] if dash_c_paths else None
    return idx, first, global_options, tuple(dash_c_paths), inline_aliases


def _record_inline_alias(config_pair: str, inline_aliases: dict) -> None:
    """`-c alias.X=值` 的設定對：記為行內別名；其他設定鍵不處理。"""
    key, sep, value = config_pair.partition("=")
    if sep and key.startswith("alias.") and len(key) > len("alias."):
        inline_aliases[key[len("alias."):]] = value


# ===== 目錄狀態（cd / -C 串接） =====


@dataclass(frozen=True)
class _DirState:
    """語句開始時的目錄狀態：path 為已知目錄（可為 None），unknown 為不可信旗標。"""

    path: Optional[str] = None
    unknown: bool = False


def _is_dynamic_path(path: str) -> bool:
    return "$" in path or "`" in path


def resolve_dir_path(base: Optional[str], target: str) -> str:
    """依 cd／-C 語意解析單一路徑：展開 `~`，絕對路徑取代 base，相對路徑接續，
    結果一律 normpath（消除 `..` 與重複分隔符）。base 為 None 時相對路徑以相對字串回傳。

    `find_git_invocations` 的 effective_dir 與 `find_git_dash_c_dirs` 共用此函式，
    使三支 hook 對同一 `-C` 字面解析出同一目錄。
    """
    target = os.path.expanduser(target) if target.startswith("~") else target
    if os.path.isabs(target) or base is None:
        return os.path.normpath(target)
    return os.path.normpath(os.path.join(base, target))


def _join_dir(state: _DirState, target: str) -> _DirState:
    """依 cd／-C 語意把 target 套用到 state：動態值轉未知，其餘委派 resolve_dir_path。"""
    if state.unknown or _is_dynamic_path(target):
        return _DirState(None, True)
    if not target:
        return state
    return _DirState(resolve_dir_path(state.path, target), False)


# 控制結構的語句頭關鍵字：其後才是命令位置（`for`／`select` 的語句頭沒有命令位置，
# 不跳過；整句落到「非 git」而自然無命中）
_CONTROL_KEYWORDS = frozenset(
    {"if", "then", "else", "elif", "do", "while", "until", "{", "}", "!", "coproc"}
)


def _leading_control_count(statement: List[str]) -> int:
    """語句頭的控制關鍵字數；`function NAME` 連同函式名稱一併計入。"""
    count = 0
    while count < len(statement):
        if statement[count] in _CONTROL_KEYWORDS:
            count += 1
        elif statement[count] == "function" and count + 1 < len(statement):
            count += 2
        else:
            break
    return count


def _apply_cd(statement: List[str], state: _DirState, prev_sep: str, next_sep: str) -> _DirState:
    """計算語句執行後留給後續語句的目錄狀態。

    只處理語句開頭的 `cd` / `pushd` / `popd`。管線兩側在子 shell 執行，不外溢；
    `||` 前後的 cd 是否執行不確定，標未知。
    """
    statement = statement[_leading_control_count(statement):]
    head = statement[0] if statement else ""
    if head not in ("cd", "pushd", "popd") or "|" in (prev_sep, next_sep) or next_sep == "&":
        return state
    if head == "popd":
        return _DirState(None, True)
    args = [t for t in statement[1:] if t not in ("-P", "-L", "-e", "-@", "--")]
    if len(args) != 1 or args[0] == "-" or "||" in (prev_sep, next_sep):
        return _DirState(None, True)  # HOME／cd -／條件式 cd：目的地不可靜態得知
    return _join_dir(state, args[0])


def _walk_statements(
    tokens: List[str], init: _DirState
) -> List[Tuple[List[str], _DirState]]:
    """切分語句並為每條語句附上其開始時的目錄狀態；括號為 cd 作用域邊界。"""
    result: List[Tuple[List[str], _DirState]] = []
    stack: List[_DirState] = []
    state = init
    current: List[str] = []
    prev_sep = ""

    def flush(next_sep: str) -> None:
        nonlocal state, current
        if current:
            result.append((current, state))
            state = _apply_cd(current, state, prev_sep, next_sep)
            current = []

    for token in tokens:
        if token not in _STATEMENT_SEPARATORS:
            current.append(token)
            continue
        flush(token)
        if token == "(":
            stack.append(state)
        elif token == ")" and stack:
            state = stack.pop()
        prev_sep = token
    flush("")
    return result


# ===== 包裝命令、巢狀 shell、別名 =====

_MAX_NESTING = 5
_ALIAS_READ_TIMEOUT_SEC = 1
_MAX_ALIAS_LOOKUPS = 8  # 單次解析最多實際讀取（不含快取命中）次數
_ALIAS_TOTAL_BUDGET_SEC = 3.0  # 單次解析別名讀取累計時間上限


class _Unparseable(Exception):
    """內部訊號：無法安全解析（超出深度、巢狀無法 tokenize、別名查詢超限或逾時）。

    由 `find_git_invocations` 轉為與頂層 tokenize 失敗相同的 None，
    使巢狀情形與頂層情形對呼叫端語意一致，不靜默放行。
    """
_SHELLS = frozenset({"bash", "sh", "zsh", "dash", "ksh"})
_SHELL_C_FLAG_RE = re.compile(r"^-[A-Za-z]*c[A-Za-z]*$")

# git 內建子命令：不可被別名覆蓋，查 git config 前直接略過以省子程序
_GIT_BUILTINS = frozenset(
    {
        "add", "am", "apply", "bisect", "blame", "branch", "checkout", "cherry-pick",
        "clean", "clone", "commit", "config", "describe", "diff", "fetch", "grep",
        "init", "log", "merge", "mv", "pull", "push", "rebase", "remote", "reset",
        "restore", "revert", "rm", "show", "stash", "status", "switch", "tag",
        "worktree", "reflog", "rev-parse", "ls-files", "commit-tree", "update-ref",
        "show-ref", "for-each-ref", "cat-file", "hash-object", "write-tree",
        "read-tree", "symbolic-ref", "merge-base", "diff-tree", "diff-index",
        "ls-tree", "ls-remote", "submodule", "notes", "archive", "bundle", "gc",
        "fsck", "count-objects", "maintenance", "sparse-checkout", "version",
        "help", "shortlog", "format-patch", "mergetool", "difftool", "prune",
        "pack-refs", "repack", "update-index", "checkout-index", "var",
    }
)


def _read_git_alias(directory: Optional[str], name: str) -> Optional[str]:
    """讀 `alias.<name>`；任何失敗（無 git、逾時、目錄不存在、未設定）皆回 None。"""
    cmd = ["git"] + (["-C", directory] if directory else []) + ["config", "--get", f"alias.{name}"]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=_ALIAS_READ_TIMEOUT_SEC
        )
    except subprocess.TimeoutExpired as exc:
        raise _Unparseable("alias read timeout") from exc  # 逾時無法判定：不可當作無別名
    except Exception as exc:  # 無 git 等讀取失敗：視為無別名
        _logger.debug("read git alias failed (name=%s): %s", name, exc)  # i18n-exempt
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def _is_git_word(token: str) -> bool:
    return token == "git" or token.endswith("/git")


def _skip_wrappers(statement: List[str]) -> Optional[int]:
    """跳過控制結構語句頭、sudo/env/nohup 等前綴與 `command`、`exec`；
    回傳命令位置，`command -v` 回 None。"""
    idx = 0
    while True:
        start = idx
        idx += _leading_control_count(statement[idx:])
        idx += skip_prefix_wrapper_count(statement[idx:], extended=True)
        if idx < len(statement) and statement[idx] in ("command", "exec"):
            is_command = statement[idx] == "command"
            idx += 1
            while idx < len(statement) and statement[idx].startswith("-"):
                if is_command and statement[idx] in ("-v", "-V"):
                    return None  # 查詢而非執行
                idx += 2 if statement[idx] == "-a" and not is_command else 1
            continue
        if idx > start:
            continue  # 前綴後可能再接控制關鍵字或前綴（如 `then nice <命令>`）
        return idx


def _nested_script(statement: List[str], idx: int) -> Optional[str]:
    """若 statement[idx] 為 `bash -c`／`eval`，取出其腳本字串，否則回 None。"""
    head = statement[idx]
    if head in _STRING_COMMAND_WRAPPERS:
        return _wrapper_script(statement, idx)
    if head == "eval":
        return " ".join(statement[idx + 1:])
    if os.path.basename(head) not in _SHELLS:
        return None
    pos = idx + 1
    while pos < len(statement) and statement[pos].startswith("-") and statement[pos] != "--":
        if _SHELL_C_FLAG_RE.match(statement[pos]):
            return statement[pos + 1] if pos + 1 < len(statement) else None
        pos += 1
    return None


_REDIRECT_OPERATOR_RE = re.compile(r"^\d*(>>?|<{1,3})$")


def _is_stdin_shell(statement: List[str], idx: int) -> bool:
    """statement[idx] 為從 stdin 讀腳本的 shell（無 `-c`、無腳本檔參數）。"""
    if os.path.basename(statement[idx]) not in _SHELLS:
        return False
    args = iter(statement[idx + 1:])
    for tok in args:
        if _SHELL_C_FLAG_RE.match(tok):
            return False
        if _REDIRECT_OPERATOR_RE.match(tok):
            next(args, None)  # 略過重導向目標
        elif not tok.startswith("-") and not is_shell_redirection_token(tok):
            return False
    return True


def _raise_if_pipes_into_shell(tokens: List[str]) -> None:
    """管線輸出餵給 stdin shell：腳本內容在執行期才產生，靜態不可解析。"""
    for pos, token in enumerate(tokens):
        if token != "|":
            continue
        following: List[str] = []
        for nxt in tokens[pos + 1:]:
            if nxt in _STATEMENT_SEPARATORS:
                break
            following.append(nxt)
        idx = _skip_wrappers(following)
        if idx is not None and idx < len(following) and _is_stdin_shell(following, idx):
            raise _Unparseable("pipe into shell")


class _Ctx:
    """單次解析的共用參數：關注子命令集合與基準目錄。"""

    def __init__(self, wanted: FrozenSet[str], base_dir: Optional[str], scan: bool = False):
        self.wanted = wanted
        self.base_dir = base_dir
        self.scan = scan
        self.alias_cache: dict = {}
        self.lookups = 0
        self.alias_elapsed = 0.0

    def alias(self, directory: Optional[str], name: str) -> Optional[str]:
        """帶快取、次數與累計時間上限的別名讀取；超限丟 _Unparseable。"""
        key = (directory, name)
        if key in self.alias_cache:
            return self.alias_cache[key]
        if self.lookups >= _MAX_ALIAS_LOOKUPS or self.alias_elapsed >= _ALIAS_TOTAL_BUDGET_SEC:
            raise _Unparseable("alias lookup budget exceeded")
        self.lookups += 1
        started = time.monotonic()
        try:
            value = _read_git_alias(directory, name)
        finally:
            self.alias_elapsed += time.monotonic() - started
        self.alias_cache[key] = value
        return value


def _scan_script(script: str, state: _DirState, depth: int, ctx: "_Ctx") -> List[GitInvocation]:
    """遞迴解析巢狀腳本；巢狀內的 cd 不外溢，無法 tokenize 時視為無命中。"""
    if depth >= _MAX_NESTING:
        raise _Unparseable("nesting too deep")
    tokens = _tokenize_command(script)
    if tokens is None:
        raise _Unparseable("nested script cannot be tokenized")
    return _scan_tokens(tokens, state, depth + 1, ctx)


def _scan_tokens(
    tokens: List[str], init: _DirState, depth: int, ctx: "_Ctx"
) -> List[GitInvocation]:
    found: List[GitInvocation] = []
    _raise_if_pipes_into_shell(tokens)
    for statement, state in _walk_statements(tokens, init):
        found.extend(_invocations_in_statement(statement, state, depth, ctx))
    return found


def _invocations_in_statement(
    statement: List[str], state: _DirState, depth: int, ctx: "_Ctx"
) -> List[GitInvocation]:
    idx = _skip_wrappers(statement)
    if idx is None or idx >= len(statement):
        return []  # `command -v` 為查詢，scan 模式同樣不掃
    found = _positional_invocations(statement, idx, state, depth, ctx)
    if found or not ctx.scan:
        return found
    return [replace(inv, via_scan=True) for inv in _scan_statement(statement, state, depth, ctx)]


def _positional_invocations(
    statement: List[str], idx: int, state: _DirState, depth: int, ctx: "_Ctx"
) -> List[GitInvocation]:
    """命令位置判定：statement[idx] 必須是 git 或可遞迴的巢狀腳本。"""
    if _is_git_word(statement[idx]):
        return _git_invocations(statement, idx, state, depth, ctx)
    script = _nested_script(statement, idx)
    if script:
        return _scan_script(script, state, depth, ctx)
    if "<<<" in statement and _is_stdin_shell(statement, idx):
        raise _Unparseable("here-string into shell")
    return []


# scan 模式的例外：這些命令之後的參數列只是輸出文字，不是命令
_SCAN_OUTPUT_COMMANDS = frozenset({"echo", "printf"})


def _scan_statement(
    statement: List[str], state: _DirState, depth: int, ctx: "_Ctx"
) -> List[GitInvocation]:
    """任意位置掃描：語句中任何 git token 或巢狀腳本載體都視為呼叫。

    遇 echo／printf 即停止；找到 git 後其餘 token 是它的參數，不再掃（避免
    `-C git` 之類的值被重複計數）；eval／env -S／flock -c／watch 的腳本已含
    其後全部 token，處理後同樣停止，shell -c 的腳本只是一個 token，其後繼續掃。
    """
    if "<<<" in statement and any(
        _is_stdin_shell(statement, i) for i in range(len(statement))
    ):
        raise _Unparseable("here-string into shell")
    found: List[GitInvocation] = []
    for i, tok in enumerate(statement):
        if os.path.basename(tok) in _SCAN_OUTPUT_COMMANDS:
            break
        if _is_git_word(tok):
            found.extend(_git_invocations(statement, i, state, depth, ctx))
            break
        script = _nested_script(statement, i)
        if script:
            found.extend(_scan_script(script, state, depth, ctx))
            if os.path.basename(tok) not in _SHELLS:
                break
    return found


def _git_invocations(
    statement: List[str], git_idx: int, state: _DirState, depth: int, ctx: "_Ctx"
) -> List[GitInvocation]:
    """`state` 為套用本呼叫 -C 之前的目錄狀態。"""
    consumed = _consume_global_options(statement, git_idx + 1)
    if consumed is None:
        return []
    idx, dash_c_path, global_options, dash_c_paths, inline_aliases = consumed
    if idx >= len(statement):
        return []
    eff = state
    dash_c_dirs: List[str] = []
    for path in dash_c_paths:
        eff = _join_dir(eff, path)
        if not eff.unknown and eff.path is not None:
            dash_c_dirs.append(eff.path)
    token = statement[idx]
    if token in ctx.wanted:
        return [
            GitInvocation(
                statement=statement,
                subcommand=_canonical_subcommand(token),
                subcommand_index=idx,
                dash_c_path=dash_c_path,
                global_options=global_options,
                dash_c_paths=dash_c_paths,
                effective_dir=None if eff.unknown else eff.path,
                dir_unknown=eff.unknown,
                dash_c_dirs=tuple(dash_c_dirs),
            )
        ]
    if token.startswith("-") or token in _GIT_BUILTINS:
        return []
    if depth >= _MAX_NESTING:
        raise _Unparseable("alias chain too deep")
    lookup_dir = ctx.base_dir if eff.unknown else eff.path
    return _expand_alias(
        statement, git_idx, idx, lookup_dir, state, depth, ctx, inline_aliases.get(token)
    )


def _expand_alias(
    statement: List[str], git_idx: int, idx: int, lookup_dir: Optional[str],
    state: _DirState, depth: int, ctx: "_Ctx", inline_value: Optional[str] = None,
) -> List[GitInvocation]:
    """展開別名；`inline_value` 為 `-c alias.X=` 行內別名，優先於設定檔。"""
    value = inline_value if inline_value is not None else ctx.alias(lookup_dir, statement[idx])
    if not value:
        return []
    if value.startswith("!"):
        # shell 別名：內容只能當腳本遞迴解析；實際目錄與參數不可知，結果一律標未知
        found = _scan_script(value[1:], _DirState(None, True), depth, ctx)
        return [replace(inv, dir_unknown=True, effective_dir=None) for inv in found]
    try:
        alias_tokens = shlex.split(value)
    except ValueError:
        return []
    expanded = statement[:idx] + alias_tokens + statement[idx + 1:]
    return _git_invocations(expanded, git_idx, state, depth + 1, ctx)


class _AnySubcommand(frozenset):
    """比對任何子命令的集合（供列舉全部 git 呼叫的 -C 目錄用）。"""

    def __contains__(self, item: object) -> bool:
        return True


def find_git_dash_c_dirs(command: str, base_dir: Optional[str] = None) -> Optional[List[str]]:
    """命令內所有 git 呼叫（任意子命令、含 scan 模式）的目標目錄，有序去重：
    每個 `-C` 的累積目錄，加上呼叫最終的 effective_dir（含語句內 `cd`）。

    無法安全解析回 None。與 `find_git_invocations` 同一解析路徑，目錄語意一致。
    """
    if not command:
        return []
    tokens = _tokenize_command(command)
    if tokens is None:
        return None
    ctx = _Ctx(_AnySubcommand(), base_dir, True)
    try:
        found = _scan_tokens(tokens, _DirState(base_dir, False), 0, ctx)
    except _Unparseable:
        return None
    dirs = [
        d
        for inv in found
        for d in (*inv.dash_c_dirs, inv.effective_dir)
        if d and not inv.dir_unknown
    ]
    return list(dict.fromkeys(dirs))


def parse_command_statements(command: str) -> Optional[List[List[str]]]:
    """公開版本的語句 token 化：heredoc 剝離 + 換行正規化 + shlex tokenize +
    依運算子（`;`／`&&`／`||`／`|`／`(`／`)`）切分語句。

    供非 git 專用的呼叫端（如偵測特定 CLI 子命令形態的 hook）判斷「命令
    位置 token」而非在命令字串原文上做全文 regex search——後者會把引號內
    的參數值（如描述文字提及某命令形態的字面文字）誤判為實際要執行的
    命令：shlex 會把整段引號內容收斂成單一 token，與分開的多個 token 精確
    比對時不會誤命中。`find_git_invocations` 內部即呼叫此同一條處理管線，
    本函式僅將其對外公開，避免非 git 呼叫端重新實作一份 tokenize 邏輯。

    Args:
        command: PreToolUse/PostToolUse 收到的原始命令字串。

    Returns:
        - `None`：命令字串無法安全 tokenize（shlex 遇未閉合引號）。呼叫端
          須明確處理此情況並自行決定 fail-open 或 fail-closed，不可與空
          清單混淆處理（語意與 `find_git_invocations` 一致，見模組
          docstring「失敗語意」段）。
        - `List[List[str]]`：每個內層清單為一條語句的 token 序列；可能為
          空清單（可正常解析但無任何語句，如空字串命令）。
    """
    if not command:
        return []
    tokens = _tokenize_command(command)
    if tokens is None:
        return None
    return _split_statements(tokens)


def find_git_invocations(
    command: str, subcommands: Iterable[str], base_dir: Optional[str] = None,
    scan: bool = False,
) -> Optional[List[GitInvocation]]:
    """解析命令字串，回傳指定子命令的所有 git 呼叫結構化記錄。

    處理順序：剝離 heredoc 本體（含保底）-> 換行正規化為語句分隔符 ->
    shlex tokenize -> 依運算子切分語句（追蹤 cd 作用域）-> 逐語句跳過前綴
    包裹／`command`／`exec`／環境變數賦值 -> 確認為 `git`（含絕對路徑）或
    遞迴進入 `bash|sh|zsh -c` 與 `eval` 的腳本 -> 消耗全域選項（含 `-C`）
    -> 比對子命令（含內建別名展開，其次讀 `git config alias.X` 展開使用者別名）。

    Args:
        command: PreToolUse 收到的原始命令字串（`tool_input.command`）。
        subcommands: 要匹配的 canonical 子命令名稱集合（如 `{"commit"}`
            或 `{"add"}`）。別名由 `SUBCOMMAND_ALIASES` 自動展開，呼叫端
            傳 canonical 名稱即可，不需自行列出別名。
        base_dir: 命令開始執行時的目錄（通常為 payload cwd），僅用於
            計算 `effective_dir` 與讀取別名；預設 None 不影響既有行為。
        scan: True 時命令位置找不到的語句改做任意位置掃描（語句中任何 git
            token 皆視為呼叫，echo、printf 之後與 `command -v` 例外），僅
            掃描命中的呼叫其 `via_scan` 為 True。已知誤判：git 作為其他命令
            的參數（如 `bash script.sh git commit`、`grep git commit f`），
            以及 ssh、docker run 內的遠端執行（有意保守）。預設 False
            （僅命令位置，行為與未提供此參數時相同）。

    Returns:
        - `None`：命令字串無法安全 tokenize（shlex 遇未閉合引號）。呼叫端
          須明確處理此情況並自行決定 fail-open 或 fail-closed（見模組
          docstring「失敗語意」段），不可與空清單混淆處理。
        - `List[GitInvocation]`：可能為空清單（可正常解析但無符合條件的
          git 呼叫），亦可能含多筆（同一命令多個語句各自命中）。
    """
    if not command:
        return []

    tokens = _tokenize_command(command)
    if tokens is None:
        return None

    ctx = _Ctx(_expand_subcommand_aliases(subcommands), base_dir, scan)
    try:
        return _scan_tokens(tokens, _DirState(base_dir, False), 0, ctx)
    except _Unparseable as exc:
        # 無法解析是正常判定結果（None 由呼叫端依各自守衛語意處置），不是 hook 失敗：
        # 只寫 debug 日誌，不輸出 stderr。會阻擋的守衛自有 stderr 訊息；
        # 在 hook-dispatcher 單一行程下，此處若寫 stderr 會被每支 hook 各印一次。
        _logger.debug("command cannot be parsed safely: %s", exc)  # i18n-exempt
        return None


def match_git_commit(
    command: str, exclude_amend: bool = True, base_dir: Optional[str] = None,
    scan: bool = False,
) -> Optional[bool]:
    """判定命令字串是否含一次 git commit 呼叫，回傳三態。

    供 hook 的 commit 判定共用，取代各 hook 自行重複的
    contains_git_word 篩選、find_git_invocations、amend 排除。

    Args:
        command: Bash 工具的原始命令字串（`tool_input.command`）。
        exclude_amend: True（預設）時，args 含 `--amend` 的呼叫不算命中
            （只剩 amend 呼叫的命令回 False）；False 時 amend 也命中。
            同一命令含多個 commit 呼叫時，任一呼叫符合即命中。
        base_dir: 傳給 `find_git_invocations` 的起始目錄，通常為 payload cwd。
        scan: 傳給 `find_git_invocations` 的任意位置掃描開關，預設 False。

    Returns:
        - `True`：命中，命令含至少一次（符合 exclude_amend 的）git commit。
        - `False`：未命中，含空命令、不含 git 字樣、`echo git commit`
          這類非實際呼叫、非 commit 子命令，以及只含被排除的 amend。
        - `None`：無法解析（`find_git_invocations` 回 None：未閉合引號、
          巢狀過深、別名查詢超限）。呼叫端自行決定處置：提示型 hook
          視為未命中，阻擋型守衛依並行期等條件保守處理。
          須用 `is None` 區分，不可只寫 `if not result`。
    """
    if not contains_git_word(command):
        return False
    invocations = find_git_invocations(command, {"commit"}, base_dir, scan)
    if invocations is None:
        return None
    if not exclude_amend:
        return bool(invocations)
    return any("--amend" not in inv.args for inv in invocations)


# ===== 無法解析成因分類（供守衛區分提示文案）=====

PARSE_CAUSE_TOKENIZE = "tokenize"
PARSE_CAUSE_SCAN_ONLY = "scan_only"

SCAN_ONLY_EXPLANATION = (
    "git 出現在非命令位置（例如其他命令的參數，或 find -exec 之類的包裝命令之後），"
    "守衛無法判斷該命令會不會把它當命令執行，保守視為無法確認。"
    "改寫方式：把 git 字樣加上引號（例如 grep 'git commit' file），"
    "或把 git 放在命令位置直接呼叫。"
)

TOKENIZE_EXPLANATION = (
    "原因：未閉合引號，或命令結構（例如管線接 shell）無法解析；"
    "請檢查命令引號是否配對，或改寫為單純的命令。"
)


def classify_parse_cause(invocations: Optional[List[GitInvocation]]) -> Optional[str]:
    """由 `find_git_invocations(scan=True)` 的回傳值判定「無法確認」的成因。

    - `None`：tokenize 失敗（或結構無法解析）-> `PARSE_CAUSE_TOKENIZE`
    - 非空且全為 `via_scan`：僅掃描命中 -> `PARSE_CAUSE_SCAN_ONLY`
    - 其餘：可確認，回傳 None
    """
    if invocations is None:
        return PARSE_CAUSE_TOKENIZE
    if invocations and all(inv.via_scan for inv in invocations):
        return PARSE_CAUSE_SCAN_ONLY
    return None


def explain_parse_cause(cause: Optional[str]) -> str:
    """成因對應的說明文字（tokenize 失敗與僅掃描命中給不同的修正方向）。"""
    if cause == PARSE_CAUSE_SCAN_ONLY:
        return SCAN_ONLY_EXPLANATION
    return TOKENIZE_EXPLANATION


# 供 ticket_command_parse 等同 lib 解析器共用的公開名稱（僅別名，行為同私有符號）
UnparseableCommand = _Unparseable
SHELLS = _SHELLS
SCAN_OUTPUT_COMMANDS = _SCAN_OUTPUT_COMMANDS
skip_wrappers = _skip_wrappers
nested_script = _nested_script
is_stdin_shell = _is_stdin_shell
raise_if_pipes_into_shell = _raise_if_pipes_into_shell
tokenize_command = _tokenize_command
