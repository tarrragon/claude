"""接行偵測（IMP-LLM-013）：合併前掃描 diff，找出「相鄰兩行被接成一行」與「.py 程式行被併入註解」。

Edit 以空字串刪行尾片段時會連換行一起刪除，下一行接到上一行。兩種偵測：
- 相鄰行接合：diff 同一 hunk 內，被刪的相鄰兩行 a、b，新增行 L 滿足 L = P + b 且 P 為 a 的非空前綴。
- .py 結構比對：字串內容正規化後比 AST，結構有變且被刪的程式行文字出現在新版註解中才報；
  新版無法解析而舊版可解析也報。只改字串或註解（AST 不變）不報。

本模組只產出 findings，不決定阻擋與否；預設語意為警告，由 merge_gate 掛接。
"""

import ast
import io
import os
import re
import subprocess
import sys
import tokenize
from typing import NamedTuple, Optional

SCAN_ENV = "LINE_JOIN_SCAN"  # warn（預設）| off；阻擋模式待主控放行後才新增
MIN_CODE_LINE_CHARS = 4  # 被刪程式行短於此不比對註解（避免 `pass`、`)` 之類的巧合）
_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


class Finding(NamedTuple):
    kind: str  # "join" | "py-comment" | "py-syntax"
    path: str
    line: int
    detail: str


# ----- (a) 相鄰行接合 -----

def _is_join(joined: str, first: str, second: str) -> bool:
    """joined 是否為 first 的非空前綴接上完整 second。"""
    tail = second.strip()  # 下一行的縮排會留在接合處，比對時略過
    if not tail or not joined.endswith(tail):
        return False
    prefix = joined[: len(joined) - len(tail)].rstrip()
    return bool(prefix.strip()) and first.startswith(prefix)


def _hunk_joins(path: str, removed: list, added: list) -> list:
    """removed、added 為 [(行號, 文字)]；回傳該 hunk 的接行 findings。"""
    added_texts = {text for _, text in added}
    found = []
    for (_, first), (_, second) in zip(removed, removed[1:]):
        if second in added_texts:
            continue  # 第二行仍獨立存在，不是被吞掉
        for lineno, text in added:
            if _is_join(text, first, second):
                found.append(Finding("join", path, lineno, f"兩行被接成一行：{text.strip()[:80]}"))
    return found


def scan_diff(diff_text: str) -> list:
    """解析 `git diff --unified=0` 輸出，回傳相鄰行接合 findings。"""
    findings, path = [], ""
    removed: list = []
    added: list = []
    new_line = 0

    def flush():
        findings.extend(_hunk_joins(path, removed, added))
        removed.clear()
        added.clear()

    for raw in diff_text.splitlines():
        if raw.startswith("+++ "):
            flush()
            path = raw[4:].removeprefix("b/")
        elif raw.startswith("--- "):
            flush()
        elif raw.startswith("@@"):
            flush()
            match = _HUNK_RE.match(raw)
            new_line = int(match.group(1)) if match else 0
        elif raw.startswith("-"):
            removed.append((0, raw[1:]))
        elif raw.startswith("+"):
            added.append((new_line, raw[1:]))
            new_line += 1
    flush()
    return findings


# ----- (b) .py AST 結構比對 -----

class _NormalizeStrings(ast.NodeTransformer):
    def visit_Constant(self, node):
        if isinstance(node.value, (str, bytes)):
            return ast.copy_location(ast.Constant(value=type(node.value)()), node)
        return node

    def visit_JoinedStr(self, node):
        return ast.copy_location(ast.Constant(value=""), node)


def _structure(source: str) -> Optional[str]:
    """字串內容正規化後的 AST dump；無法解析回 None。"""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return None
    return ast.dump(_NormalizeStrings().visit(tree))


def _comments(source: str) -> list:
    """[(行號, 註解文字)]；tokenize 失敗時退回逐行找 '#'。"""
    try:
        return [(t.start[0], t.string) for t in tokenize.generate_tokens(io.StringIO(source).readline)
                if t.type == tokenize.COMMENT]
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return [(i, line[line.index("#"):]) for i, line in enumerate(source.splitlines(), 1) if "#" in line]


def _removed_code_lines(old: str, new: str) -> list:
    new_set = {line.strip() for line in new.splitlines()}
    return [s for s in (line.strip() for line in old.splitlines())
            if len(s) >= MIN_CODE_LINE_CHARS and not s.startswith("#") and s not in new_set]


def scan_py_pair(path: str, old: str, new: str) -> list:
    """比對同一 .py 檔的舊新內容。"""
    old_struct = _structure(old)
    if old_struct is None:
        return []  # 舊版本身不可解析，無從比較
    new_struct = _structure(new)
    if new_struct is None:
        return [Finding("py-syntax", path, 1, "新版無法解析（舊版可解析）")]
    if new_struct == old_struct:
        return []  # 只改字串或註解
    comments = _comments(new)
    found = []
    for code in _removed_code_lines(old, new):
        for lineno, text in comments:
            if code in text:
                found.append(Finding("py-comment", path, lineno, f"程式行被併入註解：{code[:80]}"))
                break
    return found


# ----- 合併前掛接 -----

def _git_text(repo: str, args: list) -> Optional[str]:
    proc = subprocess.run(["git", *args], cwd=repo, capture_output=True, timeout=60)
    return proc.stdout.decode("utf-8", "replace") if proc.returncode == 0 else None


def scan_range(repo: str, old: str, new: str) -> list:
    """掃 old..new 的 diff 與其中的 .py 檔。"""
    diff = _git_text(repo, ["diff", "--unified=0", "--no-renames", old, new])
    if diff is None:
        raise RuntimeError(f"git diff {old[:12]}..{new[:12]} 失敗")
    findings = scan_diff(diff)
    names = _git_text(repo, ["diff", "--name-only", "--diff-filter=M", "--no-renames", old, new]) or ""
    for path in (n for n in names.splitlines() if n.endswith(".py")):
        before = _git_text(repo, ["show", f"{old}:{path}"])
        after = _git_text(repo, ["show", f"{new}:{path}"])
        if before is not None and after is not None:
            findings.extend(scan_py_pair(path, before, after))
    return findings


def warn_on_range(repo: str, old: str, new: str) -> list:
    """合併前警告入口：只輸出，不阻擋；掃描自身失敗寫 stderr 後放行。"""
    if os.environ.get(SCAN_ENV, "warn") == "off":
        return []
    try:
        findings = scan_range(repo, old, new)
    except Exception as exc:  # 掃描只是警告：任何例外都不得中斷閘門，寫 stderr 後放行
        sys.stderr.write(f"[合併前掃描] WARNING：接行偵測無法執行，略過：{exc}\n")
        return []
    for f in findings:
        line = f"[合併前掃描] WARNING：疑似接行（IMP-LLM-013）{f.kind}｜{f.path}:{f.line}｜{f.detail}"
        print(line)
        sys.stderr.write(line + "\n")
    return findings
