"""
合併前全套件閘門

掛在 merge_cas.merge_branch_cas 的 pre_merge_check 掛點：commit-tree 之後、
update-ref 之前，在「合併 commit 的 detached worktree 快照」內，經 run-with-timeout
（取得 heavy 名額）跑全套件；紅燈即回報不通過，ref 不變。

為何在快照內跑：共用 checkout 的工作區含其他 session 未提交的修改，測試會直接載入，
結果無法對應到單一 commit。測合併 commit 而非分支 HEAD：測到的即是將寫入 main 的樹。

CAS 重試：每次重試依新 HEAD 產生不同的合併 commit。上次驗過的 commit 與新 commit 的
差異依套件選擇規則判定：不觸及某套件範圍（豁免清單內的檔案本就不計）者沿用該套件的驗證結果，
只重跑受影響的套件；驗證狀態以套件為單位記錄（verified_suites），重跑或沿用後都可再被下一次重試沿用。

名額：合併序列（commit-tree、快照全套件、update-ref）整段持有 heavy 名額，由 MergeGate.hold 在
merge_branch_cas 產生合併 commit 之前取得、update-ref 完成或中止後釋放；窗口因此只剩實際測試時間，
不含排隊。持有期間以環境標記（slot_gate.export_hold）讓快照內經 run-with-timeout 的套件免重複取得。

套件執行器可注入（SuiteRunner），單元測試不真的跑 hooks 或 flutter 全套件。
"""

import os
import re
import shutil
import statistics
import signal
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # .claude/，供 import lib
from lib import slot_gate  # noqa: E402

try:
    from .merge_cas import CheckResult
except ImportError:
    # Fallback when running with scripts/ on sys.path (test 與直接執行情境)
    from merge_cas import CheckResult

# 閘門允許的 CAS 重試次數（不含首次嘗試）；超過即中止並回報最後一次失敗原因
GATE_MAX_RETRIES = 3
# 單一套件的逾時秒數（不含排隊時間，排隊由 run-with-timeout 的名額閘門處理）
SUITE_TIMEOUT_SECONDS = 3600
# 快照目錄（位於 .claude/worktrees/，已被 gitignore）
SNAPSHOT_DIR = ".claude/worktrees"
SNAPSHOT_PREFIX = "merge-gate-"
_GIT_TIMEOUT_SECONDS = 120
_FAILED_ITEMS_MAX = 20
UNMAPPED_SHOW_MAX = 10
_OUTPUT_TAIL_LINES = 15

SUITE_FLUTTER = "flutter"
SUITE_HOOKS = "hooks"
SUITE_SCRIPTS = "scripts"
SUITE_SKILL_PREFIX = "skill:"

# 全套件命令（argv）；相對於快照根目錄執行
SUITE_COMMANDS = {
    SUITE_FLUTTER: ["fvm", "flutter", "test"],
    SUITE_HOOKS: ["uv", "--directory", ".claude/hooks", "run", "pytest"],
    SUITE_SCRIPTS: ["uv", "--directory", ".claude/scripts", "run", "pytest"],
}

# 範圍判準：路徑前綴或精確檔名命中即需對應套件。見 SKILL.md〈合併前全套件〉
FLUTTER_SCOPE_PREFIXES = ("lib/", "test/", "integration_test/", "macos/", "docs/", "assets/")
FLUTTER_SCOPE_FILES = ("pubspec.yaml", "pubspec.lock", "l10n.yaml", "analysis_options.yaml")

# 快照內執行前必須就緒的 gitignored 生成產物：套件 -> ((產物路徑, 生成命令), ...)
REQUIRED_ARTIFACTS = {
    SUITE_FLUTTER: ((".dart_tool/package_config.json", ["fvm", "flutter", "pub", "get"]),),
    SUITE_HOOKS: (),
    SUITE_SCRIPTS: (),
}

# 專案宣告：取代內建 Flutter 對應；位於根層 project-integration/，sync 雙向排除。見 SKILL.md〈合併前全套件〉
DECLARATION_PATH = ".claude/project-integration/merge-gate.yaml"
_RESERVED_SUITES = (SUITE_HOOKS, SUITE_SCRIPTS)


class DeclarationError(ValueError):
    """宣告檔格式錯誤；訊息指名檔案與欄位。閘門 fail-closed：不退回內建對應。"""


# 宣告：套件名 -> {"prefixes": tuple, "files": tuple, "command": list, "artifacts": tuple[(path, generate)]}
Declaration = Optional[dict]


def _bad(field: str, why: str) -> DeclarationError:
    return DeclarationError(f"{DECLARATION_PATH}: {field} {why}")


def _str_list(value, field: str, required: bool = False) -> list:
    if value is None:
        value = []
    if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
        raise _bad(field, "必須是非空字串的清單")
    if required and not value:
        raise _bad(field, "不可為空")
    return value


