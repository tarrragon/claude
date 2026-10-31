"""套件宣告 changed_files：只把本次改動且仍存在的符合檔附加到 argv。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import merge_gate as mg  # noqa: E402

DECL = """\
suites:
  dart-format:
    prefixes: [lib/, test/]
    command: [fvm, dart, format, --set-exit-if-changed]
    changed_files: '\\.dart$'
  plain:
    prefixes: [lib/]
    command: [echo, plain]
"""


@pytest.fixture
def snap(tmp_path):
    root = tmp_path / "snap"
    (root / ".claude/project-integration").mkdir(parents=True)
    (root / mg.DECLARATION_PATH).write_text(DECL)
    for rel in ("lib/a.dart", "lib/b.dart", "lib/note.txt", "docs/x.dart"):
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("x")
    return str(root)


def run(snap, suites, paths, rc=0, out="", capsys=None):
    calls = []

    def runner(argv, cwd):
        calls.append(argv[argv.index("--") + 1:])
        return rc, out

    reason = mg._run_suites(suites, snap, snap, runner, snap, paths=paths)
    return reason, calls


class TestChangedFilesScope:
    def test_non_matching_change_does_not_select_suite(self, snap):
        assert "dart-format" not in mg.select_suites(["lib/note.txt"], snap)

    def test_matching_change_selects_suite(self, snap):
        assert "dart-format" in mg.select_suites(["lib/a.dart"], snap)

    def test_match_outside_prefixes_does_not_select(self, snap):
        assert mg.select_suites(["docs/x.dart"], snap) == []

    def test_invalid_pattern_fails_closed(self):
        with pytest.raises(mg.DeclarationError, match="changed_files"):
            mg.parse_declaration("suites:\n  s:\n    prefixes: [lib/]\n    command: [x]\n    changed_files: '('\n")


class TestChangedFilesArgv:
    def test_matching_existing_files_appended(self, snap):
        reason, calls = run(snap, ["dart-format"], ["lib/a.dart", "lib/note.txt", "lib/b.dart"])
        assert reason == ""
        assert calls == [["fvm", "dart", "format", "--set-exit-if-changed", "lib/a.dart", "lib/b.dart"]]

    def test_deleted_file_excluded(self, snap):
        _, calls = run(snap, ["dart-format"], ["lib/a.dart", "lib/gone.dart"])
        assert calls[0][-1] == "lib/a.dart" and "lib/gone.dart" not in calls[0]

    def test_only_deleted_skips_with_notice(self, snap, capsys):
        reason, calls = run(snap, ["dart-format"], ["lib/gone.dart"])
        assert reason == "" and calls == []
        out = capsys.readouterr().out
        assert "免跑" in out and "dart-format" in out and "綠燈" not in out

    def test_format_violation_is_red(self, snap):
        """E2 正向對照：格式不符（假 runner 回 rc=1）必須判紅。"""
        reason, calls = run(snap, ["dart-format"], ["lib/a.dart"], rc=1, out="Changed lib/a.dart\n")
        assert reason != "" and calls

    def test_suite_without_changed_files_argv_unchanged(self, snap):
        """E1 對照：未宣告 changed_files 的套件 argv 不附加改動檔。"""
        _, calls = run(snap, ["plain"], ["lib/a.dart"])
        assert calls == [["echo", "plain"]]
