"""G1 讀回狀態四支 hook 改經 get_hook_log_dir 的測試（3.3.0-W1-204.1.6.6）。

四支：phase-completion-gate（報告）、subagent-stop-dispatch-cleanup（dedup）、
package-version-sync（cache）、file-size-guardian（log 與門檻差值 state）。

方法：tmp_path 內建真實 repo（MAIN）與 linked worktree（WT），不設
HOOK_TEST_ISOLATION，cwd 與 CLAUDE_PROJECT_DIR 皆切到被測 checkout。
斷言讀與寫都落在 MAIN/.claude/hook-logs，WT 內不得出現狀態檔；
並以「WT 寫、MAIN 讀」「MAIN 寫、WT 讀」驗證跨 checkout 合流行為。
"""

from __future__ import annotations

import importlib.util
import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parent.parent
for _p in (HOOKS, HOOKS.parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True, capture_output=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"},
    )


@pytest.fixture
def repos(tmp_path: Path):
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q", "-b", "main")
    (main / "README.md").write_text("x")
    _git(main, "add", "README.md")
    _git(main, "commit", "-q", "-m", "init")
    wt = tmp_path / "wt"
    _git(main, "worktree", "add", "-q", "-b", "feat", str(wt))
    return main.resolve(), wt.resolve()


def _enter(monkeypatch, checkout: Path) -> None:
    """模擬 hook 在該 checkout 啟動（不設測試隔離）。"""
    monkeypatch.chdir(checkout)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(checkout))
    monkeypatch.delenv("HOOK_TEST_ISOLATION", raising=False)


