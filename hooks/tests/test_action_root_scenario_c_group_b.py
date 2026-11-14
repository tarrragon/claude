"""
Test: get_action_root 與 B 組五支（情境 C：env=MAIN、payload.cwd=WT）

B 組：lib/commit_content_guards（未傳根時）、active-dispatch-tracker-hook
（work_checkout 登記）、domain-import-lint-hook、uc-reference-validation-hook、
git-index-lock-cleanup-hook（有 cwd 時以 WT 鎖路徑判定；缺 cwd fallback 不遷）。
每支含正向對照（WT 上應擋或應偵測者被擋或被偵測）、反向對照（MAIN 有、WT 沒有的
狀態不影響判定）與缺 cwd 測試（stderr 無 `[get_action_root]`）。用真實 git repo 與
linked worktree。

Source: ticket 3.3.0-W1-204.1.3.2（判定表 B 組 AR 列，3.3.0-W1-204.1）
"""

import importlib.util
import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE_DIR = HOOKS_DIR.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(CLAUDE_DIR))

MARKER = "[get_action_root]"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *args],
        check=True, capture_output=True,
    )


@pytest.fixture
def main_and_wt(tmp_path):
    main_repo = tmp_path / "main"
    main_repo.mkdir()
    _git(main_repo, "init", "-q", "-b", "main")
    (main_repo / "a.txt").write_text("a\n")
    _git(main_repo, "add", ".")
    _git(main_repo, "commit", "-q", "-m", "base")
    wt = tmp_path / "wt"
    _git(main_repo, "worktree", "add", "-q", "-b", "wtbr", str(wt), "main")
    return main_repo, wt


def _stdin(monkeypatch, payload: dict) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))


# ============================================================================
# lib/commit_content_guards：未傳根時的 UC 豁免與分支判定（AR）
# ============================================================================

import lib.commit_content_guards as ccg  # noqa: E402
from lib.commit_content_guards import StagedFile  # noqa: E402


def _uc_spec(root: Path, *ucs: str) -> None:
    (root / "docs").mkdir(exist_ok=True)
    body = "# UC\n\n" + "".join(f"## {u}: t\n\n說明\n\n" for u in ucs)
    (root / "docs" / "app-use-cases.md").write_text(body, encoding="utf-8")


def _staged(added: str) -> StagedFile:
    import inspect

    params = inspect.signature(StagedFile).parameters
    kwargs = {"rel_path": "lib/x.dart", "added_text": added}
    for k in params:
        if k not in kwargs and params[k].default is inspect.Parameter.empty:
            kwargs[k] = ""
    return StagedFile(**kwargs)


class TestCommitContentGuardsScenarioC:
    def test_wt_undefined_uc_detected(self, monkeypatch, main_and_wt):
        """正向對照：MAIN 有 UC-09、WT 沒有 → WT 判定下偵測到（舊碼讀 MAIN 而漏報）。"""
        main_repo, wt = main_and_wt
        _uc_spec(main_repo, "UC-01", "UC-09")
        _uc_spec(wt, "UC-01")
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(main_repo))
        found = ccg._check_uc_reference(
            _staged("// UC-09"), None, payload={"cwd": str(wt)}
        )
        assert found, "WT 未定義 UC-09，應偵測"

    def test_main_undefined_does_not_affect_wt(self, monkeypatch, main_and_wt):
        """反向對照：MAIN 沒有 UC-05、WT 有 → 不偵測。"""
        main_repo, wt = main_and_wt
        _uc_spec(main_repo, "UC-01")
        _uc_spec(wt, "UC-01", "UC-05")
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(main_repo))
        found = ccg._check_uc_reference(
            _staged("// UC-05"), None, payload={"cwd": str(wt)}
        )
        assert found == []

    def test_fallback_action_root_is_wt(self, monkeypatch, main_and_wt):
        main_repo, wt = main_and_wt
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(main_repo))
        assert ccg._fallback_action_root({"cwd": str(wt)}) == wt

    def test_branch_context_uses_wt_head(self, monkeypatch, main_and_wt):
        """分支判定：MAIN 在保護分支 main、WT 在 wtbr（非保護）→ 以 WT 判定無須檢查。"""
        main_repo, wt = main_and_wt
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(main_repo))
        assert ccg._resolve_branch_context(False, payload={"cwd": str(wt)}) is None
        # 正向對照：缺 cwd 沿用 MAIN（保護分支 main）→ 產生檢查脈絡
        ctx = ccg._resolve_branch_context(False)
        assert ctx is not None and ctx.current_branch == "main"

    def test_missing_cwd_no_helper_stderr(self, monkeypatch, main_and_wt, capsys):
        main_repo, _ = main_and_wt
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(main_repo))
        ccg._fallback_action_root({})
        ccg._fallback_action_root(None)
        assert MARKER not in capsys.readouterr().err


