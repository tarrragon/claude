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

兩層檢查：
- 第一層（主線程與代理人皆適用，不受開發分支跳過影響）：候選路徑以 payload cwd
  解析、換算成所在 checkout 根目錄的相對路徑，落在 lib/、test/、integration_test/、
  .claude/** 即 DENY。豁免：建置快取（.venv、__pycache__ 等）、.claude 本地執行期
  產物（hook-logs、dispatch-active.json 等，清單對齊 .gitignore）、.git/、
  checkout 外路徑（暫存區、/dev/null）、git mv。ticket／doc CLI 自寫檔不經 shell
  重導向，命令文字無目標路徑，不受影響。
- 第二層（僅主線程；與 main-thread-edit-restriction-hook.py 一致）：轉呼
  check_file_permission，開發分支（feat/*、fix/* 等）跳過
- 失敗語意 fail_closed：解析例外或分派層逾時時擋下
- 殘留風險清單（靜態解析 fail-open，未偵測）：
  直譯器內動態組成、且命令與原始碼都沒有受限路徑線索的寫入目標（不擋，以
  additionalContext 警告放行；有線索時以線索路徑判定範圍）；腳本檔內目標無法判定的寫入
  （不走線索、不警告：既有腳本參數常含 .claude/ 路徑，套用線索會誤擋例行包裝命令）；
  腳本以 python -m 模組形態執行；同一命令內先寫腳本再執行（PreToolUse 時腳本尚不存在，
  只剩 argv 的字面路徑線索）；
  值含其他變數或命令替換的 $VAR（同命令內的字面賦值、~、$HOME、$(pwd) 前綴已展開）；
  bash -c／eval 的非字面引數；
  awk -i inplace、ruby、install、truncate、patch、tar -C、dd of=、rsync、ln -s、
  touch、curl -o 與版本控制的還原類子命令（命令集合為列舉式）
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
- cp src dst / mv src dst（目的地路徑；mv 的來源也算，移出等同刪除原位置）
- rm／unlink 的引數（路徑段含快取、hook-logs、.git、.github 者略過）
- 一般輸出重導向 > path / >> path（排除檔案描述符重導向 2>、&>）
- ed／ex 的檔案引數（編輯指令經 stdin 或 -c 送入，w／x 寫回該檔）
- python 腳本檔形態 python3 [選項] script.py args：腳本讀得到時以 ast 分析，
  只採可判定的寫入目標（常數或 argv 展開）；讀不到時 argv 中受限範圍的字面路徑納入候選
- node -e／--eval 腳本字串內 writeFileSync、appendFileSync 等 fs 寫入的字面路徑

共用介面：iter_checkout_write_targets(command, cwd) 逐候選產生 checkout 相對路徑，
bash-edit-guard-hook.py 以 importlib 載入本檔取用，兩支守衛的寫入目標判定同源。

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

import ast
import itertools
import os
import posixpath
import re
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent))         # .claude/hooks/
sys.path.insert(0, str(Path(__file__).parent.parent))   # .claude/       (lib.*)

from lib import setup_hook_logging, run_hook_safely, read_json_from_stdin, is_subagent_environment, emit_hook_output
from lib.git_utils import get_current_branch, is_allowed_branch
from lib.path_permission import check_file_permission, normalize_path
from lib.checkout_identity import (
    common_dir as _common_dir,
    same_repo as _same_repo,
    owning_checkout_root as _owning_checkout_root,
)

EXIT_ALLOW = 0
EXIT_BLOCK = 2

_MAX_HEREDOC_RECURSION = 2


# ============================================================================
# 命令解析：單趟 token 走訪（O(n)）
# ============================================================================

# 無特殊意義的連續字元，整段一次吃掉（字元集互斥，無回溯）
_PLAIN_RUN = re.compile(r"[^'\"\\\s;|&()`<>#]+")

# python open('path', ...) / open("path", ...)
# 字串可帶 1-2 字元前綴（f、r、rb 等）；第二個參數（模式）可為位置或 mode= 關鍵字
_OPEN_CALL_PATTERN = re.compile(
    r"open\(\s*[A-Za-z]{0,2}(['\"])([^'\"]+)\1(?:\s*,\s*(?:mode\s*=\s*)?[A-Za-z]{0,2}(['\"])([^'\"]*)\3)?"
)

# Path('x').write_text(...) / write_bytes(...)（含 pathlib.Path 前綴）
_PATH_WRITE_PATTERN = re.compile(
    r"Path\(\s*[A-Za-z]{0,2}(['\"])([^'\"]+)\1\s*\)\s*\.write_(?:text|bytes)\("
)


def _python_write_targets(text: str) -> List[str]:
    """python 原文中的寫入目標：open() 僅在模式含 w／a／x／+ 時算寫入（沒給模式為唯讀）。"""
    out = [m.group(2) for m in _OPEN_CALL_PATTERN.finditer(text)
           if m.group(4) and any(ch in m.group(4) for ch in "waxWAX+")]
    out.extend(m.group(2) for m in _PATH_WRITE_PATTERN.finditer(text))
    return out


_COPY_FUNCS = frozenset({"copy", "copy2", "copyfile", "move", "replace", "rename"})
_COPY_MODULES = frozenset({"shutil", "os"})
_PATH_CTORS = frozenset({"Path", "PurePath", "PosixPath"})


def _dotted(node: ast.AST) -> str:
    """Name／Attribute 鏈轉成 'a.b.c'；其他節點回空字串。"""
    parts: List[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return ""


def _is_argv(node: ast.AST, env) -> bool:
    """node 是否指向 sys.argv：sys.argv 本身，或 from sys import argv（含 as）／a = sys.argv 的別名。"""
    if _dotted(node) == "sys.argv":
        return True
    return isinstance(node, ast.Name) and node.id in env.get("__argv_names__", ())


def _argv_index(node: Optional[ast.AST], env) -> Optional[int]:
    """argv[<整數常數>] 的索引（負值為倒數第 k 個）；其他節點回 None。"""
    if not isinstance(node, ast.Subscript) or not _is_argv(node.value, env):
        return None
    idx = node.slice
    if hasattr(ast, "Index") and isinstance(idx, getattr(ast, "Index")):  # Python 3.8 相容
        idx = idx.value
    if (isinstance(idx, ast.UnaryOp) and isinstance(idx.op, ast.USub)
            and isinstance(idx.operand, ast.Constant) and isinstance(idx.operand.value, int)):
        return -idx.operand.value
    if isinstance(idx, ast.Constant) and isinstance(idx.value, int):
        return int(idx.value)  # bool 依 Python 語意為 int（True→1、False→0）
    return None


def _collect_argv_names(tree: ast.AST) -> set:
    """argv 的別名：from sys import argv [as x]，以及 a = sys.argv／a = <別名>（反覆至不再增加）。"""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "sys":
            names.update(a.asname or a.name for a in node.names if a.name == "argv")
    env = {"__argv_names__": names}
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and _is_argv(node.value, env):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id not in names:
                        names.add(target.id)
                        changed = True
    return names


def _const_path(node: Optional[ast.AST], env) -> Optional[str]:
    """節點若為全常數的字串／Path／串接／join 運算則回傳其字面值，否則 None。
    sys.argv[n] 取 env["sys.argv"]（命令列引數展開後清單，含 argv[0]）的對應項。"""
    index = _argv_index(node, env)
    if index is not None:
        argv = env.get("sys.argv") or []
        return argv[index] if -len(argv) <= index < len(argv) else None
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else None
    if isinstance(node, ast.Name):
        vals = env.get(node.id)
        return vals[-1] if vals else None
    if isinstance(node, ast.JoinedStr):
        # f-string：各段（常數與無格式指定的插值）皆可常數化才組出字串
        parts = []
        for value in node.values:
            if isinstance(value, ast.FormattedValue):
                if value.conversion != -1 or value.format_spec is not None:
                    return None
                value = value.value
            part = _const_path(value, env)
            if part is None:
                return None
            parts.append(part)
        return "".join(parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Div)):
        left, right = _const_path(node.left, env), _const_path(node.right, env)
        if left is None or right is None:
            return None
        return left + right if isinstance(node.op, ast.Add) else posixpath.join(left, right)
    if isinstance(node, ast.Call) and not node.keywords:
        name = _dotted(node.func)
        args = [_const_path(a, env) for a in node.args]
        if args and None not in args:
            if name.split(".")[-1] in _PATH_CTORS or name == "os.path.join":
                return posixpath.join(*args)
    return None


def _write_mode(node: Optional[ast.AST]) -> bool:
    return (isinstance(node, ast.Constant) and isinstance(node.value, str)
            and any(ch in node.value for ch in "waxWAX+"))


def _arg(call: ast.Call, index: int, kw: str) -> Optional[ast.AST]:
    if len(call.args) > index:
        return call.args[index]
    for k in call.keywords:
        if k.arg == kw:
            return k.value
    return None


def _mode_may_write(node: Optional[ast.AST]) -> bool:
    """open 的模式引數可能是寫入：常數含 w／a／x／+，或非常數（執行期才知道）。沒給模式為唯讀。"""
    if node is None:
        return False
    if isinstance(node, ast.Constant):
        return _write_mode(node)
    return True


def _argv_out_of_range(node: Optional[ast.AST], env) -> bool:
    """node 為 sys.argv[n] 且命令列引數已知、n 超出範圍：執行期 IndexError，不會寫入。"""
    index = _argv_index(node, env)
    argv = env.get("sys.argv")
    return index is not None and argv is not None and not -len(argv) <= index < len(argv)


def _call_write(call: ast.Call, env) -> tuple:
    """單一呼叫的 (是否為寫入呼叫, 寫入目標字面路徑或 None)。
    寫入呼叫但目標無法常數化時回 (True, None)，由呼叫端決定是否以其他線索補判。"""
    func = call.func
    name = _dotted(func)
    if name in ("open", "io.open"):
        file_arg = _arg(call, 0, "file")
        if _mode_may_write(_arg(call, 1, "mode")) and not _argv_out_of_range(file_arg, env):
            return True, _const_path(file_arg, env)
        return False, None
    if not isinstance(func, ast.Attribute):
        return False, None
    if func.attr in ("write_text", "write_bytes"):
        return True, _const_path(func.value, env)
    if func.attr == "open" and _mode_may_write(_arg(call, 0, "mode")):
        # 只有接收者是路徑（可常數化，或以 Path 建構）才算檔案寫入；file.open 等其他物件不判
        value = func.value
        is_path = isinstance(value, ast.Call) and _dotted(value.func).split(".")[-1] in _PATH_CTORS
        target = _const_path(value, env)
        if target is not None or is_path:
            return True, target
        return False, None
    if func.attr in _COPY_FUNCS and name.split(".")[0] in _COPY_MODULES:
        return True, _const_path(_arg(call, 1, "dst"), env)
    return False, None


def _call_write_target(call: ast.Call, env) -> Optional[str]:
    """單一呼叫的寫入目標字面路徑；非寫入或無法常數化則 None。"""
    return _call_write(call, env)[1]


def _ast_write_targets(source: str, argv: Optional[List[str]] = None) -> Optional[List[str]]:
    """以 ast 追蹤常數賦值後的寫入目標；解析失敗回 None（呼叫端退回 regex）。
    argv 為 python 命令列引數（含 argv[0]），供 sys.argv[n] 展開。"""
    result = _ast_analyze(source, argv)
    return None if result is None else result[0]


def _ast_analyze(source: str, argv: Optional[List[str]] = None) -> Optional[tuple]:
    """回傳 (寫入目標清單, 目標無法常數化的寫入呼叫數, 原始碼中的字串常數)；解析失敗回 None。"""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return None
    env = {}
    if argv is not None:
        env["sys.argv"] = argv
        env["__argv_names__"] = _collect_argv_names(tree)
    assigns = sorted((n for n in ast.walk(tree) if isinstance(n, ast.Assign)),
                     key=lambda n: (n.lineno, n.col_offset))
    for node in assigns:
        value = _const_path(node.value, env)
        if value is None:
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                env.setdefault(target.id, []).append(value)
    out: List[str] = []
    opaque = 0
    strings: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            is_write, target = _call_write(node, env)
            if target:
                out.append(target)
            elif is_write:
                opaque += 1
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            strings.append(node.value)
    return out, opaque, strings


# 寫入目標無法常數化時，命令或原始碼中出現的路徑線索。線索含受限頂層目錄的路徑段即納入候選，
# 交由路徑範圍檢查解析（checkout 外的同名目錄，如 /usr/lib/x，解析後不落在範圍內而放行）
def _scope_evidence(texts: List[str]) -> List[str]:
    """texts 中含受限頂層目錄路徑段（lib／test／integration_test／.claude）且含斜線的字串。"""
    out = []
    for text in texts:
        if "/" not in text or "\n" in text or len(text) > 512:
            continue
        if any(part in _SCOPE_TOP_DIRS for part in text.split("/")):
            out.append(text)
    return out


_TEMP_HINTS = ("/tmp/", "/private/tmp/", "/var/folders/")


def _temp_target_hint(texts: List[str], sources: List[str]) -> bool:
    """寫入目標可判定在暫存區：路徑線索以暫存目錄開頭，或原始碼使用 tempfile。"""
    if any(t.startswith(_TEMP_HINTS) or t in ("/tmp", "/private/tmp") for t in texts):
        return True
    return any(re.search(r"\btempfile\b", s) for s in sources)


_PYTHON_OPTS_WITH_ARG = frozenset({"-W", "-X", "-Q"})


def _python_argv_parts(tokens: List[str]) -> Optional[tuple]:
    """python 命令列引數的 (argv[0], 其後原始 token)；-m 模組形態與無引數回 None。
    python3 - a b：('-', [a, b])；python3 -c CODE a b：('-c', [a, b])；
    python3 script.py a b：('script.py', [a, b])；
    其間的直譯器選項（-u、-I、-B 等）不算引數，-W／-X 連同其值略過。"""
    start = next((i for i, t in enumerate(tokens) if _PYTHON_NAME.fullmatch(_basename(t))), None)
    if start is None:
        return None
    i = start + 1
    while i < len(tokens):
        tok = tokens[i]
        if tok == "-":
            return "-", tokens[i + 1:]
        short = tok.startswith("-") and not tok.startswith("--")
        if short and tok.endswith("c"):
            return "-c", tokens[i + 2:]
        if short and tok.endswith("m"):
            return None
        if not tok.startswith("-"):
            return tok, tokens[i + 1:]
        i += 2 if tok in _PYTHON_OPTS_WITH_ARG else 1
    return None


_MAX_SCRIPT_BYTES = 1 << 20


def _script_head(parts: Optional[tuple]) -> Optional[str]:
    """腳本檔形態的腳本路徑（argv[0]）；stdin、-c 與非 python 陳述回 None。"""
    if parts is None or parts[0] in ("-", "-c"):
        return None
    return parts[0]


def _read_script(head: str, cwd: Optional[str], cd: Optional[str]) -> Optional[str]:
    """腳本檔原文。開頭的 $CLAUDE_PROJECT_DIR、~、$HOME 以環境變數展開（與 _resolve_candidate 一致）；
    其餘變數或命令替換、cd 位移不明、讀不到或超過大小上限時回 None。"""
    project_dir, home = os.environ.get("CLAUDE_PROJECT_DIR"), os.environ.get("HOME")
    if project_dir:
        head = _PROJECT_DIR_VAR.sub(lambda _m: project_dir, head, count=1)
    if home:
        head = _HOME_PREFIX.sub(lambda _m: home, head, count=1)
    if cwd is None or cd is None or "$" in head or "`" in head or head.startswith("~"):
        return None
    path = os.path.join(cwd, cd, head)
    try:
        if os.path.getsize(path) > _MAX_SCRIPT_BYTES:
            return None
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:  # 不存在或無權限：呼叫端改以 argv 線索判定，屬預期分支不記錄
        return None


def _python_argvs(tokens: List[str], env: dict):
    """python 命令列引數（含 argv[0]）對所有可能值組合的展開，回傳 (argv 清單或 None, 是否超限)。
    非 stdin／-c 形態回 (None, False)。"""
    parts = _python_argv_parts(tokens)
    if parts is None:
        return None, False
    head, rest = parts
    per_token = []
    total = 1
    for t in rest:
        exps = _expand_all(t, env)
        if exps is None:
            return None, True
        total *= len(exps)
        if total > _MAX_COMBINATIONS:
            return None, True
        per_token.append(exps)
    return [[head] + list(combo) for combo in itertools.product(*per_token)], False


def _python_sources(tokens: List[str], bodies: List[str]) -> List[str]:
    """python 陳述的可解析原始碼：-c 後的引數（引號已剝除）與 heredoc 正文。"""
    sources = list(bodies)
    for i, tok in enumerate(tokens[:-1]):
        if tok == "-c" or (tok.startswith("-") and not tok.startswith("--") and tok.endswith("c")):
            sources.append(tokens[i + 1])
    return sources

_PYTHON_NAME = re.compile(r"python[\d.]*")
_SHELL_NAMES = frozenset({"sh", "bash", "zsh"})
_HEREDOC_DELIM_STOP = frozenset(" \t\r\n;|&()<>")


class _Statement:
    """一個以 | ; & 換行 ( ) 切出的陳述。"""

    __slots__ = ("tokens", "targets", "bodies", "start", "end", "pre", "before", "after")

    def __init__(self, start: int) -> None:
        self.tokens: List[str] = []    # 引號已剝除的 token（不含重導向目標）
        self.targets: List[str] = []   # 輸出重導向目標
        self.bodies: List[str] = []    # 此陳述宣告的 heredoc 正文
        self.start = start
        self.end = start
        self.pre = ""                  # 此陳述之前累積的括號邊界字元（只含 "(" 與 ")"）
        self.before = ""               # 與前一陳述之間的全部邊界字元（換行記為 ";"）
        self.after = ""                # 終結此陳述的邊界字元（換行與結尾記為 ";"）


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
    parens = ""  # 尚未歸屬任何陳述的括號邊界字元
    seps = ""    # 尚未歸屬任何陳述的全部邊界字元
    i = 0

    def flush() -> None:
        nonlocal buf, has_tok, redirect
        if not has_tok:
            return
        text = "".join(buf)
        if redirect == "dup":
            # >&N、>&- 是 fd 複製／關閉，其餘 >&word 是寫檔
            if not (text.isdigit() or text == "-"):
                cur.targets.append(text)
        elif redirect == "write":
            cur.targets.append(text)
        elif redirect != "skip":
            cur.tokens.append(text)
        redirect = None
        buf = []
        has_tok = False

    def end_statement(end_pos: int, next_start: int, boundary: str = "") -> None:
        nonlocal cur, redirect, parens, seps
        flush()
        cur.end = end_pos
        term = boundary or ";"
        if boundary in ("&", "|") and command.startswith(boundary * 2, end_pos):
            term = boundary * 2  # && 與 ||：左側必然在當前 shell 執行
        if cur.tokens or cur.targets or cur.bodies:
            cur.pre = parens
            parens = ""
            cur.before = seps
            cur.after = term
            seps = ""
            stmts.append(cur)
        seps += term
        if boundary in ("(", ")"):
            parens += boundary
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
            fd_text = "".join(buf) if has_tok else ""
            is_fd = fd_text.isdigit()
            if is_fd:
                buf = []
                has_tok = False
            else:
                flush()
            i += 2 if command.startswith(">>", i) else 1
            # 所有 fd（含 0）的 > >> >| 檔案目標皆是寫入；>&N、>&- 為 fd 複製
            dup = False
            if i < n and command[i] in "&|":
                dup = command[i] == "&"
                i += 1
            redirect = "dup" if dup else "write"
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
            redirect = "write"
        elif c == "(" and has_tok and buf[-1].endswith("$") and command.startswith("pwd)", i + 1):
            buf.append("(pwd)")  # $(pwd)：保留為 token 成分，由 _resolve_candidate 展開
            i += 5
        elif c == "`" and command.startswith("`pwd`", i):
            buf.append("`pwd`")
            has_tok = True
            i += 5
        else:
            # ; | & ( ) `：陳述邊界
            end_statement(i, i + 1, c)
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


def _scan_cp_mv(toks: List[str], j: int, out: List[str], move: bool = False) -> int:
    """cp / mv：略過旗標，最後一個位置參數為目的地（至少需要來源與目的地）。
    move 為真（mv）時來源也是候選：移出等同刪除原位置的檔案。cp 與 ln 的來源不變動，不列。"""
    positionals: List[str] = []
    target_dir: Optional[str] = None
    k = j
    while k < len(toks):
        t = toks[k]
        k += 1
        if t.startswith("--target-directory="):
            target_dir = t.split("=", 1)[1]
        elif t == "--target-directory" and k < len(toks):
            target_dir = toks[k]
            k += 1
        elif t.startswith("--") or t == "-" or t == "":
            if t in ("", "-"):
                positionals.append(t)
        elif t[0] == "-":
            if "t" in t[1:]:
                rest = t[t.index("t") + 1:]
                if rest:
                    target_dir = rest
                elif k < len(toks):
                    target_dir = toks[k]
                    k += 1
        else:
            positionals.append(t)
    if target_dir is not None:
        out.append(target_dir)  # -t DIR：所有位置參數都是來源
        sources = positionals
    elif len(positionals) >= 2:
        out.append(positionals[-1])
        sources = positionals[:-1]
    else:
        sources = []
    if move:
        out.extend(s for s in sources if s not in ("", "-"))
    return len(toks)


# rm 的引數落在這些快取、日誌或版本控制資料目錄時不算刪除受限內容（.claude 底下同樣適用）。
# .git／.github：首次安裝 clone 後刪除 .claude/.git、.claude/.github 是 README 的例行步驟
_REMOVABLE_COMPONENTS = frozenset({
    ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".dart_tool", "hook-logs",
    ".git", ".github",
})


def _scan_rm(toks: List[str], j: int, out: List[str]) -> int:
    """rm／unlink：位置參數皆為刪除目標；路徑段含快取或日誌目錄者略過。"""
    end_opts = False
    for t in toks[j:]:
        if not end_opts and t == "--":
            end_opts = True
        elif not end_opts and t.startswith("-") and t != "-":
            continue
        elif t and not any(p in _REMOVABLE_COMPONENTS for p in t.split("/")):
            out.append(t)
    return len(toks)


def _scan_perl(toks: List[str], j: int, out: List[str]) -> int:
    """perl -i / -pi / -i.bak：原地編輯，位置參數（扣掉未用 -e 時的腳本檔）為目標。"""
    inplace = False
    has_script_opt = False
    positionals: List[str] = []
    k = j
    while k < len(toks):
        t = toks[k]
        k += 1
        if len(t) > 1 and t[0] == "-" and t[1] != "-":
            for ch_idx in range(1, len(t)):
                ch = t[ch_idx]
                if ch == "i":
                    inplace = True
                    break
                if ch in "eE":
                    has_script_opt = True
                    if ch_idx == len(t) - 1:
                        k += 1
                    break
        elif not t.startswith("--"):
            positionals.append(t)
    if inplace:
        out.extend(positionals if has_script_opt else positionals[1:])
    return len(toks)


def _scan_tee(toks: List[str], j: int, out: List[str]) -> int:
    out.extend(t for t in toks[j:] if t == "" or t[0] != "-")
    return len(toks)


def _split_opts(toks: List[str], j: int, short_arg: str, long_arg: frozenset):
    """通用選項走訪：回傳 (位置參數, {選項: 值})。short_arg 為帶引數的短旗標字元集合，
    long_arg 為帶引數的長選項；`--opt=v` 與 `-Xv` 形式一併處理。"""
    positionals: List[str] = []
    opts: dict = {}
    k = j
    end_opts = False
    while k < len(toks):
        t = toks[k]
        k += 1
        if end_opts or t == "" or t[0] != "-" or t == "-":
            positionals.append(t)
        elif t == "--":
            end_opts = True
        elif t.startswith("--"):
            name, eq, val = t.partition("=")
            if eq:
                opts[name] = val
            elif name in long_arg and k < len(toks):
                opts[name] = toks[k]
                k += 1
            else:
                opts[name] = ""
        else:
            for idx in range(1, len(t)):
                ch = t[idx]
                if ch in short_arg:
                    rest = t[idx + 1:]
                    if rest:
                        opts["-" + ch] = rest
                    elif k < len(toks):
                        opts["-" + ch] = toks[k]
                        k += 1
                    break
                opts.setdefault("-" + ch, "")
    return positionals, opts


def _scan_dd(toks: List[str], j: int, out: List[str]) -> int:
    """dd：of=PATH 為寫入目標；只有 if= 的只讀用法不收集。"""
    out.extend(t[3:] for t in toks[j:] if t.startswith("of=") and len(t) > 3)
    return len(toks)


def _scan_install(toks: List[str], j: int, out: List[str]) -> int:
    """install：-d 時所有位置參數皆為建立目標，其餘同 cp（最後引數或 -t DIR）。"""
    pos, opts = _split_opts(toks, j, "mogSt", frozenset(
        {"--mode", "--owner", "--group", "--suffix", "--target-directory"}))
    target = opts.get("-t") or opts.get("--target-directory")
    if "-d" in opts or "--directory" in opts:
        out.extend(pos)
    elif target:
        out.append(target)
    elif len(pos) >= 2:
        out.append(pos[-1])
    return len(toks)


def _scan_truncate(toks: List[str], j: int, out: List[str]) -> int:
    """truncate / touch：略過帶引數的選項後，其餘位置參數皆為檔案目標。"""
    pos, _ = _split_opts(toks, j, "srtd", frozenset(
        {"--size", "--reference", "--date"}))
    out.extend(pos)
    return len(toks)


_RSYNC_ARG_OPTS = frozenset({
    "--exclude", "--include", "--exclude-from", "--include-from", "--filter",
    "--rsh", "--port", "--rsync-path", "--files-from", "--backup-dir", "--suffix",
    "--compare-dest", "--copy-dest", "--link-dest", "--bwlimit", "--max-size",
    "--min-size", "--log-file", "--temp-dir",
})


def _scan_rsync(toks: List[str], j: int, out: List[str]) -> int:
    """rsync：至少來源與目的地兩個位置參數時，最後一個為目的地；來源端不收集。"""
    pos, _ = _split_opts(toks, j, "ef", _RSYNC_ARG_OPTS)
    if len(pos) >= 2:
        out.append(pos[-1])
    return len(toks)


def _scan_tar(toks: List[str], j: int, out: List[str]) -> int:
    """tar：僅在解包（-x／--extract／舊式 x 模式字）時，-C／--directory 為寫入目標。"""
    extract = False
    pos, opts = _split_opts(toks, j, "CfTXLIKb", frozenset(
        {"--directory", "--file", "--files-from", "--exclude-from"}))
    if "--extract" in opts or "--get" in opts or "-x" in opts:
        extract = True
    elif toks[j:j + 1] and toks[j][:1] not in ("-", ""):
        extract = "x" in toks[j]  # 舊式 `tar xzf a.tgz`：第一個 token 是模式字
    if extract:
        d = opts.get("-C") or opts.get("--directory")
        if d:
            out.append(d)
    return len(toks)


def _scan_patch(toks: List[str], j: int, out: List[str]) -> int:
    """patch：--dry-run 不收集；-o 指定輸出檔時只收輸出檔；否則 -d DIR 與目標檔（有 -d 時合併）。"""
    pos, opts = _split_opts(toks, j, "pdiorBVzFD", frozenset(
        {"--strip", "--directory", "--input", "--output", "--reject-file", "--suffix"}))
    if "--dry-run" in opts or "-C" in opts or "--check" in opts:
        return len(toks)
    outfile = opts.get("-o") or opts.get("--output")
    d = opts.get("-d") or opts.get("--directory")
    if outfile:
        out.append(outfile)
        return len(toks)
    target = pos[0] if pos else None
    if target and d:
        out.append(d.rstrip("/") + "/" + target)
    elif target:
        out.append(target)
    elif d:
        out.append(d)
    return len(toks)


_ASSIGN_ARG = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")


def _scan_awk(toks: List[str], j: int, out: List[str]) -> int:
    """awk / gawk：-i inplace（或 -iinplace）時，程式文字（未用 -f）之後的檔案引數為目標。"""
    pos, opts = _split_opts(toks, j, "fvFi", frozenset(
        {"--file", "--assign", "--field-separator", "--include", "--load"}))
    inplace = opts.get("-i") == "inplace" or opts.get("--include") == "inplace"
    if inplace:
        has_prog_file = "-f" in opts or "--file" in opts
        files = pos if has_prog_file else pos[1:]
        out.extend(f for f in files if not _ASSIGN_ARG.match(f))
    return len(toks)


def _scan_ed_ex(toks: List[str], j: int, out: List[str]) -> int:
    """ed／ex：編輯指令由 stdin 或 -c 送入，w／x 指令寫回檔案引數，位置參數一律視為目標。"""
    pos, _ = _split_opts(toks, j, "pc", frozenset({"--prompt"}))
    out.extend(pos)
    return len(toks)


_RUBY_WRITE_LITERAL = re.compile(
    r"""File\.(?:write|binwrite)\(\s*(['"])([^'"]+)\1"""
    r"""|File\.open\(\s*(['"])([^'"]+)\3\s*,\s*['"][wa]""")


def _scan_ruby_perl_e(toks: List[str], j: int, out: List[str]) -> None:
    """ruby／perl 的腳本字串內 File.write／File.open(...,'w') 字面路徑。"""
    for t in toks[j:]:
        for m in _RUBY_WRITE_LITERAL.finditer(t):
            out.append(m.group(2) or m.group(4))


_NODE_WRITE_LITERAL = re.compile(
    r"""\b(?:writeFileSync|appendFileSync|writeFile|appendFile|createWriteStream)\(\s*(['"`])([^'"`]+)\1""")


def _scan_node_eval(toks: List[str], j: int, out: List[str]) -> None:
    """node 的 -e／--eval 腳本字串內 fs 寫入呼叫的字面路徑。"""
    for t in toks[j:]:
        out.extend(m.group(2) for m in _NODE_WRITE_LITERAL.finditer(t))


_ENV_ASSIGN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
_GIT_OPTS_WITH_ARG = frozenset({"-C", "-c", "--git-dir", "--work-tree", "--namespace"})


def _is_git_mv(toks: List[str]) -> bool:
    """陳述的命令字為 git（略過前置 env 賦值與 git 全域選項）且子命令為 mv。"""
    j = 0
    while j < len(toks) and _ENV_ASSIGN.match(toks[j]):
        j += 1
    if j >= len(toks) or _basename(toks[j]) != "git":
        return False
    j += 1
    while j < len(toks) and toks[j].startswith("-"):
        j += 2 if toks[j] in _GIT_OPTS_WITH_ARG else 1
    return j < len(toks) and toks[j] == "mv"


def _scan_statement_tokens(toks: List[str], out: List[str]) -> None:
    if _is_git_mv(toks):
        return  # git mv 是版本控制內的搬移（deny 訊息指定的正規做法），不是 shell 寫入
    cmd_word = _command_word_index(toks)  # 365.3 新增的命令只認命令字位置（避免 uv tool install 之類子命令誤判）
    j = 0
    while j < len(toks):
        name = _basename(toks[j])
        at_cmd = j == cmd_word
        if name == "sed":
            j = _scan_sed(toks, j + 1, out)
        elif name == "perl":
            if at_cmd:
                _scan_ruby_perl_e(toks, j + 1, out)
            j = _scan_perl(toks, j + 1, out)
        elif name in ("cp", "mv"):
            j = _scan_cp_mv(toks, j + 1, out, move=(name == "mv"))
        elif at_cmd and name in ("rm", "unlink"):
            j = _scan_rm(toks, j + 1, out)
        elif at_cmd and name == "ruby":
            _scan_ruby_perl_e(toks, j + 1, out)
            j += 1
        elif at_cmd and name in ("node", "nodejs"):
            _scan_node_eval(toks, j + 1, out)
            j += 1
        elif at_cmd and name == "ln":
            j = _scan_cp_mv(toks, j + 1, out)
        elif at_cmd and name == "dd":
            j = _scan_dd(toks, j + 1, out)
        elif at_cmd and name == "install":
            j = _scan_install(toks, j + 1, out)
        elif at_cmd and name in ("truncate", "touch"):
            j = _scan_truncate(toks, j + 1, out)
        elif at_cmd and name == "rsync":
            j = _scan_rsync(toks, j + 1, out)
        elif at_cmd and name == "tar":
            j = _scan_tar(toks, j + 1, out)
        elif at_cmd and name == "patch":
            j = _scan_patch(toks, j + 1, out)
        elif at_cmd and name in ("awk", "gawk"):
            j = _scan_awk(toks, j + 1, out)
        elif at_cmd and name in ("ed", "ex"):
            j = _scan_ed_ex(toks, j + 1, out)
        elif name == "tee":
            j = _scan_tee(toks, j + 1, out)
        else:
            j += 1


def _next_cd(cur_cd: Optional[str], toks: List[str]) -> Optional[str]:
    """陳述以 cd 開頭時更新累積的 cd 位移；None 表示無法靜態判定。"""
    if not toks or _basename(toks[0]) not in ("cd", "pushd"):
        return cur_cd
    if "-" in toks[1:]:
        return None  # cd -：回到前一個目錄，無法靜態判定
    args = [t for t in toks[1:] if t == "" or t[0] != "-"]
    if not args or cur_cd is None:
        return cur_cd
    target = args[0]
    if target[:1] in ("~", "$") or "$" in target or "`" in target:
        return None
    return target if target.startswith("/") else posixpath.join(cur_cd, target)


_ASSIGN = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)\Z", re.S)
_VAR_REF = re.compile(r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))")
# 值開頭的前綴由 _resolve_candidate 展開（家目錄、專案目錄），其餘 $ 與反引號皆視為無法判定
_RESOLVER_PREFIX = re.compile(r"^(?:~|\$HOME|\$\{HOME\}|\$CLAUDE_PROJECT_DIR|\$\{CLAUDE_PROJECT_DIR\})(?=/|$)")
_DECLARE_WORDS = frozenset({"export", "declare", "local", "readonly", "typeset"})
_WRAPPER_WORDS = frozenset({"env", "sudo", "exec", "nohup", "time", "command", "builtin"})


# 由解析階段（_resolve_candidate）以真實值展開的變數；命令內賦值不得改變其「展開前」形式
_SPECIAL_VARS = frozenset({"HOME", "CLAUDE_PROJECT_DIR"})
_MAX_COMBINATIONS = 16  # 可能值組合數上限；超過視為命中（保守擋下）
# 超限時的替身候選：本身即落在 lib/ 受限範圍，使超限必然被擋下
_OVERFLOW_PATH = "lib/_bash_guard_combination_overflow"
_SLOT = re.compile(r"^~(?=/|$)|\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")
# 複合命令（賦值可能不執行或重複執行）的開頭／結尾字，及其子句連接字
_COMPOUND_OPEN = frozenset({"if", "while", "until", "for", "select", "case", "{"})
_COMPOUND_CLOSE = frozenset({"fi", "done", "esac", "}"})
_CLAUSE_WORDS = frozenset({"then", "else", "elif", "do", "!", "time"})


def _slot_options(m, env: dict) -> List[str]:
    """一個變數參照（或開頭的 ~）的可能展開結果。env 值集合含 None 代表可能無法判定，
    該組合原樣保留參照文字。HOME、CLAUDE_PROJECT_DIR 另保留展開前形式（交給
    _resolve_candidate 以真實值解析）。"""
    name = "HOME" if m.group(0) == "~" else (m.group(1) or m.group(2))
    known = env.get(name)
    if name in _SPECIAL_VARS:
        return [m.group(0)] + sorted(v for v in (known or ()) if v is not None)
    if known is None:
        return [m.group(0)]
    out = [m.group(0) if v is None else v for v in sorted(known, key=lambda v: (v is None, v or ""))]
    return list(dict.fromkeys(out))


def _expand_all(raw: str, env: dict) -> Optional[List[str]]:
    """raw 內所有 $VAR／${VAR}／開頭 ~ 對各變數可能值的全部組合展開。
    組合數超過 _MAX_COMBINATIONS 或牽涉超限變數時回傳 None（呼叫端視為命中）。"""
    matches = list(_SLOT.finditer(raw))
    if not matches:
        return [raw]
    options = [_slot_options(m, env) for m in matches]
    total = 1
    for opts in options:
        if _OVERFLOW_PATH in opts:
            return None
        total *= len(opts)
        if total > _MAX_COMBINATIONS:
            return None
    results = []
    for combo in itertools.product(*options):
        parts, pos = [], 0
        for m, val in zip(matches, combo):
            parts.append(raw[pos:m.start()])
            parts.append(val)
            pos = m.end()
        parts.append(raw[pos:])
        results.append("".join(parts))
    return list(dict.fromkeys(results))


def _expand_candidate(raw: str, env: dict) -> List[str]:
    """候選路徑的全部可能展開；超限時以必擋的替身路徑取代。"""
    exps = _expand_all(raw, env)
    return [_OVERFLOW_PATH] if exps is None else exps


def _assignment_is_certain(stmt, depth: int) -> bool:
    """賦值陳述必然在當前 shell 執行：括號深度 0、非管線成員、不在 &&／|| 之後、非背景。"""
    before, after = stmt.before, stmt.after
    if depth > 0 or "|" in before or "&&" in before or "`" in before:
        return False
    return after not in ("|", "&", "`")


def _record_assignments(toks: List[str], env: dict, certain: bool = True) -> None:
    """純賦值陳述（可帶 export 等宣告字）更新 env：變數 → 可能值集合（含 None 代表可能無法判定）。
    值內的變數參照與 ~ 於賦值當下依當時的可能值展開；非字面（命令替換等）記 None。
    必然執行的賦值取代集合；非必然執行的賦值（certain=False）把新值併入既有集合
    （原本未知則併入 None）。集合大小超過上限時記超限替身。"""
    j = 1 if toks and toks[0] in _DECLARE_WORDS else 0
    items = toks[j:]
    if not items or not all(_ASSIGN.match(t) for t in items):
        return
    for t in items:
        name, value = _ASSIGN.match(t).groups()
        exps = _expand_all(value, env)
        if exps is None:
            new = {_OVERFLOW_PATH}
        else:
            new = {None if ("$" in rest or "`" in rest) else e
                   for e in exps for rest in [_RESOLVER_PREFIX.sub("", e, count=1)]}
        merged = new if certain else (env.get(name) or frozenset({None})) | new
        if len(merged) > _MAX_COMBINATIONS or _OVERFLOW_PATH in merged:
            merged = {_OVERFLOW_PATH}
        env[name] = frozenset(merged)


def _compound_effect(toks: List[str]):
    """陳述開頭的複合命令字：回傳 (開啟數, 結束數, 去除這些字後的 token)。"""
    opened = closed = 0
    k = 0
    while k < len(toks) and toks[k] in (_COMPOUND_OPEN | _COMPOUND_CLOSE | _CLAUSE_WORDS):
        if toks[k] in _COMPOUND_OPEN:
            opened += 1
        elif toks[k] in _COMPOUND_CLOSE:
            closed += 1
        k += 1
    return opened, closed, toks[k:]


def _command_word_index(toks: List[str]) -> Optional[int]:
    """命令字位置：略過前置賦值與 env／sudo 等包裝字及其旗標；無則 None。"""
    j = 0
    while j < len(toks):
        if _ENV_ASSIGN.match(toks[j]):
            j += 1
        elif _basename(toks[j]) in _WRAPPER_WORDS:
            j += 1
            while j < len(toks) and (toks[j].startswith("-") or _ENV_ASSIGN.match(toks[j])):
                j += 1
        else:
            return j
    return None


def _inline_script(toks: List[str]) -> Optional[str]:
    """命令字為 sh／bash／zsh 且帶 -c（含 -lc 等合併旗標）時的字面腳本；eval 的字面引數。"""
    j = _command_word_index(toks)
    if j is None:
        return None
    name = _basename(toks[j])
    if name == "eval":
        return " ".join(toks[j + 1:]) or None
    if name not in _SHELL_NAMES:
        return None
    k = j + 1
    while k < len(toks) and toks[k].startswith("-") and toks[k] != "--":
        flag = toks[k]
        k += 1
        if not flag.startswith("--") and "c" in flag[1:]:
            return toks[k] if k < len(toks) else None
    return None


def _collect_candidates(command: str, depth: int, dirs: Optional[List[Optional[str]]] = None,
                        base_cd: Optional[str] = "",
                        opaque: Optional[List[str]] = None,
                        cwd: Optional[str] = None) -> List[str]:
    """dirs 非 None 時，與回傳清單逐項對應地記錄各候選路徑生效的 cd 位移（"" 為無位移）。
    opaque 非 None 時，追加「有寫入呼叫但目標不明、也找不到受限路徑線索」的 python 陳述（截斷），
    供呼叫端以模型可見的警告放行。cwd 非 None 時，python 腳本檔形態會讀入腳本原文分析。"""
    candidates: List[str] = []
    statements = _parse_statements(command)
    command_tokens = [t for s in statements for t in s.tokens]
    env: dict = {}  # 同命令內先前語句的字面賦值
    cur_cd = base_cd
    compound_depth = 0  # 目前所在的複合命令（if／while／case／{ } 等）層數
    cd_stack: List[Optional[str]] = []  # 子殼：( 保存當下位移，) 還原

    def sync() -> None:
        if dirs is not None:
            dirs.extend([cur_cd] * (len(candidates) - len(dirs)))

    for stmt in statements:
        for ch in stmt.pre:
            if ch == "(":
                cd_stack.append(cur_cd)
            elif cd_stack:
                cur_cd = cd_stack.pop()
        cur_cd = _next_cd(cur_cd, stmt.tokens)
        opened, closed, body_toks = _compound_effect(stmt.tokens)
        compound_depth += opened
        certain = compound_depth == 0 and _assignment_is_certain(stmt, len(cd_stack))
        _record_assignments(body_toks, env, certain)
        compound_depth = max(0, compound_depth - closed)
        shell_candidates = list(stmt.targets)
        _scan_statement_tokens(stmt.tokens, shell_candidates)
        for c in shell_candidates:
            candidates.extend(_expand_candidate(c, env))
        names = [_basename(t) for t in stmt.tokens]
        if any(_PYTHON_NAME.fullmatch(name) for name in names):
            for text in [command[stmt.start:stmt.end]] + stmt.bodies:
                candidates.extend(_python_write_targets(text))
            # ast 追蹤變數持有的字面路徑；解析失敗時只保留上列 regex 結果（不放寬、不改擋）
            argvs, overflow = _python_argvs(stmt.tokens, env)
            if overflow:
                candidates.append(_OVERFLOW_PATH)
            sources = _python_sources(stmt.tokens, stmt.bodies)
            parts = _python_argv_parts(stmt.tokens)
            head = _script_head(parts)
            # 未給 cwd（日誌輔助、第二層檢查）時無從判斷腳本是否讀得到，不走腳本分支
            if head is not None and cwd is not None:
                script_text = _read_script(head, cwd, cur_cd)
                if script_text is not None:
                    # 腳本檔只採可判定的寫入目標（常數或 argv 展開）。目標不明的寫入
                    # （如狀態檔的 os.replace(tmp, path)）不走命令 token 線索：既有腳本
                    # 的參數常含 .claude/ 路徑，套用線索會誤擋 run-with-timeout 等例行包裝
                    for argv in (argvs if argvs is not None else [None]):
                        analysis = _ast_analyze(script_text, argv)
                        if analysis is not None:
                            candidates.extend(analysis[0])
                else:
                    # 腳本讀不到：無從分析寫入呼叫，argv 中落在受限範圍的字面路徑納入候選
                    candidates.extend(_scope_evidence(parts[1]))
            opaque_writes = 0
            strings: List[str] = []
            for argv in (argvs if argvs is not None else [None]):
                for source in sources:
                    analysis = _ast_analyze(source, argv)
                    if analysis is None:
                        continue
                    targets, n_opaque, found = analysis
                    candidates.extend(targets)
                    # argv 未展開的 shell 變數（$f）同樣是目標不明，路徑範圍檢查會判 unresolvable
                    opaque_writes += n_opaque + sum(1 for t in targets if "$" in t or "`" in t)
                    strings.extend(found)
            if opaque_writes:
                # 寫入呼叫的目標不明：以原始碼字串常數與整條命令的 token 找受限路徑線索
                clues = strings + command_tokens
                evidence = _scope_evidence(clues)
                if evidence:
                    candidates.extend(dict.fromkeys(evidence))
                elif opaque is not None and not _temp_target_hint(clues, sources):
                    opaque.append(command[stmt.start:stmt.end][:120])
        sync()
        script = _inline_script(stmt.tokens) if depth < _MAX_HEREDOC_RECURSION else None
        if script is not None:
            sub_dirs: List[Optional[str]] = []
            candidates.extend(_collect_candidates(script, depth + 1, sub_dirs, cur_cd, opaque, cwd))
            if dirs is not None:
                dirs.extend(sub_dirs)
        if depth < _MAX_HEREDOC_RECURSION and any(name in _SHELL_NAMES for name in names):
            for body in stmt.bodies:
                candidates.extend(_collect_candidates(body, depth + 1, None, cur_cd, opaque, cwd))
                sync()
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


# ============================================================================
# 路徑範圍阻擋：主線程與代理人共用，不受開發分支跳過影響
# ============================================================================

# checkout 根目錄下，Bash 不得寫入的頂層目錄
_SCOPE_TOP_DIRS = frozenset({"lib", "test", "integration_test", ".claude"})

# 路徑任一層級為這些名稱即視為建置／快取產物
_EXEMPT_COMPONENTS = frozenset({
    ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".dart_tool",
})

# .claude 底下的本地執行期產物。只保留「無任何 hook／閘門／CLI 讀為判定輸入、
# 也不注入模型 context」者（逐項 grep 讀取方複核後的結果）。
# 已移除：settings.local.json、dispatch-active.json／.lock、hook-state、state、handoff、
# hook-logs、logs、.sync-state.json、.version-release.yaml（皆有讀取方）。
_EXEMPT_CLAUDE_ENTRIES = frozenset({
    ".sync-conflicts", ".zhtw-mcp-skip",
    "ARCHITECTURE_REVIEW_REQUIRED", "PM_INTERVENTION_REQUIRED", "TASK_AVOIDANCE_FIX_MODE",
    "analyses", "migration-backups", "plans", "pm-status.json",
    "scheduled_tasks.lock", "tool-results",
})

_WORKTREE_PREFIX = ".claude/worktrees/"
_PROJECT_DIR_VAR = re.compile(r"^\$\{?CLAUDE_PROJECT_DIR\}?(?=/|$)")


def _slash(path: str) -> str:
    """判定鏈一律以正斜線比對：Windows 上 os.path 回傳反斜線路徑，
    不換算時 root + "/" 前綴與以 "/" 切分的範圍判定全數不命中，範圍內寫入會被放行（#132）。
    磁碟機代號統一大寫，避免 c: 與 C: 被當成不同根。POSIX 上原樣回傳。"""
    if os.path.sep == "/":
        return path
    path = path.replace(os.path.sep, "/")
    if len(path) > 1 and path[1] == ":":
        path = path[0].upper() + path[1:]
    return path


def _find_checkout_root(cwd: str) -> str:
    """自 cwd 向上找含 .git（目錄或檔案）的目錄，即所在 checkout 根目錄；找不到回傳 cwd。
    回傳值已經 _slash 換算。"""
    cur = os.path.realpath(cwd)
    while True:
        if os.path.exists(os.path.join(cur, ".git")):
            return _slash(cur)
        parent = os.path.dirname(cur)
        if parent == cur:
            return _slash(os.path.realpath(cwd))
        cur = parent


def _scope_roots(cwd: str) -> List[str]:
    """候選路徑要換算的 checkout 根目錄：所在 checkout，加上 worktree 對應的主 checkout。"""
    root = _find_checkout_root(cwd)
    roots = [root]
    marker = "/" + _WORKTREE_PREFIX
    if marker in root + "/":
        main_root = (root + "/").split(marker, 1)[0]
        if main_root and main_root != root:
            roots.append(main_root)
    return roots


def _relative_to_roots(abs_path: str, roots: List[str]) -> Optional[str]:
    for root in roots:
        if abs_path == root:
            return ""
        if abs_path.startswith(root + "/"):
            return abs_path[len(root) + 1:]
    return None


def _strip_worktree_prefix(rel: str) -> str:
    """從主 checkout 看 worktree 內的檔案：剝掉前綴，以 worktree 自己的根目錄判定。"""
    while rel.startswith(_WORKTREE_PREFIX):
        rel = rel[len(_WORKTREE_PREFIX):].partition("/")[2]
    return rel


def _scope_hit(rel: str) -> bool:
    """rel（checkout 相對路徑，已剝 worktree 前綴）是否落在阻擋範圍且不在豁免清單。"""
    parts = [p for p in rel.split("/") if p]
    if not parts or parts[0] not in _SCOPE_TOP_DIRS:
        return False
    # 建置快取只在 .claude 之外豁免：.claude/hooks／lib 下的 .pyc 會在 hook 執行時載入
    if parts[0] != ".claude" and any(p in _EXEMPT_COMPONENTS for p in parts):
        return False
    if parts[0] == ".claude" and len(parts) > 1 and parts[1] in _EXEMPT_CLAUDE_ENTRIES:
        return False
    return True


_HOME_PREFIX = re.compile(r"^(?:~|\$HOME|\$\{HOME\})(?=/|$)")
_PWD_PREFIX = re.compile(r"^(?:\$\(pwd\)|`pwd`)(?=/|$)")


def _resolve_candidate(raw: str, cd: str, cwd: str, root: str) -> Optional[str]:
    """候選路徑解析為絕對路徑；展開 CLAUDE_PROJECT_DIR、~／$HOME、$(pwd)／`pwd` 前綴。
    含其他無法靜態判定的成分（其他變數、命令替換、~user）回傳 None。"""
    if not raw:
        return None
    # 以函式作替換值：root 為 Windows 路徑（含反斜線）時，字串替換值會被 re 解析為跳脫序列而拋例外（#132）
    raw = _PROJECT_DIR_VAR.sub(lambda _m: root, raw)
    if _HOME_PREFIX.match(raw):
        home = os.environ.get("HOME")
        if not home:
            return None
        raw = _HOME_PREFIX.sub(lambda _m: home, raw, count=1)
    raw = _PWD_PREFIX.sub(lambda _m: os.path.join(cwd, cd), raw, count=1)
    if raw[0] == "~" or "$" in raw or "`" in raw:
        return None
    return _slash(os.path.realpath(os.path.join(cwd, cd, raw)))


def _checkout_root_or_none(cwd: str) -> Optional[str]:
    """cwd 所在 checkout 根目錄；cwd 不在任何 checkout 內回傳 None。"""
    root = _find_checkout_root(cwd)
    return root if os.path.exists(os.path.join(root, ".git")) else None


def iter_checkout_write_targets(command: str, cwd: str, opaque: Optional[List[str]] = None):
    """逐候選寫入路徑產生 (raw, rel, why)。供本 hook 與 bash-edit-guard 共用。

    rel 為 checkout 相對路徑（已剝 worktree 前綴）。候選相對於 cwd（含命令內 cd 位移）
    解析，換算成所在 checkout 根目錄（worktree 另加其主 checkout）的相對路徑；
    目標落在同 repo 的其他 worktree 時以該 checkout 為根。無法靜態判定時 rel 為 None、
    why 為 unresolvable；落在 checkout 之外時 rel 為 None、why 為 out_of_scope。
    cwd 不在任何 checkout 內時，以 CLAUDE_PROJECT_DIR 所屬 checkout 為比對基準。
    """
    dirs: List[Optional[str]] = []
    base = os.path.realpath(cwd)
    candidates = _collect_candidates(command, 0, dirs, opaque=opaque, cwd=base)
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if project_dir and _checkout_root_or_none(cwd) is None:
        roots = _scope_roots(project_dir)
    else:
        roots = _scope_roots(cwd)
    for raw, cd in zip(candidates, dirs):
        abs_path = None if cd is None else _resolve_candidate(raw, cd, base, roots[0])
        if abs_path is None:
            yield raw, None, "unresolvable"
            continue
        rel = _relative_to_roots(abs_path, roots)
        if rel is None:
            owner = _owning_checkout_root(abs_path)
            if owner is None or not _same_repo(owner, roots[0]):
                yield raw, None, "out_of_scope"
                continue
            owner = _slash(owner)
            rel = abs_path[len(owner) + 1:] if abs_path != owner else ""
        yield raw, _strip_worktree_prefix(rel), ""


def _find_scope_violation(command: str, cwd: str, logger,
                          skipped: Optional[List[str]] = None,
                          opaque: Optional[List[str]] = None) -> Optional[str]:
    """
    回傳第一個落在 lib/、test/、integration_test/、.claude/**（扣除豁免）的候選寫入路徑
    （換算成 checkout 相對路徑）；無命中回傳 None。

    候選路徑相對於 cwd（含命令內 cd 位移）解析，再換算成所在 checkout 根目錄
    （worktree 另加其主 checkout）的相對路徑比對，因此 worktree 內的 lib/x 也會命中。
    無法靜態判定的路徑（其他變數、命令替換、字串拼接）放行，見模組檔頭殘留風險。
    cwd 不在任何 checkout 內時，以 CLAUDE_PROJECT_DIR 所屬 checkout 為比對基準
    （未設定則維持以 cwd 為基準）。
    skipped 非 None 時，逐候選追加 "<raw>:<unresolvable|out_of_scope>"（命中者不列）。
    """
    def skip(raw: str, why: str) -> None:
        if skipped is not None:
            skipped.append("%s:%s" % (raw, why))

    for raw, rel, why in iter_checkout_write_targets(command, cwd, opaque):
        if rel is None:
            skip(raw, why)
            continue
        if not _scope_hit(rel):
            skip(raw, "out_of_scope")
            continue
        logger.warning("偵測到 Bash 寫入受限路徑: path=%s cwd=%s command=%s", rel, cwd, command)
        return rel
    return None


_LOG_CMD_LIMIT = 200  # 判定日誌的命令截斷上限，heredoc 正文不全文入日誌


def _decision_source(input_data: dict) -> str:
    """來源：沿用 is_subagent_environment 判定；代理人取 agent_id（缺則 agent_type），否則 main。"""
    if is_subagent_environment(input_data):
        return "agent:%s" % (input_data.get("agent_id") or input_data.get("agent_type") or "unknown")
    return "main"


def _log_decision(logger, decision: str, input_data: dict, reason_code: str,
                  command: str, targets: Optional[List[str]] = None,
                  skipped: Optional[List[str]] = None) -> None:
    """每個放行／阻擋分支記一行穩定可 grep 的判定：
    decision=<allow|deny> source=<main|agent:ID> reason=<code> targets=[...] skipped=[...] cmd=<前 200 字元>
    targets 為 None 時才即時抽取候選目標（抽取失敗記空，不影響判定）。
    skipped 為路徑範圍檢查逐候選的跳過原因（"<raw>:out_of_scope|unresolvable"），未檢查時為空。"""
    if targets is None:
        try:
            targets = _extract_candidate_paths(command) if command else []
        except Exception:  # 日誌輔助不得改變判定；失敗以空目標記錄
            targets = []
    cmd = command[:_LOG_CMD_LIMIT].replace("\n", "\\n")
    logger.info(
        "decision=%s source=%s reason=%s targets=%s skipped=%s cmd=%s",
        decision, _decision_source(input_data), reason_code, list(targets), list(skipped or []), cmd,
    )


def _opaque_write_warning(opaque: List[str]) -> Optional[str]:
    """寫入目標不明的 python 陳述的模型可見警告；無則 None。"""
    if not opaque:
        return None
    return (
        "[bash-write-boundary-guard] 放行，但偵測到 python 寫入呼叫的目標路徑無法靜態判定"
        f"（{opaque[0]}）。本 hook 無法確認它是否寫入 lib/、test/、integration_test/、.claude/**。"
        "若寫入對象是這些範圍或 docs/ 等受管檔案，改用 Edit／Write；"
        "寫入暫存區請讓路徑以字面寫出（如 /tmp/...）。"
    )


def _allow_and_exit(logger, reason: str, input_data: Optional[dict] = None,
                    reason_code: str = "", command: str = "",
                    skipped: Optional[List[str]] = None,
                    opaque: Optional[List[str]] = None) -> int:
    _log_decision(logger, "allow", input_data or {}, reason_code, command, None, skipped)
    warning = _opaque_write_warning(opaque or [])
    if warning:
        # 警告路徑只送 additionalContext，不帶 permission_decision：不擴大略過權限提示的範圍
        logger.info("opaque_write_warning count=%d first=%s", len(opaque), opaque[0][:80].replace("\n", "\\n"))
        emit_hook_output("PreToolUse", additional_context=warning)
        return EXIT_ALLOW
    # 放行不輸出 decision：allow 會略過平台的權限提示，等於代用戶核可
    logger.debug("放行不輸出 decision：%s", reason)
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
        return _allow_and_exit(logger, "輸入為空，預設允許", {}, "empty_input")

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input") or {}

    if tool_name != "Bash":
        logger.debug(f"跳過: 工具類型 {tool_name} 不是 Bash")
        return _allow_and_exit(logger, f"工具 {tool_name} 不在檢查範圍", input_data, "non_bash_tool")

    command = tool_input.get("command", "")
    if not command:
        return _allow_and_exit(logger, "command 為空，允許", input_data, "empty_command")

    # 第一層：路徑範圍阻擋，主線程與代理人皆適用，不受開發分支跳過影響
    # （feat/* worktree 內若跳過，整層即失效）
    cwd = input_data.get("cwd") or os.getcwd()
    skipped: List[str] = []
    opaque: List[str] = []
    scope_path = _find_scope_violation(command, cwd, logger, skipped, opaque)
    if scope_path is not None:
        who = "代理人" if is_subagent_environment(input_data) else "主線程"
        reason = (
            f"Bash 寫入受限路徑被擋下（path={scope_path}，呼叫身份={who}）。"
            "lib/、test/、integration_test/、.claude/** 禁止透過 Bash"
            "（cat/printf/tee/sed -i/python open()/cp/mv/重導向）寫入。"
            "請改用 Edit 或 Write 工具修改檔案；搬移已追蹤的檔案用 git mv，刪除已追蹤的檔案用 git rm"
            "（mv 的來源與 rm／unlink 的引數同樣受限）；未追蹤的檔案需要刪除或移出時停手回報。"
            "不得改用其他 Bash 寫法（python heredoc、argv 傳路徑、腳本檔等）重試同一寫入；"
            "Edit／Write 不可用時停手，於 ticket NeedsContext 記錄並回報 PM。"
            "依行範圍搬移文字（拆檔、移段落）改用 "
            "ticket track move-lines <ticket-id> --src … --lines A-B --dst … --at N；"
            "src 與 dst 須在該票 where.files 內，無票或檔案不在範圍內時不適用。"
            "lib/ 等處的建置快取（.dart_tool 等）與少數無讀取方的 .claude 本地產物不受此限。"
            "用戶以 ! 前綴自行執行的命令不經過本 hook，不受此限制。"
            "若是本 hook 自身異常而誤擋正常命令，改用 Edit 修正 "
            ".claude/hooks/bash-write-boundary-guard-hook.py（Edit 不受本 hook 影響）。"
        )
        _log_decision(logger, "deny", input_data, "scope_violation", command, [scope_path], skipped)
        emit_hook_output(
            "PreToolUse",
            permission_decision="deny",
            permission_decision_reason=reason,
        )
        logger.info("Hook 檢查完成（路徑範圍阻擋），exit code: %d", EXIT_BLOCK)
        return EXIT_BLOCK

    # 第二層（僅主線程）：PM 可寫路徑模型。Subagent 的 lib/test 寫入權責由
    # 第一層決定，不套用 PM 模型
    if is_subagent_environment(input_data):
        logger.info(f"subagent 環境（agent_id={input_data.get('agent_id')}），路徑範圍檢查通過")
        return _allow_and_exit(logger, "subagent 的 Bash 寫入未命中受限路徑", input_data, "subagent_no_scope_hit", command, skipped, opaque)

    # 開發分支跳過（feat/*, fix/* 等），與 main-thread-edit-restriction 一致；
    # 僅作用於第二層
    current_branch = get_current_branch()
    if current_branch and is_allowed_branch(current_branch):
        logger.info(f"開發分支 '{current_branch}' 上，跳過 Bash 寫入邊界限制")
        return _allow_and_exit(
            logger, f"開發分支 '{current_branch}' 不受主線程 Bash 寫入邊界限制",
            input_data, "dev_branch_skip", command, skipped, opaque,
        )

    violation_path = _find_boundary_violation(command, logger)

    if violation_path is None:
        logger.debug("未偵測到明確的 test/lib/dart 寫入目標，允許（fail-open）")
        return _allow_and_exit(logger, "未偵測到職責邊界違規的 Bash 寫入形態", input_data, "no_boundary_violation", command, skipped, opaque)

    reason = (
        f"偵測到 Bash 寫入職責邊界違規（path={violation_path}）。"
        "主線程禁止透過 Bash（cat/tee/sed -i/python open()/cp/mv/heredoc 等）"
        "寫入 test/、lib/、*.dart，等同繞過 main-thread-edit-restriction-hook.py "
        "的職責邊界執法。請改派代理人執行此寫入。"
    )
    _log_decision(logger, "deny", input_data, "boundary_violation", command, [violation_path])
    emit_hook_output(
        "PreToolUse",
        permission_decision="deny",
        permission_decision_reason=reason,
    )
    logger.info("Hook 檢查完成，exit code: %d", EXIT_BLOCK)
    return EXIT_BLOCK


if __name__ == "__main__":
    # fail_closed：此守衛的失效方向是放行；解析異常或分派層逾時時擋下，
    # 理由與負載實測見票面 Solution
    sys.exit(run_hook_safely(main, "bash-write-boundary-guard", fail_closed=True))