def _parse_artifacts(raw, prefix: str) -> tuple:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise _bad(f"{prefix}.artifacts", "必須是清單")
    out = []
    for i, item in enumerate(raw):
        field = f"{prefix}.artifacts[{i}]"
        if not isinstance(item, dict):
            raise _bad(field, "必須是含 path 與 generate 的對應")
        path = item.get("path")
        if not isinstance(path, str) or not path:
            raise _bad(f"{field}.path", "必須是非空字串")
        out.append((path, _str_list(item.get("generate"), f"{field}.generate", required=True)))
    return tuple(out)


def _parse_suite(name, raw) -> dict:
    prefix = f"suites.{name}"
    if not isinstance(name, str) or name in _RESERVED_SUITES or name.startswith(SUITE_SKILL_PREFIX):
        raise _bad(prefix, "套件名不可為框架保留名（hooks、scripts、skill:*）")
    if not isinstance(raw, dict):
        raise _bad(prefix, "必須是對應")
    prefixes = _str_list(raw.get("prefixes"), f"{prefix}.prefixes")
    files = _str_list(raw.get("files"), f"{prefix}.files")
    if not prefixes and not files:
        raise _bad(f"{prefix}.prefixes", "與 files 至少須有一項")
    return {"prefixes": tuple(prefixes), "files": tuple(files),
            "command": _str_list(raw.get("command"), f"{prefix}.command", required=True),
            "artifacts": _parse_artifacts(raw.get("artifacts"), prefix)}


def parse_declaration(text: str) -> dict:
    # 延遲匯入：hook 以無 pyyaml 的 python3 載入本模組，只有宣告存在時才需要 yaml
    try:
        import yaml
    except ImportError as exc:
        raise DeclarationError(f"{DECLARATION_PATH}: 無法匯入 pyyaml，宣告無法解析：{exc}") from exc
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise DeclarationError(f"{DECLARATION_PATH}: YAML 無法解析：{exc}") from exc
    suites = doc.get("suites") if isinstance(doc, dict) else None
    if not isinstance(suites, dict):
        raise _bad("suites", "必須是套件名對應")
    return {name: _parse_suite(name, raw) for name, raw in suites.items()}


def load_declaration(root: str) -> Declaration:
    """從目錄（合併快照）讀宣告；檔案不存在回 None（沿用內建），格式錯誤拋 DeclarationError。"""
    path = Path(root) / DECLARATION_PATH
    if not path.is_file():
        return None
    return parse_declaration(_read_text(path))


def load_declaration_at(repo: str, ref: str) -> Declaration:
    """從 git ref（commit／分支）讀宣告，不需快照；供建立快照前的範圍判定。"""
    if _git(["cat-file", "-e", f"{ref}:{DECLARATION_PATH}"], repo).returncode != 0:
        return None
    proc = _git(["show", f"{ref}:{DECLARATION_PATH}"], repo)
    if proc.returncode != 0:
        raise DeclarationError(
            f"{DECLARATION_PATH}: 無法自 {ref[:12]} 讀取：{proc.stderr.decode('utf-8', 'replace').strip()}")
    return parse_declaration(proc.stdout.decode("utf-8", "replace"))


def _in_declared_scope(path: str, decl: dict) -> bool:
    return any(path.startswith(s["prefixes"]) or path in s["files"] for s in decl.values())


def declared_artifacts(suite: str, decl: Declaration) -> tuple:
    """套件快照內須就緒的產物：宣告優先，其餘沿用 REQUIRED_ARTIFACTS。"""
    if decl is not None and suite in decl:
        return decl[suite]["artifacts"]
    return REQUIRED_ARTIFACTS.get(suite, ())


# CAS 重試沿用驗證結果的豁免清單：測試不讀取這些檔，只改它們不影響全套件結果。
# 安全性由 test_merge_gate 的守衛測試維持（掃描測試目錄，出現讀取清單內實際檔案即紅）。
RETRY_REUSE_EXEMPT_GLOBS = (
    "docs/work-logs/**/tickets/*.md",
    "docs/work-logs/**/v*-main.md",
    "docs/work-logs/topic-assignments.txt",  # 每次建票都追加，並行時幾乎每次重試都會變
)

# (完整 argv, 工作目錄) -> (結束碼, 合併輸出)
SuiteRunner = Callable[[list, str], tuple]


