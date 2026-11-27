"""error-pattern 上游狀態比對測試（3.6.0-W1-352.2）。

upstream_status 位於 .claude/skills/error-pattern/lib/upstream_status.py；
以 tmp_path 建本地與上游兩棵 error-patterns 樹。
"""

import sys
from pathlib import Path

_skill_lib = (
    Path(__file__).resolve().parent.parent.parent
    / "skills"
    / "error-pattern"
    / "lib"
)
if str(_skill_lib) not in sys.path:
    sys.path.insert(0, str(_skill_lib))

from upstream_status import classify, format_summary_lines  # noqa: E402


def _write(root, category, name, body="內容\n", issue=None):
    path = root / category / name
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = f"---\nid: x\nupstream_issue: {issue}\n---\n" if issue else "---\nid: x\n---\n"
    path.write_text(fm + body, encoding="utf-8")
    return path


def _trees(tmp_path):
    local, upstream = tmp_path / "local", tmp_path / "upstream"
    local.mkdir()
    upstream.mkdir()
    return local, upstream


def test_installed_same_content_not_listed(tmp_path):
    local, upstream = _trees(tmp_path)
    _write(local, "process-compliance", "PC-ZZZ-001-a.md")
    _write(upstream, "process-compliance", "PC-ZZZ-001-a.md")
    status = classify(local, upstream)
    assert status.installed == 1
    assert not status.pending and not status.reported and not status.differing
    assert format_summary_lines(status) == []


def test_same_id_different_content_listed_separately(tmp_path):
    """E2 正向對照：同號不同內容必須落入 differing，不得被當成已收錄。"""
    local, upstream = _trees(tmp_path)
    _write(local, "process-compliance", "PC-ZZZ-002-a.md", body="本地版\n")
    _write(upstream, "process-compliance", "PC-ZZZ-002-b.md", body="上游版\n")
    status = classify(local, upstream)
    assert status.installed == 0
    assert [i for i, _ in status.differing] == ["PC-ZZZ-002"]
    assert not status.pending
    assert any("同號不同內容" in l and "PC-ZZZ-002" in l for l in format_summary_lines(status))


def test_reported_only_count_and_issue_numbers(tmp_path):
    local, upstream = _trees(tmp_path)
    _write(local, "implementation", "IMP-ZZZ-003-a.md", issue=77)
    _write(local, "implementation", "IMP-ZZZ-004-a.md", issue=78)
    status = classify(local, upstream)
    lines = format_summary_lines(status)
    assert len(lines) == 1
    assert "2" in lines[0] and "#77" in lines[0] and "#78" in lines[0]
    assert "IMP-ZZZ-003" not in lines[0]


def test_pending_listed_per_pattern_with_command(tmp_path):
    local, upstream = _trees(tmp_path)
    _write(local, "implementation", "IMP-ZZZ-005-a.md")
    _write(local, "implementation", "IMP-ZZZ-006-a.md")
    status = classify(local, upstream)
    text = "\n".join(format_summary_lines(status))
    assert "IMP-ZZZ-005" in text and "IMP-ZZZ-006" in text
    assert text.count("intake_draft.py") == 2
    assert ".claude/error-patterns/implementation/IMP-ZZZ-005-a.md" in text


def test_non_pattern_files_ignored(tmp_path):
    local, upstream = _trees(tmp_path)
    (local / "README.md").write_text("x", encoding="utf-8")
    (local / "_project-registry.yaml").write_text("x", encoding="utf-8")
    status = classify(local, upstream)
    assert not status.pending and status.installed == 0
