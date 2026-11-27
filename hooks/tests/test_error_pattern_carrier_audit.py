"""error-pattern carrier 欄位檢查腳本測試。

carrier_audit 位於 .claude/skills/error-pattern/lib/carrier_audit.py；
測試借 hooks pytest env 執行（比照 test_error_pattern_severity_audit.py）。
以 tmp_path 建假的 rules／skills／agents／patterns。
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

from carrier_audit import audit, format_report, main  # noqa: E402


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _pattern(root, pid, carrier):
    carrier_line = f"carrier: {carrier}\n" if carrier is not None else ""
    _write(
        root / "error-patterns" / "process-compliance" / f"{pid}-x.md",
        f"---\nid: {pid}\ntitle: t\ncategory: process-compliance\n{carrier_line}---\n\n# {pid}\n",
    )


def _kinds(result):
    return {(f.pattern_id, f.kind) for f in result}


def test_missing_route_is_listed_positive_control(tmp_path):
    """E2：carrier 指向不含 ID 的載體，必須被列出。"""
    _pattern(tmp_path, "PC-900", "skill:foo")
    _write(tmp_path / "skills" / "foo" / "SKILL.md", "no route here")
    assert ("PC-900", "no_route") in _kinds(audit(tmp_path))


def test_route_present_is_clean(tmp_path):
    _pattern(tmp_path, "PC-901", "skill:foo")
    _write(tmp_path / "skills" / "foo" / "SKILL.md", "see PC-901 for details")
    assert audit(tmp_path) == []


def test_invalid_value_listed(tmp_path):
    _pattern(tmp_path, "PC-902", "bogus")
    assert ("PC-902", "invalid") in _kinds(audit(tmp_path))


def test_missing_target_listed(tmp_path):
    _pattern(tmp_path, "PC-903", "agent:ghost")
    assert ("PC-903", "missing_target") in _kinds(audit(tmp_path))


def test_none_and_absent_skipped(tmp_path):
    _pattern(tmp_path, "PC-904", "none")
    _pattern(tmp_path, "PC-905", None)
    assert audit(tmp_path) == []


def test_rule_any_file_and_lang_pack(tmp_path):
    _pattern(tmp_path, "PC-906", "rule")
    _write(tmp_path / "pm-rules" / "a.md", "PC-906")
    _pattern(tmp_path, "PC-907", "lang-pack:bar/python")
    _write(tmp_path / "skills" / "bar" / "references" / "python.md", "PC-907")
    assert audit(tmp_path) == []


def test_main_exit_codes(tmp_path):
    _pattern(tmp_path, "PC-908", "agent:ghost")
    assert main(["--claude-dir", str(tmp_path)]) == 1
    _pattern(tmp_path, "PC-908", "none")
    assert main(["--claude-dir", str(tmp_path)]) == 0
    assert "PC-908" not in format_report([])