def _glob_to_regex(glob: str) -> "re.Pattern":
    out, i = [], 0
    while i < len(glob):
        if glob.startswith("**/", i):
            out.append("(?:.+/)?")
            i += 3
        elif glob[i] == "*":
            out.append("[^/]*")
            i += 1
        else:
            out.append(re.escape(glob[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


_EXEMPT_PATTERNS = tuple(_glob_to_regex(g) for g in RETRY_REUSE_EXEMPT_GLOBS)


def is_reuse_exempt(path: str) -> bool:
    return any(p.match(path) for p in _EXEMPT_PATTERNS)


def _skill_name(path: str) -> Optional[str]:
    parts = path.split("/")
    return parts[2] if len(parts) > 3 and parts[:2] == [".claude", "skills"] else None


def _skill_has_tests(root: str, name: str) -> bool:
    return os.path.isdir(os.path.join(root, ".claude", "skills", name, "tests"))


_LIB_IMPORT = re.compile(r"^\s*(?:from|import)\s+lib(?:\.|\s|$)", re.MULTILINE)


def _skills_importing_lib(root: str) -> list:
    """掃描快照：帶 tests 目錄且有 .py 匯入 lib 的 skill 名稱（不寫死清單，新增 skill 不會漏）。"""
    base = Path(root) / ".claude" / "skills"
    found = []
    for skill in sorted(p for p in base.iterdir() if p.is_dir()) if base.is_dir() else []:
        if not (skill / "tests").is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(skill):
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
            if any(_LIB_IMPORT.search(_read_text(Path(dirpath) / n)) for n in filenames if n.endswith(".py")):
                found.append(skill.name)
                break
    return found


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""  # 掃描中途消失或不可讀：視為不匯入 lib，不影響其他檔


def _skill_top_modules(root: str, name: str) -> set:
    """skill 提供的頂層模組名：skill 根與其 scripts/ 下的 .py 模組、帶 __init__.py 的套件。

    hook 常以 sys.path.insert 指向 skill 根或 scripts/ 後匯入，所以兩處都算。
    """
    mods = set()
    for sub in ("", "scripts"):
        base = Path(root) / ".claude" / "skills" / name / sub
        if not base.is_dir():
            continue
        for entry in base.iterdir():
            if entry.is_dir() and (entry / "__init__.py").is_file() and entry.name != "tests":
                mods.add(entry.name)
            elif entry.suffix == ".py" and entry.stem != "__init__" and not entry.stem.startswith("test_"):
                mods.add(entry.stem)
    return mods


def _consumer_suites(root: str, skills: set) -> set:
    """hooks／scripts 的 .py 若匯入這些 skill 的頂層模組，或引用 `skills/<名稱>/` 路徑，回傳對應套件。

    匯入以行首 `from X`／`import X` 辨識，故 sys.path.insert 之後的匯入同樣涵蓋；路徑引用
    只計非測試檔（測試檔提到路徑多為斷言字串）。通用模組名（如 constants）可能多報，只會多跑套件。
    """
    suites = set()
    for suite, sub in ((SUITE_HOOKS, "hooks"), (SUITE_SCRIPTS, "scripts")):
        mods = {s: _skill_top_modules(root, s) for s in skills}
        for dirpath, dirnames, filenames in os.walk(Path(root) / ".claude" / sub):
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
            is_test = "tests" in Path(dirpath).parts
            for n in (n for n in filenames if n.endswith(".py")):
                text = _read_text(Path(dirpath) / n)
                if any(_imports_any(text, m) or (not is_test and f"skills/{s}/" in text)
                       for s, m in mods.items()):
                    suites.add(suite)
    return suites


def _imports_any(text: str, modules: set) -> bool:
    return bool(modules) and re.search(
        r"^\s*(?:from|import)\s+(?:%s)\b" % "|".join(re.escape(m) for m in sorted(modules)), text, re.MULTILINE
    ) is not None


def needs_gate(changed_paths: list, decl: Declaration = None) -> bool:
    """改動是否可能落在任何全套件範圍內（用於決定是否值得建立快照）。"""
    return any(_in_any_suite_scope(p, decl) for p in changed_paths if not is_reuse_exempt(p))


def _in_any_suite_scope(path: str, decl: Declaration = None) -> bool:
    """範圍判準唯一處：警告與 needs_gate 共用，宣告前綴與內建 Flutter 範圍都經此判定。"""
    if path.startswith(".claude/"):
        return True
    if decl is not None:
        return _in_declared_scope(path, decl)
    return path.startswith(FLUTTER_SCOPE_PREFIXES) or path in FLUTTER_SCOPE_FILES


def unmapped_paths(changed_paths: list, decl: Declaration = None) -> list:
    """既非豁免、也不屬任何套件範圍的路徑（如自帶測試的子專案）：閘門不會替它們跑任何測試。"""
    return [p for p in changed_paths if not is_reuse_exempt(p) and not _in_any_suite_scope(p, decl)]


def _warn_unmapped(paths: list, decl: Declaration = None) -> None:
    unmapped = unmapped_paths(paths, decl)
    if not unmapped:
        return
    shown = unmapped[:UNMAPPED_SHOW_MAX]
    more = f"，其餘 {len(unmapped) - len(shown)} 個略" if len(unmapped) > len(shown) else ""
    print(f"[合併前測試] WARNING：{len(unmapped)} 個改動路徑不對應任何全套件，閘門不會測它們："
          f"{', '.join(shown)}{more}")


def select_suites(changed_paths: list, root: str) -> list:
    """依改動路徑決定套件範圍（root 為合併 commit 的快照，供掃描 skill）。對應表見 SKILL.md。

    套件識別：flutter／hooks／scripts／skill:<名稱>。回傳順序固定，空清單表示免跑。
    """
    decl = load_declaration(root)
    paths = [p for p in changed_paths if not is_reuse_exempt(p)]
    want = set()
    touched_skills = {n for n in (_skill_name(p) for p in paths) if n}
    if decl is None:
        if any(p.startswith(FLUTTER_SCOPE_PREFIXES) or p in FLUTTER_SCOPE_FILES for p in paths):
            want.add(SUITE_FLUTTER)
    else:
        want.update(n for n, s in decl.items()
                    if any(p.startswith(s["prefixes"]) or p in s["files"] for p in paths))
    for p in (p for p in paths if p.startswith(".claude/")):
        skill = _skill_name(p)
        if skill and _skill_has_tests(root, skill):
            want.add(f"{SUITE_SKILL_PREFIX}{skill}")
        elif p.startswith(".claude/scripts/"):
            want.add(SUITE_SCRIPTS)
        elif p.startswith(".claude/lib/"):
            want.update({SUITE_HOOKS, SUITE_SCRIPTS})
            want.update(f"{SUITE_SKILL_PREFIX}{s}" for s in _skills_importing_lib(root))
        else:  # hooks、rules、settings、無 tests 的 skill 等：hook 測試會讀這些檔
            want.add(SUITE_HOOKS)
    if touched_skills:
        want |= _consumer_suites(root, touched_skills)  # hooks／scripts 匯入該 skill 時加跑
    declared = [n for n in (decl or {}) if n in want]  # 宣告順序在前，與內建 flutter 居首一致
    head = declared + [s for s in (SUITE_FLUTTER, SUITE_HOOKS, SUITE_SCRIPTS) if s in want and s not in declared]
    return head + sorted(s for s in want if s.startswith(SUITE_SKILL_PREFIX))


def suite_command(suite: str, root: str) -> list:
    """套件的執行命令；skill 有 pyproject 沿用 uv --directory，無則借 hooks 的環境跑其 tests 目錄。"""
    decl = load_declaration(root)
    if decl is not None and suite in decl:
        return decl[suite]["command"]
    if not suite.startswith(SUITE_SKILL_PREFIX):
        return SUITE_COMMANDS[suite]
    name = suite[len(SUITE_SKILL_PREFIX):]
    if os.path.isfile(os.path.join(root, ".claude", "skills", name, "pyproject.toml")):
        return ["uv", "--directory", f".claude/skills/{name}", "run", "pytest"]
    return ["uv", "--directory", ".claude/hooks", "run", "pytest", "-p", "no:cacheprovider", f"../skills/{name}/tests"]


def _git(args: list, repo: str):
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")}
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, env=env, timeout=_GIT_TIMEOUT_SECONDS)


def changed_paths_between(repo: str, old: str, new: str) -> Optional[list]:
    """兩個 commit 間改動的路徑；git 失敗回傳 None（呼叫端須視為需重跑）。"""
    proc = _git(["diff-tree", "-r", "-z", "--name-only", "--no-renames", old, new], repo)
    if proc.returncode != 0:
        return None
    return [p.decode("utf-8", "surrogateescape") for p in proc.stdout.split(b"\0") if p]


def _remove_snapshot(repo: str, path: str) -> None:
    """移除快照；git 移除失敗時退回直接刪目錄，最後 prune 清掉登記。"""
    try:
        _git(["worktree", "remove", "--force", path], repo)
    finally:
        if os.path.lexists(path):
            shutil.rmtree(path, ignore_errors=True)
        _git(["worktree", "prune"], repo)


@contextmanager
def merge_snapshot(repo: str, commit: str) -> Iterator[str]:
    """建立合併 commit 的 detached worktree 快照；離開（成功、例外、中斷）時一律移除。"""
    parent = Path(repo) / SNAPSHOT_DIR
    parent.mkdir(parents=True, exist_ok=True)
    path = str(parent / f"{SNAPSHOT_PREFIX}{commit[:12]}-{os.getpid()}")
    try:
        proc = _git(["worktree", "add", "--detach", path, commit], repo)
        if proc.returncode != 0:
            raise RuntimeError(f"建立快照失敗：{proc.stderr.decode('utf-8', 'replace').strip()}")
        yield path
    finally:
        _remove_snapshot(repo, path)


@contextmanager
def _sigterm_as_interrupt() -> Iterator[None]:
    """SIGTERM 轉為 KeyboardInterrupt，使 finally 有機會移除快照；非主執行緒不處理。"""
    if threading.current_thread() is not threading.main_thread():
        yield
        return

    def _raise(_signum, _frame):
        raise KeyboardInterrupt("收到 SIGTERM")

    previous = signal.signal(signal.SIGTERM, _raise)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous)


def wrapped_argv(command: list, timeout: int = SUITE_TIMEOUT_SECONDS) -> list:
    """全套件一律經 run-with-timeout（heavy 命令自動取得全機名額）。

    腳本取自本檔所在的樹而非主 checkout：持有者（本檔的 slot_gate）與子程序必須載入同一版
    slot_gate，否則子程序不認得持有標記，會等待持有者自己占用的名額。
    """
    script = str(Path(__file__).resolve().parents[3] / "scripts" / "run-with-timeout.py")
    return [sys.executable, script, str(timeout), "--", *command]


def default_runner(argv: list, cwd: str) -> tuple:
    """真實執行；回傳 (結束碼, stdout+stderr)。"""
    proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, errors="replace")
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _failed_items(output: str) -> list:
    """從 pytest／flutter 輸出摘出失敗項與其 E 行（assertion 訊息）；摘不到時回傳輸出尾段。"""
    lines = output.splitlines()
    items = [ln.strip() for ln in lines if ln.startswith("FAILED ") or "[E]" in ln]
    items += [ln.rstrip() for ln in lines if ln.startswith("E  ")]
    if not items:
        items = [ln for ln in lines[-_OUTPUT_TAIL_LINES:] if ln.strip()]
    return items[:_FAILED_ITEMS_MAX]


