"""同檔競爭計數：近期有幾棵不同票樹修改過某檔。

判準來源：`.claude/skills/cognitive-load-assessment/references/file-split-by-contention.md`
  - §1 量法：`git log --no-merges --name-only`，以 commit 主旨票號取票樹根
  - §2 門檻：>= 3 棵不同票樹；同一票樹的連續修改只算一棵（以根計數）
  - §4 聚合檔：不以職責拆分處理，僅註明

票樹根 = 票號第一段（版本-波次-序號，不含 `.N` 子序號）。`chore(` 開頭的
commit 是票面中繼（claim／append-log 等）而非實作修改，排除。
"""

from __future__ import annotations

import fnmatch
import re
import subprocess
from pathlib import PurePosixPath
from typing import Dict, Iterable, List, Optional, Set

DEFAULT_SINCE_DAYS = 14
SPLIT_THRESHOLD = 3
MIN_CONTENTION_TREES = 2  # 1 棵票樹依定義不是競爭，table 不列
GIT_TIMEOUT_SECONDS = 30

AGGREGATE_NOTE = "聚合檔，不以職責拆分"

# 聚合檔判定（file-split-by-contention.md §4）：集中於此，新增類型只改這裡
AGGREGATE_BASENAMES = frozenset({
    "settings.json",
    "settings.local.json",
    "CHANGELOG.md",
    "todolist.yaml",
    "topic-assignments.txt",
})
AGGREGATE_BASENAME_PATTERNS = (
    "*registry*.json",
    "*index*.json",
    "*index*.md",
    "*index*.yaml",
)
# 版本日誌：docs/work-logs/v{version}/ 直接子層的 md（tickets/ 下的票面不算）
VERSION_LOG_PATTERN = "docs/work-logs/v*/*.md"

_COMMIT_MARK = "\x01"
_TICKET_ROOT_RE = re.compile(r"\d+\.\d+\.\d+-W\d+-\d+")
_META_SUBJECT_PREFIX = "chore("


class ContentionUnavailable(Exception):
    """git 不可用或 log 失敗；呼叫端略過競爭訊號並於 stderr 說明。"""


def is_aggregate_file(path: str) -> bool:
    """是否為聚合檔（競爭是結構性的，不建議職責拆分）。"""
    posix = PurePosixPath(path)
    name = posix.name
    if name in AGGREGATE_BASENAMES:
        return True
    if any(fnmatch.fnmatch(name, p) for p in AGGREGATE_BASENAME_PATTERNS):
        return True
    return fnmatch.fnmatch(str(posix), VERSION_LOG_PATTERN) and len(posix.parts) == 4


def ticket_tree_root(subject: str) -> Optional[str]:
    """由 commit 主旨取票樹根；無票號或為票面中繼 commit 回傳 None。"""
    if subject.startswith(_META_SUBJECT_PREFIX):
        return None
    match = _TICKET_ROOT_RE.search(subject)
    return match.group(0) if match else None


def parse_log(output: str) -> Dict[str, Set[str]]:
    """解析 `--format=%x01%s --name-only` 輸出為 {檔案: {票樹根}}。"""
    roots_by_file: Dict[str, Set[str]] = {}
    current_root: Optional[str] = None
    for line in output.splitlines():
        if line.startswith(_COMMIT_MARK):
            current_root = ticket_tree_root(line[len(_COMMIT_MARK):])
        elif line.strip() and current_root:
            roots_by_file.setdefault(line.strip(), set()).add(current_root)
    return roots_by_file


def collect_tree_roots(
    project_root: str, since_days: int = DEFAULT_SINCE_DAYS
) -> Dict[str, Set[str]]:
    """跑 git log 回傳 {檔案: {票樹根}}；失敗拋 ContentionUnavailable。"""
    cmd = [
        "git", "-C", str(project_root), "log", f"--since={since_days}.days",
        "--no-merges", f"--format={_COMMIT_MARK}%s", "--name-only",
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=GIT_TIMEOUT_SECONDS
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ContentionUnavailable(f"git 無法執行：{exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or "").strip().splitlines()[:1]
        raise ContentionUnavailable(
            f"git log 失敗（exit {result.returncode}）{detail[0] if detail else ''}"
        )
    return parse_log(result.stdout)


def split_matched_entry(entry: str) -> List[str]:
    """conflict.matched_files 的項目可能是 `a ~ b`，拆成個別路徑。"""
    return [p.strip() for p in entry.split(" ~ ") if p.strip()]


def contention_for_files(
    paths: Iterable[str], roots_by_file: Dict[str, Set[str]], since_days: int
) -> List[Dict[str, object]]:
    """對每個路徑產生競爭記錄；近期無票樹修改的路徑略過。"""
    records: List[Dict[str, object]] = []
    for path in sorted(set(paths)):
        roots = roots_by_file.get(path)
        if not roots:
            continue
        aggregate = is_aggregate_file(path)
        records.append({
            "file": path,
            "tree_count": len(roots),
            "since_days": since_days,
            "aggregate": aggregate,
            "suggest_split": len(roots) >= SPLIT_THRESHOLD and not aggregate,
        })
    return records


def render_contention_lines(records: List[Dict[str, object]]) -> List[str]:
    """渲染為表格輸出的附加行；只列票樹數達 MIN_CONTENTION_TREES 的記錄。"""
    lines: List[str] = []
    for r in records:
        if r["tree_count"] < MIN_CONTENTION_TREES:
            continue
        lines.append(
            f"  [競爭] {r['file']}: 近 {r['since_days']} 天被 {r['tree_count']} 棵票樹修改"
        )
        if r["aggregate"]:
            lines.append(f"    （{AGGREGATE_NOTE}）")
        elif r["suggest_split"]:
            lines.append(
                f"    建議拆分：>= {SPLIT_THRESHOLD} 棵票樹改同一檔，先建拆分評估票"
                "（.claude/skills/cognitive-load-assessment/references/file-split-by-contention.md）"
            )
    return lines
