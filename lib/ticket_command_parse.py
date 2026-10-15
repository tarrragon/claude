"""ticket CLI 完成類命令的共用判定（供 hook 以 token 位置辨識，非子字串比對）。

判定與 acceptance-gate-hook 的 `_statement_complete_verb` 同一規則：語句去掉
env/nohup/time 等前綴後，以 `ticket track <完成類動詞>` 開頭。引號內字面與
heredoc 內文由 parse_command_statements 收斂，不會被誤判為命令。

失敗語意由呼叫端決定：解析失敗時 `parse_command_statements` 回傳 None，
`has_complete_command` 同樣回傳 None 以保留該訊號。
"""

import os
import re
from typing import List, Optional, Tuple

from .git_command_parse import (
    SCAN_OUTPUT_COMMANDS,
    SHELLS,
    UnparseableCommand,
    is_stdin_shell,
    nested_script,
    parse_command_statements,
    raise_if_pipes_into_shell,
    skip_prefix_wrapper_count,
    skip_wrappers,
    tokenize_command,
)

COMPLETE_VERBS = ("complete", "finish", "batch-complete")

# shell -c 巢狀字串的遞迴深度上限
_MAX_SCAN_NESTING = 5


_HELP_FLAGS = ("-h", "--help")


def is_help_only(args: List[str]) -> bool:
    """動詞之後的 token 是否只查說明（argparse 印說明後結束，不執行命令）。

    token 須完全等於 -h 或 --help，且位於單獨的 `--` 之前；引號內字面
    （如 `--why '見 --help'`）已由 tokenizer 併為單一 token，不會相等。
    """
    for tok in args:
        if tok == "--":
            return False
        if tok in _HELP_FLAGS:
            return True
    return False


def complete_statement_args(tokens: List[str]) -> Optional[List[str]]:
    """若語句為完成類命令，回傳動詞之後的 token；否則回傳 None（含只查說明）。"""
    i = skip_prefix_wrapper_count(tokens)
    if (
        len(tokens) >= i + 3
        and tokens[i] == "ticket"
        and tokens[i + 1] == "track"
        and tokens[i + 2] in COMPLETE_VERBS
    ):
        args = tokens[i + 3:]
        return None if is_help_only(args) else args
    return None


def is_complete_statement(tokens: List[str]) -> bool:
    """語句（去前綴後）是否以 ticket track <完成類動詞> 開頭。"""
    return complete_statement_args(tokens) is not None


def _scan_statement(
    statement: List[str], depth: int, verbs: Tuple[str, ...]
) -> Optional[List[Tuple[str, List[str]]]]:
    """單一語句的任意位置掃描；巢狀腳本無法解析時回傳 None。"""
    if skip_wrappers(statement) is None:
        return []  # `command -v` 為查詢，不是執行
    if "<<<" in statement and any(is_stdin_shell(statement, i) for i in range(len(statement))):
        return None  # here-string 餵 stdin shell：腳本執行期才產生，靜態不可解析
    found: List[Tuple[str, List[str]]] = []
    for i, tok in enumerate(statement):
        if os.path.basename(tok) in SCAN_OUTPUT_COMMANDS:
            break  # echo、printf 之後只是輸出文字
        if (
            os.path.basename(tok) == "ticket"
            and len(statement) >= i + 3
            and statement[i + 1] == "track"
            and statement[i + 2] in verbs
        ):
            args = statement[i + 3:]
            if not is_help_only(args):
                found.append((statement[i + 2], args))
            break  # 其餘 token 是該命令的參數
        script = nested_script(statement, i)
        if script:
            nested = _scan_command(script, depth + 1, verbs)
            if nested is None:
                return None
            found.extend(nested)
            if os.path.basename(tok) not in SHELLS:
                break  # eval、env -S 等的腳本已含其後全部 token
    return found


def _scan_command(
    command: str, depth: int, verbs: Tuple[str, ...]
) -> Optional[List[Tuple[str, List[str]]]]:
    if depth > _MAX_SCAN_NESTING:
        return None
    statements = parse_command_statements(command)
    tokens = tokenize_command(command) if command else []
    if statements is None or tokens is None:
        return None
    try:
        raise_if_pipes_into_shell(tokens)  # 管線餵 stdin shell，同 git 解析器 fail-closed
    except UnparseableCommand:
        return None
    found: List[Tuple[str, List[str]]] = []
    for statement in statements:
        part = _scan_statement(statement, depth, verbs)
        if part is None:
            return None
        found.extend(part)
    return found


def find_ticket_track_invocations(
    command: str, verbs: Tuple[str, ...]
) -> Optional[List[Tuple[str, List[str]]]]:
    """任意位置掃描 `ticket track <verbs 之一>`，回傳 (動詞, 動詞之後的 token) 清單。

    掃描規則與失敗語意同 `find_complete_invocations`（它委派本函式）。動詞之後
    的參數形狀由呼叫端解讀（如 `phase <ID> phase4`）。
    """
    return _scan_command(command, 0, verbs)


def find_complete_invocations(command: str) -> Optional[List[Tuple[str, List[str]]]]:
    """任意位置掃描完成類命令，回傳 (動詞, 動詞之後的 token) 清單。

    與 `has_complete_command` 的差別：不要求 `ticket track` 位於命令位置，語句
    中任何位置的 `ticket track <完成類動詞>`（ticket 可為絕對路徑）皆算，涵蓋
    前綴包裝白名單以外的包裝器；shell -c／eval 巢狀字串遞迴解析。例外：echo、
    printf 之後的 token 與 `command -v` 語句不是執行，不辨識。管線或 here-string
    餵給 stdin shell（`echo ... | bash`、`bash <<< ...`）腳本內容靜態不可解析，
    回傳 None。已知誤判：動詞
    字樣作為其他命令的參數（如 `grep ticket track complete f`），呼叫端需以
    狀態條件緩衝。

    Returns:
        - `None`：命令（或巢狀腳本）無法解析、或巢狀過深；呼叫端自行決定
          fail-open 或 fail-closed，不可與空清單混淆。
        - 清單：可能為空（可解析但無完成類命令）。
    """
    return find_ticket_track_invocations(command, COMPLETE_VERBS)