# ============================================================================
# active-dispatch-tracker-hook：work_checkout 登記（AR）
# ============================================================================

_tracker = _load(
    "active_dispatch_tracker_hook_c", HOOKS_DIR / "active-dispatch-tracker-hook.py"
)


def _run_tracker(monkeypatch, main_repo: Path, cwd: "Path | None") -> list:
    calls: list = []
    payload = {
        "tool_use_id": "tu",
        "tool_input": {"description": "d", "isolation": "", "prompt": "", "name": ""},
        "tool_response": {"agentId": "ag", "isAsync": False},
    }
    if cwd is not None:
        payload["cwd"] = str(cwd)
    _stdin(monkeypatch, payload)
    monkeypatch.setattr(_tracker, "is_subagent_environment", lambda _d: False)
    monkeypatch.setattr(_tracker, "get_project_root", lambda: main_repo)
    monkeypatch.setattr(_tracker, "cleanup_expired", lambda _r: 0)
    monkeypatch.setattr(_tracker, "detect_orphan_branches", lambda _r: [])
    monkeypatch.setattr(_tracker, "extract_where_files", lambda *a, **k: [])
    monkeypatch.setattr(_tracker, "record_dispatch", lambda **kw: calls.append(kw))
    assert _tracker.main() == 0
    return calls


class TestActiveDispatchTrackerScenarioC:
    def test_wt_cwd_registers_wt_checkout(self, monkeypatch, main_and_wt):
        """正向對照：cwd 在 WT → work_checkout 為 WT（舊碼登記 MAIN）。"""
        main_repo, wt = main_and_wt
        calls = _run_tracker(monkeypatch, main_repo, wt)
        assert calls[0]["work_checkout"] == str(wt)

    def test_main_cwd_registers_main_checkout(self, monkeypatch, main_and_wt):
        """反向對照：cwd 在 MAIN → work_checkout 為 MAIN，不受 WT 影響。"""
        main_repo, wt = main_and_wt
        calls = _run_tracker(monkeypatch, main_repo, main_repo)
        assert calls[0]["work_checkout"] == str(main_repo)

    def test_missing_cwd_keeps_project_root_no_stderr(
        self, monkeypatch, main_and_wt, capsys
    ):
        main_repo, _ = main_and_wt
        calls = _run_tracker(monkeypatch, main_repo, None)
        assert calls[0]["work_checkout"] == str(main_repo)
        assert MARKER not in capsys.readouterr().err


# ============================================================================
# domain-import-lint-hook：lib/domain 掃描（AR）
# ============================================================================

_domain = _load("domain_import_lint_hook_c", HOOKS_DIR / "domain-import-lint-hook.py")

_BAD = "import 'package:flutter_balance/data/x.dart';\n"
_OK = "import 'dart:core';\n"


def _domain_file(root: Path, content: str) -> None:
    d = root / "lib" / "domain"
    d.mkdir(parents=True, exist_ok=True)
    (d / "foo.dart").write_text(content, encoding="utf-8")


def _run_domain(monkeypatch, main_repo: Path, cwd: "Path | None") -> int:
    payload = {"tool_name": "Bash", "tool_input": {"command": "git commit -m x"}}
    if cwd is not None:
        payload["cwd"] = str(cwd)
    _stdin(monkeypatch, payload)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(main_repo))
    monkeypatch.setenv("HOOK_TEST_ISOLATION", "1")
    return _domain.main()


class TestDomainImportLintScenarioC:
    def test_wt_violation_blocked(self, monkeypatch, main_and_wt):
        """正向對照：WT 的 domain 有違規、MAIN 乾淨 → 擋（舊碼掃 MAIN 而放行）。"""
        main_repo, wt = main_and_wt
        _domain_file(main_repo, _OK)
        _domain_file(wt, _BAD)
        assert _run_domain(monkeypatch, main_repo, wt) == 2

    def test_main_violation_does_not_affect_wt(self, monkeypatch, main_and_wt):
        """反向對照：MAIN 有違規、WT 乾淨 → 放行。"""
        main_repo, wt = main_and_wt
        _domain_file(main_repo, _BAD)
        _domain_file(wt, _OK)
        assert _run_domain(monkeypatch, main_repo, wt) == 0

    def test_missing_cwd_scans_project_root_no_stderr(
        self, monkeypatch, main_and_wt, capsys
    ):
        main_repo, wt = main_and_wt
        _domain_file(main_repo, _BAD)
        _domain_file(wt, _OK)
        assert _run_domain(monkeypatch, main_repo, None) == 2
        assert MARKER not in capsys.readouterr().err


