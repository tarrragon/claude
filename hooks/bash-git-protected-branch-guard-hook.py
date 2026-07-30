#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Bash Git Protected-Branch Guard Hook - PreToolUse Hook

功能: 封閉 branch-verify-hook 的 Bash 層繞道路徑（0.2.1-W3-151，PC-V1-012 實例），
並封閉 0.2.1-W3-154 發現的 add-and-commit 串接繞道。
branch-verify-hook 只註冊於 Edit/Write matcher，以 file_path 判斷保護分支；
Bash `git commit` 可達成同一後果（外部 repo 保護分支被寫入）卻不受檢查。
本 hook 專責 Bash 路徑，與 branch-verify-hook（Edit/Write 路徑）分離。

Hook Event: PreToolUse
Matcher: Bash
Decision: "allow"（無輸出，沿用 bash-edit-guard-hook 慣例）| "deny"

============================================================
方案取捨（0.2.1-W3-151 ticket Solution 摘要，完整記錄見 ticket md）
============================================================
選定：另建專責 Bash 守衛（而非擴充 branch-verify-hook 加 Bash matcher）。

理由：
1. 輸入形態不同 —— Edit/Write 的 tool_input 有 file_path，Bash 只有 command
   字串。混進同一 main() 需整段分支兩種形狀，膨脹既有已測試路徑的變更半徑
   （branch-verify-hook 的 Edit/Write 行為是「不可回歸項」，風險最高）。
2. Bash 是最高頻工具（已有 15 個 PreToolUse Bash hook），需要在昂貴解析前
   做便宜的前置判斷；獨立 hook 可讓非 git 命令在第一行 regex 後就短路，
   不需先經過 Edit/Write 路徑無關的程式碼。
3. 豁免清單語意仍須與 Edit/Write 路徑一致 —— 透過 lib/git_utils.py 的
   GENERIC_EXEMPT_EXACT（SSOT）共用，而非各自維護一份清單。

============================================================
add-and-commit 串接繞道與修復設計（0.2.1-W3-154）
============================================================
根因：PreToolUse 評估時機在 Bash 命令「執行前」。若命令為
`git add X && git commit`，hook 評估當下 `add` 尚未真正跑，`git diff --cached`
讀到的仍是「執行前」的舊狀態（空），命中舊版「無 staged 即 no-op」的假設——
該假設在串接情境不成立，commit 實際上會把 add 的檔案一併提交。

修復：不再只讀「當下」的 staged 狀態，改為從命令字串本身**額外推導**本次
commit 完成後會納入的檔案集合，三個來源取聯集：
1. commit 呼叫自身的明確 pathspec（如 `git commit README.md`）。
2. 同範圍內（同 -C 目標 repo字串 / 同子 shell）先出現的 `git add <path...>`
   之 path 引數（字面路徑，不含萬用字元 / `-A` / `.` 等目錄列舉語意）。
3. 呼叫當下已 staged 的檔案（沿用舊邏輯，涵蓋「commit 前已用獨立 Bash 呼叫
   add 過」的情況——這個來源本身沒有問題，問題出在「只看這個來源」）。

三者任一無法靜態列舉（萬用字元、`git add -A`/`.`、`git commit -a`/`-am`/
`--all`）→ **fail-closed**（deny，要求拆成獨立 Bash 呼叫）。這與舊版「無法
確認 staged 清單則 deny」是同一保守方向的延伸，但新增「無法從命令字串靜態
推導」也視為無法確認。`git commit -a`/`-am`/`--all` 一律 fail-closed（不嘗試
用 `git diff --name-only` 反推，理由：與同鏈的 `git add` 疊加時，何者最終被
`-a` 涵蓋在字串層無法可靠判定，寧可要求使用者明確拆分）。

三者皆可列舉且聯集為空集合 → 真正 no-op，放行（不誤擋，acceptance 3）。