_FAILURE_DIR = ".claude/logs/merge-gate-failures"
_MEMORY_PROBE_TIMEOUT_SECONDS = 10
_PAGEOUTS_LINE = re.compile(r"^Pageouts:\s*(\d+)", re.MULTILINE)
_MEMORY_FREE_LINE = re.compile(r"^System-wide memory free percentage:.*$", re.MULTILINE)


def _probe(argv: list) -> str:
    """執行唯讀記憶體探針；取不到（非 macOS、命令缺、逾時）回空字串並寫 stderr，不影響閘門判定。"""
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, errors="replace",
                              timeout=_MEMORY_PROBE_TIMEOUT_SECONDS)
        return proc.stdout or ""
    except (OSError, subprocess.SubprocessError) as exc:
        sys.stderr.write(f"[WARNING] merge-gate 記憶體快照 {argv[0]} 取得失敗（fail-open）：{exc}\n")
        return ""


def memory_snapshot() -> str:
    """紅燈當下的 memory_pressure 摘要與 vm_stat pageouts 計數，供比對失敗時點是否落在換頁激增時段。"""
    pressure = _MEMORY_FREE_LINE.search(_probe(["memory_pressure"]))
    pageouts = _PAGEOUTS_LINE.search(_probe(["vm_stat"]))
    swap = _probe(["sysctl", "vm.swapusage"]).strip()
    return (f"memory_pressure: {pressure.group(0).strip() if pressure else '取不到'}\n"
            f"vm_stat pageouts: {pageouts.group(1) if pageouts else '取不到'}\n"
            f"swap: {swap or '取不到'}")


