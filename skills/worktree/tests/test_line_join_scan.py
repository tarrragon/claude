"""接行偵測（IMP-LLM-013）：E2 正向對照（3.3.0 四種接行形態）與不該報的正常改動。"""
import difflib
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import line_join_scan as ljs  # noqa: E402
import merge_gate as mg  # noqa: E402


def diff_of(path, old, new):
    lines = difflib.unified_diff(old.splitlines(), new.splitlines(), f"a/{path}", f"b/{path}", n=0, lineterm="")
    return "\n".join(lines)


def scan(path, old, new):
    return ljs.scan_diff(diff_of(path, old, new))


# 3.3.0 的 4 處實例形態（清理行尾票號引用時 Edit 吞掉換行）：清單項、Version 行、表格列、.py 註解併程式行
JOINED_CASES = {
    "markdown 清單項": (
        "- 項目一 (3.3.0-W1-225.3)\n- 項目二\n- 項目三\n",
        "- 項目一- 項目二\n- 項目三\n"),
    "Version 行": (
        "**Version**: 1.0.0 — 說明 W1-009\n**Version**: 0.9.0 — 舊說明\n",
        "**Version**: 1.0.0 — 說明**Version**: 0.9.0 — 舊說明\n"),
    "表格列": (
        "| a | b | 225 |\n| c | d | e |\n",
        "| a | b || c | d | e |\n"),
    "py 註解併程式行": (
        "    # 取得根目錄 W1-009\n    root = compute_root()\n    use(root)\n",
        "    # 取得根目錄    root = compute_root()\n    use(root)\n"),
}


class TestAdjacentJoin:
    @pytest.mark.parametrize("name", JOINED_CASES)
    def test_positive_control_reports(self, name):
        old, new = JOINED_CASES[name]
        found = scan("f.md", old, new)
        assert [f.kind for f in found] == ["join"], name

    def test_normal_edit_not_reported(self):
        assert scan("f.md", "- 項目一 (W1-9)\n- 項目二\n", "- 項目一\n- 項目二\n") == []

    def test_deleting_whole_line_not_reported(self):
        assert scan("f.md", "a\nb\nc\n", "a\nc\n") == []

    def test_shared_blank_and_short_not_reported(self):
        assert scan("f.md", "x\n\ny\n", "x\ny\n") == []


OLD_PY = 'def f():\n    # 說明 W1-009\n    root = compute_root()\n    return root\n'


class TestPyStructure:
    def test_code_swallowed_by_comment_reported(self):
        new = 'def f():\n    # 說明root = compute_root()\n    return root\n'
        found = ljs.scan_py_pair("m.py", OLD_PY, new)
        assert [f.kind for f in found] == ["py-comment"]

    def test_syntax_broken_reported(self):
        new = 'def f():\n    # 說明 root = compute_root()\n    return root\n  x = (\n'
        assert [f.kind for f in ljs.scan_py_pair("m.py", OLD_PY, new)] == ["py-syntax"]

    def test_comment_only_change_not_reported(self):
        new = OLD_PY.replace("說明 W1-009", "說明")
        assert ljs.scan_py_pair("m.py", OLD_PY, new) == []

    def test_string_only_change_not_reported(self):
        old = 'def f():\n    return "rule W1-009 hit"\n'
        new = 'def f():\n    return "rule hit"\n'
        assert ljs.scan_py_pair("m.py", old, new) == []

    def test_real_code_deletion_not_reported(self):
        new = 'def f():\n    # 說明 W1-009\n    return 1\n'
        assert ljs.scan_py_pair("m.py", OLD_PY, new) == []


def git(repo, *args):
    proc = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


@pytest.fixture
def repo(tmp_path):
    r = str(tmp_path)
    git(r, "init", "-q")
    git(r, "config", "user.email", "t@t")
    git(r, "config", "user.name", "t")
    return r


def commit_file(repo, name, text):
    (Path(repo) / name).write_text(text)
    git(repo, "add", name)
    git(repo, "commit", "-qm", "c")
    return git(repo, "rev-parse", "HEAD")


class TestGateWiring:
    def test_scan_range_finds_join_and_py(self, repo):
        commit_file(repo, "m.py", OLD_PY)
        old = commit_file(repo, "a.md", JOINED_CASES["markdown 清單項"][0])
        commit_file(repo, "a.md", JOINED_CASES["markdown 清單項"][1])
        new = commit_file(repo, "m.py", 'def f():\n    # 說明root = compute_root()\n    return root\n')
        found = ljs.scan_range(repo, old, new)
        assert {(f.path, f.kind) for f in found} == {("a.md", "join"), ("m.py", "join"), ("m.py", "py-comment")}

    def test_gate_warns_but_still_passes(self, repo, capsys):
        old = commit_file(repo, "a.md", JOINED_CASES["markdown 清單項"][0])
        new = commit_file(repo, "a.md", JOINED_CASES["markdown 清單項"][1])
        gate = mg.MergeGate(repo, runner=lambda argv, cwd: (0, ""), periodic=None)
        result = gate(new, "main", old, 1)
        out = capsys.readouterr()
        assert result.passed is True  # 預設只警告，不阻擋
        assert "[合併前掃描] WARNING" in out.out and "a.md" in out.out

    def test_clean_diff_no_warning(self, repo, capsys):
        old = commit_file(repo, "a.md", "- x (W1-9)\n- y\n")
        new = commit_file(repo, "a.md", "- x\n- y\n")
        mg.MergeGate(repo, runner=lambda argv, cwd: (0, ""), periodic=None)(new, "main", old, 1)
        assert "[合併前掃描]" not in capsys.readouterr().out

    def test_unexpected_exception_does_not_break_gate(self, repo, monkeypatch, capsys):
        old = commit_file(repo, "a.md", "x\n")
        new = commit_file(repo, "a.md", "y\n")

        def boom(*_a):
            raise IndexError("scan bug")

        monkeypatch.setattr(ljs, "scan_range", boom)
        gate = mg.MergeGate(repo, runner=lambda argv, cwd: (0, ""), periodic=None)
        result = gate(new, "main", old, 1)
        assert result.passed is True
        assert "scan bug" in capsys.readouterr().err

    def test_off_switch(self, repo, monkeypatch):
        monkeypatch.setenv(ljs.SCAN_ENV, "off")
        old = commit_file(repo, "a.md", JOINED_CASES["markdown 清單項"][0])
        new = commit_file(repo, "a.md", JOINED_CASES["markdown 清單項"][1])
        assert ljs.warn_on_range(repo, old, new) == []