============================================================
-C 目標 shell 展開語法繞道與修復設計（0.2.1-W3-156）
============================================================
根因：0.2.1-W3-154 落地後 PM 以 scratchpad 臨時 repo 實測，同一違規情境
（外部 repo 在保護分支、add 非豁免檔後 commit）依 `-C` 目標的字面形式產生
相反結果——目標為字面絕對路徑正確 deny；目標為 shell 變數（如
`git -C $T add x && git -C $T commit`）時靜默放行。成因：PreToolUse 時機看到
的是命令的**原始未展開文字**，`$T` 這個字面字串不以 `/` 開頭，舊版
`_resolve_repo_root` 判定「非絕對路徑」即回 None，`_resolve_cross_repo_
protected_target` 將 None 一律視為「無法解析，安全放行」——這與同 hook 對
pathspec 無法靜態列舉時採 fail-closed 的原則矛盾：兩種「不確定」情境本應
採同一保守方向。

修復：`_resolve_repo_root` 拆分「無法解析」的兩種成因，分別對應不同處置：
1. **含 shell 展開語法**（`$`/反引號/`~`）→ `outcome="shell_expansion"`，
   呼叫端 **fail-closed**（deny）。理由：這些字元的實際值只有 shell 真正
   執行時才知道，PreToolUse 時機的字面文字不可信，無法透過任何靜態手段
   確認其真實指向（Bash 工具的持久 shell 狀態、環境變數皆不透傳給 hook
   子行程，見下方殘留限制）。
2. **純粹不含展開語法但無法解析**（相對路徑、或指向不存在的字面絕對路徑）
   → `outcome="unresolvable"`，維持 **fail-open**（allow，沿用
   0.2.1-W3-151 既有邊界）。理由：該命令本身在真正執行時就會因路徑不存在
   而失敗，不需要 hook 額外把關。

**已知且無法收口的殘留類別**：一旦 `-C` 目標含 shell 展開語法，hook
無法判斷該變數展開後是否恰好等於本專案路徑——`os.environ` 不含 Bash 工具
持久 shell 內的變數賦值（該 shell 狀態不跨 Bash 呼叫持久化，更不透傳給
另一個行程啟動的 hook）。因此 **凡 `-C` 目標含展開語法者一律 fail-closed，
不分是否恰好指向本專案**。若使用者確實需要對本專案套用變數化 `-C` 目標，
建議改用字面絕對路徑，或省略 `-C`（cwd 隱含形式完全不受本 hook 解析）。
此為結構性限制而非本票遺漏，已於 Solution 記錄供 PM 評估是否需要另立
Ticket 處理（如降級為模糊比對或提示式警告）。

同批修復 pathspec 解析誤把 shell 重導向 token（`2>`、`2>&1`、`>>` 等）當
路徑的問題（acceptance 5）：`_parse_literal_paths`/`_parse_commit_pathspec`
新增 `_is_shell_redirection_token()` 過濾，命中即略過（不計入路徑，也不
fail-closed——重導向 token 本身不影響「是否有未知內容待提交」的判斷）。
已知殘留：僅涵蓋「重導向符號單獨成 token」（如 `2>&1`），不含與路徑黏在
一起無空格的形式（如 `2>/dev/null`），此形式仍會被當作路徑列出（多報不
漏報，方向安全，未進一步處理）。

============================================================
範疇邊界（刻意不做，非遺漏）
============================================================
- 僅偵測 `git commit`。不含 merge/rebase/cherry-pick/revert/push——這些
  子命令在 write 前無法可靠取得「即將變更的檔案清單」，若要涵蓋需要不同的
  豁免判斷設計，留待實際發現繞道案例時再開票（quality-baseline 規則 5，
  非預先臆測擴大範疇）。
- 僅解析 `git -C <abs> commit` 與 `(cd <abs> && ... git commit ...)` 兩種
  明確表達目標 repo 的形式。cwd 隱含形式（無 -C、無 cd）不解析——Bash 工具
  的持久 cwd 對 hook 進程不可見，猜測會有誤判風險。未解析到明確目標 repo
  且不含 shell 展開語法時一律 allow（安全預設：寧可漏放，不誤擋本專案）。
- `-C`/`cd` 目標為相對路徑（不含展開語法）時不解析，維持 allow（同上理由）。
- `git add`/`git commit` 的路徑引數若含跳脫字元或無法被 `shlex.split` 正確
  切分（如未閉合引號），視為無法靜態列舉，fail-closed。