def save_failure_output(log_root: str, tag: str, suite: str, rc: int, output: str) -> str:
    """紅燈時把全輸出（附記憶體快照）寫入旁置檔，回傳路徑；寫入失敗回空字串（只警告）。"""
    if not log_root:
        sys.stderr.write("[WARNING] merge-gate 無 log_root，略過失敗細節旁置檔\n")
        return ""
    safe_suite = re.sub(r"[^A-Za-z0-9_.-]", "_", suite)
    path = Path(log_root) / _FAILURE_DIR / f"{tag[:12]}-{safe_suite}.log"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        header = (f"# suite={suite} exit={rc} time={time.strftime('%Y-%m-%dT%H:%M:%S')}\n"
                  f"{memory_snapshot()}\n---- 全輸出 ----\n")
        path.write_text(header + output, encoding="utf-8")
    except OSError as exc:
        sys.stderr.write(f"[WARNING] merge-gate 失敗細節旁置檔寫入失敗：{exc}\n")
        return ""
    return str(path)


def _rc_reason(suite: str, rc: int, output: str, detail_path: str = "") -> str:
    if rc == 124:
        return f"[{suite}] 全套件逾時（{SUITE_TIMEOUT_SECONDS} 秒）"
    if rc == 125:
        return f"[{suite}] 等待本機名額逾時，全套件未執行"
    reason = f"[{suite}] 全套件紅燈（exit {rc}），失敗項：\n  " + "\n  ".join(_failed_items(output))
    if detail_path:
        reason += f"\n  全輸出與記憶體快照：{detail_path}"
    return reason


