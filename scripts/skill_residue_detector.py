"""偵測 skill 內殘留的他專案痕跡。

skill 內容跨專案流動時，來源專案的檔案路徑、版本號、腳本名會一併被帶進來，
在下次 push 時擴散回 canonical 再被其他 consumer 取走。這類殘留不會讓任何
指令失敗——它只是把讀者導向不存在的東西，所以沒有自動偵測時，是否乾淨完全
取決於推送者當下有沒有逐檔核對。

三類訊號都以「本專案能否驗證其存在」為判準，不猜測內容意圖：

| 訊號 | 級別 | 判準 |
|------|------|------|
| MISSING_PATH | blocking | 引用的路徑其頂層目錄存在於本專案，但該檔不存在 |
| MISSING_SCRIPT | blocking | 指示執行的腳本在本專案與 skill 目錄皆不存在 |
| FOREIGN_TICKET_ID | advisory | ticket ID 的版本段在 docs/work-logs/ 找不到對應目錄 |

**為何 FOREIGN_TICKET_ID 只作 advisory**：跨專案共享的 skill 引用其開發歷史的
ticket ID 是既有的大量存量（DOC-010 的範疇），與「他專案殘留內容」是不同的問題。
把它列為 blocking 會讓每次 push 都被存量債擋下，實際效果是使用者一律加 --force，
連帶讓 blocking 級的真訊號失去效力。

**頂層目錄先決**：只有當引用路徑的頂層目錄（`lib/`、`test/`）確實存在於本專案時，
才檢查其下的檔案。專案沒有 `tests/` 目錄時，`tests/auth/test_login_flow.py` 是
文件的通用示意而非殘留——無從區分，就不該報。

**刻意不偵測裸版本號**：初版把所有 `vX.Y.Z` 都當訊號，結果 30 個 skill 命中，
其中 skill 自身版本號（`v1.2.0`）、Claude Code 版本（`v2.1.133`）、他框架版本
全被誤判。裸版本號無法從字面判斷其指涉對象，收窄為「帶 W 波次的 ticket ID」
才有明確歸屬——那正是 DOC-010 關注的、框架文件引用專案識別符的樣態。

**刻意不偵測 error-pattern 編號**：同樣的理由。`UC-001` 是 use case 而非
error-pattern，光看前綴無從分辨，硬判會把正常的需求追溯標記當殘留。

豁免走兩軌：行內標記供個案說明，佔位樣式白名單供文件慣用的示意路徑
（`path/to/x.dart`、`<your-file>.dart`）。缺豁免機制的偵測器會把自身變成
另一個雜訊來源，讀者學會忽略後就等於沒有偵測。
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.skill_case_guard import warn_skill_md_case_mismatch

EXEMPT_MARKER = "skill-residue-exempt"

# 文件慣用的示意路徑：這些本來就不該存在於任何專案，命中不代表殘留。
PLACEHOLDER_SIGNALS = (
    "path/to",
    "your-",
    "your_",
    "example",
    "xxx",
    "<",
    "{",
    "$",
)

_PATH_RE = re.compile(r"(?<![\w./-])((?:lib|test|tests)/[A-Za-z0-9_./-]+\.(?:dart|py|ts|js))\b")
# 路徑可能以 . 開頭（.claude/...），故不用 \b 起錨——\b 會在 . 之後才成立，
# 使 `.claude/skills/x.py` 被切成 `claude/skills/x.py` 而查無此檔。
_SCRIPT_RE = re.compile(
    r"(?:uv run|python3?|dart run|node)\s+((?:\./)?[.A-Za-z0-9_/-]+\.(?:py|dart|ts|js))"
)
_TICKET_ID_RE = re.compile(r"\b(\d+\.\d+\.\d+)-W\d+-\d+(?:\.\d+)*\b")


BLOCKING_KINDS = frozenset({"MISSING_PATH", "MISSING_SCRIPT"})


@dataclass(frozen=True)
class Residue:
    """One suspected leftover, located precisely enough to act on."""
    skill: str
    file: Path
    line: int
    kind: str
    detail: str

    @property
    def is_blocking(self) -> bool:
        return self.kind in BLOCKING_KINDS

    def format(self) -> str:
        return f"{self.file}:{self.line} [{self.kind}] {self.detail}"


def _is_placeholder(text: str) -> bool:
    lowered = text.lower()
    return any(signal in lowered for signal in PLACEHOLDER_SIGNALS)


def _line_is_exempt(line: str) -> bool:
    return EXEMPT_MARKER in line


def known_versions(project_root: Path) -> set[str]:
    """Versions this project can vouch for, read from its worklog tree.

    Derived rather than hand-listed: a hand-maintained list drifts from the
    directories it claims to describe, and then starts rejecting the project's
    own versions (ARCH-BAL-003).
    """
    worklog = project_root / "docs" / "work-logs"
    if not worklog.is_dir():
        return set()
    return {
        d.name.lstrip("v")
        for d in worklog.rglob("v*")
        if d.is_dir() and re.fullmatch(r"v\d+(\.\d+)*", d.name)
    }


def _version_is_known(version: str, versions: set[str]) -> bool:
    """A version counts as known when it, or any prefix of it, has a directory.

    `docs/work-logs/` nests as v0 / v0.2 / v0.2.1, so a three-segment version
    may only ever appear as a two-segment directory. Requiring an exact match
    would flag the project's own versions.
    """
    parts = version.split(".")
    return any(".".join(parts[: i + 1]) in versions for i in range(len(parts)))


def _resolvable(ref: str, project_root: Path, skill_dir: Path | None) -> bool:
    """Whether the reference points at something that exists.

    Three roots are tried before calling a reference broken. Beyond the project
    root and the skill directory, the skill's whole subtree is searched by
    filename: skill docs routinely name their own modules in shortened form
    (`lib/staleness.py` for `ticket_system/lib/staleness.py`), and treating
    those as missing would flag a skill for describing itself.
    """
    if (project_root / ref).exists():
        return True
    if not skill_dir:
        return False
    if (skill_dir / ref).exists():
        return True
    tail = Path(ref).name
    return any(skill_dir.rglob(tail))


def scan_file(
    path: Path,
    project_root: Path,
    skill: str,
    versions: set[str],
    skill_dir: Path | None = None,
) -> list[Residue]:
    """Scan one file, skipping lines the author explicitly exempted."""
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    found: list[Residue] = []
    for lineno, line in enumerate(content.split("\n"), 1):
        if _line_is_exempt(line):
            continue

        for match in _PATH_RE.finditer(line):
            ref = match.group(1)
            top_level = ref.split("/", 1)[0]
            if not (project_root / top_level).is_dir():
                continue  # 專案沒有這個頂層目錄，該引用是通用示意而非殘留
            if _is_placeholder(ref) or _resolvable(ref, project_root, skill_dir):
                continue
            found.append(Residue(skill, path, lineno, "MISSING_PATH", ref))

        for match in _SCRIPT_RE.finditer(line):
            ref = match.group(1)
            ref = ref[2:] if ref.startswith("./") else ref
            if _is_placeholder(ref) or _resolvable(ref, project_root, skill_dir):
                continue
            found.append(Residue(skill, path, lineno, "MISSING_SCRIPT", ref))

        for match in _TICKET_ID_RE.finditer(line):
            if _version_is_known(match.group(1), versions):
                continue
            found.append(Residue(skill, path, lineno, "FOREIGN_TICKET_ID", match.group(0)))

    return found


def is_reader_facing(path: Path, skill_dir: Path) -> bool:
    """Whether this file tells a reader to go look at something.

    Limited to `SKILL.md` and `references/` because that is where a path
    reference is an instruction. The same string inside a test fixture, a
    template, or a Python message constant is data or illustration — flagging
    those buries the instructions that actually mislead someone under noise
    nobody can act on.
    """
    if path.suffix != ".md":
        return False
    if path.name == "SKILL.md" and path.parent == skill_dir:
        return True
    return "references" in path.relative_to(skill_dir).parts


def scan_skill(skill_dir: Path, project_root: Path) -> list[Residue]:
    """Scan a single skill directory."""
    versions = known_versions(project_root)
    found: list[Residue] = []
    for path in sorted(skill_dir.rglob("*")):
        if not path.is_file() or not is_reader_facing(path, skill_dir):
            continue
        if any(part in {".venv", "__pycache__", ".pytest_cache"} for part in path.parts):
            continue
        found.extend(
            scan_file(path, project_root, skill_dir.name, versions, skill_dir=skill_dir)
        )
    return found


def scan_all(skills_dir: Path, project_root: Path) -> dict[str, list[Residue]]:
    """Scan every installed skill, returning only those with findings.

    A `skill.md` (wrong case) never matches `is_reader_facing`'s exact
    `SKILL.md` check, so its content is silently skipped by this scanner
    regardless of filesystem case sensitivity. Warn about that blind spot
    on stderr before scanning, so it is not read as "nothing to report".
    """
    result: dict[str, list[Residue]] = {}
    if not skills_dir.is_dir():
        return result
    for warning in warn_skill_md_case_mismatch(skills_dir):
        print(f"[skill-residue-detector] {warning}", file=sys.stderr)  # i18n-exempt
    for skill_dir in sorted(d for d in skills_dir.iterdir() if d.is_dir()):
        found = scan_skill(skill_dir, project_root)
        if found:
            result[skill_dir.name] = found
    return result


def blocking_only(findings: dict[str, list[Residue]]) -> dict[str, list[Residue]]:
    """Keep only findings strong enough to justify stopping a push."""
    result = {}
    for skill, items in findings.items():
        blocking = [r for r in items if r.is_blocking]
        if blocking:
            result[skill] = blocking
    return result


def format_report(findings: dict[str, list[Residue]], limit_per_skill: int = 5) -> list[str]:
    """Render findings for terminal output, capping per-skill detail lines.

    The cap reports how many it withheld rather than trimming silently — a
    truncated list that looks complete gets read as "that's all of it".
    """
    lines: list[str] = []
    for skill, items in findings.items():
        # i18n-exempt: 開發者工具的終端輸出，不進使用者介面
        lines.append(f"  {skill}（{len(items)} 項）")
        for residue in items[:limit_per_skill]:
            lines.append(f"    {residue.format()}")
        if len(items) > limit_per_skill:
            # i18n-exempt: 同上
            lines.append(f"    ... 另有 {len(items) - limit_per_skill} 項未列出")
    return lines
