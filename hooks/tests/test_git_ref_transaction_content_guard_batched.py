"""
Test: git-ref-transaction-content-guard 批次化路徑的重量級驗證。

自 test_git_ref_transaction_content_guard.py 搬出（斷言未改），原因：
hooks-test-gate 只對被改動 hook 本體執行「名稱完全符合」的單一測試檔
（test_<stem>.py），該檔在 consumer 環境曾逾 PER_FILE_TIMEOUT。本檔不被
gate 選中，但全套件照跑。

gate 驗什麼（留在原檔）：批次路徑與舊路徑的等價性，代表情境 violation
（StagedFile 與 findings 各一案）。
本檔驗什麼：其餘情境（clean／multi_file／root_commit／merge）的等價性、
deny／放行對照輸入、patch 區段數不符的 fallback、子程序數與變更檔數無關。
剩餘風險：改 hook 時，上述重量級變體的問題要等全套件才會被發現。

共用 fixture 與輔助函式自原檔匯入，不複製。
"""

import subprocess
import sys

import pytest

from .test_git_ref_transaction_content_guard import (  # noqa: F401  (fixture 須在本模組命名空間)
    HOOKS_DIR,
    _GATE_SCENARIOS,
    _SCENARIOS,
    _Logger,
    _baseline_template,
    _capture,
    _clone_baseline,
    _legacy_findings,
    _make_commit_from_files,
    _scenario_templates,
    hook_module,
    scenario_repo,
)

_HEAVY_SCENARIOS = sorted(set(_SCENARIOS) - set(_GATE_SCENARIOS))


class TestBatchedEquivalenceHeavy:
    @pytest.mark.parametrize("name", _HEAVY_SCENARIOS)
    def test_staged_files_identical_to_legacy(self, scenario_repo, monkeypatch, name):
        scratch_repo, _base, new_sha, _merge = scenario_repo(name)
        monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
        monkeypatch.chdir(scratch_repo)

        legacy = hook_module._build_scan_files_legacy(new_sha, scratch_repo)
        commits = hook_module._collect_new_commits_with_parents([new_sha], scratch_repo)
        batched = hook_module._build_scan_files_batched(commits, scratch_repo)

        assert legacy, "情境應至少有一個變更檔"
        assert batched[new_sha] == legacy

    @pytest.mark.parametrize("name", _HEAVY_SCENARIOS)
    def test_findings_identical_to_legacy(self, scenario_repo, monkeypatch, name):
        from lib import commit_content_guards as ccg

        scratch_repo, _base, new_sha, is_merge = scenario_repo(name)
        monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
        monkeypatch.chdir(scratch_repo)
        files = hook_module._build_scan_files_legacy(new_sha, scratch_repo)

        old = _legacy_findings(files, scratch_repo, is_merge)
        new = ccg._run_all_checks(files, scratch_repo, _Logger(), is_merge_commit=is_merge)

        assert new == old

    def test_scenarios_cover_both_verdicts(self, scenario_repo, monkeypatch):
        """對照輸入（規則 E2）：情境集合必須同時含有 deny 與無 deny，否則
        等價性測試可能在「兩邊都空」的情況下空轉通過。"""
        from lib import commit_content_guards as ccg

        monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
        v_repo, _b, violating, _m = scenario_repo("violation")
        c_repo, _b, clean, _m = scenario_repo("clean")
        monkeypatch.chdir(v_repo)
        v = ccg._run_all_checks(
            hook_module._build_scan_files_legacy(violating, v_repo), v_repo, _Logger()
        )
        monkeypatch.chdir(c_repo)
        c = ccg._run_all_checks(
            hook_module._build_scan_files_legacy(clean, c_repo), c_repo, _Logger()
        )
        assert any(f.severity == "deny" for f in v)
        assert not any(f.severity == "deny" for f in c)

    def test_fallback_to_legacy_when_patch_sections_mismatch(self, scenario_repo, monkeypatch):
        """全量 patch 區段數與 name-status 條目數不符時，批次路徑必須退回
        逐檔實作，結果仍與舊路徑相同。"""
        scratch_repo, _b, new_sha, _m = scenario_repo("multi_file")
        monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
        monkeypatch.chdir(scratch_repo)
        legacy = hook_module._build_scan_files_legacy(new_sha, scratch_repo)
        commits = hook_module._collect_new_commits_with_parents([new_sha], scratch_repo)
        monkeypatch.setattr(hook_module, "_split_patch_sections", lambda text: [])
        assert hook_module._build_scan_files_batched(commits, scratch_repo)[new_sha] == legacy


def _count_git_subprocesses(repo, stdin_text, tmp_path):
    trace = tmp_path / f"trace-{repo.name}.log"
    env = {"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "GIT_TRACE": str(trace)}
    result = subprocess.run(
        [sys.executable, str(HOOKS_DIR / "git-ref-transaction-content-guard.py"), "prepared"],
        input=stdin_text, cwd=str(repo), capture_output=True, text=True, env=env,
    )
    lines = trace.read_text(encoding="utf-8").splitlines()
    return result, sum(1 for line in lines if "trace: built-in: git" in line)


class TestSubprocessCountConstant:
    """git 子程序數不得隨變更檔數 F 成長（持鎖時間與子程序數成正比）。"""

    def _run_with_f(self, tmp_path, n_files, template):
        repo = _clone_baseline(template, tmp_path / f"r{n_files}")
        head = _capture(["rev-parse", "HEAD"], cwd=repo)
        files = {f".claude/notes/n{i}.md": b"plain content\n" for i in range(n_files)}
        new_sha = _make_commit_from_files(repo, head, files)
        return _count_git_subprocesses(repo, f"{head} {new_sha} refs/heads/main\n", tmp_path)

    def test_count_independent_of_changed_file_count(self, tmp_path, _baseline_template):
        r1, n1 = self._run_with_f(tmp_path, 1, _baseline_template)
        r21, n21 = self._run_with_f(tmp_path, 21, _baseline_template)
        assert r1.returncode == 0 and r21.returncode == 0
        assert n21 == n1, f"F=1 -> {n1} 個子程序，F=21 -> {n21} 個"
        assert n21 <= 20


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
