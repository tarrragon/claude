"""
Test: homoglyph-guard-hook（PC-150 形似字混淆對防護，0.18.0-W17-205）

0.2.1-W3-1232 ANA 盤點確認本 hook 為「執法型（PreToolUse:Bash，命中混淆對
exit 2 阻擋）+ tests/ 全目錄零提及」，本檔補上功能性測試。本 hook 已具備
hook_utils 統一日誌（setup_hook_logging/run_hook_safely），無需遷移。

驗證項目：
1. _is_git_commit_command：排除 --amend / log / diff / show / status
2. _scan_diff_for_homoglyph：同一 hunk 內 +行含「汲」且 -行含「汙/污」才命中
3. main() 整合行為：
   - 非 Bash 工具短路
   - 非 git commit 命令短路（含 --amend）
   - commit msg 含 [skip homoglyph] 標記短路
   - 正常放行路徑（真實 git repo，staged diff 無混淆對命中）
   - 觸發阻擋路徑（真實 git repo，staged diff 命中混淆對，exit 2 +
     stderr 含 PC-150 訊息與命中檔案）
4. hook-logs 落檔（本 session 實地觸發確認）+ liveness 索引記錄

Source: ticket 0.2.1-W3-1238（來源 ANA 0.2.1-W3-1232）
"""

import io
import json
import subprocess
import sys
import importlib.util
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent))

_spec = importlib.util.spec_from_file_location(
    "homoglyph_guard_hook",
    HOOKS_DIR / "homoglyph-guard-hook.py",
)
hook_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook_module)

_is_git_commit_command = hook_module._is_git_commit_command
_scan_diff_for_homoglyph = hook_module._scan_diff_for_homoglyph
main = hook_module.main


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@test.local")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")


def _make_repo_with_staged_change(tmp_path: Path, before: str, after: str) -> Path:
    """建立真實 git repo：以 before 內容 commit，再改為 after 內容並 stage，
    模擬本 hook 掃描的 `git diff --cached` 情境。"""
    repo = tmp_path / "fake_repo"
    _init_repo(repo)
    target = repo / "notes.md"
    target.write_text(before, encoding="utf-8")
    _git(repo, "add", "notes.md")
    _git(repo, "commit", "-q", "-m", "init")
    target.write_text(after, encoding="utf-8")
    _git(repo, "add", "notes.md")
    return repo


def _run_hook(
    monkeypatch,
    command: str,
    project_root: "Path | None" = None,
    tool_name: str = "Bash",
) -> int:
    payload = {"tool_name": tool_name, "tool_input": {"command": command}}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    if project_root is not None:
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project_root))
        monkeypatch.setenv("HOOK_TEST_ISOLATION", "1")
    else:
        monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
        monkeypatch.delenv("HOOK_TEST_ISOLATION", raising=False)
    return main()


# ============================================================================
# _is_git_commit_command
# ============================================================================


class TestIsGitCommitCommand:
    def test_plain_commit_matches(self):
        assert _is_git_commit_command('git commit -m "x"') is True

    def test_amend_excluded(self):
        assert _is_git_commit_command("git commit --amend") is False

    def test_log_excluded(self):
        assert _is_git_commit_command("git log") is False

    def test_diff_excluded(self):
        assert _is_git_commit_command("git diff --cached") is False

    def test_show_excluded(self):
        assert _is_git_commit_command("git show HEAD") is False

    def test_status_excluded(self):
        assert _is_git_commit_command("git status") is False

    def test_non_commit_command(self):
        assert _is_git_commit_command("git add foo.py") is False


# ============================================================================
# _scan_diff_for_homoglyph
# ============================================================================


class TestScanDiffForHomoglyph:
    def test_hit_when_added_wrong_char_removed_correct_char_same_hunk(self):
        diff = (
            "diff --git a/notes.md b/notes.md\n"
            "@@ -1 +1 @@\n"
            "-這是汙染的說明\n"
            "+這是汲染的說明\n"
        )
        hits = _scan_diff_for_homoglyph(diff)
        assert len(hits) == 1
        assert hits[0][0] == "notes.md"

    def test_no_hit_when_legitimate_usage(self):
        """新增內容含「汲取」但無同 hunk 內的汙/污被移除，不應誤判。"""
        diff = (
            "diff --git a/notes.md b/notes.md\n"
            "@@ -1 +1,2 @@\n"
            " 既有行\n"
            "+新增汲取知識的說明\n"
        )
        assert _scan_diff_for_homoglyph(diff) == []

    def test_no_hit_when_no_wrong_char(self):
        diff = (
            "diff --git a/notes.md b/notes.md\n"
            "@@ -1 +1 @@\n"
            "-舊內容\n"
            "+新內容\n"
        )
        assert _scan_diff_for_homoglyph(diff) == []

    def test_empty_diff_returns_empty(self):
        assert _scan_diff_for_homoglyph("") == []


