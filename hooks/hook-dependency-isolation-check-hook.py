#!/usr/bin/env python3
"""hook-dependency-isolation-check — SessionStart + PostToolUse Hook

背景：`.claude/hooks/*.py` 與 `.claude/skills/<skill>/hooks/*.py` 可用兩種
方式宣告依賴隔離：(a) shebang 為 `uv run --script` 搭配 PEP 723 inline
metadata（`# /// script ... dependencies = [...] ... # ///`），settings.json
以可執行檔路徑（無額外直譯器前綴）登記時，由 OS shebang 機制交給 uv
建立隔離環境；(b) 純 `#!/usr/bin/env python3` shebang，依賴 ambient 環境
已安裝對應套件。本檢查針對的是「宣告」與「ambient 環境依賴現實」的落差
——同批修復已驗證 uv shebang 隔離確實生效（將受影響 hook 改用該寫法後
問題消失），故本檢查以此為判準基準。

兩種寫法各自都可能出現「宣告與現實不一致」：

1. **危險宣告**：shebang 非 uv，但 PEP 723 `dependencies` 宣告非空——宣告
   寫了卻不會被任何工具讀取生效，屬「看起來有隔離、實際沒有」的表面現象。
2. **隱性依賴**：shebang 非 uv 且無 PEP 723 宣告（或宣告為空），但程式碼
   實際 `import` 非 stdlib 套件——比危險宣告更隱蔽，因為連可疑的 PEP 723
   區塊都不存在，肉眼審查容易略過，完全依賴 ambient 環境是否剛好裝了該
   套件；ambient 環境一旦缺套件，hook 的核心邏輯會靜默失效或崩潰。
3. **宣告不完整**：shebang 為 uv 且有 PEP 723 宣告，但宣告的 dependencies
   未涵蓋程式碼實際 import 的套件——聲稱隔離但隔離環境本身不完整。

三態刻意保留區分（不可壓成二分）：「無 PEP 723 且無外部 import」是完全
無風險的合法狀態（純 stdlib 用法本就不需要任何隔離宣告），與「無 PEP 723
但確實 import 外部套件」的真實風險狀態必須分開判定，否則會對純 stdlib
hook 誤報。

偵測手段：
- shebang：讀檔案第一行是否含 `uv run`
- PEP 723 宣告：擷取 `# /// script ... # ///` 區塊，正則抓
  `dependencies = [...]` 列表內容
- 實際 import：以 `ast.parse` 解析整份原始碼（含函式內、try/except 內的
  巢狀 import，非僅模組頂層陳述式），收集所有非相對 import 的頂層模組名，
  排除 stdlib（`sys.stdlib_module_names`，3.9 環境無此屬性時退化為內建
  常見清單）與本專案共用套件 `lib`（透過 `sys.path.insert` 動態掛載，非
  PyPI 依賴）

Hook Type: SessionStart（全量盤點，warning-only）+ PostToolUse（Edit /
Write / MultiEdit，目標為 `.claude/settings.json` 或 `.claude/hooks/**/*.py`
或 `.claude/skills/*/hooks/*.py` 時即時觸發同一檢查，防止未來新增違規）

阻擋策略：僅警告，不阻擋（exit 0 恆定）。理由：本檢查的「隱性依賴」與
「宣告不完整」判定依賴 AST 靜態掃描這一啟發式手段，無法涵蓋動態 import
（`importlib.import_module(name)`）等邊界情境，假陽性風險高於
frontmatter-yaml-syntax-guard（該檢查是確定性的 YAML 語法解析，近零假
陽性）；PEP 723 名稱—匯入名稱對照表（如 pyyaml -> yaml）亦僅涵蓋已知
案例，非完整 PyPI 名稱解析。採 warning-only 沿用 hook-completeness-check
同款「存量漂移盤點」慣例，把判斷留給人工複核。

Exit Codes:
    0 - 恆定（本 hook 僅警告，不阻擋任何操作；hook 自身異常 fail-open）
"""

from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path
from typing import List, Optional, Set

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from lib import setup_hook_logging, run_hook_safely, read_json_from_stdin, get_project_root
except ImportError as e:
    # hook 自身失敗雙通道（quality-baseline 規則 4）：import 失敗時尚無
    # logger 可用，僅能靠 stderr 讓用戶可見；fail-open（exit 0）避免因
    # 本 hook 壞掉而連帶擋住 SessionStart / Edit / Write。
    print(f"[Hook Import Error] {Path(__file__).name}: {e}", file=sys.stderr)
    sys.exit(0)


