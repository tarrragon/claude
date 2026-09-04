"""
Test: domain-import-lint-hook（ARCH-BAL-001 防護，ticket 0.1.0-W2-015）

0.2.1-W3-1232 ANA 盤點確認本 hook 為「執法型（PreToolUse:Bash，違規 exit 2
阻擋）+ tests/ 全目錄零提及」，本檔補上功能性測試；同 wave 另將本 hook 遷移
至 hook_utils 統一日誌（原完全無 setup_hook_logging/run_hook_safely，
hook-logs 落檔數為 0），本檔一併驗證遷移後落檔行為。

驗證項目：
1. is_commit_command：git commit / git merge 字串匹配判斷
2. scan_domain_imports：掃描 lib/domain/ 下違反 import 方向規則的行
3. main() 整合行為：
   - 非 Bash 工具短路（不觸發掃描）
   - Bash 但非 commit/merge 命令短路
   - CLAUDE_PROJECT_DIR 未設定時短路
   - 正常放行路徑（Bash + commit/merge 命令，domain 目錄無違規）
   - 觸發阻擋路徑（Bash + commit/merge 命令，domain 目錄含違規 import，
     exit 2 + stderr 含違規檔案位置與 ARCH-BAL-001 訊息）
4. hook_utils 遷移後可觀測性：main() 經 run_hook_safely 執行後，放行／
   阻擋兩分支皆實測 `.claude/hook-logs/domain-import-lint-hook/*.log`
   落檔，且 liveness 索引 `.claude/hook-logs/_liveness/<session>.jsonl`
   記錄本 hook 已進入（liveness 驗證方式）

Source: ticket 0.2.1-W3-1238（來源 ANA 0.2.1-W3-1232）
"""

import io
import json
import sys
import importlib.util
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent))

_spec = importlib.util.spec_from_file_location(
    "domain_import_lint_hook",
    HOOKS_DIR / "domain-import-lint-hook.py",
)
hook_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook_module)

is_commit_command = hook_module.is_commit_command
scan_domain_imports = hook_module.scan_domain_imports
main = hook_module.main


def _make_domain_project(tmp_path: Path, dart_content: str = "") -> Path:
    """建立最小化假專案：lib/domain/foo.dart 內容為 dart_content（空字串則
    不建立檔案，模擬 domain 目錄存在但無檔案）。"""
    project_root = tmp_path / "fake_project"
    domain_dir = project_root / "lib" / "domain"
    domain_dir.mkdir(parents=True, exist_ok=True)
    if dart_content:
        (domain_dir / "foo.dart").write_text(dart_content, encoding="utf-8")
    return project_root


def _run_hook(
    monkeypatch,
    command: str,
    project_root: "Path | None" = None,
    tool_name: str = "Bash",
) -> int:
    """以 monkeypatch 模擬 stdin + CLAUDE_PROJECT_DIR，執行 main()。

    HOOK_TEST_ISOLATION=1 使 get_project_root()（供 setup_hook_logging 內部
    解析日誌根目錄使用）優先採用 CLAUDE_PROJECT_DIR，不受 pytest 進程實際
    cwd 是否位於 git linked worktree 影響（conftest.hook_project_env 同一
    逃生艙，見 lib/hook_base.py 優先級 0）。
    """
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
# is_commit_command
# ============================================================================


class TestIsCommitCommand:
    def test_git_commit_matches(self):
        assert is_commit_command('git commit -m "x"') is True

    def test_git_merge_matches(self):
        assert is_commit_command("git merge feature-branch") is True

    def test_unrelated_command_does_not_match(self):
        assert is_commit_command("git status") is False

    def test_empty_command(self):
        assert is_commit_command("") is False


# ============================================================================
# scan_domain_imports
# ============================================================================


class TestScanDomainImports:
    def test_no_domain_dir_returns_empty(self, tmp_path):
        assert scan_domain_imports(str(tmp_path)) == []

    def test_clean_domain_file_returns_empty(self, tmp_path):
        project_root = _make_domain_project(
            tmp_path, "import 'package:flutter_balance/domain/entity.dart';\n"
        )
        assert scan_domain_imports(str(project_root)) == []

    def test_forbidden_data_import_detected(self, tmp_path):
        project_root = _make_domain_project(
            tmp_path, "import 'package:flutter_balance/data/repo.dart';\n"
        )
        violations = scan_domain_imports(str(project_root))
        assert len(violations) == 1
        assert "foo.dart:1" in violations[0]

    def test_forbidden_flutter_import_detected(self, tmp_path):
        project_root = _make_domain_project(
            tmp_path, "import 'package:flutter/material.dart';\n"
        )
        assert len(scan_domain_imports(str(project_root))) == 1

    def test_non_import_lines_ignored(self, tmp_path):
        """非 import 起始的行（含字面提及 forbidden pattern 的註解/字串）
        不應誤判。"""
        project_root = _make_domain_project(
            tmp_path,
            "// 不要 import 'package:flutter/material.dart';\n"
            "class Foo {}\n",
        )
        assert scan_domain_imports(str(project_root)) == []


# ============================================================================
# main() 整合：短路路徑
# ============================================================================


class TestMainShortCircuit:
    def test_non_bash_tool_short_circuits(self, monkeypatch, tmp_path, capsys):
        project_root = _make_domain_project(
            tmp_path, "import 'package:flutter/material.dart';\n"
        )
        exit_code = _run_hook(
            monkeypatch,
            'git commit -m "x"',
            project_root=project_root,
            tool_name="Edit",
        )
        assert exit_code == 0
        assert capsys.readouterr().err == ""

    def test_non_commit_command_short_circuits(self, monkeypatch, tmp_path, capsys):
        project_root = _make_domain_project(
            tmp_path, "import 'package:flutter/material.dart';\n"
        )
        exit_code = _run_hook(monkeypatch, "git status", project_root=project_root)
        assert exit_code == 0
        assert capsys.readouterr().err == ""

    def test_missing_project_root_short_circuits(self, monkeypatch):
        exit_code = _run_hook(monkeypatch, 'git commit -m "x"', project_root=None)
        assert exit_code == 0


