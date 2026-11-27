"""比對本地與上游 error-patterns 樹，分類待回報狀態（純函式，不讀網路）。

狀態定義唯一處：.claude/skills/framework-issue/references/content-intake-request.md
〈收錄方處置〉。比對鍵是檔名中的 pattern ID。
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

_ID_RE = re.compile(r"^([A-Z]+(?:-[A-Z][A-Z0-9]*)*-\d+)")
_ISSUE_RE = re.compile(r"^upstream_issue:\s*#?(\d+)\s*$", re.MULTILINE)
_INTAKE_SCRIPT = ".claude/skills/error-pattern/lib/intake_draft.py"
_PATTERN_ROOT = ".claude/error-patterns"


@dataclass
class UpstreamStatus:
    installed: int = 0
    reported: list = field(default_factory=list)  # (id, issue 號)
    pending: list = field(default_factory=list)  # (id, 本地路徑)
    differing: list = field(default_factory=list)  # (id, 本地路徑)


def _index(root: Path) -> dict:
    """ID -> 檔案路徑；非 pattern 檔（README、registry）無 ID，略過。"""
    found = {}
    if not root.is_dir():
        return found
    for path in sorted(root.rglob("*.md")):
        match = _ID_RE.match(path.name)
        if match:
            found.setdefault(match.group(1), path)
    return found


def _upstream_issue(path: Path):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    match = _ISSUE_RE.search(parts[1])
    return match.group(1) if match else None


def classify(local_root: Path, upstream_root: Path) -> UpstreamStatus:
    status = UpstreamStatus()
    upstream = _index(upstream_root)
    for pattern_id, path in _index(local_root).items():
        if pattern_id in upstream:
            if path.read_bytes() == upstream[pattern_id].read_bytes():
                status.installed += 1
            else:
                status.differing.append((pattern_id, path))
            continue
        issue = _upstream_issue(path)
        if issue:
            status.reported.append((pattern_id, issue))
        else:
            status.pending.append((pattern_id, path))
    return status


def format_summary_lines(status: UpstreamStatus) -> list:
    """摘要行；待回報、同號不同內容、已回報皆空（已收錄不列）回傳空清單。"""
    lines = []
    if status.pending:
        lines.append(f"待回報 error-pattern（{len(status.pending)} 則，本地獨有且無 upstream_issue）：")
        for pattern_id, path in status.pending:
            rel = f"{_PATTERN_ROOT}/{path.parent.name}/{path.name}"
            lines.append(f"  - {pattern_id}：uv run --script {_INTAKE_SCRIPT} {rel}")
    if status.differing:
        lines.append(f"同號不同內容 error-pattern（{len(status.differing)} 則，需人工判斷以哪邊為準）：")
        lines.extend(f"  - {pattern_id}（同號不同內容）" for pattern_id, _ in status.differing)
    if status.reported:
        issues = "、".join(f"#{issue}" for _, issue in status.reported)
        lines.append(f"已回報 error-pattern：{len(status.reported)} 則（issue {issues}）")
    return lines
