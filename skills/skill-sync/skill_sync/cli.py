"""skill-sync CLI: sync skills with a remote skills repository."""

from __future__ import annotations

import argparse
import ast
import contextlib
import difflib
import filecmp
import hashlib
import os
import shutil
import json
import re
import subprocess
import sys
import tempfile
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

DEFAULT_REPO = "https://github.com/tarrragon/claude-skills.git"

# 取遠端 manifest（fetch_remote_manifest，淺 clone）的等待上限。正常約 1.8 秒
# （實測對發佈庫），比改走 git clone 之前的 HTTP 直接 GET（0.5-1.2 秒）
# 慢，故上限沿用同一顆常數但放寬，避免正常網路延遲被誤判為逾時；被防火牆
# 黑洞時仍會用滿整個上限，這份資料只影響一段資訊性報告，不值得讓呼叫端無限
# 等待。
REMOTE_FETCH_TIMEOUT_SECONDS = 15
EXCLUDE_DIRS = {
    "project-integration",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "htmlcov",
    "build",
    ".egg-info",
    "hook-logs",
}

# --force 繞過可攜性閘門的記錄檔位置。env var 名稱沿用專案既有慣例
# （ticket_system.lib.precondition 的 HOOK_LOGS_DIR），純為命名一致，不 import
# 該模組——skill-sync 是零框架依賴的獨立套件（見 pyproject.toml
# dependencies = []），任何跨套件 import 都會讓它無法安裝到不含該套件的環境。
_HOOK_LOGS_DIR_ENV = "HOOK_LOGS_DIR"
_DEFAULT_HOOK_LOGS_DIR = ".claude/hook-logs"
_PORTABILITY_FORCE_LOG_FILENAME = "skill-sync-portability-force.jsonl"
_DIVERGENCE_FORCE_LOG_FILENAME = "skill-sync-divergence-force.jsonl"

# 憑證判準（移植自 .claude/lib/sync_exclude_manifest.py 的憑證維度）。
#
# 只移植判準本身，不移植整份清單：manifest 作用域是整個 .claude/ 樹，本模組
# 作用域是單一 skill 目錄，兩者要排除的目錄集合天差地遠（如 manifest 的
# LOCAL_ONLY_PATTERNS 含 hook-state / .claude-state 等，對單一 skill 目錄
# 無意義）；只有「憑證」這個判準——外流即安全事故——與作用域無關，跨通道
# 應處置一致（push 目標是公開 GitHub repo，原判準只比對 EXCLUDE_DIRS 目錄
# 名，對憑證檔零攔截）。
_CREDENTIAL_SUFFIXES = frozenset({".pem", ".key", ".p12", ".pfx", ".jks"})
_CREDENTIAL_NAME_PREFIXES = frozenset({".env.", "secret"})
# 無副檔名、不以 env/secret 開頭的憑證慣例檔名，suffix/prefix 判準覆蓋不到，
# 須精確列名：.env 本身（前綴判準只匹配 ".env." 變體，不含裸檔名）、.keys、
# 與 SSH 私鑰的慣例俗名（framework 通道也同樣漏檢這類，另由專屬票處理）。
_CREDENTIAL_EXACT_NAMES = frozenset({
    ".env",
    ".keys",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
})

# 標記檔存在即宣告該 skill 的本地內容為刻意客製，`pull`（全量）分歧檢查略過回報
# （0.2.1-W3-124 acceptance 4 的宣告式 local override 決策：見 update_sync_manifest
# 與 _classify_sync_status 的 docstring）。
SKILL_SYNC_OVERRIDE_MARKER = ".skill-sync-override"

# 記錄「上次成功 pull/push 時」該 skill 的內容雜湊（見 _record_sync_base，pull/push
# 成功後寫入）。versions.json 只存 hash 與 version，本地原本無任何「上次同步到哪」
# 的記錄，三方資訊塌成兩方，覆蓋方向因此永遠推不出來、必須人判——一次漏判即以舊版
# 覆蓋發佈庫。本標記檔補上第三方資訊：local==base 而 remote!=base 代表遠端已
# 前進 -> 該 pull；反向 -> 該 push；兩者皆偏離 base -> 真衝突（見
# _resolve_diverge_direction）。從未走過本機制的既有 skill 無此檔，維持現行
# diverged 輸出（方向 "unknown"，向後相容）。
SKILL_SYNC_BASE_MARKER = ".skill-sync-base"


class DivergedSkill(NamedTuple):
    """One skill whose local content differs from the remote copy.

    Carries its own remediation commands so consumers print what this module
    says to run, rather than each keeping a hand-written copy that drifts from
    the actual subcommands.

    `direction` defaults to "unknown": a skill with no recorded sync base
    (see SKILL_SYNC_BASE_MARKER) cannot have its direction resolved, and the
    default keeps every existing construction site valid without having to
    thread a base lookup through call sites that never had one.

    `direction` can also be `"suspect_revert"`: a `"pull"` classification
    (local unchanged, remote moved) whose remote content turned out to match
    an older historical commit of that skill rather than genuinely new
    content — see `_check_suspect_revert`. `suspect_revert_commit` carries a
    display string (short SHA + timestamp) for that match; it stays `None`
    for every other direction, so existing construction sites need no
    change.
    """

    name: str
    local: str
    remote: str
    pull_command: str
    push_command: str
    direction: str = "unknown"
    suspect_revert_commit: str | None = None


class SyncStatus(NamedTuple):
    """Outcome of comparing every installed skill against the remote manifest.

    Named fields rather than a bare tuple: consumers unpack this across module
    boundaries, and a positional tuple turns any added category into a
    `ValueError` at the call site instead of a compatible addition.
    """

    repo_url: str
    remote_count: int
    up_to_date: list[str]
    diverged: list[DivergedSkill]
    overridden: list[str]
    excluded_by_policy: list[str]
    skipped_no_hash: list[str]
    skipped_remote_missing: list[str]

    @property
    def local_count(self) -> int:
        return (
            len(self.up_to_date)
            + len(self.diverged)
            + len(self.overridden)
            + len(self.excluded_by_policy)
            + len(self.skipped_no_hash)
            + len(self.skipped_remote_missing)
        )


def _should_exclude_file(rel_path: str) -> bool:
    """Check if a file path should be excluded.

    Covers dir names (incl. nested hook-logs/), credential file names, and
    the skill-sync-override marker file.

    Credentials matter here because `push` targets a public GitHub repo and
    `--force` skips only the interactive preview, not this function (see
    compute_diff, the sole call site feeding both overlay_copy and the
    dst-only scan). The marker matters for the same reason via a different
    failure mode: it is a single consumer's local declaration, and if it
    ever reached the upstream repo, every consumer pulling afterwards would
    have that skill silently classified `overridden`, suppressing drift
    reports for everyone. This is the single judgment point both
    compute_diff and compute_content_hash rely on for marker exclusion, so
    the two paths cannot drift apart on marker handling the way they
    previously did (compute_content_hash used to carry its own separate
    `f.name == SKILL_SYNC_OVERRIDE_MARKER` check).

    SKILL_SYNC_BASE_MARKER shares the same rationale via the same failure
    mode: it too is a single consumer's local bookkeeping (this sync's
    publish-repo hash, see _record_sync_base), and letting it into the content
    hash would make writing it change the hash it is meant to describe — a
    self-referential loop where every write invalidates itself.
    """
    path = Path(rel_path)
    if path.name in (SKILL_SYNC_OVERRIDE_MARKER, SKILL_SYNC_BASE_MARKER):
        return True
    for part in path.parts:
        if part in EXCLUDE_DIRS or part.endswith(".egg-info"):
            return True
    name_lower = path.name.lower()
    if name_lower in _CREDENTIAL_EXACT_NAMES:
        return True
    if path.suffix.lower() in _CREDENTIAL_SUFFIXES:
        return True
    if any(name_lower.startswith(prefix) for prefix in _CREDENTIAL_NAME_PREFIXES):
        return True
    return False



# --- Incremental banned-term scan -------------------------------------------------

# 字面複製自 .claude/hooks/skill-banned-term-scan-hook.py 的 BANNED_TERMS /
# INLINE_MARKER / 隱式規則（fenced code block、inline code span），非 import——
# skill-sync 是零框架依賴的獨立套件（見 pyproject.toml dependencies = []），
# 任何跨套件 import 都會讓它無法安裝到不含該 hook 的環境。兩份判準是否一致
# 由專案層級的獨立測試斷言（`.claude/hooks/tests/`，比照既有裸格式 ticket ID
# 正則複製同一模式，不放在本套件目錄內以免測試原始碼自身的字面路徑引用被
# `check_portability` 的 consumer-path 判準命中形成自我指涉）。
#
# 只複製「判準本身」（詞表 + 行內豁免規則），不複製該 hook 的
# FILE_LEVEL_ALLOWLIST：那份白名單是為全檔掃描設計（術語對照表整篇都是
# mention），而本模組只掃描 push 相對遠端新增/修改的行——範圍已經比全檔
# 掃描窄得多，尚未觀察到需要整檔豁免的實例，且新增行不太可能剛好是既有
# 全檔白名單想保護的既有內容。若未來出現真實需求再加，不預先照搬一個
# 用不到的機制。
_BANNED_TERMS = {
    "智能": "Hook 系統、規則比對",
    "文檔": "文件",
    "數據": "資料",
    "默認": "預設",
    "代碼": "程式碼",
    "視頻": "影片",
    "軟件": "軟體",
    "硬件": "硬體",
    "信息": "資訊",
}
_BANNED_TERM_INLINE_MARKER = "banned-term-exempt"
_BANNED_TERM_INLINE_CODE_SPAN_RE = re.compile(r"`[^`]*`")
_BANNED_TERM_FENCE_RE = re.compile(r"^\s*```")


class BannedTermHit(NamedTuple):
    """一處疑似禁用詞散文使用。file 為 skill 目錄內的相對路徑。"""

    file: str
    line: int
    term: str
    suggestion: str
    text: str


def _strip_banned_term_code_spans(line: str) -> str:
    """把反引號內的內容清空，避免 mention 被誤判為 use（保留字元數不變，
    比對到的 term 位置不受影響，用空白填充維持行內位置對齊）。字面複製自
    `skill-banned-term-scan-hook.py` 的 `_strip_inline_code_spans`。
    """
    return _BANNED_TERM_INLINE_CODE_SPAN_RE.sub(lambda m: " " * len(m.group(0)), line)


def _new_line_numbers_from_diff(before_lines: list[str], after_lines: list[str]) -> set[int]:
    """回傳 after_lines 中屬於「新增或取代」的 1-index 行號集合。

    重用 `_diff_line_counts` 的 `difflib.SequenceMatcher` opcode 機制：
    insert / replace 段落的 after 側行號範圍即為本次改動新增的行，delete
    段落不影響 after 側行號、equal 段落不是新增，皆不計入。
    """
    new_lines: set[int] = set()
    for tag, _i1, _i2, j1, j2 in difflib.SequenceMatcher(None, before_lines, after_lines).get_opcodes():
        if tag in ("insert", "replace"):
            new_lines.update(range(j1 + 1, j2 + 1))
    return new_lines