# ============================================================================
# uc-reference-validation-hook：豁免路徑、UC 對照（AR）
# ============================================================================

_uc = _load(
    "uc_reference_validation_hook_c", HOOKS_DIR / "uc-reference-validation-hook.py"
)


def _run_uc(monkeypatch, main_repo: Path, cwd: "Path | None", text: str) -> int:
    payload = {
        "tool_name": "Edit",
        "tool_input": {"file_path": "lib/x.dart", "old_string": "x", "new_string": text},
    }
    if cwd is not None:
        payload["cwd"] = str(cwd)
    _stdin(monkeypatch, payload)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(main_repo))
    return _uc.main()


class TestUcReferenceValidationScenarioC:
    def test_wt_undefined_uc_warned(self, monkeypatch, main_and_wt, capsys):
        """正向對照：MAIN 有 UC-09、WT 沒有 → 警告（舊碼讀 MAIN 而靜默）。"""
        main_repo, wt = main_and_wt
        _uc_spec(main_repo, "UC-01", "UC-09")
        _uc_spec(wt, "UC-01")
        assert _run_uc(monkeypatch, main_repo, wt, "// UC-09") == 0
        assert "UC-09" in capsys.readouterr().out

    def test_main_undefined_does_not_affect_wt(self, monkeypatch, main_and_wt, capsys):
        """反向對照：MAIN 沒有 UC-05、WT 有 → 靜默。"""
        main_repo, wt = main_and_wt
        _uc_spec(main_repo, "UC-01")
        _uc_spec(wt, "UC-01", "UC-05")
        assert _run_uc(monkeypatch, main_repo, wt, "// UC-05") == 0
        assert capsys.readouterr().out == ""

    def test_missing_cwd_uses_project_root_no_stderr(
        self, monkeypatch, main_and_wt, capsys
    ):
        main_repo, wt = main_and_wt
        _uc_spec(main_repo, "UC-01", "UC-09")
        _uc_spec(wt, "UC-01")
        assert _run_uc(monkeypatch, main_repo, None, "// UC-09") == 0
        cap = capsys.readouterr()
        assert MARKER not in cap.err
        assert "UC-09" not in cap.out  # MAIN 有 UC-09 → 沿用 MAIN 判定，靜默


# ============================================================================
# git-index-lock-cleanup-hook：不遷移，釘住有 cwd 時以 WT 鎖路徑判定
# ============================================================================

_lock = _load(
    "git_index_lock_cleanup_hook_c", HOOKS_DIR / "git-index-lock-cleanup-hook.py"
)


def _aged_empty(lock: Path) -> None:
    lock.write_text("")
    t = time.time() - (_lock.STALE_THRESHOLD_SECONDS + 60)
    os.utime(lock, (t, t))


def _lock_path(repo: Path) -> Path:
    out = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--git-path", "index.lock"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    p = Path(out)
    return p if p.is_absolute() else repo / p


class TestGitIndexLockScenarioC:
    def test_cwd_wt_cleans_wt_lock_keeps_main_lock(self, main_and_wt):
        """有 cwd：清 WT 的鎖，MAIN 的鎖不動（get_project_root 指 MAIN）。"""
        import logging

        main_repo, wt = main_and_wt
        wlock, mlock = _lock_path(wt), _lock_path(main_repo)
        _aged_empty(wlock)
        _aged_empty(mlock)
        with patch.object(_lock, "get_project_root", return_value=str(main_repo)):
            _lock.check_and_cleanup_index_lock(
                logging.getLogger("t"), str(wt), "git add x"
            )
        assert not wlock.exists()
        assert mlock.exists()

    def test_missing_cwd_no_helper_stderr(self, main_and_wt, capsys):
        import logging

        main_repo, _ = main_and_wt
        with patch.object(_lock, "get_project_root", return_value=str(main_repo)):
            _lock.check_and_cleanup_index_lock(logging.getLogger("t"), None, "git add x")
        assert MARKER not in capsys.readouterr().err