# ============================================================================
# main() 整合：短路路徑
# ============================================================================


class TestMainShortCircuit:
    def test_non_bash_tool_short_circuits(self, monkeypatch, tmp_path):
        repo = _make_repo_with_staged_change(tmp_path, "汙染", "汲染")
        exit_code = _run_hook(
            monkeypatch, 'git commit -m "x"', project_root=repo, tool_name="Edit"
        )
        assert exit_code == 0

    def test_non_git_commit_command_short_circuits(self, monkeypatch, tmp_path):
        repo = _make_repo_with_staged_change(tmp_path, "汙染", "汲染")
        exit_code = _run_hook(monkeypatch, "git status", project_root=repo)
        assert exit_code == 0

    def test_amend_short_circuits_even_with_pending_violation(self, monkeypatch, tmp_path):
        repo = _make_repo_with_staged_change(tmp_path, "汙染", "汲染")
        exit_code = _run_hook(monkeypatch, "git commit --amend", project_root=repo)
        assert exit_code == 0

    def test_skip_marker_short_circuits(self, monkeypatch, tmp_path, capsys):
        repo = _make_repo_with_staged_change(tmp_path, "汙染", "汲染")
        exit_code = _run_hook(
            monkeypatch,
            'git commit -m "x [skip homoglyph]"',
            project_root=repo,
        )
        assert exit_code == 0
        assert capsys.readouterr().err == ""

    def test_no_staged_diff_short_circuits(self, monkeypatch, tmp_path):
        repo = tmp_path / "empty_repo"
        _init_repo(repo)
        (repo / "a.md").write_text("內容", encoding="utf-8")
        _git(repo, "add", "a.md")
        _git(repo, "commit", "-q", "-m", "init")
        # 無 staged 變更
        exit_code = _run_hook(monkeypatch, 'git commit -m "x"', project_root=repo)
        assert exit_code == 0


# ============================================================================
# main() 整合：正常放行路徑
# ============================================================================


class TestMainAllowPath:
    def test_clean_staged_diff_allowed(self, monkeypatch, tmp_path, capsys):
        repo = _make_repo_with_staged_change(tmp_path, "舊說明文字", "新說明文字")
        exit_code = _run_hook(monkeypatch, 'git commit -m "x"', project_root=repo)
        assert exit_code == 0
        assert capsys.readouterr().err == ""


# ============================================================================
# main() 整合：觸發阻擋路徑
# ============================================================================


class TestMainBlockPath:
    def test_homoglyph_substitution_denied(self, monkeypatch, tmp_path, capsys):
        repo = _make_repo_with_staged_change(tmp_path, "這是汙染的說明", "這是汲染的說明")
        exit_code = _run_hook(monkeypatch, 'git commit -m "x"', project_root=repo)
        assert exit_code == 2
        err = capsys.readouterr().err
        assert "Homoglyph Guard" in err
        assert "PC-150" in err
        assert "notes.md" in err


# ============================================================================
# hook-logs 落檔（本 session 實地觸發確認）+ liveness 索引
# ============================================================================


class TestHookLogsObservability:
    def test_run_hook_safely_writes_log_and_liveness(self, monkeypatch, tmp_path):
        repo = _make_repo_with_staged_change(tmp_path, "這是汙染的說明", "這是汲染的說明")
        monkeypatch.setattr(
            sys,
            "stdin",
            io.StringIO(json.dumps(
                {"tool_name": "Bash", "tool_input": {"command": 'git commit -m "x"'}}
            )),
        )
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(repo))
        monkeypatch.setenv("HOOK_TEST_ISOLATION", "1")

        exit_code = hook_module.run_hook_safely(main, "homoglyph-guard-hook")
        assert exit_code == 2

        log_dir = repo / ".claude" / "hook-logs" / "homoglyph-guard-hook"
        log_files = list(log_dir.glob("*.log"))
        assert log_files, f"預期落檔，實際：{list(log_dir.iterdir()) if log_dir.exists() else '不存在'}"
        assert "阻擋" in log_files[0].read_text(encoding="utf-8")

        liveness_dir = repo / ".claude" / "hook-logs" / "_liveness"
        jsonl_files = list(liveness_dir.glob("*.jsonl"))
        assert jsonl_files, "預期 liveness 索引檔存在"
        entries = [
            json.loads(line)
            for line in jsonl_files[0].read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert any(e.get("hook") == "homoglyph-guard-hook" for e in entries)
