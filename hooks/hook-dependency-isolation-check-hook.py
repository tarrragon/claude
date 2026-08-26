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
- uses_uv 判定：實際決定隔離是否生效的是 settings.json 登記的呼叫方式，
  非檔案自身 shebang——`uv run <path>` 直接呼叫時 uv 讀的是目標檔的 PEP
  723 metadata，與 shebang 無關；`python3 <path>` 等明確直譯器呼叫時
  shebang 同樣完全不被讀取。故優先讀 settings.json 登記路徑對應的呼叫
  前綴，僅當登記為裸路徑（無直譯器前綴，OS 依可執行位元直接 exec）時才
  回退讀檔案第一行是否含 `uv run`（見 `_resolve_uses_uv`）
- PEP 723 宣告：擷取 `# /// script ... # ///` 區塊，正則抓
  `dependencies = [...]` 列表內容
- 實際 import：以 `ast.parse` 解析整份原始碼（含函式內、try/except 內的
  巢狀 import，非僅模組頂層陳述式），收集所有非相對 import 的頂層模組名，
  排除 stdlib（`sys.stdlib_module_names`，3.9 環境無此屬性時退化為內建
  常見清單）與本專案共用套件 `lib`（透過 `sys.path.insert` 動態掛載，非
  PyPI 依賴）
- lib 遞移依賴：`lib` 本身被排除於外部依賴判定之外的理由僅對 `lib` 這個
  套件名稱本身成立，不代表其內部模組不需要第三方套件（如 `hook_ticket`
  需要 `pyyaml`）。故另建 `LibDependencyIndex` 走訪 `.claude/lib/*.py`，
  解析各子模組自身的第三方 import、彼此的內部依賴圖（遞迴解析並防循環）
  與頂層符號定義索引；hook 對 `lib` 的三種匯入形態（`from lib.X import`
  /`import lib.X` 直接定位子模組、`from lib import X` 經符號索引定位 X
  的歸屬模組、`import lib` 併入 `__init__.py` 頂層即時匯入的子模組足跡）
  各自解析出實際觸及的子模組，再併入該 hook 的外部依賴比對基準

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
from typing import Dict, List, Optional, Set

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

# settings.json 單一 command 欄位值抽取（供解析路徑前的直譯器宣告）
_COMMAND_VALUE_RE = re.compile(r'"command":\s*"([^"]*)"')

# 路徑前綴中的專案根目錄變數參照（本身不是直譯器宣告，需剝除才能判斷是否
# 為裸路徑呼叫）：`uv run --quiet $CLAUDE_PROJECT_DIR/...` 剝除後餘
# "uv run --quiet"；`$CLAUDE_PROJECT_DIR/...`（無直譯器）剝除後餘空字串
_PATH_VAR_SUFFIX_RE = re.compile(r"\$\{?CLAUDE_PROJECT_DIR\}?/?\s*$")

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


def extract_hook_command_prefixes(settings_path: Path) -> "Dict[str, Set[str]]":
    """從 settings.json 抽取每個登記路徑對應的呼叫前綴集合。

    「前綴」指 command 字串中路徑之前的直譯器宣告部分（如 `"uv run
    --quiet"`），空字串表示裸路徑呼叫（無直譯器前綴，由 OS 依可執行位元
    讀 shebang 決定直譯器）。同一路徑可能被多個 hook event 重複登記，故
    值為集合而非單一字串；供 `_resolve_uses_uv` 判定隔離是否實際生效。
    """
    try:
        raw = settings_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    prefixes: Dict[str, Set[str]] = {}
    for command in _COMMAND_VALUE_RE.findall(raw):
        match = _REGISTERED_HOOK_PATH_RE.search(command)
        if not match:
            continue
        rel_path = match.group(0)
        prefix = _PATH_VAR_SUFFIX_RE.sub("", command[: match.start()]).strip()
        prefixes.setdefault(rel_path, set()).add(prefix)
    return prefixes


def _resolve_uses_uv(shebang: str, command_prefixes: "Optional[Set[str]]") -> bool:
    """判定 PEP 723 隔離是否實際生效。

    決定隔離與否的是「runtime 實際如何呼叫這個檔案」，不是檔案自身
    shebang——settings.json 以 `uv run <path>` 直接呼叫時，uv 讀的是目標
    檔的 PEP 723 metadata 建立隔離環境，與檔案自身 shebang 完全無關（shell
    執行的是 `uv` 這個執行檔、`<path>` 只是傳給它的參數，shebang 只在 OS
    依可執行位元直接 exec 該檔案時才會被讀取，此處不成立）；反之以
    `python3 <path>` 等明確直譯器呼叫時，shebang 同樣完全不被讀取，即使
    宣告 `uv run --script` 也不生效。故判準優先序：

    1. 任一登記呼叫前綴以 `uv run` 開頭 -> 隔離確定生效
    2. 任一登記呼叫前綴為空字串（裸路徑） -> 該路徑實際依賴檔案自身
       shebang，回退讀 shebang
    3. 全部登記呼叫前綴皆為其他明確直譯器 -> 隔離確定不生效，shebang
       在此完全不被讀取，不可用來反駁

    無登記資訊時（如既有測試未提供 `command_prefixes`）維持既有純 shebang
    判定，向後相容。
    """
    if not command_prefixes:
        return "uv run" in shebang
    if any(prefix.startswith("uv run") for prefix in command_prefixes):
        return True
    if any(prefix == "" for prefix in command_prefixes):
        return "uv run" in shebang
    return False


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