============================================================
效能設計
============================================================
`_contains_git_word()` 為第一道便宜判斷（單一 regex 搜尋 "git" 字樣）。
非 git 命令（Bash 工具最大宗）在此短路，不進入 `_find_write_invocations()`
的多重 regex 解析，避免每次 Bash 呼叫都承擔完整解析成本。
"""

import os
import re
import shlex
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.git_utils import (
    GENERIC_EXEMPT_EXACT,
    find_target_repo,
    get_current_branch,
    get_project_root,
    is_protected_branch,
    run_git_command,
)
from lib import setup_hook_logging, run_hook_safely, read_json_from_stdin, emit_hook_output


# 目前僅涵蓋 commit（範疇邊界見檔頭說明）
WRITE_SUBCOMMANDS = ("commit",)

_WRITE_ALTERNATION = "|".join(WRITE_SUBCOMMANDS)

# 便宜前置判斷：命令是否含 "git" 字樣（避免非 git 命令進入昂貴解析路徑）
_GIT_WORD_RE = re.compile(r"\bgit\b")

# 形式 1：git -C <path> commit ...（rest 截至 && / ; / 子 shell 右括號 / 字串結尾）
_GIT_DASH_C_WRITE_RE = re.compile(
    r"\bgit\s+-C\s+(?P<repo>\S+)\s+(?P<subcmd>" + _WRITE_ALTERNATION + r")\b(?P<rest>[^&;)]*)"
)

# 形式 2：子 shell (cd <dir> && ... git commit ...)（未帶 -C 的 git 呼叫）
_SUBSHELL_RE = re.compile(r"\(([^()]*)\)")
_SUBSHELL_CD_RE = re.compile(r"^\s*cd\s+(?P<repo>\S+)\s*(?:&&|;)")
_SUBSHELL_GIT_WRITE_RE = re.compile(
    r"\bgit\s+(?!-C\b)(?P<subcmd>" + _WRITE_ALTERNATION + r")\b(?P<rest>[^&;)]*)"
)

# git add 呼叫（0.2.1-W3-154：用於推導本次命令會額外 stage 的檔案）
_GIT_DASH_C_ADD_RE_TEMPLATE = r"\bgit\s+-C\s+{repo}\s+add\b(?P<rest>[^&;)]*)"
_SUBSHELL_ADD_RE = re.compile(r"\bgit\s+(?!-C\b)add\b(?P<rest>[^&;)]*)")

# git add 無法靜態列舉的 flag（目錄列舉語意，需實際檔案系統狀態）
_ADD_UNENUMERABLE_FLAGS = {
    "-A", "--all", "-u", "--update", "-i", "--interactive", "-p", "--patch",
    "-e", "--edit", "-N", "--intent-to-add",
}

# git commit 會消耗下一個 token 作為值的 flag（該值不是 pathspec）
_COMMIT_VALUE_FLAGS = {
    "-m", "--message", "-c", "--reuse-message", "-C", "--reedit-message",
    "--fixup", "--author", "--date", "-F", "--file", "-t", "--template",
    "--squash",
}

# 短 flag 組合偵測：含 'a' 字元的短 flag（如 -a / -am / -av）視為隱含
# stage-all，一律 fail-closed（範疇邊界：不嘗試用 git diff --name-only 反推）
_SHORT_FLAG_RE = re.compile(r"^-[a-zA-Z]+$")

_GLOB_CHARS = ("*", "?", "[")

# 0.2.1-W3-156：-C/cd 目標含 shell 展開語法（$變數/`反引號`/~家目錄）時，
# PreToolUse 看到的是未展開的原始文字，無法信任其字面內容，須 fail-closed。
_SHELL_EXPANSION_RE = re.compile(r"[$`~]")

# 0.2.1-W3-156：shell 重導向 token（>、>>、<、N>、N>&M、&>）不是路徑，
# 解析 add/commit 引數時應略過而非誤列為檔案。
_REDIRECTION_TOKEN_RE = re.compile(r"^&?\d*(>>?|<)&?\d*$")


def _contains_git_word(command: str) -> bool:
    """便宜前置判斷：命令是否含獨立的 'git' 字樣。

    非 git 命令（Bash 工具最大宗）在此短路，不進入後續解析（規則對應
    ticket acceptance「非 git 的 Bash 命令不受影響且無顯著延遲增加」）。
    """
    if not command:
        return False
    return bool(_GIT_WORD_RE.search(command))


def _has_shell_expansion_syntax(s: str) -> bool:
    """判斷字串是否含 shell 展開語法（$/`` ` ``/~）。

    命令字串在 PreToolUse 時機為原始未展開文字，這些字元代表實際執行時
    的值會與此刻看到的字面文字不同，靜態比對其字面內容不可靠
    （0.2.1-W3-156）。
    """
    if not s:
        return False
    return bool(_SHELL_EXPANSION_RE.search(s))


def _is_shell_redirection_token(tok: str) -> bool:
    """判斷 token 是否為 shell 重導向符號（>、>>、<、2>、2>&1 等）。

    這些 token 是 shell 重導向語法的一部分，不是路徑；解析 add/commit
    引數時應略過，避免誤列為非豁免檔案污染 deny 訊息（0.2.1-W3-156）。
    已知殘留：不含與路徑黏在一起無空格的形式（如 `2>/dev/null`），
    該形式仍會被當作路徑列出（多報不漏報，方向安全）。
    """
    return bool(_REDIRECTION_TOKEN_RE.match(tok))


def _find_write_invocations(command: str) -> List[Dict[str, object]]:
    """解析命令中的 git write 呼叫。

    回傳 [{"repo_hint": str, "subcmd": str, "rest": str,
           "scope_content": str|None}, ...]。

    涵蓋兩種目標 repo 表達形式（範疇邊界見檔頭）：
    1. `git -C <path> commit ...`（scope_content=None，代表「同範圍」的
       `git add` 需以相同 repo_hint 字串在整個命令內搜尋）
    2. `(cd <dir> && ... git commit ...)`（scope_content=該子 shell 內容，
       「同範圍」的 `git add` 只在此子 shell 內容內搜尋）

    repo_hint 可能是相對路徑或絕對路徑，是否可解析交由呼叫端
    `_resolve_repo_root()` 決定（相對路徑一律視為無法解析）。
    """
    invocations: List[Dict[str, object]] = []

    for match in _GIT_DASH_C_WRITE_RE.finditer(command):
        invocations.append(
            {
                "repo_hint": match.group("repo"),
                "subcmd": match.group("subcmd"),
                "rest": match.group("rest"),
                "scope_content": None,
            }
        )

    for sub_match in _SUBSHELL_RE.finditer(command):
        content = sub_match.group(1)
        cd_match = _SUBSHELL_CD_RE.match(content.strip())
        if not cd_match:
            continue
        write_match = _SUBSHELL_GIT_WRITE_RE.search(content)
        if not write_match:
            continue
        invocations.append(
            {
                "repo_hint": cd_match.group("repo"),
                "subcmd": write_match.group("subcmd"),
                "rest": write_match.group("rest"),
                "scope_content": content,
            }
        )

    return invocations


def _resolve_repo_root(repo_hint: str) -> Tuple[str, Optional[str]]:
    """將 repo_hint 解析為實際 repo 根目錄，並標註無法解析時的成因。

    回傳 (outcome, target_root)：
    - outcome="resolved"：target_root 為實際 repo 根目錄。
    - outcome="shell_expansion"：repo_hint 含 $/`` ` ``/~ 等 shell 展開語法，
      target_root 恆為 None，呼叫端應 fail-closed（0.2.1-W3-156）。
    - outcome="unresolvable"：不含展開語法但非絕對路徑，或指向不存在的
      git repo，target_root 恆為 None，呼叫端維持 fail-open（該命令本身
      在真正執行時會失敗，範疇邊界沿用 0.2.1-W3-151）。

    repo_hint 可能指向 repo 內任意子目錄（git -C 語意），用 find_target_repo
    向上尋找 .git 標記取得真正的 repo 根目錄。
    """
    if _has_shell_expansion_syntax(repo_hint):
        return "shell_expansion", None
    if not repo_hint or not repo_hint.startswith("/"):
        return "unresolvable", None
    target_root = find_target_repo(repo_hint)
    if target_root is None:
        return "unresolvable", None
    return "resolved", target_root


def _is_host_repo(target_root: str, host_root: str) -> bool:
    """判斷 target_root 是否與本專案（host）相同 repo。"""
    return os.path.realpath(target_root) == os.path.realpath(host_root)


def _get_staged_files(target_root: str, logger) -> Optional[List[str]]:
    """回傳 target_root 內已 staged（--cached）的相對路徑清單。

    回傳 None 表示無法確認（git 命令失敗），呼叫端應保守判定為 deny——
    此時已確認目標是跨專案保護分支的 commit 呼叫，無法驗證安全性時
    寧可擋下讓使用者重試，也不放行未知內容。
    """
    success, output = run_git_command(["diff", "--cached", "--name-only"], cwd=target_root)
    if not success:
        logger.warning(
            "無法讀取 %s 的 staged 檔案清單，保守判定為 deny: %s", target_root, output
        )
        return None
    if not output:
        return []
    return [line for line in output.split("\n") if line.strip()]


def _parse_literal_paths(rest: str, unenumerable_flags: "set") -> Optional[List[str]]:
    """將 rest 字串解析為明確的字面路徑清單。

    回傳 None 表示無法靜態列舉（fail-closed 訊號）：命中 unenumerable_flags、
    出現 `.`（目錄列舉）、含萬用字元、或 shlex 無法切分（未閉合引號等）。
    """
    try:
        tokens = shlex.split(rest)
    except ValueError:
        return None

    paths: List[str] = []
    for tok in tokens:
        if tok in unenumerable_flags:
            return None
        if tok == ".":
            return None
        if tok == "--":
            continue
        if _is_shell_redirection_token(tok):
            continue  # shell 重導向 token（2>&1 等）不是路徑，略過（W3-156）
        if tok.startswith("-"):
            continue  # 其餘 flag（如 -v/--verbose）不影響列舉，略過
        if any(c in tok for c in _GLOB_CHARS):
            return None
        paths.append(tok)
    return paths


def _parse_commit_pathspec(rest: str) -> Tuple[bool, Optional[List[str]]]:
    """解析 commit 呼叫自身的 rest，回傳 (has_stage_all_flag, paths)。

    has_stage_all_flag=True：命中 -a/-am/--all 等隱含 stage-all 的 flag，
      paths 恆為 None，呼叫端一律 fail-closed（範疇邊界，理由見檔頭）。
    否則 paths 為明確 pathspec 清單（可能為空清單），None 表示無法靜態
    列舉（萬用字元、shlex 解析失敗）。
    """
    try:
        tokens = shlex.split(rest)
    except ValueError:
        return False, None

    paths: List[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]

        if tok == "--all" or (_SHORT_FLAG_RE.match(tok) and "a" in tok[1:]):
            return True, None

        if tok in _COMMIT_VALUE_FLAGS:
            i += 2  # 跳過 flag 及其值（值不是 pathspec）
            continue

        if tok == "--":
            i += 1
            continue

        if _is_shell_redirection_token(tok):
            i += 1  # shell 重導向 token（2>&1 等）不是路徑，略過（W3-156）
            continue

        if tok.startswith("-"):
            i += 1  # 其餘無值旗標（如 --amend、-n、-v），略過
            continue

        if any(c in tok for c in _GLOB_CHARS):
            return False, None

        paths.append(tok)
        i += 1

    return False, paths


def _find_add_rests(command: str, repo_hint: str, scope_content: Optional[str]) -> List[str]:
    """回傳同範圍內 `git add` 呼叫的 rest 引數字串清單。

    -C 形式（scope_content=None）：在整個命令內搜尋相同 repo_hint 字串的
    `git -C <repo_hint> add ...`（字面字串比對，非路徑語意等價比對，
    已知限制見檔頭範疇邊界）。
    子 shell 形式（scope_content 非 None）：只在該子 shell 內容內搜尋。
    """
    if scope_content is not None:
        return [m.group("rest") for m in _SUBSHELL_ADD_RE.finditer(scope_content)]

    pattern = re.compile(_GIT_DASH_C_ADD_RE_TEMPLATE.format(repo=re.escape(repo_hint)))
    return [m.group("rest") for m in pattern.finditer(command)]


def _normalize_paths(paths: List[str], repo_hint: str, target_root: str) -> List[str]:
    """將 add/commit 引數路徑正規化為相對 repo root 的路徑。

    repo_hint 恆為絕對路徑（呼叫時機已通過 `_resolve_repo_root` 篩選）。
    repo_hint 可能指向 repo 內子目錄（git -C 語意），故相對路徑引數需先
    併入 repo_hint 相對 root 的偏移，才是相對 root 的正確路徑。
    """
    hint_rel = os.path.relpath(repo_hint, target_root)
    normalized = []
    for p in paths:
        if os.path.isabs(p):
            normalized.append(os.path.normpath(os.path.relpath(p, target_root)))
        elif hint_rel == ".":
            normalized.append(os.path.normpath(p))
        else:
            normalized.append(os.path.normpath(os.path.join(hint_rel, p)))
    return normalized


def build_bash_cross_repo_deny_message(
    target_repo: str,
    target_branch: str,
    non_exempt_files: List[str],
    suggested_branch: str = "feat/cross-repo-edit",
    fail_closed: bool = False,
) -> str:
    """跨專案保護分支 Bash commit 的 deny 訊息，與 Write 路徑語意一致。

    附目標 repo/branch、非豁免檔案清單（或 fail-closed 說明）、可執行的
    下一步指令（0.2.1-W3-149 依此決定執行方式）。
    """
    if fail_closed:
        files_block = (
            "  (無法從命令字串靜態確認本次 commit 完成後的完整檔案集合，\n"
            "   可能含 git commit -a/-am/--all、git add 萬用字元或目錄列舉，\n"
            "   為避免遺漏保護，已保守阻擋)"
        )
        next_step = (
            "請拆成獨立 Bash 呼叫：先執行 git add <明確檔案清單>，\n"
            "以 git -C {repo} status 確認 staged 內容後，再單獨執行 git commit。"
        ).format(repo=target_repo)
    elif non_exempt_files:
        files_block = "\n".join(f"  - {f}" for f in non_exempt_files)
        next_step = (
            "跨專案豁免清單僅含通用文件（README.md / CHANGELOG.md / .gitignore / "
            ".gitattributes），此次提交內容不在豁免清單內，需先切換到 feature 分支再提交。"
        )
    else:
        files_block = "  (無法確認 staged 檔案清單，保守阻擋)"
        next_step = "無法確認提交內容是否安全，需先切換到 feature 分支再提交。"

    return f"""保護分支寫入被阻止（跨專案，Bash git commit）

