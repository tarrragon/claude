"""
Test: commit-stage-guard-gate-hook（0.2.1-W3-893，源自 0.2.1-W3-825 ANA
B 組結論）——commit 階段補網，統一轉呼 12 支既有 Edit/Write-only guard
的核心判斷函式，對 staged 內容做事後掃描。

驗證項目：
1. `_get_staged_file_list` / `_git_show` / `_get_added_text`：三種文字
   重建（pre/post/added）在隔離 git repo 下的行為
2. `_check_rule8`：staged 內容新增 ticket ID 命中 -> deny；無新增命中
   （或全屬既有存量）-> 放行
3. `_check_ticket_path`：staged 路徑落在 `.claude/tickets/` -> deny
4. `_check_error_pattern_flat`：新建 flat 號 error-pattern -> deny；
   前綴號 -> 放行
5. `main()` 整合行為：
   - 非 Bash 工具 / 非 git commit 命令 -> 放行（exit 0）
   - 無 staged 檔案 -> 放行（exit 0）
   - staged 內容命中 deny 級發現 -> exit 2，stderr 含逐項訊息
   - staged 內容僅命中 warn 級發現 -> exit 0，stderr 含提醒
   - staged 內容無發現 -> 靜默 exit 0
6. dogfooding 實地觸發（對本專案真實 staged 內容，見
   `test_dogfooding_live_trigger_on_project`）：模擬含違規檔與乾淨檔
   各一，驗證 trigger 邏輯與設計相符，並落檔供 acceptance-gate 稽核。

Source: ticket 0.2.1-W3-893（來源 ANA 0.2.1-W3-825）
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE_DIR = HOOKS_DIR.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(CLAUDE_DIR))

_spec = importlib.util.spec_from_file_location(
    "commit_stage_guard_gate_hook",
    HOOKS_DIR / "commit-stage-guard-gate-hook.py",
)
hook_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook_module)


def _run_git(args, cwd):
    result = subprocess.run(
        ["git"] + args, cwd=str(cwd), capture_output=True, text=True
    )
    return result.returncode, result.stdout, result.stderr


@pytest.fixture()
def scratch_repo(tmp_path):
    """建立最小化隔離 git repo，含一個已 commit 的 HEAD 基準，供 staged
    diff 相關測試使用（不影響真實專案 repo 的 index/HEAD）。"""
    repo = tmp_path / "scratch"
    repo.mkdir()
    _run_git(["init", "-q"], cwd=repo)
    _run_git(["config", "user.email", "test@example.com"], cwd=repo)
    _run_git(["config", "user.name", "Test"], cwd=repo)
    (repo / "README.md").write_text("baseline\n", encoding="utf-8")
    _run_git(["add", "README.md"], cwd=repo)
    _run_git(["commit", "-q", "-m", "baseline"], cwd=repo)
    return repo


class TestStagedTextReconstruction:
    def test_get_staged_file_list_returns_added_file(self, scratch_repo):
        new_file = scratch_repo / "new.md"
        new_file.write_text("hello\n", encoding="utf-8")
        _run_git(["add", "new.md"], cwd=scratch_repo)

        files = hook_module._get_staged_file_list(scratch_repo)

        assert files == ["new.md"]

    def test_get_staged_file_list_empty_when_nothing_staged(self, scratch_repo):
        files = hook_module._get_staged_file_list(scratch_repo)
        assert files == []

    def test_build_staged_file_pre_text_empty_for_new_file(self, scratch_repo):
        new_file = scratch_repo / "new.md"
        new_file.write_text("line one\n", encoding="utf-8")
        _run_git(["add", "new.md"], cwd=scratch_repo)

        sf = hook_module._build_staged_file("new.md", scratch_repo)

        assert sf.pre_text == ""
        assert "line one" in sf.post_text
        assert "line one" in sf.added_text

    def test_build_staged_file_pre_text_nonempty_for_modified_file(self, scratch_repo):
        readme = scratch_repo / "README.md"
        readme.write_text("baseline\nnew line\n", encoding="utf-8")
        _run_git(["add", "README.md"], cwd=scratch_repo)

        sf = hook_module._build_staged_file("README.md", scratch_repo)

        assert "baseline" in sf.pre_text
        assert "new line" in sf.post_text
        assert sf.added_text.strip() == "new line"


class TestRenameHandling:
    """rename 檔案的 pre_text/added_text 重建（0.2.1-W3-1139）：純 rename
    應零命中不阻擋；rename 併內容變更僅掃真正新增的內容。"""

    def test_pure_rename_pre_text_equals_post_text(self, scratch_repo):
        old_file = scratch_repo / "sub"
        old_file.mkdir()
        (old_file / "old.md").write_text("W9-100 既有內容\n", encoding="utf-8")
        _run_git(["add", "sub/old.md"], cwd=scratch_repo)
        _run_git(["commit", "-q", "-m", "add old.md"], cwd=scratch_repo)

        _run_git(["mv", "sub/old.md", "sub/new.md"], cwd=scratch_repo)

        rename_map = hook_module._get_staged_rename_map(scratch_repo)
        assert rename_map == {"sub/new.md": "sub/old.md"}

        sf = hook_module._build_staged_file("sub/new.md", scratch_repo, rename_map)

        assert sf.pre_text == sf.post_text
        assert sf.added_text == ""

    def test_pure_rename_produces_zero_rule8_findings(self, scratch_repo):
        old_file = scratch_repo / ".claude" / "references"
        old_file.mkdir(parents=True)
        (old_file / "old.md").write_text(
            "既有內容引用 W9-101 的分析結論。\n", encoding="utf-8"
        )
        _run_git(["add", ".claude/references/old.md"], cwd=scratch_repo)
        _run_git(["commit", "-q", "-m", "add old.md"], cwd=scratch_repo)

        _run_git(
            ["mv", ".claude/references/old.md", ".claude/references/new.md"],
            cwd=scratch_repo,
        )

        rename_map = hook_module._get_staged_rename_map(scratch_repo)
        sf = hook_module._build_staged_file(
            ".claude/references/new.md", scratch_repo, rename_map
        )
        findings = hook_module._check_rule8(sf, logger=_NullLogger())

        assert findings == []

    def test_rename_with_content_change_only_scans_true_new_content(self, scratch_repo):
        old_file = scratch_repo / "sub"
        old_file.mkdir()
        (old_file / "old.md").write_text(
            "line1\nline2\nline3\n", encoding="utf-8"
        )
        _run_git(["add", "sub/old.md"], cwd=scratch_repo)
        _run_git(["commit", "-q", "-m", "add old.md"], cwd=scratch_repo)

        _run_git(["mv", "sub/old.md", "sub/new.md"], cwd=scratch_repo)
        (old_file / "new.md").write_text(
            "line1\nline2\nline3\nline4 新增\n", encoding="utf-8"
        )
        _run_git(["add", "sub/new.md"], cwd=scratch_repo)

        rename_map = hook_module._get_staged_rename_map(scratch_repo)
        sf = hook_module._build_staged_file("sub/new.md", scratch_repo, rename_map)

        assert "line1" in sf.pre_text
        assert sf.added_text.strip() == "line4 新增"

    def test_rename_with_content_change_denies_only_on_new_ticket_id(self, scratch_repo):
        old_file = scratch_repo / ".claude" / "references"
        old_file.mkdir(parents=True)
        (old_file / "old.md").write_text(
            "既有內容，不含引用。\n", encoding="utf-8"
        )
        _run_git(["add", ".claude/references/old.md"], cwd=scratch_repo)
        _run_git(["commit", "-q", "-m", "add old.md"], cwd=scratch_repo)

        _run_git(
            ["mv", ".claude/references/old.md", ".claude/references/new.md"],
            cwd=scratch_repo,
        )
        (old_file / "new.md").write_text(
            "既有內容，不含引用。\n引用 W9-102 的分析結論。\n", encoding="utf-8"
        )
        _run_git(["add", ".claude/references/new.md"], cwd=scratch_repo)

        rename_map = hook_module._get_staged_rename_map(scratch_repo)
        sf = hook_module._build_staged_file(
            ".claude/references/new.md", scratch_repo, rename_map
        )
        findings = hook_module._check_rule8(sf, logger=_NullLogger())

        assert len(findings) == 1
        assert findings[0].severity == "deny"

    def test_main_integration_pure_rename_allows_commit(self, scratch_repo):
        old_file = scratch_repo / ".claude" / "references"
        old_file.mkdir(parents=True)
        (old_file / "old.md").write_text(
            "既有內容引用 W9-103 的分析結論。\n", encoding="utf-8"
        )
        _run_git(["add", ".claude/references/old.md"], cwd=scratch_repo)
        _run_git(["commit", "-q", "-m", "add old.md"], cwd=scratch_repo)

        _run_git(
            ["mv", ".claude/references/old.md", ".claude/references/new.md"],
            cwd=scratch_repo,
        )

        result = TestMainIntegration()._run_hook(
            {"tool_name": "Bash", "tool_input": {"command": "git commit -m x"}},
            scratch_repo,
        )

        assert result.returncode == 0


class TestCheckRule8:
    def test_deny_when_new_ticket_id_hit_in_framework_path(self, scratch_repo):
        target = scratch_repo / ".claude" / "references" / "x.md"
        target.parent.mkdir(parents=True)
        target.write_text("既有內容，不含引用。\n", encoding="utf-8")
        _run_git(["add", "."], cwd=scratch_repo)
        _run_git(["commit", "-q", "-m", "add x.md"], cwd=scratch_repo)

        # 模擬繞過寫入：新增一行含裸格式 ticket ID
        target.write_text(
            "既有內容，不含引用。\n引用 W9-001 的分析結論。\n", encoding="utf-8"
        )
        _run_git(["add", ".claude/references/x.md"], cwd=scratch_repo)

        sf = hook_module._build_staged_file(".claude/references/x.md", scratch_repo)
        findings = hook_module._check_rule8(sf, logger=_NullLogger())

        assert len(findings) == 1
        assert findings[0].severity == "deny"
        assert "reference-stability-rule8-guard" == findings[0].source

    def test_allow_when_no_new_ticket_id(self, scratch_repo):
        target = scratch_repo / ".claude" / "references" / "clean.md"
        target.parent.mkdir(parents=True)
        target.write_text("無任何 ticket ID 引用的一般內容。\n", encoding="utf-8")
        _run_git(["add", "."], cwd=scratch_repo)

        sf = hook_module._build_staged_file(".claude/references/clean.md", scratch_repo)
        findings = hook_module._check_rule8(sf, logger=_NullLogger())

        assert findings == []

    def test_allow_when_path_outside_claude_scope(self, scratch_repo):
        target = scratch_repo / "docs" / "notes.md"
        target.parent.mkdir(parents=True)
        target.write_text("引用 W9-001 的分析結論（非 .claude/ 範圍）。\n", encoding="utf-8")
        _run_git(["add", "."], cwd=scratch_repo)

        sf = hook_module._build_staged_file("docs/notes.md", scratch_repo)
        findings = hook_module._check_rule8(sf, logger=_NullLogger())

        assert findings == []


class TestCheckTicketPath:
    def test_deny_when_staged_path_is_forbidden_ticket_dir(self):
        sf = hook_module.StagedFile(
            rel_path=".claude/tickets/foo.md",
            pre_text="",
            post_text="content",
            added_text="content",
        )
        findings = hook_module._check_ticket_path(sf, logger=_NullLogger())

        assert len(findings) == 1
        assert findings[0].severity == "deny"
        assert findings[0].source == "ticket-path-guard"

    def test_allow_when_staged_path_is_correct_ticket_dir(self):
        sf = hook_module.StagedFile(
            rel_path="docs/work-logs/v0.2.1/tickets/foo.md",
            pre_text="",
            post_text="content",
            added_text="content",
        )
        findings = hook_module._check_ticket_path(sf, logger=_NullLogger())

        assert findings == []


class TestCheckErrorPatternFlat:
    def test_deny_new_flat_id_error_pattern(self, tmp_path):
        rel_path = "error-patterns/process-compliance/PC-999-scratch.md"
        (tmp_path / rel_path).parent.mkdir(parents=True, exist_ok=True)
        # 不建立實體檔案：decide() 以 Path(file_path).exists() 判斷是否新建，
        # rel_path 相對路徑在測試環境下天然不存在於磁碟絕對路徑，語意上等同新建。
        sf = hook_module.StagedFile(
            rel_path=rel_path, pre_text="", post_text="x", added_text="x"
        )
        findings = hook_module._check_error_pattern_flat(sf, logger=_NullLogger())

        assert len(findings) == 1
        assert findings[0].severity == "deny"
        assert findings[0].source == "error-pattern-flat-gate"

    def test_allow_prefixed_id_error_pattern(self):
        sf = hook_module.StagedFile(
            rel_path="error-patterns/process-compliance/PC-V1-999-scratch.md",
            pre_text="",
            post_text="x",
            added_text="x",
        )
        findings = hook_module._check_error_pattern_flat(sf, logger=_NullLogger())

        assert findings == []


class _NullLogger:
    def debug(self, *a, **k):
        pass

    def info(self, *a, **k):
        pass

    def warning(self, *a, **k):
        pass

    def error(self, *a, **k):
        pass


class TestMainIntegration:
    def _run_hook(self, stdin_payload: dict, cwd: Path):
        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "commit-stage-guard-gate-hook.py")],
            input=json.dumps(stdin_payload),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            env={"PATH": "/usr/bin:/bin:/usr/local/bin", "CLAUDE_PROJECT_DIR": str(cwd)},
        )
        return result

    def test_non_bash_tool_allows(self, scratch_repo):
        result = self._run_hook({"tool_name": "Write", "tool_input": {}}, scratch_repo)
        assert result.returncode == 0

    def test_non_commit_command_allows(self, scratch_repo):
        result = self._run_hook(
            {"tool_name": "Bash", "tool_input": {"command": "git status"}}, scratch_repo
        )
        assert result.returncode == 0

    def test_no_staged_files_allows(self, scratch_repo):
        result = self._run_hook(
            {"tool_name": "Bash", "tool_input": {"command": "git commit -m x"}},
            scratch_repo,
        )
        assert result.returncode == 0

    def test_staged_violation_denies_commit(self, scratch_repo):
        target = scratch_repo / ".claude" / "references" / "x.md"
        target.parent.mkdir(parents=True)
        target.write_text("baseline\n", encoding="utf-8")
        _run_git(["add", "."], cwd=scratch_repo)
        _run_git(["commit", "-q", "-m", "baseline2"], cwd=scratch_repo)

        target.write_text("baseline\n引用 W9-002 的分析結論。\n", encoding="utf-8")
        _run_git(["add", ".claude/references/x.md"], cwd=scratch_repo)

        result = self._run_hook(
            {"tool_name": "Bash", "tool_input": {"command": "git commit -m x"}},
            scratch_repo,
        )

        assert result.returncode == 2
        assert "commit-stage-guard-gate" in result.stderr
        assert "reference-stability-rule8-guard" in result.stderr

    def test_staged_clean_content_allows_commit(self, scratch_repo):
        target = scratch_repo / ".claude" / "references" / "clean.md"
        target.parent.mkdir(parents=True)
        target.write_text("一般內容，無違規。\n", encoding="utf-8")
        _run_git(["add", "."], cwd=scratch_repo)

        result = self._run_hook(
            {"tool_name": "Bash", "tool_input": {"command": "git commit -m x"}},
            scratch_repo,
        )

        assert result.returncode == 0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