HOOK_NAME = "hook-dependency-isolation-check"

# 登記路徑判別（settings.json command 字串前綴）
_REGISTERED_HOOK_PATH_RE = re.compile(
    r"\.claude/(?:hooks|skills/[A-Za-z0-9_-]+/hooks)/[A-Za-z0-9_.-]+\.py"
)

# PEP 723 inline metadata 區塊
_PEP723_BLOCK_RE = re.compile(r"^# /// script\s*\n(.*?)^# ///\s*$", re.MULTILINE | re.DOTALL)
_DEPENDENCIES_RE = re.compile(r"dependencies\s*=\s*\[(.*?)\]", re.DOTALL)
_DEP_ITEM_RE = re.compile(r"[\"']([^\"']+)[\"']")

# PyPI 套件名稱 -> import 名稱對照（僅涵蓋本專案已知案例，非完整解析）
_PACKAGE_TO_IMPORT_NAME = {
    "pyyaml": "yaml",
}

# 本地模組索引排除目錄（非原始碼、體積大、會拖慢掃描且不含真實依賴訊號）
_LOCAL_INDEX_EXCLUDE_DIR_NAMES = frozenset(
    {".venv", "__pycache__", "node_modules", "build", ".git", ".dart_tool"}
)

# Python 3.9 無 sys.stdlib_module_names 時的退化清單（涵蓋本專案 hook
# 常見用法；非完整 stdlib 清單，僅供 3.9 相容退化路徑使用）
_STDLIB_FALLBACK = frozenset(
    {
        "os", "sys", "re", "json", "io", "time", "datetime", "pathlib",
        "typing", "subprocess", "collections", "itertools", "functools",
        "dataclasses", "enum", "logging", "tempfile", "shutil", "hashlib",
        "csv", "argparse", "textwrap", "traceback", "unittest", "inspect",
        "ast", "copy", "abc", "contextlib", "string", "random", "math",
        "socket", "threading", "queue", "signal", "glob", "fnmatch",
        "uuid", "base64", "struct", "warnings", "importlib", "types",
        "operator", "heapq", "bisect", "array", "weakref", "gc",
        "platform", "getpass", "stat", "errno", "urllib", "http",
        "xml", "html", "sqlite3", "zlib", "gzip", "tarfile", "zipfile",
        "configparser", "shlex", "pickle", "copyreg", "numbers",
        "decimal", "fractions", "statistics", "difflib", "pprint",
        "reprlib", "keyword", "token", "tokenize", "dis", "symtable",
        "traceback", "faulthandler", "pdb", "profile", "timeit",
        "concurrent", "multiprocessing", "asyncio", "select", "selectors",
        "ssl", "email", "mimetypes", "webbrowser", "cgi", "wsgiref",
        "ipaddress", "locale", "gettext", "codecs", "unicodedata",
    }
)


class HookConsistencyIssue:
    """單一檔案的一筆一致性檢查結果。"""

    def __init__(self, file_path: str, kind: str, detail: str):
        self.file_path = file_path
        self.kind = kind
        self.detail = detail


def _get_stdlib_module_names() -> "Set[str]":
    """回傳 stdlib 模組名稱集合（優先用 sys.stdlib_module_names，3.9 相容退化）。"""
    names = getattr(sys, "stdlib_module_names", None)
    if names is not None:
        return set(names)
    return set(_STDLIB_FALLBACK)


def extract_registered_hook_paths(settings_path: Path) -> "List[str]":
    """從 settings.json 抽取所有登記的 hook 檔案相對路徑（去重排序）。"""
    try:
        raw = settings_path.read_text(encoding="utf-8")
    except OSError:
        return []
    hits = set(_REGISTERED_HOOK_PATH_RE.findall(raw))
    return sorted(hits)