目標 repo 當前在保護分支：
- 目標 repo：{target_repo}
- 目標 branch：{target_branch}
- 非豁免檔案：
{files_block}

{next_step}

複製以下指令切換目標 repo 分支（在另一個 terminal 執行）：

  git -C {target_repo} status
  git -C {target_repo} checkout -b {suggested_branch}

完成切換後即可重試本次 commit。"""


def build_shell_expansion_deny_message(repo_hint: str) -> str:
    """`-C`/`cd` 目標含 shell 展開語法時的 deny 訊息（0.2.1-W3-156）。

    PreToolUse 時機看到的是命令的原始未展開文字，`$` 變數 / 反引號指令
    替換 / `~` 家目錄展開的實際值只有 shell 真正執行時才知道，靜態比對
    其字面內容不可靠，故一律 deny，而非嘗試臆測其展開後的值。
    """
    return f"""保護分支寫入被阻止（git -C 目標無法靜態解析）

git -C（或子 shell 內的 cd）目標含 shell 展開語法：
- 目標字串：{repo_hint}

PreToolUse 檢查時機在命令真正執行之前，看到的是未展開的原始文字，無法
確認其實際指向哪個 repo，也就無法確認是否為受保護分支。為避免遺漏保護，
已保守阻擋（無法區分是否恰好指向本專案）。