class LibDependencyIndex:
    """`.claude/lib/` 套件依賴解析索引，供 hook 間接依賴比對使用。

    `lib/__init__.py` 以顯式具名匯入與 `__getattr__` 惰性匯入兩種方式重新
    匯出子模組符號；本索引不解析 `__init__.py` 的重新匯出機制本身，改為
    直接掃描各子模組頂層定義的符號歸屬（symbol_index），對 `from lib
    import X` 具名匯入具通用鑑別力，不因重新匯出手法（即時或惰性）而失準。
    """

    def __init__(
        self,
        direct_external: "Dict[str, Set[str]]",
        internal_graph: "Dict[str, Set[str]]",
        symbol_index: "Dict[str, Set[str]]",
        eager_footprint: "Set[str]",
    ):
        self.direct_external = direct_external
        self.internal_graph = internal_graph
        self.symbol_index = symbol_index
        self.eager_footprint = eager_footprint

    @property
    def module_stems(self) -> "Set[str]":
        return set(self.direct_external.keys())


def _extract_top_level_symbols(tree: "ast.Module") -> "Set[str]":
    """收集模組頂層定義的符號名稱（函式、類別、變數賦值）。"""
    symbols: Set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    symbols.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            symbols.add(node.target.id)
    return symbols


def _extract_lib_internal_targets(tree: "ast.Module", lib_module_stems: "Set[str]") -> "Set[str]":
    """收集模組對其他 lib 子模組的內部依賴（相對匯入與 `lib.X` 絕對匯入皆算）。"""
    targets: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                if node.module:
                    top = node.module.split(".")[0]
                    if top in lib_module_stems:
                        targets.add(top)
                else:
                    for alias in node.names:
                        if alias.name in lib_module_stems:
                            targets.add(alias.name)
            elif node.module and node.module.split(".", 1)[0] == "lib":
                parts = node.module.split(".")
                if len(parts) > 1 and parts[1] in lib_module_stems:
                    targets.add(parts[1])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if parts[0] == "lib" and len(parts) > 1 and parts[1] in lib_module_stems:
                    targets.add(parts[1])
    return targets


def _resolve_module_external_deps(
    module_name: str,
    direct_external: "Dict[str, Set[str]]",
    internal_graph: "Dict[str, Set[str]]",
    visited: "Optional[Set[str]]" = None,
) -> "Set[str]":
    """遞迴解析單一 lib 子模組的完整第三方依賴足跡（含透過內部匯入串連的
    間接依賴）。`visited` 防止子模組間相互匯入造成無限遞迴。
    """
    if visited is None:
        visited = set()
    if module_name in visited:
        return set()
    visited.add(module_name)

    result = set(direct_external.get(module_name, set()))
    for dep in internal_graph.get(module_name, set()):
        result |= _resolve_module_external_deps(dep, direct_external, internal_graph, visited)
    return result