def _load(filename: str):
    spec = importlib.util.spec_from_file_location(
        "g1_" + filename.replace("-", "_").removesuffix(".py"), HOOKS / filename
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _hook_logs(root: Path) -> Path:
    return root / ".claude" / "hook-logs"


LOGGER = logging.getLogger("g1-readback-test")


class TestDispatchCleanupDedup:
    """[WAIT] 廣播 dedup state：讀寫皆在主 checkout，跨 checkout 合流。"""

    @pytest.fixture
    def mod(self):
        return _load("subagent-stop-dispatch-cleanup-hook.py")

    @pytest.mark.parametrize("start", ["main", "wt"])
    def test_state_file_under_main(self, repos, monkeypatch, mod, start):
        main, wt = repos
        _enter(monkeypatch, {"main": main, "wt": wt}[start])
        path = mod._get_wait_dedup_state_file(wt)
        assert path == _hook_logs(main) / mod.HOOK_NAME / "wait-broadcast-dedup.json"

    def test_wt_write_then_main_read_is_suppressed(self, repos, monkeypatch, mod):
        main, wt = repos
        _enter(monkeypatch, wt)
        first = mod.check_and_record_broadcast(
            mod._get_wait_dedup_state_file(wt), "k", 600, LOGGER)
        assert first is False
        assert (_hook_logs(main) / mod.HOOK_NAME / "wait-broadcast-dedup.json").exists()
        assert not (_hook_logs(wt) / mod.HOOK_NAME / "wait-broadcast-dedup.json").exists()
        _enter(monkeypatch, main)
        second = mod.check_and_record_broadcast(
            mod._get_wait_dedup_state_file(main), "k", 600, LOGGER)
        assert second is True  # 合流：另一 checkout 的同 key 在 TTL 內被抑制


class TestPackageVersionSyncCache:
    @pytest.fixture
    def mod(self):
        return _load("package-version-sync-hook.py")

    @pytest.mark.parametrize("start", ["main", "wt"])
    def test_cache_dir_under_main(self, repos, monkeypatch, mod, start):
        main, wt = repos
        _enter(monkeypatch, {"main": main, "wt": wt}[start])
        d = mod._get_cache_dir(wt)
        assert d == _hook_logs(main) / mod.HOOK_NAME / "cache"
        assert not (_hook_logs(wt) / mod.HOOK_NAME).exists()

    def test_wt_write_main_read_roundtrip(self, repos, monkeypatch, mod):
        main, wt = repos
        _enter(monkeypatch, wt)
        data = {"version": mod.SYNC_CACHE_VERSION, "pyproject_hashes": {"a": "h"}}
        assert mod._save_sync_cache(wt, data) is True
        _enter(monkeypatch, main)
        assert mod._load_sync_cache(main) == data  # 合流：MAIN 讀到 WT 寫的 cache

    def test_hash_mismatch_across_checkouts_is_miss(self, repos, monkeypatch, mod):
        """合流後的後果：pyproject 內容不同的 checkout 讀到對方 cache 仍判 miss（照常同步）。"""
        main, wt = repos
        for root, text in ((main, "a"), (wt, "b")):
            pkg = root / "pk"
            pkg.mkdir()
            (pkg / "pyproject.toml").write_text(text)
        packages = {"pk": {"path": "pk", "version": "1"}}
        _enter(monkeypatch, main)
        mod._update_sync_cache(main, packages, {})
        assert mod._should_skip_sync_due_to_cache(main, packages) is True
        _enter(monkeypatch, wt)
        assert mod._should_skip_sync_due_to_cache(wt, packages) is False


class TestPhaseCompletionGateReport:
    def test_report_lands_in_main(self, repos, monkeypatch):
        mod = _load("phase-completion-gate-hook.py")
        main, wt = repos
        _enter(monkeypatch, wt)
        out = mod.save_completion_report(str(wt), {"k": 1}, LOGGER)
        assert out
        assert Path(out).parent == _hook_logs(main) / "phase-completion-gate"
        assert not (_hook_logs(wt) / "phase-completion-gate").exists()


class TestFileSizeGuardianState:
    @pytest.fixture
    def mod(self):
        return _load("file-size-guardian-hook.py")

    @pytest.mark.parametrize("start", ["main", "wt"])
    def test_budget_state_path_under_main(self, repos, monkeypatch, mod, start):
        main, wt = repos
        _enter(monkeypatch, {"main": main, "wt": wt}[start])
        assert mod._get_budget_state_path(wt) == (
            _hook_logs(main) / "file-size-guardian" / "auto-load-budget-state.json")

    def test_delta_read_back_across_checkouts(self, repos, monkeypatch, mod, capsys):
        """MAIN 先存總量；WT 啟動超標時讀到該值並輸出差值。"""
        main, wt = repos
        _enter(monkeypatch, main)
        mod.save_budget_state(mod._get_budget_state_path(main), 1000)
        _enter(monkeypatch, wt)
        monkeypatch.setattr(
            mod, "measure_auto_load_budget",
            lambda root: (mod.AUTO_LOAD_BUDGET_TOKENS + 500, [("f.md", 1)]))
        mod.report_auto_load_budget(wt, LOGGER)
        out = capsys.readouterr().out
        assert f"差值: +{mod.AUTO_LOAD_BUDGET_TOKENS + 500 - 1000} tokens" in out
        assert (_hook_logs(main) / "file-size-guardian" / "auto-load-budget-state.json").exists()
        assert not (_hook_logs(wt) / "file-size-guardian").exists()

    def test_main_writes_report_log_to_main(self, repos, monkeypatch, mod, capsys):
        main, wt = repos
        _enter(monkeypatch, wt)
        (wt / "big").mkdir()
        (wt / "big" / "a.md").write_text("x\n" * 10)
        monkeypatch.setattr(mod, "SCAN_CONFIG", [("big", ".md", 1, 2, "t")])
        monkeypatch.setattr(mod, "report_auto_load_budget", lambda root, logger: None)
        monkeypatch.setattr(mod, "get_code_root", lambda: wt)
        mod.main()
        capsys.readouterr()
        assert (_hook_logs(main) / "file-size-guardian" / "file-size-guardian.log").exists()
        assert not (_hook_logs(wt) / "file-size-guardian.log").exists()
        assert not (_hook_logs(wt) / "file-size-guardian" / "file-size-guardian.log").exists()