def build_local_module_index(claude_dir: Path) -> "Set[str]":
    """走訪 .claude/ 樹一次，建立本地模組/套件名稱索引。

    本專案 hook 慣用 `sys.path.insert(0, <目錄>)` 掛載內部套件（`lib`、
    `ticket_system`、`doc_system`、`acceptance_checkers` 等），而非透過
    PyPI 安裝。靜態解析每個 hook 檔案各自的 sys.path.insert 運算式（往往
    是 `Path(__file__).resolve().parents[N]` 等動態運算式）成本高且脆弱；
    改以「掃過 .claude/ 樹一次，收集所有 .py 檔案 stem 與含 __init__.py
    的目錄名稱」建立全域索引，用集合成員判定取代逐檔路徑推導——任何
    import 名稱若能在此索引找到同名本地模組/套件，即視為本地掛載而非
    外部 PyPI 依賴。

    改用 `os.walk` 並在走訪當下修剪 `dirnames`（而非 `Path.rglob` 後過濾
    結果），避免深入每個 skill 各自的 `.venv/`（內含完整 site-packages，
    數萬檔案）——`rglob` 先枚舉全部路徑才過濾，仍會付出完整遍歷成本；
    `os.walk` 的 `dirnames[:] = [...]` 慣用法在下探前剔除，實測將掃描
    時間從 80 秒級降至次秒級（見 ticket Test Results 效能量測）。
    """
    names: Set[str] = set()
    for dirpath, dirnames, filenames in os.walk(claude_dir):
        dirnames[:] = [d for d in dirnames if d not in _LOCAL_INDEX_EXCLUDE_DIR_NAMES]
        for filename in filenames:
            if filename.endswith(".py"):
                names.add(filename[: -len(".py")])
        if "__init__.py" in filenames:
            names.add(Path(dirpath).name)
    return names


def extract_pep723_dependencies(content: str) -> "Optional[List[str]]":
    """擷取 PEP 723 dependencies 列表；無 PEP 723 區塊回傳 None，區塊存在但
    無 dependencies 欄位或為空清單回傳 []。
    """
    block_match = _PEP723_BLOCK_RE.search(content)
    if block_match is None:
        return None
    dep_match = _DEPENDENCIES_RE.search(block_match.group(1))
    if dep_match is None:
        return []
    return _DEP_ITEM_RE.findall(dep_match.group(1))


def extract_external_imports(
    content: str, stdlib_names: "Set[str]", local_names: "Set[str]"
) -> "Set[str]":
    """以 AST 解析原始碼，回傳非 stdlib、非本地模組的頂層匯入模組名稱集合。

    刻意不限制掃描範圍於模組頂層陳述式——`ast.walk` 會走訪函式內、
    try/except 內的巢狀 import，這類寫法在本專案的既有 hook 中已有實例
    （如以 try/except ImportError 包裹的降級式匯入），仍代表真實的
    runtime 依賴需求，不應因巢狀而被漏判。
    """
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return set()

    external: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top not in stdlib_names and top not in local_names:
                    external.add(top)
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue  # 相對匯入，必為本地模組
            if node.module is None:
                continue
            top = node.module.split(".")[0]
            if top not in stdlib_names and top not in local_names:
                external.add(top)
    return external


def _normalize_declared(deps: "List[str]") -> "Set[str]":
    """把宣告的 PyPI 套件名稱換算為對應 import 名稱集合（供覆蓋率比對）。"""
    normalized = set()
    for dep in deps:
        # 去除版本限定符（如 "pyyaml>=6.0"），僅取套件名稱本體
        name = re.split(r"[<>=!~\[]", dep, maxsplit=1)[0].strip().lower()
        normalized.add(_PACKAGE_TO_IMPORT_NAME.get(name, name))
    return normalized


def check_file_consistency(
    rel_path: str,
    project_root: Path,
    stdlib_names: "Set[str]",
    local_names: "Set[str]",
) -> "List[HookConsistencyIssue]":
    """對單一登記路徑的 hook 檔案執行一致性檢查，回傳發現的問題清單。"""
    file_path = project_root / rel_path
    if not file_path.exists():
        return []  # 登記路徑但檔案不存在，非本 hook 職責範圍（見 how.strategy 產生路徑盤點表）

    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    shebang = content.splitlines()[0] if content else ""
    uses_uv = "uv run" in shebang
    declared_deps = extract_pep723_dependencies(content)
    external_imports = extract_external_imports(content, stdlib_names, local_names)

    issues: List[HookConsistencyIssue] = []

    if not uses_uv and declared_deps:
        issues.append(
            HookConsistencyIssue(
                rel_path,
                "declared_but_unused",
                "shebang 非 uv run --script，但 PEP 723 dependencies 宣告 {} "
                "不會被任何工具讀取生效".format(declared_deps),
            )
        )

    covered = _normalize_declared(declared_deps or []) if uses_uv else set()
    uncovered = external_imports if not uses_uv else (external_imports - covered)
    if uncovered:
        issues.append(
            HookConsistencyIssue(
                rel_path,
                "undeclared_or_uncovered_import",
                "實際 import 非 stdlib 套件 {} 但未經 uv + PEP 723 隔離涵蓋"
                "（{}）".format(
                    sorted(uncovered),
                    "無 PEP 723 宣告" if declared_deps is None else "宣告未涵蓋此套件",
                ),
            )
        )

    return issues


