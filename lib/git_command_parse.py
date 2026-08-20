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

import re
import shlex
from dataclasses import dataclass, field
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


def _skip_prefix_wrapper_count(tokens: List[str]) -> int:
    """計算語句開頭需跳過的前綴包裹與環境變數賦值 token 數，供索引位移用。

    涵蓋：`sudo` / `nohup` / `time` / `xargs`（跳過自身，不消耗選項值——
    這些命令的選項形式多樣且與本模組要解決的問題無關，簡化為只跳過命令
    本身；即使後面接的是該命令自身的選項而非 `git`，後續「下一個 token
    是否為 git」的檢查會自然判定為不匹配，不會誤判）、`env`（跳過自身與
    其後任意數量的 `KEY=VALUE` 賦值）、裸的 `KEY=VALUE` 賦值前綴（不經
    `env` 也是合法 shell 語法）。
    """
    idx = 0
    while idx < len(tokens):
        tok = tokens[idx]
        if tok in _PREFIX_COMMANDS_SIMPLE:
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
    """

    statement: List[str]
    subcommand: str
    subcommand_index: int
    dash_c_path: Optional[str]
    global_options: List[str] = field(default_factory=list)

    @property
    def args(self) -> List[str]:
        return self.statement[self.subcommand_index + 1:]


# ===== 語句切分 =====

_STATEMENT_SEPARATORS = frozenset({"&&", "||", ";", "|", "(", ")"})


def _tokenize(command: str) -> Optional[List[str]]:
    """以 shlex 保留引號語意做 token 化，運算子（&&/;/|/( )）成為獨立 token。

    回傳 None 表示無法安全解析（未閉合引號等）——與空清單明確區分，見
    模組 docstring「失敗語意」段。
    """
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        return list(lexer)
    except ValueError:
        return None


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
) -> Optional[Tuple[int, Optional[str], List[str]]]:
    """從 `start_idx`（緊接在 `git` 之後）開始，逐一消耗 git 全域選項。

    回傳 `(下一個未消耗的 idx, dash_c_path, global_options)`；回傳 None
    表示 `-C` 後無值（語句不完整，非可辨識的 git 呼叫）。獨立為函式是
    因為此迴圈要處理四種選項形態（`-C`、消耗值的長選項、`--opt=value`
    單一 token 形式、不消耗值的長選項），分支數對應 git 全域選項語法本身
    的固有複雜度，抽出後呼叫端 `_find_invocation_in_statement` 只需處理
    一次函式呼叫的結果，不需在自身迴圈中內嵌這四種判斷。
    """
    idx = start_idx
    dash_c_path: Optional[str] = None
    global_options: List[str] = []
    while idx < len(statement):
        tok = statement[idx]
        if tok == "-C":
            if idx + 1 >= len(statement):
                return None  # -C 後無值，語句不完整，非可辨識的 git 呼叫
            if dash_c_path is None:
                dash_c_path = statement[idx + 1]
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
    return idx, dash_c_path, global_options


def _find_invocation_in_statement(
    statement: List[str], wanted_tokens: FrozenSet[str]
) -> Optional[GitInvocation]:
    """在單一語句 token 清單中尋找第一個符合條件的 git 呼叫。"""
    idx = _skip_prefix_wrapper_count(statement)
    if idx >= len(statement) or statement[idx] != "git":
        return None
    idx += 1

    consumed = _consume_global_options(statement, idx)
    if consumed is None:
        return None
    idx, dash_c_path, global_options = consumed

    if idx >= len(statement):
        return None

    subcommand_token = statement[idx]
    if subcommand_token not in wanted_tokens:
        return None

    return GitInvocation(
        statement=statement,
        subcommand=_canonical_subcommand(subcommand_token),
        subcommand_index=idx,
        dash_c_path=dash_c_path,
        global_options=global_options,
    )


def find_git_invocations(
    command: str, subcommands: Iterable[str]
) -> Optional[List[GitInvocation]]:
    """解析命令字串，回傳指定子命令的所有 git 呼叫結構化記錄。

    處理順序：剝離 heredoc 本體（含保底）-> 換行正規化為語句分隔符 ->
    shlex tokenize -> 依運算子切分語句 -> 逐語句跳過前綴包裹/環境變數
    賦值 -> 確認為 `git` -> 消耗全域選項（含 `-C <path>`）-> 比對子命令
    （含別名展開）。

    Args:
        command: PreToolUse 收到的原始命令字串（`tool_input.command`）。
        subcommands: 要匹配的 canonical 子命令名稱集合（如 `{"commit"}`
            或 `{"add"}`）。別名由 `SUBCOMMAND_ALIASES` 自動展開，呼叫端
            傳 canonical 名稱即可，不需自行列出別名。

    Returns:
        - `None`：命令字串無法安全 tokenize（shlex 遇未閉合引號）。呼叫端
          須明確處理此情況並自行決定 fail-open 或 fail-closed（見模組
          docstring「失敗語意」段），不可與空清單混淆處理。
        - `List[GitInvocation]`：可能為空清單（可正常解析但無符合條件的
          git 呼叫），亦可能含多筆（同一命令多個語句各自命中）。
    """
    if not command:
        return []

    stripped = strip_heredoc_bodies(command)
    normalized = normalize_newlines_to_separators(stripped)
    tokens = _tokenize(normalized)
    if tokens is None:
        return None

    wanted_tokens = _expand_subcommand_aliases(subcommands)
    invocations: List[GitInvocation] = []
    for statement in _split_statements(tokens):
        inv = _find_invocation_in_statement(statement, wanted_tokens)
        if inv is not None:
            invocations.append(inv)
    return invocations