def _scan_lines_for_banned_terms(
    rel: str, after_lines: list[str], new_line_numbers: set[int]
) -> list[BannedTermHit]:
    """對 after_lines 逐行掃描禁用詞，只回報 new_line_numbers 內的命中。

    fenced code block 狀態須從檔案第一行開始追蹤才正確——一個較早開啟、
    尚未關閉的 fence 會涵蓋到新增行卻看不到開啟該 fence 的那一行本身（那行
    通常不在新增範圍內）；因此本函式對整份 after_lines 逐行掃描以維持正確
    的 fence 狀態機，但只在該行屬於 new_line_numbers 時才記錄命中。
    """
    hits: list[BannedTermHit] = []
    in_fence = False
    for line_no, raw_line in enumerate(after_lines, start=1):
        if _BANNED_TERM_FENCE_RE.match(raw_line):
            in_fence = not in_fence
            continue
        if line_no not in new_line_numbers or in_fence:
            continue
        if _BANNED_TERM_INLINE_MARKER in raw_line:
            continue
        scannable = _strip_banned_term_code_spans(raw_line)
        for term, suggestion in _BANNED_TERMS.items():
            if term in scannable:
                hits.append(BannedTermHit(rel, line_no, term, suggestion, raw_line.strip()))
    return hits


def scan_push_for_banned_terms(source: Path, target: Path, diff: dict[str, list[str]]) -> list[BannedTermHit]:
    """對本次 push 相對遠端新增/修改的內容，掃描 language-constraints.md
    規則 2 禁用詞，report-only（呼叫端不得據此中止 push）。

    只掃描 `diff["added"]`（全檔皆新增，全部逐行掃描）與 `diff["modified"]`
    （只掃描相對 target 新增或取代的行，見 `_new_line_numbers_from_diff`）；
    `diff["unchanged"]` 與 `diff["dst_only"]` 一律略過——既有基線債務（本次
    push 未新增/修改的既有行）不在本次改動範圍內，重複舉報只會製造噪音且
    對「這次 push 是否引入新問題」無鑑別力。只掃 `.md` 檔（禁用詞規範針對
    散文，`.py` 等程式碼檔的字串常數/識別符不在規範範圍內，且比照
    `check_portability` 對 `.py` 只掃 docstring/comment 的既有先例，全文
    掃描程式碼會招致大量誤判）。

    讀取失敗或無法以 UTF-8 解碼的檔案略過，不中斷整體掃描（同
    `_diff_line_counts` 的既有處理方式）。
    """
    hits: list[BannedTermHit] = []

    for rel in diff["added"]:
        if not rel.endswith(".md"):
            continue
        try:
            after_lines = (source / rel).read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        new_line_numbers = set(range(1, len(after_lines) + 1))
        hits.extend(_scan_lines_for_banned_terms(rel, after_lines, new_line_numbers))

    for rel in diff["modified"]:
        if not rel.endswith(".md"):
            continue
        try:
            before_lines = (target / rel).read_text(encoding="utf-8").splitlines()
            after_lines = (source / rel).read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        new_line_numbers = _new_line_numbers_from_diff(before_lines, after_lines)
        hits.extend(_scan_lines_for_banned_terms(rel, after_lines, new_line_numbers))

    return hits


def _print_banned_term_report(hits: list[BannedTermHit]) -> None:
    """印出增量禁用詞掃描結果，report-only（不影響 push 是否繼續）。"""
    print(
        f"\n  [BannedTerm] {len(hits)} suspected banned-term use(s) in new/modified "
        "line(s) (language-constraints.md rule 2), reporting only:",
        file=sys.stderr,
    )
    for hit in hits:
        print(
            f"    {hit.file}:{hit.line}  \"{hit.term}\" -> \"{hit.suggestion}\"",
            file=sys.stderr,
        )
        print(f"      {hit.text}", file=sys.stderr)
    print(
        "  If this is a legitimate reference (grep pattern / terminology sample), "
        "wrap it in backticks or a fenced code block, or append "
        "<!-- banned-term-exempt: reason --> to the line.",
        file=sys.stderr,
    )


# --- Portability check ----------------------------------------------------------

# 消費端框架路徑：發佈庫根沒有 .claude/ 這一層，任何以它開頭的引用在
# 另一個 consumer 端都指向不存在的檔案。
_CONSUMER_PATH_RE = re.compile(r"\.claude/[A-Za-z0-9_./-]+")
# 專案 ticket ID：不只是斷鏈，blog 的 skill-mirror 從全檔取最大三段數字推導版號，
# 一個 ticket ID 就能讓它抓錯版並中斷發佈。
_TICKET_ID_RE = re.compile(r"\b\d+\.\d+\.\d+-W\d+-\d+")
# rule8-exempt: illustration:下一段裸格式常數註解舉例展示裸格式與全格式的字面差異
# 裸格式 ticket ID（無版本前綴，如 W8-047）：另一種下游危害——內容送進其他消費端
# 後，該端若部署框架既有的引用穩定性守衛，會因裸格式命中而阻擋其 commit。此正則
# 為框架單一權威定義（供多個獨立守衛比對裸格式用）的字面複製，非 import——
# skill-sync 是零框架依賴的獨立套件（見上方一段的既有說明），任何跨套件 import
# 都會讓它無法安裝到不含該套件的環境。字面是否與權威定義一致由專案層級的獨立測試
# 斷言（不放在本套件目錄內，避免測試原始碼自身的字面路徑引用被本檔的
# consumer-path 判準命中，形成自我指涉）。
_BARE_TICKET_ID_RE = re.compile(r"\bW\d+-\d+\b")
# 行內豁免：該行的引用經人判定為刻意保留（架構性橋接、教學範例）。標記語彙沿用
# 專案既有的 portability-allow，寫在哪一行就只豁免那一行。
# 兩個標記語彙互認：portability-allow 說「這個消費端專屬引用是刻意保留的」，
# broken-link-exempt 說「這個路徑不存在是預期的」（示範路徑、歷史遷移軌跡）。
# 後者涵蓋的情形對可攜性同樣成立——一條已判定不必存在的路徑，不會因為換個
# 專案就變成缺陷。對稱地，broken-link-check 的豁免通道也認 portability-allow。
_ALLOW_RE = re.compile(r"portability-allow|broken-link-exempt")

# 已評估、決定不偵測：以中文自然語言表述的消費端指涉（如「本專案的 pm-rules」
# 「主線程 PM」等代理人名稱／專案自稱，未搭配具體 .claude/ 路徑或 ticket ID）。
# 沒有像路徑前綴或數字樣式那樣的穩定錨點可以掛 regex——關鍵詞清單（「本專案」
# 「本框架」等）在中文敘述性文件裡出現頻率高且語意多半與可攜性無關，會產生
# 大量假陽性，稀釋既有兩類判準（consumer-path／ticket-id）的訊號可信度；而
# 反過來限縮關鍵詞集合又會漏掉大多數實際違規措辭。這類指涉留給 portable
# 宣告者人工審閱，不納入自動判定。


class PortabilityViolation(NamedTuple):
    """一處消費端專屬引用。file 為 skill 目錄內的相對路徑。"""

    file: str
    line: int
    kind: str  # "consumer-path" | "ticket-id"
    text: str


def _is_portable_declared(skill_dir: Path) -> bool:
    """讀 SKILL.md frontmatter 的 metadata.portable。

    未宣告即視為未宣告 portable——框架專屬工具 skill（ticket / doc / worktree 等）
    談 .claude/ 路徑是正當內容而非缺陷，預設嚴格會把它們全部凍結在 push 之外。
    宣告的責任歸 skill 自己，判準因此隨 skill 走而不是靠外部清單維護。
    """
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return False
    try:
        text = skill_md.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    if not text.startswith("---"):
        return False
    end = text.find("\n---", 3)
    if end == -1:
        return False
    front = text[3:end]
    return re.search(r"^\s*portable:\s*true\s*$", front, re.MULTILINE) is not None


def _scan_line_for_violations(rel: str, lineno: int, line: str) -> list[PortabilityViolation]:
    """單行文字比對消費端路徑／ticket-ID pattern，回傳違規清單（可能多筆）。

    .md 全文掃描與 .py 敘述性文字（docstring／# 註解）掃描共用同一判準，避免
    兩條路徑各自維護一份 regex 比對邏輯而彼此漂移。

    裸格式比對（_BARE_TICKET_ID_RE）會命中全格式 ID 內嵌的裸片段（如
    "0.2.1-W3-1"（rule8-exempt: illustration:示範全格式如何內嵌裸片段） 內的
    "W3-1"），需排除完全落在既有全格式命中範圍內的裸格式匹配，避免同一段文字
    被同時記兩筆違規。
    """
    if _ALLOW_RE.search(line):
        return []
    found: list[PortabilityViolation] = []
    for match in _CONSUMER_PATH_RE.finditer(line):
        found.append(PortabilityViolation(rel, lineno, "consumer-path", match.group(0)))
    full_spans: list[tuple[int, int]] = []
    for match in _TICKET_ID_RE.finditer(line):
        found.append(PortabilityViolation(rel, lineno, "ticket-id", match.group(0)))
        full_spans.append(match.span())
    for match in _BARE_TICKET_ID_RE.finditer(line):
        start, end = match.span()
        if any(fs <= start and end <= fe for fs, fe in full_spans):
            continue
        found.append(PortabilityViolation(rel, lineno, "ticket-id", match.group(0)))
    return found


_NARRATIVE_DOCSTRING_NODE_TYPES = (
    ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
)


def _extract_python_narrative_text(source: str) -> list[tuple[int, str]]:
    """從 Python 原始碼擷取「敘述性文字」：docstring 與 `#` 註解。

    docstring 用 ast 精確定位（module / function / class），不誤判一般字串
    字面值——`path = ".claude/lib/foo.py"` 這類真實執行期依賴的字串常數不會
    被當成敘述性文字。`#` 註解用簡化的行內位置判定（非完整 tokenize），精確度
    與既有 .md 掃描一致，足以捕捉已知的真實漏洞樣態：hooks/scripts 內以自然
    語言描述 .claude/ 路徑的註解行（見 check_portability 擴充理由）。

    回傳 (行號, 文字) 列表；語法錯誤的檔案 ast.parse 會失敗，此時退化為只擷取
    `#` 註解，不讓單一壞檔中斷整體掃描。
    """
    entries: list[tuple[int, str]] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        tree = None
    if tree is not None:
        for node in ast.walk(tree):
            if not isinstance(node, _NARRATIVE_DOCSTRING_NODE_TYPES):
                continue
            docstring = ast.get_docstring(node, clean=False)
            if not docstring:
                continue
            body = getattr(node, "body", None)
            start = body[0].lineno if body else getattr(node, "lineno", 1)
            for offset, doc_line in enumerate(docstring.splitlines()):
                entries.append((start + offset, doc_line))
    for lineno, line in enumerate(source.splitlines(), start=1):
        idx = line.find("#")
        if idx != -1:
            entries.append((lineno, line[idx:]))
    return entries