def _ensure_artifacts(suite: str, snapshot: str, project_root: str, runner: SuiteRunner) -> str:
    """缺 gitignored 生成產物時先生成；生成失敗或仍缺則回傳指名缺漏的理由，否則空字串。"""
    for artifact, generator in declared_artifacts(suite, load_declaration(snapshot)):
        if os.path.exists(os.path.join(snapshot, artifact)):
            continue
        rc, out = runner(wrapped_argv(generator), snapshot)
        if rc != 0 or not os.path.exists(os.path.join(snapshot, artifact)):
            tail = out.strip().splitlines()[-3:]
            return (f"[{suite}] 快照缺生成產物 {artifact}，生成命令 {' '.join(generator)} 失敗"
                    f"（exit {rc}）：{' / '.join(tail)}")
    return ""


_SUMMARY_PATTERNS = (
    re.compile(r"\d+ (?:passed|failed|error)[^\n]*"),  # pytest 摘要行
    re.compile(r"[^\n]*All tests passed[^\n]*"),  # flutter 全綠
    re.compile(r"[^\n]*Some tests failed[^\n]*"),  # flutter 紅燈
)
_LOG_FILE = ".claude/logs/worktree-merge.log"


def summarize_output(output: str) -> str:
    """從輸出尾端取最後一個測試摘要行；取不到回傳「無摘要」。"""
    for line in reversed(output.strip().splitlines()):
        for pat in _SUMMARY_PATTERNS:
            m = pat.search(line)
            if m:
                return m.group(0).strip(" =")
    return "無摘要"


# 名額預估：各套件取日誌中最近 N 筆綠燈耗時的中位數；無資料用預設值（依 2026-10-15 實測，保守取偏高）
ESTIMATE_SAMPLE_COUNT = 5
_LOG_TAIL_BYTES = 256 * 1024  # 只讀日誌尾段，避免日誌長大後每次合併都全檔解析
_DEFAULT_SUITE_SECONDS = {SUITE_FLUTTER: 600.0, SUITE_HOOKS: 230.0, SUITE_SCRIPTS: 60.0, "skill:ticket": 580.0}
_DEFAULT_SKILL_SECONDS = 120.0
_GREEN_LINE = re.compile(r"\[合併前測試\] 套件 (\S+)：綠燈｜.*｜耗時 ([0-9.]+)s")


def default_suite_seconds(suite: str) -> float:
    return _DEFAULT_SUITE_SECONDS.get(suite, _DEFAULT_SKILL_SECONDS)


def _recent_green_seconds(log_root: str) -> dict:
    """worktree-merge.log 尾段中各套件的綠燈耗時（時間序）；日誌不存在或不可讀回空 dict。"""
    log = Path(log_root) / _LOG_FILE
    try:
        with open(log, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            fh.seek(max(fh.tell() - _LOG_TAIL_BYTES, 0))
            text = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return {}  # 無日誌：全部用預設值
    out: dict = {}
    for m in _GREEN_LINE.finditer(text):
        out.setdefault(m.group(1), []).append(float(m.group(2)))
    return out


def suite_estimate_seconds(suites: list, log_root: str) -> float:
    """各套件近期綠燈耗時中位數加總；某套件無歷史則用其預設值。"""
    history = _recent_green_seconds(log_root)
    total = 0.0
    for suite in suites:
        samples = history.get(suite, [])[-ESTIMATE_SAMPLE_COUNT:]
        total += statistics.median(samples) if samples else default_suite_seconds(suite)
    return total


def _suite_result_line(suite: str, status: str, summary: str, seconds: float) -> str:
    return f"[合併前測試] 套件 {suite}：{status}｜{summary}｜耗時 {seconds:.1f}s"


def _emit_result(log_root: str, line: str) -> None:
    """結果行同時寫 stdout 與 worktree-merge.log；日誌寫入失敗只警告，不影響閘門判定。"""
    print(line)
    if not log_root:
        sys.stderr.write("[WARNING] worktree-merge 無 log_root，結果行未寫日誌\n")
        return
    try:
        log = Path(log_root) / _LOG_FILE
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, "a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {line}\n")
    except OSError as exc:
        sys.stderr.write(f"[WARNING] worktree-merge 日誌寫入失敗：{exc}\n")


_STATUS_BY_RC = {0: "綠燈", 124: "逾時", 125: "名額等待逾時"}

# 閘門開始／結束行：前綴與套件結果行（[合併前測試]）刻意不同，名額預估只認後者
GATE_LINE_PREFIX = "[合併閘門]"
GATE_WRITTEN, GATE_REFUSED, GATE_RED, GATE_TIMEOUT, GATE_ABORTED = "寫入", "拒絕", "紅燈", "逾時", "中止"
GATE_PRECHECK_CONFLICT = "預檢衝突"
GATE_PRECHECK_CLEAR = "無衝突"
_TIMEOUT_MARKERS = ("全套件逾時", "等待本機名額逾時")
_RED_MARKER = "全套件紅燈"


