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
    assert f"- .claude/references/a.md: {HIT_ID} (L1), W3-777 (L1)" in out
    assert f"- .claude/rules-note.md: {HIT_ID} (L1), W3-777 (L1)" in out
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


def test_path_track_listed_separately_from_ticket_ids(tmp_path):
    """E1 對照：同一檔含兩類命中，ticket ID 軌與專案路徑軌各自列出；ID 軌計數不含路徑。"""
    root = tmp_path / "repo"
    (root / ".claude/methodologies").mkdir(parents=True)
    _git(["init", "-q"], root)
    rel = ".claude/methodologies/x-methodology.md"
    (root / rel).write_text(f"見 docs/spec/billing/SPEC-012.md 與 {HIT_ID}\n", encoding="utf-8")
    _git(["add", "--", rel], root)

    result = _run("--root", str(root))
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "有未豁免命中的檔 1｜ID 總數 2" in out
    assert f"- {rel}: {HIT_ID} (L1), W3-777 (L1)" in out
    assert "[專案路徑軌] 有未豁免路徑的檔 1｜路徑總數 1（只提示）" in out
    assert f"- {rel}: docs/spec/billing/SPEC-012.md" in out


def test_path_track_summary_line_present_when_no_path_hits(repo):
    """無路徑命中時仍印路徑軌總數行（0），讀者知道該軌有被掃。"""
    result = _run("--root", str(repo))
    assert "[專案路徑軌] 有未豁免路徑的檔 0｜路徑總數 0（只提示）" in result.stdout


def test_group_key():
    assert report.group_key(".claude/skills/x/y.py") == "skills"
    assert report.group_key(".claude/settings.json") == "(根目錄)"


# ---------------------------------------------------------------------------
# 豁免可見性與行號：被 marker 遮住的命中要能被數到、找到
# ---------------------------------------------------------------------------

MARKED = {
    ".claude/references/reloc.md": (
        "前言\n"
        f"引用 {HIT_ID} <!-- rule8-exempt: relocation:自 .claude/references/src.md 逐字搬移 -->\n"
    ),
    ".claude/references/multi.md": f"{HIT_ID}\n中段\n{HIT_ID}\n",
}


@pytest.fixture()
def marked_repo(repo):
    for rel, text in MARKED.items():
        (repo / rel).write_text(text, encoding="utf-8")
    _git(["add", "--", *MARKED], repo)
    return repo


def test_summary_counts_exempt_hits_per_category(marked_repo):
    """正向對照：illustration 與 relocation 各遮住 2 個命中（完整形與裸形），摘要要數到。"""
    out = _run("--root", str(marked_repo), "--summary").stdout
    assert "經 marker 豁免的命中：illustration 2／relocation 2／testdata 0" in out


def test_summary_shows_zero_counts_when_nothing_exempted(tmp_path):
    """反向對照：沒有 marker 時三類都印 0，讀者知道豁免有被計算。"""
    root = tmp_path / "repo"
    (root / ".claude").mkdir(parents=True)
    _git(["init", "-q"], root)
    (root / ".claude/a.md").write_text(f"{HIT_ID}\n", encoding="utf-8")
    _git(["add", "--", ".claude/a.md"], root)
    out = _run("--root", str(root)).stdout
    assert "經 marker 豁免的命中：illustration 0／relocation 0／testdata 0" in out


def test_same_id_on_multiple_lines_lists_every_line(marked_repo):
    out = _run("--root", str(marked_repo)).stdout
    assert f"- .claude/references/multi.md: {HIT_ID} (L1, L3), W3-777 (L1, L3)" in out


def test_show_exempt_flag_controls_exempt_detail(marked_repo):
    """E1 對照：同一 fixture 傳與不傳 --show-exempt，豁免明細只在傳旗標時出現。"""
    plain = _run("--root", str(marked_repo)).stdout
    shown = _run("--root", str(marked_repo), "--show-exempt").stdout
    assert plain != shown
    assert "## 經 marker 豁免的命中" not in plain
    assert "## 經 marker 豁免的命中" in shown
    assert f"- .claude/references/reloc.md: {HIT_ID} (L2, relocation), W3-777 (L2, relocation)" in shown
    assert f"- .claude/references/marker.md: {HIT_ID} (L2, illustration)" in shown
    # 豁免的命中不進未豁免明細
    assert "- .claude/references/reloc.md:" not in plain


def test_unexempted_ids_match_guard_blocked_set(marked_repo):
    """行號定位只用於顯示：有行號的 ID 集合等於守衛判定的未豁免集合。"""
    guard = report.load_guard()
    rels = list(FILES) + list(MARKED)
    result = report.scan(marked_repo, guard, [r for r in rels if r.startswith(".claude/")])
    for fh in result.files:
        assert [v for v, _ in fh.lines] == fh.ids