def check_portability(skill_dir: Path) -> list[PortabilityViolation]:
    """掃描 skill 的 markdown 全文與 Python 檔的敘述性文字，回報消費端專屬引用。

    .md 全文皆掃：可攜性問題主要出在給人與模型讀的敘述。.py 只掃 docstring 與
    `#` 註解，不掃一般程式碼——程式碼裡的路徑常是真實的執行期依賴（如
    sys.path 操作），全掃會招致大量誤判，見 _extract_python_narrative_text。
    排除規則沿用 _should_exclude_file，project-integration/ 這類刻意隔離的
    消費端層因此不進掃描範圍。

    掃描範圍評估：skills 目錄下目前沒有 .sh 或其他腳本語言檔案，.py 是本次
    唯一新增的副檔名；若未來引入其他腳本語言，可比照 .py 的 docstring/comment
    萃取原則擴充，而非改回全文掃描。
    """
    violations: list[PortabilityViolation] = []
    if not skill_dir.is_dir():
        return violations
    for path in sorted(skill_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(skill_dir).as_posix()
        if _should_exclude_file(rel):
            continue
        if path.suffix == ".md":
            try:
                lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                continue
            for lineno, line in enumerate(lines, start=1):
                violations.extend(_scan_line_for_violations(rel, lineno, line))
        elif path.suffix == ".py":
            try:
                source = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for lineno, text in _extract_python_narrative_text(source):
                violations.extend(_scan_line_for_violations(rel, lineno, text))
    return violations


def _resolve_hook_logs_dir() -> Path:
    """解析 hook-logs 目錄；env var 優先（測試隔離用），否則錨定專案根目錄。

    改為呼叫 _resolve_project_root() 前，此函式用未錨定的相對路徑
    `.claude/hook-logs`，經由已安裝的全域 shim（`uv run --directory
    <skill_dir>`，cwd 恆等於 skill 自身目錄）執行時，稽核紀錄會寫到
    `<repo>/.claude/skills/skill-sync/.claude/hook-logs/`，而非本函式
    文件承諾的 `<repo>/.claude/hook-logs/`。
    """
    env_value = os.environ.get(_HOOK_LOGS_DIR_ENV)
    if env_value:
        return Path(env_value)
    return _resolve_project_root("hook-logs resolution") / _DEFAULT_HOOK_LOGS_DIR


def _write_portability_force_log(
    name: str,
    declared: bool,
    already_shared: bool,
    violations: list[PortabilityViolation],
) -> None:
    """--force 繞過可攜性閘門時，把違規清單落地到 hook-logs，供事後追溯來源。

    Append-only JSONL；目錄不存在時自動建立。寫入失敗只警告不阻斷 push——
    這是稽核記錄，不是主閘門本身，記錄失敗不該連帶讓一次合法的 --force 操作
    卡住（同 ticket_system.lib.precondition 的既有權衡）。
    """
    logs_dir = _resolve_hook_logs_dir()
    record = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "skill": name,
        "declared_portable": declared,
        "already_in_publish_repo": already_shared,
        "violation_count": len(violations),
        "violations": [
            {"file": v.file, "line": v.line, "kind": v.kind, "text": v.text}
            for v in violations
        ],
    }
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_file = logs_dir / _PORTABILITY_FORCE_LOG_FILENAME
        with open(log_file, mode="a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        print(f"  [Warning] force-log 寫入失敗（不阻斷 push）：{exc}", file=sys.stderr)


def _write_divergence_force_log(
    name: str,
    divergence_warned: bool,
    stale_version_warned: bool,
    push_revert_warned: bool = False,
) -> None:
    """`push --force` 使方向警告、stale-version 警告或疑似回退警告失去
    `[y/N]` 停點時，把「這次 push 忽略了哪些警告」落地到 hook-logs，供事後
    追溯。

    `push_revert_warned` 預設 `False`：`_check_push_revert` 是後補的第三種
    警告來源，既有呼叫點（測試與其他呼叫端）不需要跟著改寫就能維持原行為。

    與 `_write_portability_force_log` 同一權衡：append-only JSONL、目錄不存在
    自動建立、寫入失敗只警告不阻斷 push（這是稽核記錄，不是主閘門）。只在
    `cmd_push` 判定至少一道警告曾印出且 `force=True` 時呼叫——沒有警告或未帶
    `--force` 的正常路徑不產生任何記錄，避免每次成功 push 都無謂寫檔。
    """
    logs_dir = _resolve_hook_logs_dir()
    record = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "skill": name,
        "divergence_warning_ignored": divergence_warned,
        "stale_version_warning_ignored": stale_version_warned,
        "push_revert_warning_ignored": push_revert_warned,
    }
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_file = logs_dir / _DIVERGENCE_FORCE_LOG_FILENAME
        with open(log_file, mode="a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        print(f"  [Warning] force-log 寫入失敗（不阻斷 push）：{exc}", file=sys.stderr)


def _skill_exists_in_publish_repo(name: str, repo_dir: Path) -> bool:
    """查詢已 clone 的發佈庫工作目錄內 versions.json 是否已收錄此 skill。

    只證明「這個 skill 曾經被 push 過」，不證明「有其他 consumer 真的裝了
    它」——發佈庫是散佈通道，versions.json 只記錄 hash 與 version，不記錄
    任何安裝／訂閱資訊。回傳 True 時只適合用來給未宣告 portable 的 skill附加
    一則提示（見 _report_portability），不適合作為升級嚴重度或中止 push 的
    依據，兩者判準不同不可混用。

    讀已 clone 的目錄而非自己向遠端取：唯一呼叫端 `cmd_push` 本來就要為 diff
    與推送 clone 一次同一個 repo，本函式先前經 `fetch_remote_manifest` 再
    clone 一次只為讀同一份檔案，等於同一份遠端內容取兩次、每次 push 兩趟網路
    往返。改吃呼叫端已有的 clone 後兩次收斂為一次，判準來源不變——仍是 repo
    根目錄 versions.json 於 HEAD 的內容。

    讀取或解析失敗回傳 False（fail open）：本函式只是提示訊息的輔助查詢，不
    是主閘門本身，versions.json 缺檔或壞格式不該連帶讓 push 卡住——與先前
    網路查詢失敗時的處置一致。
    """
    versions_file = repo_dir / "versions.json"
    try:
        manifest = json.loads(versions_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(manifest, dict) and name in manifest


def _format_violation_lines(violations: list[PortabilityViolation]) -> list[str]:
    """把違規清單格式化為顯示行（不含輸出目的地），供 stderr 完整報告與
    --force 旁路時的 stdout 摘要共用同一格式，避免兩處各自維護一份「前 20
    筆 + ... and N more」的截斷邏輯而彼此漂移。
    """
    lines = [f"    {v.file}:{v.line}  [{v.kind}]  {v.text}" for v in violations[:20]]
    if len(violations) > 20:
        lines.append(f"    ... and {len(violations) - 20} more")
    return lines


def _report_portability(
    skill_dir: Path, name: str, force: bool, repo_dir: Path | None = None
) -> None:
    """push 前的可攜性閘門。

    宣告 portable 的 skill 命中即中止（--force 可覆蓋但仍列出違規並落地
    force-log，另見下方 stdout 摘要說明）。未宣告者只列出摘要，不論它是否已
    存在於發佈庫——
    「存在於發佈庫」只證明「曾被 push 過」，不證明「其他 consumer 真的
    裝了它」（實測：發佈庫現有 64 個 skill，某一線消費專案僅裝 23 個；
    `doc` / `ticket` / `worktree` 等框架專屬工具全都在發佈庫裡但該專案
    一個都沒裝，`.claude/` 路徑是它們的主題而非缺陷）。用「存在於
    發佈庫」推論「已跨 consumer 使用」是過度推論，據此中止會讓大量實際
    未共用的框架工具 push 被誤擋，且反轉「未宣告者的高命中率理當只報告不
    阻擋」的既有設計取捨——高假陽性的閘門只會催生 --force 肌肉記憶，讓
    force-log 淪為擋不住任何事的事後考古。

    確有 repo_dir 且查得到已存在於發佈庫（見 _skill_exists_in_publish_repo）
    時，只在既有的「reporting only」訊息後多印一行建議：若這個 skill 確實
    跨 consumer 使用，應顯式宣告 metadata.portable: true 讓閘門真正生效——
    這是資訊，不是判決；中止沒有可靠依據就不該做。

    repo_dir 是呼叫端已 clone 好的發佈庫工作目錄，不是 repo URL：本函式
    不自己向遠端取任何東西，remote 查詢的責任留在已經必須 clone 的呼叫端，
    避免同一份 versions.json 被取兩次。預設 None：省略時不做這項查詢，行為
    與未傳時完全一致（只印 reporting only 那一行）。

    --force 旁路時額外印一份 stdout 摘要：既有的完整違規列表只印在 stderr，
    若呼叫端只收集 stdout（如管線只轉存 stdout 供事後稽核），--force 的效果
    會只留下 hook-logs 的 jsonl 這一條痕跡，使用者不會主動去看。stdout 摘要
    與 stderr 版共用 _format_violation_lines，不重複維護格式。
    """
    violations = check_portability(skill_dir)
    if not violations:
        return
    declared = _is_portable_declared(skill_dir)
    already_shared = repo_dir is not None and _skill_exists_in_publish_repo(name, repo_dir)
    kinds = {v.kind for v in violations}
    label = " + ".join(sorted(kinds))

    if not declared:
        print(
            f"\n  [Portability] {len(violations)} consumer-specific reference(s) "
            f"({label}) in '{name}'. Not declared portable — reporting only.",
            file=sys.stderr,
        )
        if already_shared:
            print(
                f"  Note: '{name}' already exists in the skills publish repo. Existence "
                "there only means it has been pushed before, not that another "
                "consumer actually installed it — if it genuinely is shared across "
                "consumers, declare metadata.portable: true so this gate can "
                "enforce these references instead of only reporting them.",
                file=sys.stderr,
            )
        return

    print(
        f"\n  [Portability] '{name}' declares metadata.portable: true but carries "
        f"{len(violations)} consumer-specific reference(s):",
        file=sys.stderr,
    )
    for line in _format_violation_lines(violations):
        print(line, file=sys.stderr)
    print(
        "  A portable skill must not name another project's files: keep the point "
        "in the sentence and drop the path, or move the passage into "
        "references/project-integration/ (excluded from sync).",
        file=sys.stderr,
    )
    if force:
        _write_portability_force_log(name, declared, already_shared, violations)
        print("  --force given: pushing anyway.", file=sys.stderr)
        # 同一份摘要另印到 stdout：上面的完整報告只在 stderr，只收集 stdout
        # 的呼叫端（如管線只轉存 stdout）原本除了 hook-logs 的 jsonl 外看不到
        # 任何痕跡。
        print(
            f"  [Portability] --force bypassed {len(violations)} "
            f"consumer-specific reference(s) in '{name}':"
        )
        for line in _format_violation_lines(violations):
            print(line)
        return
    print("  Aborted. Use --force to push regardless.", file=sys.stderr)
    sys.exit(1)


def get_repo_url() -> str:
    return os.environ.get("SKILL_SYNC_REPO", DEFAULT_REPO)


def _extract_version_string(text: str) -> str | None:
    """從 SKILL.md 文字擷取版本字串。

    僅供人類於 changelog 對照閱讀，不進入同步決策（見 update_sync_manifest）。

    `version:` 的比對範圍限定在 frontmatter 區塊（首尾 `---` 之間）：本專案
    多數 SKILL.md 把版本寫在 frontmatter 的 metadata.version（縮排兩格），
    原本只認行首 `^version:` 的寫法會漏抓這些縮排寫法；若不限定區塊，正文
    （含本函式自身的說明文字）出現的 `version:` 字樣又會被誤抓，使抽取結果
    依賴巧合而非結構。`**Version**:` 形式（工作日誌／規則文件慣用）仍在全文
    搜尋，不受此限——本專案實測沒有 SKILL.md 使用此形式，收窄範圍無實際
    行為變更，維持全文搜尋以免影響其他消費端可能存在的既有用法。
    """
    m = re.search(r"\*\*Version\*\*:\s*(\S+)", text)
    if m:
        return m.group(1)
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    front = text[3:end]
    m = re.search(r"^\s*version:\s*(\S+)", front, re.MULTILINE)
    return m.group(1) if m else None


def compute_content_hash(skill_dir: Path) -> str | None:
    """依檔案內容計算 skill 目錄的確定性雜湊，取代版本字串作為內容同一性判定依據。

    與 `.claude/lib/sync_exclude_manifest.py` 的同名函式語意不相容，兩者的值
    不可互相比較：本函式的作用域是單一 skill 目錄（該檔是整個 `.claude/`）、
    摘要以 (路徑 bytes, 內容 bytes) 直接餵入單一 hasher（該檔先組
    `"路徑:sha256"` 文字再雜湊）、輸出完整 64 字（該檔截斷 16 字）、目錄不存在
    回傳 None（該檔無此語意），排除集亦不同（本函式另排除
    SKILL_SYNC_OVERRIDE_MARKER）。本函式的雜湊值已持久化於遠端 versions.json，
    改動摘要形式會讓全部遠端 hash 失效，故兩者不合併。


    對 (相對路徑, 檔案位元組) 依路徑排序後逐一雜湊，雜湊值只反映內容與檔案樹結構，
    與 mtime、掃描順序、檔案系統無關：相同內容不論何處產生都得到相同雜湊，內容不同
    則版本字串相同也得到不同雜湊。這修正的是版本字串同時被當內容同一性與演化祖先關係
    使用、卻兩者都擔不起的機制缺陷（0.2.1-W3-124 §11.2：blog 與發佈庫的 2.5.0
    號碼相同、內容不同，曾被判為 up_to_date）。回傳 None 表示目錄不存在。
    """
    if not skill_dir.is_dir():
        return None

    rel_paths: list[str] = []
    for f in skill_dir.rglob("*"):
        if not f.is_file():
            continue
        rel = f.relative_to(skill_dir).as_posix()
        if _should_exclude_file(rel):
            continue
        rel_paths.append(rel)
    rel_paths.sort()

    hasher = hashlib.sha256()
    for rel in rel_paths:
        hasher.update(rel.encode("utf-8"))
        hasher.update((skill_dir / rel).read_bytes())
    return hasher.hexdigest()


def _has_local_override(skill_dir: Path) -> bool:
    """標記檔存在即宣告本地內容為刻意客製，`pull`（全量）分歧檢查略過此 skill。"""
    return (skill_dir / SKILL_SYNC_OVERRIDE_MARKER).is_file()


def _read_sync_base(skill_dir: Path) -> str | None:
    """讀取上次同步基準雜湊；從未成功 pull/push 過的 skill（無此檔）回傳 None。"""
    base_file = skill_dir / SKILL_SYNC_BASE_MARKER
    if not base_file.is_file():
        return None
    try:
        text = base_file.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return text or None


def _write_sync_base(skill_dir: Path, content_hash: str) -> None:
    """寫入同步基準雜湊。呼叫端須先確認本次 pull/push 已成功再呼叫。"""
    (skill_dir / SKILL_SYNC_BASE_MARKER).write_text(content_hash + "\n", encoding="utf-8")


def _record_sync_base(skill_dir: Path) -> None:
    """pull/push 成功後，以 skill_dir 當下內容雜湊更新同步基準。

    目錄不存在時 compute_content_hash 回傳 None，略過寫入——呼叫端理應只在操作
    成功之後呼叫本函式，此時目錄應已存在；這裡只是防禦式收尾，不視為錯誤。
    """
    content_hash = compute_content_hash(skill_dir)
    if content_hash is not None:
        _write_sync_base(skill_dir, content_hash)


def _refresh_stale_sync_base(skills_dir: Path, up_to_date_names: Iterable[str]) -> int:
    """對內容已與遠端一致、但 `.skill-sync-base` 落後的 skill 重記同步基準。

    只接收呼叫端已用內容雜湊確認 local == remote 的名單：這是安全性前提——只有
    雙邊已確定一致時，「marker 落後」才等於「上次同步後兩邊各自獨立前進到同一份
    內容」，可放心視為新的同步基準；若雙邊仍分歧就重記，會把尚未真正同步的狀態
    誤標成已同步，讓下次分歧報告誤判方向。

    僅在 marker 與目前雜湊不同時才寫入：框架正本通道（sync-claude-pull 全樹
    overlay）與本地直接編輯都會讓內容前進而不觸碰 marker，`skill-sync pull`
    （無名稱）狀態報告因此需要補上這一步；但報告命令原本是唯讀的，若對每個
    marker 已經正確的 skill 也重寫一次，會讓每次報告都無謂觸碰檔案 mtime。
    回傳實際重記的數量，供呼叫端印出可觀測訊息——報告命令從純讀變成偶爾有
    寫入副作用，這個轉變不能對使用者靜默（觀測性規則 4）。
    """
    refreshed = 0
    for name in up_to_date_names:
        skill_dir = skills_dir / name
        current_hash = compute_content_hash(skill_dir)
        if current_hash is None:
            continue
        if _read_sync_base(skill_dir) != current_hash:
            _write_sync_base(skill_dir, current_hash)
            refreshed += 1
    return refreshed


def _resolve_diverge_direction(
    base_hash: str | None, local_hash: str, remote_hash: str
) -> str:
    """依同步基準，將一組已知分歧（local_hash != remote_hash）的雙方雜湊判定方向。

    回傳 "pull" / "push" / "conflict" / "unknown" 四態之一：無 base（從未同步過）
    -> "unknown"，維持現行「方向未知，需人工判斷」輸出；local 未變（仍等於 base）
    而 remote 變了 -> "pull"；反向 -> "push"；兩邊皆偏離 base -> "conflict"（雙方
    各自獨立演化，非單向落後，才是真正需要人工比對內容的情況）。呼叫端須確保
    local_hash != remote_hash（本函式不重複這項前置判斷，只處理已知分歧的情況）。
    """
    if base_hash is None:
        return "unknown"
    if local_hash == base_hash:
        return "pull"
    if remote_hash == base_hash:
        return "push"
    return "conflict"


def _diverge_warning(direction: str, expected: str) -> str | None:
    """direction 與本次操作預期方向不一致時，回傳顯著警示文字；相符或無 base
    記錄（"unknown"）時回傳 None。

    「方向不自動判定，只標示」是本工具既有哲學；有 sync base 可用時新增的是
    把風險攤在使用者眼前，不是新增一道強制關卡。expected 是呼叫端這次操作
    對應的方向：pull 命令傳 "pull"，push 命令傳 "push"。
    """
    if direction in ("unknown", expected):
        return None
    if direction == "conflict":
        return (
            "Sync base shows both sides changed independently since last sync "
            "— this operation may discard changes made on the other side."
        )
    suggested = "pull" if expected == "push" else "push"
    return (
        f"Sync base suggests this skill has only moved the other way since "
        f"last sync — consider '{suggested}' instead of '{expected}'."
    )


@contextlib.contextmanager
def _cloned_skill_history(repo_url: str, skill_name: str):
    """Clone `repo_url` 的完整歷史 metadata（不下載檔案內容）並取得該 skill
    路徑的 commit log，供呼叫端在 `with` 區塊內對回傳的 repo 目錄執行進一步
    的 git 操作（讀 tree 物件雜湊、checkout 特定歷史提交）。

    共用給 `_check_suspect_revert`（報告端，比對遠端現況 vs 遠端自己的歷史，
    皆為 git 物件可直接比對樹狀雜湊）與 `_check_push_revert`（推送端，比對
    本地檔案系統內容 vs 發佈庫歷史，需要實際 checkout 內容才能比對，
    見該函式說明）——兩者「clone + 取得該 skill 的 commit log」這段完全
    相同，只有取得 log 之後的比對手段不同。

    yield `(repo_dir, entries)`：`entries` 為 `(sha, ISO 時間戳)` 由新到舊
    排列的清單；clone 失敗、log 失敗或無任何歷史時 `repo_dir` 為 `None`、
    `entries` 為空清單，呼叫端一律先檢查 `repo_dir is not None` 才能使用。

    成本說明（team lead 要求明列）：對 repo_url 執行一次
    `--filter=blob:none --no-checkout` clone，不限 `--depth`——祖先關係
    比對需要完整歷史，深度限制的淺 clone 無法提供「更早」的比較基準。
    `blob:none` 確保 clone 當下完全不下載檔案內容，只取得 commit 與 tree
    metadata；`--no-checkout` 確保 clone 當下不落地任何工作目錄檔案（後續
    若呼叫端執行 `git checkout <sha> -- <path>`，才會針對那個路徑、那個
    commit 惰性下載對應 blob，這是刻意的按需下載，不是一次性下載全部
    歷史內容）。這個 clone 的成本隨發佈庫**全庫**歷史長度成長，不是
    隨單一 skill 的檔案量或提交數成長（git 的物件傳輸協定以整個 repo 的
    歷史圖為單位，sparse-checkout 只影響工作目錄 populate 範圍，不影響
    物件傳輸範圍）；兩個呼叫端都只在少數候選才觸發（`_check_suspect_revert`
    限 direction == "pull"、`_check_push_revert` 限本地無合法 marker），
    故實際發生頻率通常很低。若未來發佈庫歷史成長到使此操作成為報告或
    推送延遲的主要來源，才需要評估更精細的方案（如伺服器端歷史查詢 API），
    本次不預先最佳化一個尚未觀測到的問題。

    任何 git 操作失敗（網路、路徑不存在、逾時等）皆吞下、yield 空結果——
    這是報告/推送的加值判斷，不是主流程，失敗不該讓整份報告或整次推送
    連帶失敗。
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir) / "repo"
        try:
            clone = subprocess.run(
                ["git", "-c", "core.autocrlf=false", "clone",
                 "--filter=blob:none", "--no-checkout", repo_url, str(tmp)],
                capture_output=True, text=True, timeout=REMOTE_FETCH_TIMEOUT_SECONDS,
            )
            if clone.returncode != 0:
                yield None, []
                return

            log = subprocess.run(
                ["git", "log", "--follow", "--format=%H,%cI", "--", f"{skill_name}/"],
                cwd=tmp, capture_output=True, text=True,
            )
            if log.returncode != 0 or not log.stdout.strip():
                yield None, []
                return
            entries = [
                (sha, timestamp)
                for sha, timestamp in (line.split(",", 1) for line in log.stdout.strip().splitlines())
            ]
            yield tmp, entries
        except (OSError, subprocess.SubprocessError):
            yield None, []


def _check_suspect_revert(repo_url: str, skill_name: str) -> str | None:
    """對已判定方向為 "pull" 的 skill，檢查 remote 目前內容是否命中該 skill
    某個非最新歷史提交（即回退回一個更舊的版本），命中則回傳可顯示的摘要
    （短 SHA + ISO 時間戳），否則回傳 None。

    背景：三方比對（`_resolve_diverge_direction`）只回答「哪一側自 base 後
    移動過」，不回答「移動後的內容是否仍是 base 的超集」。一個沒有合法
    `.skill-sync-base` marker 的推送方（如從未透過本 CLI 同步過的既有消費
    者）用舊副本覆蓋發佈庫時，方向判定會退化為 "unknown"，但另一個
    持有合法 marker 的消費者看到的卻是字面正確、語意錯誤的 "pull"——
    remote 確實移動過，只是移動方向是倒退。本函式補上這道「移動後內容是否
    仍是超集」的檢查（`_check_push_revert` 是同一問題在推送端的縱深防禦，
    兩者共用 `_cloned_skill_history` 走訪歷史）。

    只在呼叫端已判定 direction == "pull" 時呼叫，故不影響其餘多數健康報告
    （up_to_date、無分歧）的執行成本。

    比對手段是 git 樹狀物件雜湊（`git rev-parse <commit>:<path>`），不是
    `compute_content_hash` 的 SHA256 排序雜湊——兩者演算法不同不可混用，
    但同一份內容在 git 裡不論何時提交，樹狀雜湊必定相同，足以判定「目前
    內容是否與某個歷史時刻完全相同」，且不需要重新實作一套等價的排序
    雜湊邏輯或另外持久化任何鏈結資料結構（發佈庫本身的 git 歷史就是
    現成的祖先關係來源）。
    """
    with _cloned_skill_history(repo_url, skill_name) as (repo_dir, entries):
        if repo_dir is None or len(entries) < 2:
            return None  # clone/log 失敗，或只有一筆歷史（無「更舊」可比對）

        def tree_hash(commit: str) -> str | None:
            result = subprocess.run(
                ["git", "rev-parse", f"{commit}:{skill_name}/"],
                cwd=repo_dir, capture_output=True, text=True,
            )
            return result.stdout.strip() if result.returncode == 0 else None

        current_sha, _ = entries[0]
        current_tree = tree_hash(current_sha)
        if current_tree is None:
            return None
        for sha, timestamp in entries[1:]:
            if tree_hash(sha) == current_tree:
                return f"{sha[:8]} ({timestamp})"
        return None


def _check_push_revert(repo_url: str, skill_name: str, local_hash: str) -> str | None:
    """推送方本地無合法 `.skill-sync-base` marker 時，檢查本地內容
    （`local_hash`，`compute_content_hash` 算出）是否命中該 skill 於
    發佈庫的某個非最新歷史提交，命中則回傳可顯示摘要（短 SHA + ISO
    時間戳），否則 `None`。

    與 `_check_suspect_revert` 同一問題（三方比對只判「誰動過」不判「內容
    是否仍是超集」）在推送端的縱深防禦：`_check_suspect_revert` 是報告端
    的事後防線（回退已經寫進發佈庫，只是不讓它被無感傳播），本函式是
    事前防線（在回退寫入發佈庫之前警告推送方）。兩者共用
    `_cloned_skill_history` 走訪歷史，只有走訪之後的比對手段不同——本地
    內容不是 git 物件，不能用樹狀雜湊直接比對，改為對每個候選歷史提交
    `git checkout <sha> -- <path>` 實際取出內容，用與呼叫端相同的
    `compute_content_hash` 語意逐一雜湊比對。

    只跳過歷史清單最新的一筆（`entries[0]`）：命中最新提交代表本地內容就是
    發佈庫目前的樣子，屬正常的「無變更重推」而非回退，此情況留給既有
    `_print_divergence_warning`/`_print_stale_version_warning` 處理，不在
    本函式範圍。
    """
    with _cloned_skill_history(repo_url, skill_name) as (repo_dir, entries):
        if repo_dir is None or len(entries) < 2:
            return None
        for sha, timestamp in entries[1:]:
            checkout = subprocess.run(
                ["git", "checkout", sha, "--", f"{skill_name}/"],
                cwd=repo_dir, capture_output=True, text=True,
            )
            if checkout.returncode != 0:
                continue
            historical_hash = compute_content_hash(repo_dir / skill_name)
            if historical_hash == local_hash:
                return f"{sha[:8]} ({timestamp})"
        return None


def _stale_version_warning(
    source: Path, local_ver: str | None, remote_ver: str | None
) -> str | None:
    """版號與遠端相同、但內容雜湊自 .skill-sync-base 已變更時，回傳警告文字；否則 None。

    內容改了、版號沒動是一種容易累積的分歧形態：版號相同時它不只無鑑別力，而是
    主動宣稱兩邊一致，使分歧不會被例行同步檢查發現，須等到事後逐一讀 diff 才判
    得出方向。閘門放在 push 端最便宜——寫入者當下仍握有變更脈絡，事後比對端已經
    沒有。

    版號不同（已 bump）或任一版號缺失時直接放行：本函式只鎖定「版號相同」這個
    誤導性訊號，版號已跟著內容變更時不該每次 push 都跳警告。無 base 記錄（從未
    走過本機制的既有 skill）維持向後相容的靜默，與 `_diverge_warning` 同一哲學。
    """
    if local_ver is None or remote_ver is None or local_ver != remote_ver:
        return None
    base_hash = _read_sync_base(source)
    if base_hash is None:
        return None
    current_hash = compute_content_hash(source)
    if current_hash is None or current_hash == base_hash:
        return None
    return (
        f"Content changed since last sync (hash differs from {SKILL_SYNC_BASE_MARKER}) "
        f"but version is still {local_ver}, same as remote. Bump the version before "
        "pushing, or confirm this push intentionally keeps it unchanged."
    )


def _print_stale_version_warning(
    source: Path, local_ver: str | None, remote_ver: str | None
) -> bool:
    """push preview 內印出 `_stale_version_warning` 的結果（若有）。

    回傳是否印出了警告：`push --force` 需要這個布林值來判斷警告是否存在——
    `--force` 不影響這個函式本身（檢查照跑、輸出照印），但拿掉了緊接其後的
    `[y/N]` 停點，使這行 `[WARNING]` 從「使用者必然讀到才能繼續」降級為
    「push 成功訊息前滾過去的幾行 stderr」。呼叫端（`cmd_push`）用回傳值在
    `--force` 且警告存在時於結尾摘要重述，把降級的閱讀強制性至少部分找回來。
    """
    warning = _stale_version_warning(source, local_ver, remote_ver)
    if warning:
        print(f"  [WARNING] {warning}", file=sys.stderr)
        return True
    return False


def _print_divergence_warning(
    local_skill_dir: Path,
    local_hash: str | None,
    remote_hash: str | None,
    expected: str,
) -> bool:
    """pull/push preview 前的方向檢查。local_skill_dir 是 sync base 記錄所在的
    本地目錄（pull 時是 target、push 時是 source，兩者皆為本地端）。

    任一雜湊為 None（目錄不存在，如首次 pull 或遠端尚無此 skill）或兩者相同
    （未分歧，無方向可判）時安靜略過，回傳 False。

    回傳是否印出了警告，理由與 `_print_stale_version_warning` 相同——
    `cmd_push` 用它判斷 `--force` 是否把這道警告的停點拿掉了。`cmd_pull`
    呼叫本函式時忽略回傳值：pull 沒有等價的 `--force` 降級問題，該路徑的
    `[y/N]` 停點不受 `--force` 影響。
    """
    if local_hash is None or remote_hash is None or local_hash == remote_hash:
        return False
    direction = _resolve_diverge_direction(
        _read_sync_base(local_skill_dir), local_hash, remote_hash
    )
    warning = _diverge_warning(direction, expected)
    if warning:
        print(f"  [WARNING] {warning}", file=sys.stderr)
        return True
    return False


def _warn_skill_md_case_mismatch(base_dir: Path) -> None:
    """對 base_dir 下每個 skill 目錄，若無精確大寫 SKILL.md 但存在其他大小寫變體，輸出 stderr 警告。

    `glob("*/SKILL.md")` 的大小寫敏感性依 Python 版本而異：3.12 及之前固定
    case-sensitive 比對，3.13 起在省略 `case_sensitive` 時改為探測實際檔案
    系統，在 case-insensitive 檔案系統（如 macOS APFS）上會反過來折疊命中。
    兩個版本都不報錯，只是掃描集合不同——目錄內若只有 `skill.md`（或其他
    大小寫變體），在較舊版本上會被靜默略過、永遠不進入 manifest。改為
    case-insensitive glob 會讓兩種檔名長期並存並在 push 時互相覆蓋，不採用；
    本函式只負責告警，判準仍維持 case-sensitive。

    判準讀取實際目錄項名稱（`os.scandir` 的 `entry.name`），不可用
    `Path.exists()` 或 `Path.glob()`——兩者在 case-insensitive 檔案系統上
    都可能對小寫 `skill.md` 回傳「找到了」，會讓本判準失效。

    本函式與 `.claude/lib/skill_case_guard.py` 的 `warn_skill_md_case_mismatch`
    為同一判準的兩份實作，刻意不共用程式碼：skill-sync 以 hatchling 打包為
    獨立 wheel（`pyproject.toml` 的 `dependencies = []`、
    `packages = ["skill_sync"]`），安裝到其他 consumer 專案時不含 `.claude/`
    樹，import `.claude.lib` 會在該情境下失敗。兩份實作的判準邏輯變更時須
    同步修改。
    """
    if not base_dir.is_dir():
        return
    for entry in sorted(os.scandir(base_dir), key=lambda e: e.name):
        if not entry.is_dir():
            continue
        try:
            names = [f.name for f in os.scandir(entry.path) if f.is_file()]
        except OSError:
            continue
        if "SKILL.md" in names:
            continue
        variant = next((n for n in names if n.lower() == "skill.md"), None)
        if variant is not None:
            print(
                f"  [WARN] {entry.name}: 檔名為 '{variant}'，非精確大寫 'SKILL.md'，"
                "不會進入 manifest 掃描（case-sensitive glob 在 Python 3.13 前恆漏，"
                "3.13 起依檔案系統大小寫敏感性而定）",
                file=sys.stderr,
            )


def update_sync_manifest(repo_dir: Path) -> None:
    """掃描 repo 內所有 skill，寫入版本字串（人類可讀）與內容雜湊（同步判定用）至 versions.json。

    版本字串不再進入同步決策：舊實作以版本字串相等判定內容同一性、以 semver 大小
    判定覆蓋方向，但兩個獨立演化的分支可能巧合共用同一版本號卻內容不同，semver
    比較亦預設線性演進，對分支式分歧失準（0.2.1-W3-124 §11.2）。版本字串保留於本檔
    供人類於 changelog 對照，內容同一性判定改用 hash 欄位。
    """
    _warn_skill_md_case_mismatch(repo_dir)
    manifest: dict[str, dict[str, str]] = {}
    for skill_md in sorted(repo_dir.glob("*/SKILL.md")):
        name = skill_md.parent.name
        content_hash = compute_content_hash(skill_md.parent)
        if content_hash is None:
            continue
        entry: dict[str, str] = {"hash": content_hash}
        try:
            text = skill_md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            text = ""
        version = _extract_version_string(text)
        if version:
            entry["version"] = version
        manifest[name] = entry

    vf = repo_dir / "versions.json"
    existing = {}
    if vf.exists():
        try:
            existing = json.loads(vf.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    if manifest == existing:
        return

    vf.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    run_git(["add", "versions.json"], cwd=repo_dir)

    status = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=repo_dir
    )
    if status.returncode == 0:
        return

    run_git(["commit", "-m", "chore: update versions.json"], cwd=repo_dir)
    run_git(["push"], cwd=repo_dir)
    print("  [OK] versions.json updated")


def _resolve_project_root(purpose: str = ".claude/skills resolution") -> Path:
    """解析專案根目錄，優先以 git toplevel 為基準，消除 cwd 依賴。

    在專案任意子目錄（含 skill 目錄內、`uv run --directory` 情境）執行時，
    都應解析到專案根，而非誤把子目錄當根目錄。非 git 目錄（或 git 不可用）
    時 fallback 至現行 cwd，並於 stderr 輸出警告（觀測性規則 4）。

    抽出為共用 helper：get_skills_dir() 與 _resolve_hook_logs_dir() 各自需要
    同一段「消除 cwd 依賴」邏輯，若各自實作會在同一檔案內重蹈多處各自
    解析同一件事的覆轍（`uv run --directory` shim 使 cwd 恆等於 skill 自身
    目錄，任何未錨定專案根目錄的相對路徑寫入都會落錯位置）。`purpose`
    只影響警告文字，兩個呼叫端共用判斷邏輯與 fallback 語意。
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=Path.cwd(),
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as e:
        print(
            f"Warning: git rev-parse failed ({type(e).__name__}: {e}); "
            f"falling back to current working directory for {purpose}",
            file=sys.stderr,
        )
        return Path.cwd()

    if result.returncode != 0:
        print(
            f"Warning: not a git repository; "
            f"falling back to current working directory for {purpose}",
            file=sys.stderr,
        )
        return Path.cwd()

    return Path(result.stdout.strip())


def get_skills_dir() -> Path:
    """解析 .claude/skills 目錄，優先以 git toplevel 為基準，消除 cwd 依賴。

    在專案任意子目錄（含 skill 目錄內、`uv run --directory` 情境）執行時，
    都應解析到專案根下的 .claude/skills，而非誤把子目錄當根目錄。
    非 git 目錄（或 git 不可用）時 fallback 至現行 cwd 行為，並於 stderr
    輸出警告（觀測性規則 4）。
    """
    return _resolve_project_root(".claude/skills resolution") / ".claude" / "skills"


def run_git(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"git error: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return result



def compute_diff(src: Path, dst: Path) -> dict[str, list[str]]:  # i18n-exempt
    """Compare src and dst directories, return categorized file lists.

    This is a disk-walk diff (compares filesystem trees directly).
    NOT interchangeable with sync-claude-push's copy_filtered_from_staging
    which uses git-tracked-only source (git archive) for security guarantees.

    Returns dict with keys: added, modified, unchanged, dst_only.
    """
    diff: dict[str, list[str]] = {
        "added": [],
        "modified": [],
        "unchanged": [],
        "dst_only": [],
    }

    src_files: set[str] = set()
    for f in src.rglob("*"):
        if f.is_file():
            rel = f.relative_to(src).as_posix()
            if _should_exclude_file(rel):
                continue
            src_files.add(rel)
            dst_file = dst / rel
            if not dst_file.exists():
                diff["added"].append(rel)
            elif not filecmp.cmp(f, dst_file, shallow=False):
                diff["modified"].append(rel)
            else:
                diff["unchanged"].append(rel)

    if dst.exists():
        for f in dst.rglob("*"):
            if f.is_file():
                rel = f.relative_to(dst).as_posix()
                if _should_exclude_file(rel):
                    continue
                if rel not in src_files:
                    diff["dst_only"].append(rel)

    for key in diff:
        diff[key].sort()
    return diff


def _diff_line_counts(before: Path, after: Path) -> tuple[int, int] | None:
    """回傳 (added, removed) 行數，取自 before -> after 的實際逐行差異。

    不是單純的總行數相減：兩個檔案總行數相同時，整份內容仍可能被互換覆蓋，
    行數相減會誤報「無變化」。改用 difflib.SequenceMatcher 逐段比對，insert
    段落計入 added、delete 段落計入 removed、replace 段落兩者皆計。

    讀取失敗或內容無法以 UTF-8 解碼（二進位檔）回傳 None，呼叫端改印「無法計算
    行數」，不假裝算得出一個實際上量不出來的結果。
    """
    try:
        before_lines = before.read_text(encoding="utf-8").splitlines()
        after_lines = after.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    added = removed = 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, before_lines, after_lines).get_opcodes():
        if tag in ("replace", "delete"):
            removed += i2 - i1
        if tag in ("replace", "insert"):
            added += j2 - j1
    return added, removed


def _format_line_count_suffix(dst: Path | None, src: Path | None, rel: str) -> str:
    """modified 檔案清單附掛的行數摘要；缺 dst/src（呼叫端未提供目錄）時回傳空字串。"""
    if dst is None or src is None:
        return ""
    counts = _diff_line_counts(dst / rel, src / rel)
    if counts is None:
        return "  (binary or unreadable content)"
    added, removed = counts
    return f"  (+{added}/-{removed} lines)"


def print_diff_preview(
    diff: dict[str, list[str]],
    direction: str,
    src: Path | None = None,
    dst: Path | None = None,
) -> None:
    """Print a human-readable diff preview.

    The dst-only label tracks what will actually happen: a `diff`/plan whose
    "prunable" entry is non-empty means those files get deleted, so labelling
    them "preserved" would misreport a destructive operation as a safe one.
    `prune` used to be a separate bool parameter that callers had to keep in
    sync with the plan by hand; folding it into the plan (see
    `build_push_plan`) removes that duplicate source of truth.

    `src`/`dst` are optional and default to None: when a caller supplies both
    (the two directories `diff` was computed from), each modified file's line
    gains an added/removed line count (see _diff_line_counts) — the count,
    not the file name, is what separates a routine two-line edit from a
    near-total rewrite. A preview that only lists filenames cannot tell those
    apart, and a routine-looking two-line "[MOD]" entry has previously hidden
    a change that deleted well over a thousand lines. Tests that hand-build a
    `diff` dict without real files on disk simply omit src/dst and get the
    previous filename-only output.
    """
    has_changes = diff["added"] or diff["modified"]
    if direction == "push" and diff.get("prunable"):
        preserve_label = "PRUNE (will be deleted)"
    else:
        preserve_label = (
            "remote-only (preserved)" if direction == "push" else "local-only (preserved)"
        )

    if not has_changes and not diff["dst_only"]:
        print("  No changes detected.")
        return

    if diff["added"]:
        print(f"  [ADD] {len(diff['added'])} file(s):")
        for f in diff["added"]:
            print(f"    + {f}")

    if diff["modified"]:
        print(f"  [MOD] {len(diff['modified'])} file(s):")
        for f in diff["modified"]:
            print(f"    ~ {f}{_format_line_count_suffix(dst, src, f)}")

    if diff["dst_only"]:
        print(f"  [{preserve_label}] {len(diff['dst_only'])} file(s):")
        for f in diff["dst_only"]:
            print(f"    ? {f}")

    if diff["unchanged"]:
        print(f"  [unchanged] {len(diff['unchanged'])} file(s)")


def overlay_copy(src: Path, dst: Path, diff: dict[str, list[str]]) -> int:
    """Copy only added and modified files from src to dst. Never delete dst-only files.

    Known limitation: not atomic — partial failure leaves inconsistent state.
    Acceptable for single-user CLI; git history provides recovery path.
    """
    copied = 0
    for rel in diff["added"] + diff["modified"]:
        src_file = src / rel
        dst_file = dst / rel
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dst_file)
        copied += 1
    return copied


def prune_dst_only(dst: Path, diff: dict[str, list[str]]) -> int:
    """Delete dst-only files, then drop directories the deletion left empty.

    Only entries `compute_diff` classified as dst_only are touched for file
    deletion, so EXCLUDE_DIRS content (project-integration/, hook-logs/, ...)
    is out of reach by construction — it never enters that list. `unlink`
    uses `missing_ok=True`: a file already gone by the time we get here (TOCTOU
    against the earlier compute_diff snapshot) is not a failure to report,
    just nothing left to remove.

    Empty-directory cleanup is unconditional rather than limited to
    directories this call emptied: git tracks files, not directories, so a
    leftover empty directory is local noise that would never reach the remote
    anyway, and scanning for "which ones did I empty" costs more than it
    protects. That scan does apply `_should_exclude_file`, though — an
    EXCLUDE_DIRS directory that happens to already be empty (e.g.
    project-integration/ before any consumer has written into it) must
    survive prune the same way its contents would, otherwise the "--prune
    cannot reach EXCLUDE_DIRS" guarantee only holds for non-empty ones. The
    scan also treats a symlink pointing at a directory as `is_dir()` (Python
    follows the link), but `rmdir()` on a symlink raises `NotADirectoryError`
    on POSIX; that and any other unexpected `OSError` (permission errors,
    races) are swallowed here rather than propagated, because by this point
    `overlay_copy` has already mutated the staging clone and letting an
    empty-directory cleanup error abort the whole push would leave that clone
    half-applied with no user-visible recovery step.
    """
    removed = 0
    for rel in diff["dst_only"]:
        target = dst / rel
        if target.is_file() or target.is_symlink():
            target.unlink(missing_ok=True)
            removed += 1

    if removed:
        directories = [p for p in dst.rglob("*") if p.is_dir()]
        for directory in sorted(directories, key=lambda p: len(p.parts), reverse=True):
            rel = directory.relative_to(dst).as_posix()
            if _should_exclude_file(rel):
                continue
            try:
                if not any(directory.iterdir()):
                    directory.rmdir()
            except OSError:
                continue

    return removed


def build_push_plan(diff: dict[str, list[str]], prune: bool) -> dict[str, list[str]]:
    """Fold the prune decision into the diff, producing a single plan.

    `print_diff_preview` and `prune_dst_only` previously each took `prune`
    (or a value derived from it) as a separate argument alongside `diff`,
    which meant every caller was responsible for keeping the two in sync by
    hand. `prunable` says exactly what will be deleted, so a caller that
    passes the plan around no longer needs to also thread a bool through.
    """
    plan = dict(diff)
    plan["prunable"] = list(diff["dst_only"]) if prune else []
    return plan


def _apply_prune(target: Path, plan: dict[str, list[str]]) -> int:
    """Delete `plan`'s prunable entries and report the result.

    Warns on stderr when the actual removed count diverges from what the
    preview promised (`len(plan["prunable"])`), so a partial deletion — e.g.
    a file the preview counted but a filesystem race already removed — is
    surfaced instead of being reported as if the full prune succeeded.
    """
    prunable = plan["prunable"]
    pruned = prune_dst_only(target, plan)
    if pruned != len(prunable):
        print(
            f"  [WARNING] pruned {pruned} file(s) but preview promised {len(prunable)}",
            file=sys.stderr,
        )
    print(f"  Pruned {pruned} remote-only file(s).")
    return pruned


def cmd_pull(args: argparse.Namespace) -> None:
    name: str = args.name
    force: bool = args.force
    repo_url = get_repo_url()
    skills_dir = get_skills_dir()
    target = skills_dir / name

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir) / "repo"
        print(f"Pulling skill '{name}' from {repo_url} ...")

        run_git(
            ["-c", "core.autocrlf=false", "clone", "--depth", "1", "--filter=blob:none", "--sparse", repo_url, str(tmp)]
        )
        run_git(["sparse-checkout", "set", f"{name}/"], cwd=tmp)

        source = tmp / name
        if not source.is_dir():
            print(f"Error: skill '{name}' not found in remote repo.", file=sys.stderr)
            sys.exit(1)

        skills_dir.mkdir(parents=True, exist_ok=True)

        diff = compute_diff(source, target)
        print("\n[Pull Preview]")
        _print_divergence_warning(
            target, compute_content_hash(target), compute_content_hash(source), "pull"
        )
        print_diff_preview(diff, direction="pull", src=source, dst=target)

        if not diff["added"] and not diff["modified"]:
            print(f"\n'{name}' is up to date.")
            _record_sync_base(target)
            return

        if diff["dst_only"]:
            print(f"\n  Note: {len(diff['dst_only'])} local-only file(s) will be preserved.")

        if not force:
            print("\n  Use --force to apply changes without confirmation.")
            try:
                answer = input("  Apply changes? [y/N] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                answer = ""
            if answer != "y":
                print("  Aborted.")
                return

        copied = overlay_copy(source, target, diff)
        _record_sync_base(target)
        print(f"\nPulled '{name}' to {target} ({copied} file(s) updated)")


def cmd_push(args: argparse.Namespace) -> None:
    name: str = args.name
    message: str = args.message or f"Update skill: {name}"
    force: bool = args.force
    prune: bool = getattr(args, "prune", False)
    repo_url = get_repo_url()
    skills_dir = get_skills_dir()
    source = skills_dir / name

    if not source.is_dir():
        print(f"Error: local skill '{name}' not found at {source}", file=sys.stderr)
        sys.exit(1)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir) / "repo"
        print(f"Pushing skill '{name}' to {repo_url} ...")

        # depth-1 full clone (not sparse) — push needs complete repo for git add/commit/push.
        # Sparse checkout would reduce download but git add -A behavior differs on sparse repos.
        run_git(["-c", "core.autocrlf=false", "clone", "--depth", "1", repo_url, str(tmp)])

        target = tmp / name

        # 閘門放在 clone 之後、overlay 之前：它要查的「這個 skill 是否已收錄於
        # 發佈庫的 versions.json」就在剛 clone 下來的 repo 根目錄裡，直接讀
        # 檔即可，不必自己再向遠端取一次。先前刻意把閘門放在 clone 之前是為了
        # 讓中止案例省下 push 的完整 clone，但那個順序讓「未宣告 portable 但有
        # 違規」這個最常走到的分支每次 push 都付兩趟網路往返（實測對發佈庫：
        # 閘門的 blobless sparse clone 約 1.98 秒 / 388 KB，push 本體的 depth-1
        # clone 約 4.78 秒 / 21.5 MB）。換取的代價是閘門真的中止時，省下的那次
        # clone 從較輕的一次變成較重的一次；中止屬使用者已宣告 portable 卻仍留
        # 著 consumer 路徑的錯誤路徑，不是每次 push 都會走的熱路徑，用熱路徑的
        # 一次往返去換錯誤路徑的一次往返划算。
        _report_portability(source, name, force, repo_dir=tmp)

        local_ver = _extract_single_version(source / "SKILL.md")
        remote_ver = _extract_single_version(target / "SKILL.md") if target.is_dir() else None
        if local_ver and remote_ver and local_ver != remote_ver:
            print(f"\n  [Version] local {local_ver} vs remote {remote_ver}")

        diff = compute_diff(source, target)
        plan = build_push_plan(diff, prune)
        print("\n[Push Preview]")
        local_content_hash = compute_content_hash(source)
        divergence_warned = _print_divergence_warning(
            source, local_content_hash, compute_content_hash(target), "push"
        )
        stale_version_warned = _print_stale_version_warning(source, local_ver, remote_ver)
        push_revert_warned = False
        # 只在推送方本地無合法 marker 時才查——有合法 marker 的路徑已由
        # _print_divergence_warning 的既有三態判定正確處理（見
        # _check_push_revert 說明），無謂重複查詢徒增每次 push 的成本。
        if _read_sync_base(source) is None and local_content_hash is not None:
            push_revert_commit = _check_push_revert(repo_url, name, local_content_hash)
            if push_revert_commit is not None:
                print(
                    "  [WARNING] Local content matches an older historical version "
                    f"of this skill (commit {push_revert_commit}), not genuinely "
                    "new — pushing may overwrite newer publish-repo content with a "
                    "stale copy.",
                    file=sys.stderr,
                )
                push_revert_warned = True
        banned_term_hits = scan_push_for_banned_terms(source, target, diff)
        if banned_term_hits:
            _print_banned_term_report(banned_term_hits)
        print_diff_preview(plan, direction="push", src=source, dst=target)

        prunable = plan["prunable"]
        # Deletions alone are a real change: without prunable in this guard,
        # `--prune` on an otherwise-identical skill would report "nothing to
        # push" and silently skip the deletions the flag was asked for.
        if not diff["added"] and not diff["modified"] and not prunable:
            print("\nNo changes to push.")
            _record_sync_base(source)
            return

        if prunable:
            print(f"\n  Note: {len(prunable)} remote-only file(s) will be DELETED (--prune).")
        elif diff["dst_only"]:
            print(f"\n  Note: {len(diff['dst_only'])} remote-only file(s) will be preserved (not deleted).")

        if not force:
            print("\n  Use --force to apply changes without confirmation.")
            try:
                answer = input("  Apply changes? [y/N] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                answer = ""
            if answer != "y":
                print("  Aborted.")
                return

        overlay_copy(source, target, diff)
        if prunable:
            _apply_prune(target, plan)

        run_git(["add", "-A"], cwd=tmp)

        status = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=tmp,
        )
        if status.returncode == 0:
            print("No changes to push.")
            _record_sync_base(source)
            return

        run_git(["commit", "-m", message], cwd=tmp)
        run_git(["push"], cwd=tmp)

        update_sync_manifest(tmp)
        _record_sync_base(source)

    print(f"\nPushed '{name}' to {repo_url}")

    # --force 拿掉了警告後緊接的 [y/N] 停點，使上面任何一道 [WARNING] 從
    # 「使用者必然讀到才能繼續」降級為「成功訊息前滾過去的幾行 stderr」——
    # 檢查本身沒有被跳過，變的是讀者處境。這裡在最終摘要重述被忽略的警告
    # 則數並落地 force-log，把降級的閱讀強制性至少部分找回來；未帶 --force
    # 或沒有警告產生時，這段完全不執行，不影響既有的安靜成功輸出。
    if force and (divergence_warned or stale_version_warned or push_revert_warned):
        ignored = int(divergence_warned) + int(stale_version_warned) + int(push_revert_warned)
        print(
            f"  [WARNING] --force ignored {ignored} direction warning(s) above "
            "— review them before assuming this push is safe.",
            file=sys.stderr,
        )
        _write_divergence_force_log(
            name, divergence_warned, stale_version_warned, push_revert_warned
        )


