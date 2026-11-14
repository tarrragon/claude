"""rule8 存量全樹掃描報告（3.3.0-W1-203.2）。

缺陷：rule8 守衛與 commit 守衛只看新增行，導入前就存在的命中沒有任何通道可見。
修復：以守衛自身的判定函式對 tracked `.claude/` 全樹掃描，依目錄分組報告；只報告、不阻擋。
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "rule8-stock-report.py"
_spec = importlib.util.spec_from_file_location("rule8_stock_report", SCRIPT)
report = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(report)

HIT_ID = "0.2.1-W3-777"
FILES = {
    # 正向對照：未豁免命中，應列入
    ".claude/references/a.md": f"引用 {HIT_ID} 的結論。\n",
    ".claude/rules-note.md": f"根目錄檔引用 {HIT_ID}。\n",
    # 以下皆不應列入
    ".claude/references/marker.md": f"rule8-exempt: illustration:示範\n引用 {HIT_ID}。\n",
    ".claude/references/fence.md": f"```\n{HIT_ID}\n```\n",
    ".claude/hooks/tests/test_x.py": f"ID = '{HIT_ID}'\n",
    ".claude/handoff/archive/old.md": f"{HIT_ID}\n",
    ".claude/references/clean.md": "日期 2026-01-01 與 PC-001 不是專案 ID。\n",
    "docs/outside.md": f"{HIT_ID}\n",
}


def _git(args, cwd):
    subprocess.run(["git"] + args, cwd=str(cwd), check=True, capture_output=True)


@pytest.fixture()
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _git(["init", "-q"], root)
    for rel, text in FILES.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    (root / ".claude/references/untracked.md").write_text(f"{HIT_ID}\n", encoding="utf-8")
    _git(["add", "--", *FILES], root)
    return root


def _run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, timeout=120
    )


def test_lists_only_unexempted_hits_grouped_by_dir(repo):
    result = _run("--root", str(repo))
    assert result.returncode == 0, result.stderr
    out = result.stdout
    # 守衛對版本化 ID 同時命中完整形與裸形（W3-777），每檔 2 個 ID；與守衛現行計數一致
    assert "受掃檔 5｜有未豁免命中的檔 2｜ID 總數 4｜豁免路徑 1" in out
    assert f"- .claude/references/a.md: {HIT_ID}, W3-777" in out
    assert f"- .claude/rules-note.md: {HIT_ID}, W3-777" in out
    assert "## references" in out and "## (根目錄)" in out
    for excluded in ("marker.md", "fence.md", "test_x.py", "old.md", "clean.md", "untracked.md", "outside.md"):
        assert excluded not in out


def test_summary_omits_per_file_detail(repo):
    result = _run("--root", str(repo), "--summary")
    assert result.returncode == 0
    assert "references: 1 檔 / 2 個 ID" in result.stdout
    assert "- .claude/references/a.md" not in result.stdout


def test_report_does_not_modify_files(repo):
    def _status():
        return subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True
        ).stdout

    before = ({rel: (repo / rel).read_text(encoding="utf-8") for rel in FILES}, _status())
    _run("--root", str(repo))
    after = ({rel: (repo / rel).read_text(encoding="utf-8") for rel in FILES}, _status())
    assert after == before


def test_non_git_root_fails_visibly(tmp_path):
    result = _run("--root", str(tmp_path))
    assert result.returncode == 1
    assert "git ls-files 失敗" in result.stderr


def test_group_key():
    assert report.group_key(".claude/skills/x/y.py") == "skills"
    assert report.group_key(".claude/settings.json") == "(根目錄)"