請改用展開後的字面絕對路徑重新執行本次 git 操作。可先用獨立的 Bash 呼叫
確認實際路徑（例如 `echo {repo_hint}`），再用該字面路徑呼叫 git -C。"""


def _resolve_cross_repo_protected_target(
    inv: Dict[str, object], host_root: str, logger
) -> Tuple[str, Optional[Dict[str, str]]]:
    """判斷此 invocation 的解析結果。

    回傳 (outcome, target)：
    - outcome="shell_expansion"：-C/cd 目標含 shell 展開語法，target=None，
      呼叫端應 fail-closed deny（0.2.1-W3-156，無法區分是否恰好指向本專案，
      見檔頭殘留限制說明）。
    - outcome="skip"：其餘安全放行條件（不含展開語法但無法解析 / 同 host
      repo / 無法取得分支 / 非保護分支），target=None，呼叫端允許。
    - outcome="hit"：命中跨專案保護分支，target={"target_root":..., "branch":...}，
      交由呼叫端做檔案集合檢查。
    """
    resolve_outcome, target_root = _resolve_repo_root(inv["repo_hint"])

    if resolve_outcome == "shell_expansion":
        logger.info(
            "repo_hint=%s 含 shell 展開語法，PreToolUse 時機無法信任字面內容，fail-closed",
            inv["repo_hint"],
        )
        return "shell_expansion", None

    if not target_root:
        logger.debug("repo_hint=%s 無法解析為絕對路徑下的 git repo，略過", inv["repo_hint"])
        return "skip", None

    if _is_host_repo(target_root, host_root):
        logger.debug("目標 repo %s 與本專案相同，允許", target_root)
        return "skip", None

    current_branch = get_current_branch(cwd=target_root)
    if not current_branch:
        logger.debug("無法取得 %s 的分支資訊，允許", target_root)
        return "skip", None

    if not is_protected_branch(current_branch):
        logger.debug("%s 當前分支 '%s' 非保護分支，允許", target_root, current_branch)
        return "skip", None

    return "hit", {"target_root": target_root, "branch": current_branch}


def _files_from_commit_pathspec(
    inv: Dict[str, object], target_root: str
) -> Optional[List[str]]:
    """來源 1：commit 呼叫自身的明確 pathspec。

    回傳 None 表示無法靜態列舉（-a/-am/--all，或萬用字元/無法切分），
    呼叫端應 fail-closed。
    """
    has_stage_all, commit_paths = _parse_commit_pathspec(str(inv.get("rest", "")))
    if has_stage_all or commit_paths is None:
        return None
    return _normalize_paths(commit_paths, str(inv["repo_hint"]), target_root)


def _files_from_git_add(
    command: str, inv: Dict[str, object], target_root: str
) -> Optional[List[str]]:
    """來源 2：同範圍（同 -C 目標字串 / 同子 shell）內 git add 呼叫的路徑引數。

    回傳 None 表示任一 add 呼叫含無法列舉引數（-A/./萬用字元等），
    呼叫端應 fail-closed。
    """
    files: List[str] = []
    add_rests = _find_add_rests(command, str(inv["repo_hint"]), inv.get("scope_content"))
    for rest in add_rests:
        add_paths = _parse_literal_paths(rest, _ADD_UNENUMERABLE_FLAGS)
        if add_paths is None:
            return None
        files.extend(_normalize_paths(add_paths, str(inv["repo_hint"]), target_root))
    return files


def _determine_pending_files(
    command: str, inv: Dict[str, object], target_root: str, logger
) -> Tuple[bool, List[str]]:
    """推導本次 commit 完成後會納入的完整檔案集合（相對 repo root）。

    三來源聯集：commit pathspec（來源 1）/ 同範圍 git add（來源 2）/
    呼叫當下已 staged（來源 3，沿用 0.2.1-W3-151 既有邏輯）。

    回傳 (fail_closed, files)：
    - fail_closed=True：任一來源無法靜態列舉，files 恆為空清單，
      呼叫端應直接 deny（0.2.1-W3-154 範疇：-a/-am/--all、萬用字元、
      shlex 無法切分、staged 清單讀取失敗）。
    - fail_closed=False：files 為三來源聯集後的完整清單，可能為空
      （真正 no-op）。
    """
    from_commit = _files_from_commit_pathspec(inv, target_root)
    if from_commit is None:
        logger.info(
            "%s commit 呼叫含 -a/-am/--all 或 pathspec 無法靜態列舉，fail-closed", target_root
        )
        return True, []

    from_add = _files_from_git_add(command, inv, target_root)
    if from_add is None:
        logger.info(
            "%s 同範圍 git add 含無法列舉引數（-A/./萬用字元等），fail-closed", target_root
        )
        return True, []

    staged = _get_staged_files(target_root, logger)
    if staged is None:
        return True, []

    return False, sorted(set(from_commit) | set(from_add) | set(staged))


def _check_files_for_target(
    command: str, inv: Dict[str, object], target: Dict[str, str], logger
) -> Optional[str]:
    """已確認命中跨專案保護分支，檢查待提交檔案集合，回傳 deny 訊息（None 表示允許）。"""
    target_root = target["target_root"]
    current_branch = target["branch"]

    fail_closed, files = _determine_pending_files(command, inv, target_root, logger)
    if fail_closed:
        logger.info("跨專案保護分支 commit 被阻止（fail-closed）：%s", target_root)
        return build_bash_cross_repo_deny_message(
            target_repo=target_root,
            target_branch=current_branch,
            non_exempt_files=[],
            fail_closed=True,
        )

    if not files:
        logger.debug("%s 本次 commit 完成後無任何變更檔案，允許（真正 no-op）", target_root)
        return None

    non_exempt = [f for f in files if f not in GENERIC_EXEMPT_EXACT]
    if not non_exempt:
        logger.debug("%s 本次 commit 完成後檔案皆在豁免清單，允許", target_root)
        return None

    logger.info(
        "跨專案保護分支 commit 被阻止：%s，非豁免檔案 %d 個", target_root, len(non_exempt)
    )
    return build_bash_cross_repo_deny_message(
        target_repo=target_root, target_branch=current_branch, non_exempt_files=non_exempt
    )


def _check_invocation(command: str, inv: Dict[str, object], host_root: str, logger) -> Optional[str]:
    """檢查單一 write 呼叫，回傳 deny 訊息（None 表示允許）。

    Phase 4（0.2.1-W3-156）：拆為「解析 invocation 的三態結果」與「命中時
    的檔案集合檢查」兩段，前者交由 `_resolve_cross_repo_protected_target`，
    後者交由 `_check_files_for_target`，本函式僅負責依 outcome 分派。
    """
    outcome, target = _resolve_cross_repo_protected_target(inv, host_root, logger)

    if outcome == "shell_expansion":
        return build_shell_expansion_deny_message(str(inv["repo_hint"]))

    if outcome != "hit":
        return None

    return _check_files_for_target(command, inv, target, logger)


def main() -> int:
    logger = setup_hook_logging("bash-git-protected-branch-guard")

    input_data = read_json_from_stdin(logger)
    if input_data is None:
        logger.debug("無有效輸入，允許")
        return 0

    tool_name = input_data.get("tool_name", "")
    if tool_name != "Bash":
        logger.debug("工具 %s 不需要 Bash git 守衛檢查", tool_name)
        return 0

    tool_input = input_data.get("tool_input") or {}
    command = tool_input.get("command", "")

    if not _contains_git_word(command):
        logger.debug("命令不含 git 字樣，短路允許")
        return 0

    invocations = _find_write_invocations(command)
    if not invocations:
        logger.debug("命令含 git 但無可解析的 write 呼叫（-C 或子 shell cd 形式），允許")
        return 0

    host_root = str(get_project_root())

    for inv in invocations:
        deny_message = _check_invocation(command, inv, host_root, logger)
        if deny_message:
            emit_hook_output(
                "PreToolUse",
                permission_decision="deny",
                permission_decision_reason=deny_message,
            )
            return 0

    logger.debug("所有偵測到的 git write 呼叫皆通過檢查，允許")
    return 0


if __name__ == "__main__":
    exit_code = run_hook_safely(main, "bash-git-protected-branch-guard")
    sys.exit(exit_code)