def _classify_sync_status(
    local_manifest: dict[str, dict[str, str]],
    remote_manifest: dict,
    skills_dir: Path,
    excluded_skills: Iterable[str] = (),
) -> tuple[
    list[str], list[tuple[str, str, str]], list[str], list[str], list[str], list[str]
]:
    """依內容雜湊分類本地 skill 相對 remote manifest 的同步狀態。

    回傳 (up_to_date, diverged, overridden, excluded_by_policy, skipped_no_hash,
    skipped_remote_missing)。雜湊相同 -> up_to_date；雜湊不同 -> diverged（覆蓋方向
    未知，需人工執行 pull/push 決定，見下方 rationale）；標記
    SKILL_SYNC_OVERRIDE_MARKER -> overridden（略過分歧判定）；名稱列於
    excluded_skills -> excluded_by_policy（呼叫端宣告此 skill 設計上不進遠端；本函式
    對專案層級的排除政策零知識，只接收呼叫端提供的一份現成清單，不自行判斷哪些
    skill 該排除）。excluded_by_policy 不併入 overridden——override 標記代表「本地
    內容刻意客製，遠端已有對應副本可比對」，excluded_by_policy 代表「遠端本不該有
    這個 skill，沒有可比對的對象」，兩者語意不同，合併會讓報告誤導讀者去比對一份
    不存在的遠端內容。remote 缺漏拆兩類，因盲區成因不同：remote_manifest 有此 key
    但值不是 dict 或缺 hash 欄位（舊格式 versions.json，需下次 push 後才會補上）->
    skipped_no_hash；remote_manifest 完全沒有此 key（該 skill 從未被記錄過，可能
    從未 push、或以非 push 途徑進入遠端目錄如手動複製）-> skipped_remote_missing。
    兩者對讀者意味不同的下一步（前者等下次 push 自動補；後者需先確認遠端是否該有
    這個 skill，再決定 push 或標註不推送理由），合併計數會讓讀者無從分辨該做什麼。

    excluded_skills 檢查排在最前面：政策排除是呼叫端的顯性宣告，優先於本模組
    自行判定的 override 標記與 remote 缺漏，一個名稱不會同時落入兩類。

    不再嘗試自動判定覆蓋方向：舊實作以 semver 大小決定「該推或該拉」，但這預設了
    線性演進，對分支式分歧（兩個獨立演化的副本巧合共用同一版本號）必定失準
    （0.2.1-W3-124 §11.2）。內容雜湊只能證明「相同或不同」，方向留給人工判斷。
    """
    excluded = frozenset(excluded_skills)
    up_to_date: list[str] = []
    diverged: list[tuple[str, str, str]] = []
    overridden: list[str] = []
    excluded_by_policy: list[str] = []
    skipped_no_hash: list[str] = []
    skipped_remote_missing: list[str] = []

    for name, local_entry in sorted(local_manifest.items()):
        if name in excluded:
            excluded_by_policy.append(name)
            continue

        if _has_local_override(skills_dir / name):
            overridden.append(name)
            continue

        if name not in remote_manifest:
            skipped_remote_missing.append(name)
            continue

        remote_entry = remote_manifest.get(name)
        if not isinstance(remote_entry, dict) or "hash" not in remote_entry:
            skipped_no_hash.append(name)
            continue

        if local_entry["hash"] == remote_entry["hash"]:
            up_to_date.append(name)
        else:
            local_display = local_entry.get("version") or local_entry["hash"][:8]
            remote_display = remote_entry.get("version") or remote_entry["hash"][:8]
            diverged.append((name, local_display, remote_display))

    return (
        up_to_date,
        diverged,
        overridden,
        excluded_by_policy,
        skipped_no_hash,
        skipped_remote_missing,
    )