def _resolve_init_eager_footprint(
    lib_dir: Path,
    module_stems: "Set[str]",
    direct_external: "Dict[str, Set[str]]",
    internal_graph: "Dict[str, Set[str]]",
) -> "Set[str]":
    """解析 `lib/__init__.py` 頂層（非函式內）即時匯入的子模組，回傳其遞移
    第三方依賴聯集，供 `import lib`（整個套件、無具名符號）情境使用。
    刻意只掃 `tree.body`（模組頂層陳述式），不用 `ast.walk`——`__getattr__`
    等惰性載入邏輯位於函式主體內，只有真正在套件載入當下執行的匯入才計入。
    """
    init_file = lib_dir / "__init__.py"
    if not init_file.is_file():
        return set()
    try:
        tree = ast.parse(init_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return set()

    eager_targets: Set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.level and node.level > 0:
            if node.module:
                top = node.module.split(".")[0]
                if top in module_stems:
                    eager_targets.add(top)
            else:
                for alias in node.names:
                    if alias.name in module_stems:
                        eager_targets.add(alias.name)

    footprint: Set[str] = set()
    for target in eager_targets:
        footprint |= _resolve_module_external_deps(target, direct_external, internal_graph)
    return footprint


def build_lib_dependency_index(lib_dir: Path, stdlib_names: "Set[str]") -> "LibDependencyIndex":
    """走訪 `.claude/lib/*.py`，建立子模組間依賴圖與符號索引。

    用於解析 hook 經由 `lib` 套件間接觸及的第三方 import。lib 模組體積小
    （數十檔），無需比照 `build_local_module_index` 的 `os.walk` 剪枝優化。
    """
    module_stems = {p.stem for p in lib_dir.glob("*.py")} if lib_dir.is_dir() else set()
    direct_external: Dict[str, Set[str]] = {}
    internal_graph: Dict[str, Set[str]] = {}
    symbol_index: Dict[str, Set[str]] = {}

    if lib_dir.is_dir():
        for py_file in sorted(lib_dir.glob("*.py")):
            if py_file.name == "__init__.py":
                continue
            module_name = py_file.stem
            try:
                content = py_file.read_text(encoding="utf-8")
                tree = ast.parse(content)
            except (OSError, UnicodeDecodeError, SyntaxError):
                direct_external[module_name] = set()
                internal_graph[module_name] = set()
                continue
            direct_external[module_name] = extract_external_imports(
                content, stdlib_names, module_stems | {"lib"}
            )
            internal_graph[module_name] = _extract_lib_internal_targets(
                tree, module_stems
            ) - {module_name}
            for symbol in _extract_top_level_symbols(tree):
                symbol_index.setdefault(symbol, set()).add(module_name)

    eager_footprint = _resolve_init_eager_footprint(
        lib_dir, module_stems, direct_external, internal_graph
    )
    return LibDependencyIndex(direct_external, internal_graph, symbol_index, eager_footprint)


def resolve_lib_transitive_imports(content: str, lib_index: "LibDependencyIndex") -> "Set[str]":
    """解析 hook 原始碼中經由 `lib` 套件間接觸及的第三方依賴集合。

    涵蓋三種匯入形態：`from lib.X import ...` / `import lib.X`（直接定位子
    模組）、`from lib import X`（透過符號索引定位 X 實際定義的子模組）、
    `import lib`（整個套件，併入 `__init__.py` 頂層即時匯入的子模組足跡）。
    找不到對應子模組或符號時不納入計算——寧可少報也不對未知情境臆測。
    """
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return set()

    targets: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue  # 相對匯入，非本 hook 對 lib 的匯入形態
            if node.module == "lib":
                for alias in node.names:
                    for owner in lib_index.symbol_index.get(alias.name, ()):
                        targets |= _resolve_module_external_deps(
                            owner, lib_index.direct_external, lib_index.internal_graph
                        )
            elif node.module and node.module.split(".", 1)[0] == "lib":
                parts = node.module.split(".")
                if len(parts) > 1 and parts[1] in lib_index.module_stems:
                    targets |= _resolve_module_external_deps(
                        parts[1], lib_index.direct_external, lib_index.internal_graph
                    )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if not parts or parts[0] != "lib":
                    continue
                if len(parts) > 1 and parts[1] in lib_index.module_stems:
                    targets |= _resolve_module_external_deps(
                        parts[1], lib_index.direct_external, lib_index.internal_graph
                    )
                elif len(parts) == 1:
                    targets |= lib_index.eager_footprint
    return targets


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
    lib_index: "Optional[LibDependencyIndex]" = None,
    command_prefixes: "Optional[Set[str]]" = None,
) -> "List[HookConsistencyIssue]":
    """對單一登記路徑的 hook 檔案執行一致性檢查，回傳發現的問題清單。

    `lib_index` 由呼叫端（`scan_all`）建立一次後重複傳入，避免每個 hook
    各自重新走訪 `.claude/lib/`；省略時（如既有測試直接呼叫）就地建立。
    `command_prefixes` 為該路徑在 settings.json 的呼叫前綴集合，決定隔離
    是否實際生效優先於檔案自身 shebang（見 `_resolve_uses_uv`）；省略時
    退化為既有純 shebang 判定。
    """
    file_path = project_root / rel_path
    if not file_path.exists():
        return []  # 登記路徑但檔案不存在，非本 hook 職責範圍（見 how.strategy 產生路徑盤點表）

    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    if lib_index is None:
        lib_index = build_lib_dependency_index(project_root / ".claude" / "lib", stdlib_names)

    shebang = content.splitlines()[0] if content else ""
    uses_uv = _resolve_uses_uv(shebang, command_prefixes)
    declared_deps = extract_pep723_dependencies(content)
    external_imports = extract_external_imports(content, stdlib_names, local_names)
    external_imports |= resolve_lib_transitive_imports(content, lib_index)

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
    lib_index = build_lib_dependency_index(project_root / ".claude" / "lib", stdlib_names)
    command_prefixes = extract_hook_command_prefixes(settings_path)

    all_issues: List[HookConsistencyIssue] = []
    for rel_path in rel_paths:
        issues = check_file_consistency(
            rel_path,
            project_root,
            stdlib_names,
            local_names,
            lib_index,
            command_prefixes.get(rel_path),
        )
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