class SlotWaitRefused(RuntimeError):
    """名額等待未取得（預估拒絕、等待逾時、收到訊號）：預期內結果，由呼叫端轉成結束碼，不是故障。"""

    def __init__(self, exit_code: int):
        super().__init__(f"等待本機名額失敗（exit {exit_code}）")
        self.exit_code = exit_code


def gate_result_label(error: str) -> str:
    """合併失敗理由 -> 結果類別（紅燈／逾時／中止）；理由文字由本模組 _rc_reason 產生。"""
    if any(marker in error for marker in _TIMEOUT_MARKERS):
        return GATE_TIMEOUT
    if _RED_MARKER in error:
        return GATE_RED
    return GATE_ABORTED


def gate_line(phase: str, target: str, branch: str, commit: str, result: Optional[str] = None) -> str:
    """閘門開始／結束行。commit：開始行為 base HEAD，結束行寫入時為合併 commit、其餘仍為 base HEAD。"""
    tail = f"｜結果 {result}" if result else ""
    return f"{GATE_LINE_PREFIX} {phase}｜target {target}｜分支 {branch}｜commit {commit[:12]}{tail}"


def emit_gate_line(log_root: str, line: str) -> None:
    _emit_result(log_root, line)


def _run_suites(suites: list, snapshot: str, project_root: str, runner: SuiteRunner,
                log_root: Optional[str] = None, on_green: Optional[Callable[[str], None]] = None,
                tag: str = "nocommit") -> str:
    """依序跑各套件；任一紅燈即停。每個套件結束輸出一行結果（含紅燈、逾時、中斷）。回傳空字串表示全綠。

    on_green：套件綠燈時立即回呼，後面套件紅燈時前面已綠者仍可記錄供重試沿用。
    """
    log_root = log_root or project_root
    for suite in suites:
        missing = _ensure_artifacts(suite, snapshot, project_root, runner)
        if missing:
            return missing
        start = time.monotonic()
        try:
            rc, out = runner(wrapped_argv(suite_command(suite, snapshot)), snapshot)
        except BaseException:  # 中斷也留一行紀錄後原樣再拋，讓上層清快照
            _emit_result(log_root, _suite_result_line(suite, "中斷", "無摘要", time.monotonic() - start))
            raise
        _emit_result(log_root, _suite_result_line(
            suite, _STATUS_BY_RC.get(rc, "紅燈"), summarize_output(out), time.monotonic() - start))
        if rc != 0:
            detail = save_failure_output(log_root, tag, suite, rc, out) if rc not in (124, 125) else ""
            return _rc_reason(suite, rc, out, detail)
        if on_green:
            on_green(suite)
    return ""