# ============================================================================
# main() 整合：正常放行路徑
# ============================================================================


class TestMainAllowPath:
    def test_commit_with_clean_domain_allowed(self, monkeypatch, tmp_path, capsys):
        project_root = _make_domain_project(
            tmp_path, "import 'package:flutter_balance/domain/entity.dart';\n"
        )
        exit_code = _run_hook(monkeypatch, 'git commit -m "x"', project_root=project_root)
        assert exit_code == 0
        assert capsys.readouterr().err == ""

    def test_commit_with_no_domain_files_allowed(self, monkeypatch, tmp_path, capsys):
        project_root = _make_domain_project(tmp_path)
        exit_code = _run_hook(monkeypatch, 'git commit -m "x"', project_root=project_root)
        assert exit_code == 0
        assert capsys.readouterr().err == ""


# ============================================================================
# main() 整合：觸發阻擋路徑
# ============================================================================


class TestMainBlockPath:
    def test_commit_with_violation_denied(self, monkeypatch, tmp_path, capsys):
        project_root = _make_domain_project(
            tmp_path,
            "import 'package:flutter_riverpod/flutter_riverpod.dart';\n",
        )
        exit_code = _run_hook(monkeypatch, 'git commit -m "x"', project_root=project_root)
        assert exit_code == 2
        err = capsys.readouterr().err
        assert "domain-import-lint" in err
        assert "ARCH-BAL-001" in err
        assert "foo.dart:1" in err

    def test_merge_with_violation_denied(self, monkeypatch, tmp_path, capsys):
        project_root = _make_domain_project(
            tmp_path,
            "import 'package:flutter_balance/presentation/widget.dart';\n",
        )
        exit_code = _run_hook(monkeypatch, "git merge feature", project_root=project_root)
        assert exit_code == 2
        assert "presentation" in capsys.readouterr().err


# ============================================================================
# hook_utils 遷移後可觀測性：hook-logs 落檔 + liveness 索引
# ============================================================================


class TestHookLogsMigration:
    def test_allow_path_writes_log_file(self, monkeypatch, tmp_path):
        """遷移前本 hook 無 hook_utils logging，hook-logs 落檔數為 0；遷移後
        放行分支經 run_hook_safely 執行應可實測落檔。"""
        project_root = _make_domain_project(
            tmp_path, "import 'package:flutter_balance/domain/entity.dart';\n"
        )
        monkeypatch.setattr(
            sys,
            "stdin",
            io.StringIO(json.dumps(
                {"tool_name": "Bash", "tool_input": {"command": 'git commit -m "x"'}}
            )),
        )
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project_root))
        monkeypatch.setenv("HOOK_TEST_ISOLATION", "1")

        exit_code = hook_module.run_hook_safely(main, "domain-import-lint-hook")
        assert exit_code == 0

        log_dir = project_root / ".claude" / "hook-logs" / "domain-import-lint-hook"
        log_files = list(log_dir.glob("*.log"))
        assert log_files, (
            f"預期 hook-logs 落檔，實際目錄：{list(log_dir.iterdir()) if log_dir.exists() else '不存在'}"
        )
        assert log_files[0].read_text(encoding="utf-8").strip() != ""

    def test_deny_path_also_writes_log_file(self, monkeypatch, tmp_path):
        """阻擋分支（exit 2）同樣應落日誌，確認遷移後阻擋路徑亦可觀測，
        非僅放行分支才寫日誌。"""
        project_root = _make_domain_project(
            tmp_path, "import 'package:flutter/material.dart';\n"
        )
        monkeypatch.setattr(
            sys,
            "stdin",
            io.StringIO(json.dumps(
                {"tool_name": "Bash", "tool_input": {"command": 'git commit -m "x"'}}
            )),
        )
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project_root))
        monkeypatch.setenv("HOOK_TEST_ISOLATION", "1")

        exit_code = hook_module.run_hook_safely(main, "domain-import-lint-hook")
        assert exit_code == 2

        log_dir = project_root / ".claude" / "hook-logs" / "domain-import-lint-hook"
        log_files = list(log_dir.glob("*.log"))
        assert log_files
        content = log_files[0].read_text(encoding="utf-8")
        assert "阻擋" in content

    def test_liveness_index_recorded(self, monkeypatch, tmp_path):
        """run_hook_safely 於 main_func 執行前呼叫 mark_hook_entry，應在
        `.claude/hook-logs/_liveness/<session>.jsonl` 留下本 hook 已進入的
        訊號（liveness 驗證方式：比對此索引檔是否含本 hook 名稱，供確認
        hook 確實被 runtime 載入並執行，非僅函式層級驗證）。"""
        project_root = _make_domain_project(tmp_path)
        monkeypatch.setattr(
            sys,
            "stdin",
            io.StringIO(json.dumps(
                {"tool_name": "Bash", "tool_input": {"command": "git status"}}
            )),
        )
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project_root))
        monkeypatch.setenv("HOOK_TEST_ISOLATION", "1")

        hook_module.run_hook_safely(main, "domain-import-lint-hook")

        liveness_dir = project_root / ".claude" / "hook-logs" / "_liveness"
        jsonl_files = list(liveness_dir.glob("*.jsonl"))
        assert jsonl_files, "預期 liveness 索引檔存在"
        entries = [
            json.loads(line)
            for line in jsonl_files[0].read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert any(e.get("hook") == "domain-import-lint-hook" for e in entries)