def scan_all(project_root: Path, logger) -> "List[HookConsistencyIssue]":
    """對 settings.json 登記的所有 hook 檔案執行全量掃描。"""
    settings_path = project_root / ".claude" / "settings.json"
    rel_paths = extract_registered_hook_paths(settings_path)
    stdlib_names = _get_stdlib_module_names()
    local_names = build_local_module_index(project_root / ".claude")

    all_issues: List[HookConsistencyIssue] = []
    for rel_path in rel_paths:
        issues = check_file_consistency(rel_path, project_root, stdlib_names, local_names)
        all_issues.extend(issues)

    logger.debug(
        f"{HOOK_NAME} 掃描完成：{len(rel_paths)} 檔已登記，{len(all_issues)} 筆問題"
    )
    return all_issues


def build_report(issues: "List[HookConsistencyIssue]") -> str:
    """組合警告訊息（SessionStart / PostToolUse 共用格式）。"""
    lines = [
        f"[{HOOK_NAME}] WARNING：偵測到 {len(issues)} 筆 hook 依賴隔離宣告不一致",
    ]
    for issue in issues:
        lines.append(f"  - [{issue.kind}] {issue.file_path}: {issue.detail}")
    lines.append(
        "修法：宣告非空依賴時 shebang 須為 `#!/usr/bin/env -S uv run --quiet "
        "--script`；純 stdlib 用法可保留 python3 shebang 且不需 PEP 723 區塊。"
    )
    return "\n".join(lines) + "\n"


# ============================================================================
# PostToolUse 觸發範圍判定
# ============================================================================

_SETTINGS_JSON_SUFFIX = ".claude/settings.json"
_HOOK_PY_TRIGGER_RE = re.compile(
    r"\.claude/(?:hooks|skills/[A-Za-z0-9_-]+/hooks)/[A-Za-z0-9_.-]+\.py$"
)


def is_relevant_edit_target(file_path: str) -> bool:
    """判斷 PostToolUse 的編輯目標是否需要觸發本檢查。"""
    if not file_path:
        return False
    normalized = file_path.replace("\\", "/")
    if normalized.endswith(_SETTINGS_JSON_SUFFIX):
        return True
    return bool(_HOOK_PY_TRIGGER_RE.search(normalized))


# ============================================================================
# 主入口
# ============================================================================

def main() -> int:
    logger = setup_hook_logging(HOOK_NAME)

    input_data = read_json_from_stdin(logger)
    if input_data is None:
        logger.info("stdin 無 JSON 輸入，跳過")
        return 0

    project_root = get_project_root()

    # SessionStart：全量盤點（無 tool_name 欄位，與 PostToolUse 分流）
    if input_data.get("hook_event_name") == "SessionStart":
        issues = scan_all(project_root, logger)
        if not issues:
            logger.info(f"{HOOK_NAME} SessionStart 全量盤點：0 筆問題")
            return 0
        report = build_report(issues)
        sys.stderr.write(report)
        logger.warning(f"{HOOK_NAME} SessionStart 全量盤點發現 {len(issues)} 筆問題")
        return 0

    tool_name = input_data.get("tool_name", "")
    if tool_name not in ("Edit", "Write", "MultiEdit"):
        logger.debug(f"工具 {tool_name} 不在本 hook 檢查範圍，跳過")
        return 0

    tool_input = input_data.get("tool_input") or {}
    file_path = tool_input.get("file_path", "")
    if not is_relevant_edit_target(file_path):
        logger.debug(f"非本 hook 觸發範圍，跳過: {file_path}")
        return 0

    issues = scan_all(project_root, logger)
    if not issues:
        logger.debug(f"{HOOK_NAME} PostToolUse 觸發（{file_path}）：0 筆問題")
        return 0

    report = build_report(issues)
    sys.stderr.write(report)
    logger.warning(
        f"{HOOK_NAME} PostToolUse 觸發（{file_path}）發現 {len(issues)} 筆問題"
    )
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