class MergeGate:
    """可掛到 merge_branch_cas(pre_merge_check=...) 的檢查物件；持有跨重試的驗證狀態。"""

    def __init__(self, repo: str, runner: Optional[SuiteRunner] = None, project_root: Optional[str] = None,
                 on_event: Optional[Callable[[str], None]] = None):
        self.repo = repo
        self.on_event = on_event or (lambda _name: None)  # slot_acquired／slot_released，測試斷言順序用
        self.runner = runner or default_runner
        self.project_root = project_root or repo
        self.verified_suites: dict = {}  # 套件 -> 該套件最近一次確認綠燈（含沿用）的合併 commit
        self.suite_runs = 0

    def _needs_slot(self, branch: str, base: str) -> bool:
        """分支相對 base 的改動是否可能需跑全套件；git 失敗時保守視為需要。"""
        base_proc = _git(["merge-base", base, branch], self.repo)
        if base_proc.returncode != 0:
            return True
        paths = changed_paths_between(self.repo, base_proc.stdout.decode().strip(), branch)
        try:
            decl = load_declaration_at(self.repo, branch)
        except DeclarationError:
            return True  # 宣告壞掉：保守取名額，合併時的檢查會判紅
        return paths is None or needs_gate(paths, decl)

    def _estimate_hold_seconds(self, branch: str, base: str) -> Optional[float]:
        """本次合併預計持有名額的秒數；套件範圍算不出來時回 None（交由 slot_gate 用命令預設值）。"""
        try:
            base_proc = _git(["merge-base", base, branch], self.repo)
            paths = changed_paths_between(self.repo, base_proc.stdout.decode().strip(), branch)
            if base_proc.returncode != 0 or paths is None:
                return None
            return suite_estimate_seconds(select_suites(paths, self.repo), self.repo)
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            sys.stderr.write(f"merge-gate: 無法估算持有秒數，改用預設值：{exc}\n")
            return None

    @contextmanager
    def hold(self, branch: str, base: str) -> Iterator[None]:
        """持有 heavy 名額的區段：進入時排隊取得，離開（成功、中止、例外、中斷）一律釋放。

        改動不在任何全套件範圍內者不取得，免得文件合併排在他方全套件之後。
        """
        if not self._needs_slot(branch, base):
            yield
            return
        with _sigterm_as_interrupt():
            held, early = slot_gate.acquire_slot(
                ["merge-gate", branch], lambda: None, label="merge-gate",
                estimate_seconds=self._estimate_hold_seconds(branch, base))
            if early is not None:
                raise SlotWaitRefused(early)
            if held is None:  # 名額閘門失效（目錄不可用）：與 run-with-timeout 一致，略過不擋
                yield
                return
            self.on_event("slot_acquired")
            try:
                with slot_gate.export_hold(held):
                    yield
            finally:
                held.release()
                self.on_event("slot_released")

    def _reusable(self, suite: str, commit: str, snap: str) -> Optional[str]:
        """該套件上次驗過的 commit 與新 commit 的差異若不觸及此套件，回傳該 commit；否則 None。

        「觸及」以既有套件選擇規則套在差異上判定；git 失敗保守視為觸及。
        """
        last = self.verified_suites.get(suite)
        if last is None:
            return None
        diff = changed_paths_between(self.repo, last, commit)
        if diff is None or suite in select_suites(diff, snap):
            return None
        return last

    def __call__(self, commit: str, ref: str, expected_old: str, attempt: int) -> CheckResult:
        try:
            decl = load_declaration_at(self.repo, commit)  # 先於範圍判定：格式錯誤 fail-closed，不得因免跑而放行
        except DeclarationError as exc:
            return CheckResult(False, f"[宣告] 套件宣告格式錯誤，閘門判紅：{exc}")
        if decl is None:
            print(f"[合併前測試] INFO：未找到專案宣告 {DECLARATION_PATH}，沿用內建 Flutter 對應")
        paths = changed_paths_between(self.repo, expected_old, commit)
        if paths is None:
            return CheckResult(False, "無法計算合併改動範圍")
        _warn_unmapped(paths, decl)
        if not needs_gate(paths, decl):
            print("[合併前測試] 改動不在任何全套件範圍內，免跑")
            return CheckResult(True)
        with _sigterm_as_interrupt(), merge_snapshot(self.repo, commit) as snap:
            suites = select_suites(paths, snap)
            todo = []
            for suite in suites:
                last = self._reusable(suite, commit, snap)
                if last is None:
                    todo.append(suite)
                    continue
                _emit_result(self.repo, _suite_result_line(suite, "沿用", f"沿用 {last[:12]} 的驗證結果", 0.0))
                self.verified_suites[suite] = commit  # 差異不觸及此套件，驗證結果視同延伸到新 commit
            if todo:
                print(f"[合併前測試] 快照內跑全套件：{', '.join(todo)}（合併 commit {commit[:12]}，嘗試 {attempt}）")
                self.suite_runs += 1
            reason = _run_suites(todo, snap, self.project_root, self.runner, self.repo,
                                 on_green=lambda s: self.verified_suites.__setitem__(s, commit), tag=commit)
        return CheckResult(False, reason) if reason else CheckResult(True)


_PATH_TOKEN = re.compile(r"docs/work-logs/[^\s'\"`)\]}>,]+\.(?:md|txt)")
# 同一行出現這些讀取寫法才算「讀取實際檔案」；純路徑字串比對與 JSON 資料夾具不算
_READ_CALL = re.compile(r"File\(|readAs|open\(|Path\(|read_text|read_bytes|\bcat\b|\.read\(|load\(")
_CODE_SUFFIXES = (".py", ".sh", ".dart")
_TEST_SCAN_DIRS = ("test", "integration_test")
_SKIP_DIRS = {".git", ".venv", "node_modules", "worktrees", ".dart_tool", "build", "__pycache__"}


def _test_files(root: Path) -> list:
    files = []
    for d in _TEST_SCAN_DIRS:
        files += [p for p in (root / d).rglob("*") if p.is_file()]
    for dirpath, dirnames, filenames in os.walk(root / ".claude"):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        if "tests" not in Path(dirpath).relative_to(root).parts:
            continue
        files += [Path(dirpath) / n for n in filenames]
    return [f for f in files if f.suffix in _CODE_SUFFIXES]


def find_exempt_file_reads(root: Path) -> list:
    """守衛：回傳測試程式碼中「同一行以讀取寫法引用豁免清單內且實際存在之檔案」的 (測試檔, 路徑)。

    限制：只辨識路徑字串與讀取呼叫同行的寫法；經常數或變數間接讀取者不在偵測範圍，
    新增此類寫法時須人工確認不讀豁免清單內的實際檔案。
    """
    hits = []
    for f in _test_files(root):
        try:
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue  # 守衛掃描中途消失或不可讀的測試檔：無內容可判，略過不影響其他檔
        for line in lines:
            if not _READ_CALL.search(line):
                continue
            for token in _PATH_TOKEN.findall(line):
                if is_reuse_exempt(token) and (root / token).is_file():
                    hits.append((str(f.relative_to(root)), token))
    return sorted(set(hits))