# 出現即遮蔽結束碼的語句分隔符（`&&` 與 `( )` 不在其中；換行已被正規化為 `;`）
_MASKING_SEPARATORS = frozenset({";", "|", "||", "&"})


def _masked_in_tokens(tokens: List[str]) -> bool:
    """token 流（含分隔符）是否含遮蔽結束碼的分隔符；尾端的 `;` 不算（其後無陳述）。"""
    end = len(tokens)
    while end > 0 and tokens[end - 1] == ";":
        end -= 1
    return any(tok in _MASKING_SEPARATORS for tok in tokens[:end])


_ASSIGNMENT_WORD = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\+?=")
_STATEMENT_ENDS = frozenset({";", "|", "||", "&", "&&"})


def _matching_close(tokens: List[str], open_idx: int) -> int:
    """回傳 open_idx 處 `(` 的配對 `)` 索引；未閉合時回傳 len(tokens)。"""
    depth = 0
    for j in range(open_idx, len(tokens)):
        if tokens[j] == "(":
            depth += 1
        elif tokens[j] == ")":
            depth -= 1
            if depth == 0:
                return j
    return len(tokens)


def _substitution_masks(tokens: List[str], depth: int = 0) -> bool:
    """陳述含命令替換且不是純賦值時為 True（結束碼來自命令字，替換的失敗被遮蔽）。

    純賦值（整句只有 NAME=$(...)，無命令字）才會把替換的結束碼傳出。
    `export x=$(...)`、`echo $(...)` 的結束碼來自 builtin／命令字。
    子 shell `( ... )` 內層遞迴套用同一判斷（`(echo $(...))` 為遮蔽）；超過
    _MAX_SCAN_NESTING 時保守回 True（寧可判遮蔽，多走驗證器或標記）。
    """
    words: List[str] = []
    has_subst = False
    paren_depth = 0

    def verdict() -> bool:
        return has_subst and not all(_ASSIGNMENT_WORD.match(w) for w in words)

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        i += 1
        idx = i - 1
        if tok in _STATEMENT_ENDS:
            if verdict():
                return True
            words, has_subst, paren_depth = [], False, 0
            continue
        if tok == "(":
            if idx > 0 and tokens[idx - 1].endswith("$"):
                has_subst = True
            elif paren_depth == 0:  # 子 shell：內層遞迴判斷
                if depth + 1 > _MAX_SCAN_NESTING:
                    return True
                close = _matching_close(tokens, idx)
                if _substitution_masks(tokens[idx + 1:close], depth + 1):
                    return True
                i = close + 1
                continue
            paren_depth += 1
            continue
        if tok == ")":
            paren_depth = max(0, paren_depth - 1)
            continue
        if paren_depth == 0:
            words.append(tok)
            if "$(" in tok:  # 引號內的替換被收斂為單一 token
                has_subst = True
    return verdict()


def _is_masked(command: str, depth: int) -> Optional[bool]:
    if depth > _MAX_SCAN_NESTING:
        return None
    tokens = tokenize_command(command) if command else []
    statements = parse_command_statements(command)
    if tokens is None or statements is None:
        return None
    if _masked_in_tokens(tokens) or _substitution_masks(tokens):
        return True
    for statement in statements:  # shell -c／eval 的巢狀字串另行判斷
        for i in range(len(statement)):
            script = nested_script(statement, i)
            if script:
                nested = _is_masked(script, depth + 1)
                if nested is None or nested:
                    return nested
    return False


def is_invocation_masked(command: str) -> Optional[bool]:
    """命令的結束碼是否可能被遮蔽（PostToolUse 觸發不再蘊含 ticket 呼叫成功）。

    PostToolUse 只在整條命令的 shell 層結束碼為 0 時觸發。命令中的 ticket 呼叫若
    失敗卻仍使整體結束碼為 0，即為遮蔽。判斷只看命令結構，不檢查是否含 ticket 呼叫。

    | 結構 | 回傳 |
    |------|------|
    | 單一命令、純重導向（`> log 2>&1`）、`&&` 串接、單獨的 `x=$(...)`／子 shell | False |
    | 含 `;`、管線、`||`、`&`（換行等同 `;`；尾端 `;` 不算）| True |
    | 命令替換後接其他陳述（`out=$(...); rc=$?`，因含 `;` 落入上列）| True |
    | 非純賦值陳述含命令替換（`echo $(...)`、`export x=$(...)`、`local`／`declare`）| True |
    | process substitution（`> >(tee log)`）| False |
    | `bash -c '...'`／eval 巢狀字串含上列分隔符 | True |
    | 無法解析（未閉合引號、巢狀過深）| None |

    None 與 False 不可混淆：呼叫端須退回標記判定（fail-safe），不可當作未遮蔽。
    `;` 前的陳述其實不影響最後一個陳述的結束碼，此處一律視為遮蔽（保守，多走驗證器或標記）。
    """
    return _is_masked(command, 0)


def has_complete_command(command: str) -> Optional[bool]:
    """命令中是否含完成類命令。無法解析（未閉合引號）時回傳 None。"""
    statements = parse_command_statements(command)
    if statements is None:
        return None
    return any(is_complete_statement(t) for t in statements)