def fetch_remote_manifest(repo_url: str) -> object:
    """Fetch versions.json for the given repo via a shallow, blob-less sparse clone.

    Previously read raw.githubusercontent.com directly. That path sits behind
    a CDN whose cache entry is created at push time and can keep serving the
    pre-push content for well over a minute afterwards (three real-world
    measurements against the publish repo: 158s / 0s / 308s, upper bound
    set by the CDN's own max-age=300 plus polling granularity) — a report run
    inside that window misclassifies a just-pushed skill as SHOULD PULL, and
    acting on that recommendation would overwrite the just-pushed content
    with the stale remote copy. The GitHub REST contents API is not a fix
    either: its response still carries `Cache-Control: max-age=60` (a
    shorter but non-zero staleness window, measured), and anonymous callers
    are additionally capped at 60 requests/hour — a ceiling a report command
    invoked more than once a minute (routine across a multi-agent session)
    can hit. `pull <name>` and `push <name>` already clone git directly for
    this same repo and have never exhibited this staleness: git's smart HTTP
    protocol resolves against the live ref on every request, with no CDN
    edge cache in front of it. This switches the report path onto that same
    mechanism instead of introducing a third one — repo/URL resolution for
    fetching the manifest still lives only here (see ARCH-BAL-016); cloning
    needs no URL derivation at all, `repo_url` is passed through unchanged.

    `versions.json` lives at the repository root, so the default cone-mode
    sparse pattern that `--sparse` alone applies (`/*` plus `!/*/`, meaning
    "root-level files, no subdirectories") already limits the checkout to
    it — unlike `pull <name>`, this needs no follow-up `sparse-checkout set`
    to narrow to a specific path.

    Raises `RuntimeError` on a non-zero git exit and
    `subprocess.TimeoutExpired` past `REMOTE_FETCH_TIMEOUT_SECONDS`. That
    bound is looser than the previous HTTP timeout: a clone takes longer
    than a single GET under ordinary network conditions (~1.8s vs ~0.5s,
    measured against the publish repo), and a bound sized for the old path
    would false-time-out on normal clone latency; it still keeps a
    black-holed connection from hanging a report command indefinitely.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir) / "repo"
        clone = subprocess.run(
            ["git", "-c", "core.autocrlf=false", "clone", "--depth", "1",
             "--filter=blob:none", "--sparse", repo_url, str(tmp)],
            capture_output=True, text=True, timeout=REMOTE_FETCH_TIMEOUT_SECONDS,
        )
        if clone.returncode != 0:
            raise RuntimeError(f"git clone failed: {clone.stderr.strip()}")
        versions_file = tmp / "versions.json"
        if not versions_file.is_file():
            return {}
        return json.loads(versions_file.read_text(encoding="utf-8"))


def sync_status_report(
    skills_dir: Path,
    repo_url: str | None = None,
    excluded_skills: Iterable[str] = (),
) -> SyncStatus:
    """Compare every installed skill against the remote manifest.

    This is the public entry point for consumers outside this CLI. It owns the
    whole path — repo resolution, fetch, classification — so a consumer needs
    exactly one call and cannot end up resolving the repo differently from the
    CLI itself.

    `excluded_skills` is an optional passthrough to `_classify_sync_status`:
    this module has no concept of a project-level "private" policy and never
    reads one on its own (it stays a dependency-free package installable
    outside any particular consumer's `.claude/` tree); a caller that has such
    a policy supplies the names here so they land in `excluded_by_policy`
    instead of `skipped_remote_missing`.

    Raises `ValueError` when the remote manifest is not a JSON object, and
    whatever `fetch_remote_manifest` raises when the remote is unreachable
    (`RuntimeError` on a git failure, `subprocess.TimeoutExpired` past
    `REMOTE_FETCH_TIMEOUT_SECONDS`). Callers decide how to degrade:
    `cmd_pull_all` reports and stops, an informational consumer may
    downgrade to a warning. Deciding that here would force one policy on both.
    """
    resolved_url = repo_url or get_repo_url()
    remote_manifest = fetch_remote_manifest(resolved_url)
    if not isinstance(remote_manifest, dict):
        raise ValueError(
            f"versions.json is {type(remote_manifest).__name__}, expected an object"
        )

    local_manifest = _extract_local_manifest(skills_dir)
    (
        up_to_date,
        diverged,
        overridden,
        excluded_by_policy,
        skipped_no_hash,
        skipped_remote_missing,
    ) = _classify_sync_status(
        local_manifest, remote_manifest, skills_dir, excluded_skills
    )
    diverged_skills: list[DivergedSkill] = []
    for name, local_display, remote_display in diverged:
        direction = _resolve_diverge_direction(
            _read_sync_base(skills_dir / name),
            local_manifest[name]["hash"],
            remote_manifest[name]["hash"],
        )
        suspect_revert_commit = None
        # 只對已判定為 "pull" 的候選額外查驗——多數健康報告（up_to_date、
        # 無分歧）與其餘方向不受這道加值檢查的執行成本影響，見
        # _check_suspect_revert 的成本說明。
        if direction == "pull":
            suspect_revert_commit = _check_suspect_revert(resolved_url, name)
            if suspect_revert_commit is not None:
                direction = "suspect_revert"
        diverged_skills.append(
            DivergedSkill(
                name=name,
                local=local_display,
                remote=remote_display,
                pull_command=f"skill-sync pull {name}",
                push_command=f"skill-sync push {name}",
                direction=direction,
                suspect_revert_commit=suspect_revert_commit,
            )
        )

    return SyncStatus(
        repo_url=resolved_url,
        remote_count=len(remote_manifest),
        up_to_date=up_to_date,
        diverged=diverged_skills,
        overridden=overridden,
        excluded_by_policy=excluded_by_policy,
        skipped_no_hash=skipped_no_hash,
        skipped_remote_missing=skipped_remote_missing,
    )


def _print_single_command_group(
    header: str, entries: list[DivergedSkill], command_attr: str
) -> None:
    """列印一組已知方向的分歧 skill，只帶該方向唯一需要的一條指令。"""
    print(f"\n{header}\n")
    for entry in entries:
        print(f"  {entry.name}: local({entry.local}) vs remote({entry.remote})")
        print(f"    -> {getattr(entry, command_attr)}")


def _print_dual_command_group(header: str, entries: list[DivergedSkill]) -> None:
    """列印一組方向未定的分歧 skill，兩條指令並列供人工比對後選擇。"""
    print(f"\n{header}\n")
    for entry in entries:
        print(f"  {entry.name}: local({entry.local}) vs remote({entry.remote})")
        print(f"    -> {entry.pull_command}   # inspect/take remote content")
        print(f"    -> {entry.push_command}   # inspect/send local content")


def _print_suspect_revert_group(entries: list[DivergedSkill]) -> None:
    """列印疑似回退的 skill：字面上是 "pull"（remote 移動過），但移動後的
    內容命中一個更舊的歷史提交，不是真正的前進。不直接建議 pull——與
    `_print_dual_command_group` 一樣兩條指令並列，多印一行命中的歷史 commit，
    供人工判斷這是刻意回退（如撤銷某次變更）還是意外事故（見
    `_check_suspect_revert`）。
    """
    print(
        f"\n[SUSPECT REVERT] {len(entries)} skill(s) — remote has moved, but its "
        "current content matches an older historical version rather than being "
        "genuinely new. Review before pulling:\n"
    )
    for entry in entries:
        print(f"  {entry.name}: local({entry.local}) vs remote({entry.remote})")
        print(f"    remote matches historical commit {entry.suspect_revert_commit}")
        print(f"    -> {entry.pull_command}   # inspect/take remote content")
        print(f"    -> {entry.push_command}   # inspect/send local content")


def cmd_pull_all(args: argparse.Namespace) -> None:
    """掃描本地已安裝 skill，以內容雜湊比對 versions.json，回報分歧供人工處理。

    --force 對此路徑無效：分歧不再自動套用（見 _classify_sync_status），每個分歧
    項目一律需個別執行 `skill-sync pull <name>` 或 `skill-sync push <name>` 決定方向。
    """
    skills_dir = get_skills_dir()

    try:
        status = sync_status_report(skills_dir)
    except Exception as e:
        print(f"Failed to read remote versions.json: {type(e).__name__}: {e}")
        print("Use 'skill-sync pull <name>' to work on a single skill instead.")
        return

    refreshed = _refresh_stale_sync_base(skills_dir, status.up_to_date)
    if refreshed:
        print(
            f"[OK] Refreshed {refreshed} stale '{SKILL_SYNC_BASE_MARKER}' marker(s) "
            "for already up-to-date skill(s)."
        )

    if not status.local_count:
        print("No local skills found.")
        return

    if not status.remote_count:
        print("versions.json is empty. Use 'skill-sync pull <name>' instead.")
        return

    if status.overridden:
        print(f"[OVERRIDE] {len(status.overridden)} skill(s) declared local override "
              f"(skipped from divergence check):")
        for name in status.overridden:
            print(f"  {name}")

    if status.skipped_no_hash:
        print(f"\n[SKIP] {len(status.skipped_no_hash)} skill(s) have a remote entry but no hash data yet "
              f"(remote versions.json needs regenerating via next 'skill-sync push'):")
        for name in status.skipped_no_hash:
            print(f"  {name}")

    if status.skipped_remote_missing:
        print(f"\n[SKIP] {len(status.skipped_remote_missing)} skill(s) have no remote entry at all "
              f"(never recorded in versions.json — confirm the remote should have this skill, "
              f"then 'skill-sync push <name>' or document why not):")
        for name in status.skipped_remote_missing:
            print(f"  {name}")

    if not status.diverged:
        print(f"\nAll {len(status.up_to_date)} checked skill(s) are up to date.")
        return

    # 依 direction 分成五組：有 sync base 記錄的三態可給出明確建議，
    # "suspect_revert" 是 "pull" 的子集但另設分類（見 _check_suspect_revert），
    # "unknown"（無 base 記錄的既有 skill）維持現行「方向未知，需人工判斷」輸出。
    should_pull = [e for e in status.diverged if e.direction == "pull"]
    should_push = [e for e in status.diverged if e.direction == "push"]
    conflicts = [e for e in status.diverged if e.direction == "conflict"]
    unresolved = [e for e in status.diverged if e.direction == "unknown"]
    suspect_reverts = [e for e in status.diverged if e.direction == "suspect_revert"]

    if should_pull:
        _print_single_command_group(
            f"[SHOULD PULL] {len(should_pull)} skill(s) — local unchanged since last "
            "sync, remote has moved on:",
            should_pull, "pull_command",
        )
    if should_push:
        _print_single_command_group(
            f"[SHOULD PUSH] {len(should_push)} skill(s) — remote unchanged since last "
            "sync, local has moved on:",
            should_push, "push_command",
        )
    if conflicts:
        _print_dual_command_group(
            f"[CONFLICT] {len(conflicts)} skill(s) diverged from both sides since last "
            "sync — review and resolve manually:",
            conflicts,
        )
    if unresolved:
        _print_dual_command_group(
            f"[DIVERGED] {len(unresolved)} skill(s) differ from remote by content. "
            "Direction unknown from hash alone — review and resolve manually:",
            unresolved,
        )
    if suspect_reverts:
        _print_suspect_revert_group(suspect_reverts)

    if status.up_to_date:
        print(f"\n{len(status.up_to_date)} other skill(s) are up to date.")


def _extract_single_version(skill_md: Path) -> str | None:
    """從單一 SKILL.md 提取版本號（僅供人類顯示，不進入同步判定）。"""
    if not skill_md.is_file():
        return None
    try:
        text = skill_md.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    return _extract_version_string(text)


def _extract_local_manifest(skills_dir: Path) -> dict[str, dict[str, str]]:
    """掃描本地 skills/*，回傳每個 skill 的內容雜湊（同步判定用）與版本字串（人類顯示用）。"""
    manifest: dict[str, dict[str, str]] = {}
    if not skills_dir.is_dir():
        return manifest
    _warn_skill_md_case_mismatch(skills_dir)
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        skill_dir = skill_md.parent
        content_hash = compute_content_hash(skill_dir)
        if content_hash is None:
            continue
        entry: dict[str, str] = {"hash": content_hash}
        try:
            text = skill_md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            text = ""
        version = _extract_version_string(text)
        if version:
            entry["version"] = version
        manifest[skill_dir.name] = entry
    return manifest


def cmd_list(args: argparse.Namespace) -> None:
    repo_url = get_repo_url()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir) / "repo"
        run_git(
            ["-c", "core.autocrlf=false", "clone", "--depth", "1", "--filter=blob:none", "--sparse", repo_url, str(tmp)]
        )
        run_git(["sparse-checkout", "set", "--no-cone", "*/SKILL.md"], cwd=tmp)

        result = run_git(["ls-tree", "--name-only", "HEAD"], cwd=tmp)
        dirs = [line for line in result.stdout.strip().splitlines() if line]

        if not dirs:
            print("No skills found in remote repo.")
            return

        print(f"{'Skill':<30} Description")
        print(f"{'-----':<30} -----------")

        for d in sorted(dirs):
            skill_md = tmp / d / "SKILL.md"
            desc = ""
            if skill_md.is_file():
                for line in skill_md.read_text(encoding="utf-8").splitlines():
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#"):
                        desc = stripped[:70]
                        break
            print(f"{d:<30} {desc}")


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser.

    Separated from main() so callers can inspect the available subcommands and
    flags without executing anything — consumers that print "run skill-sync X"
    guidance can assert X exists instead of the string silently going stale
    (0.2.1-W3-351: sync-claude-push advertised a `pull-all` subcommand that
    never existed).
    """
    parser = argparse.ArgumentParser(
        prog="skill-sync",
        description="Sync Claude Code skills with a remote repository.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    pull_parser = sub.add_parser(
        "pull",
        help="Pull a skill from remote repo, or print a sync status report for "
             "all installed skills (omit name)",
    )
    pull_parser.add_argument(
        "name", nargs="?", default=None,
        help="Skill name to pull (omit to print a sync status report for all "
             "installed skills instead; report only — writes nothing except "
             "refreshing a stale '.skill-sync-base' marker for a skill "
             "already up to date)",
    )
    pull_parser.add_argument("--force", "-f", action="store_true",
                             help="Apply changes without confirmation")

    push_parser = sub.add_parser("push", help="Push a local skill to remote repo")
    push_parser.add_argument("name", help="Skill name to push")
    push_parser.add_argument("-m", "--message", help="Commit message", default=None)
    push_parser.add_argument("--force", "-f", action="store_true",
                             help="Apply changes without confirmation; also bypasses the "
                                  "portability gate for a declared-portable skill (violations "
                                  "are still printed to stdout/stderr and logged); and removes "
                                  "the confirmation stop that would otherwise follow a direction "
                                  "or stale-version [WARNING] (the checks still run and still "
                                  "print, but a summary line and force-log entry are the only "
                                  "things left demanding you actually read them)")
    push_parser.add_argument("--prune", action="store_true",
                             help="Delete remote-only files (default: keep them)")

    sub.add_parser("list", help="List available skills in remote repo")
    return parser


def main() -> None:
    args = build_parser().parse_args()

    if args.command == "pull" and args.name is None:
        cmd_pull_all(args)
    else:
        commands = {
            "pull": cmd_pull,
            "push": cmd_push,
            "list": cmd_list,
        }
        commands[args.command](args)


if __name__ == "__main__":
    main()
