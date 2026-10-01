"""
Test: git-ref-transaction-content-guard（源自 commit-stage-guard-gate 補網
掃描點綁「命令」而非「ref 寫入事件」的修復）——原生 git
`reference-transaction` hook 承載體，覆蓋 commit-stage-guard-gate-hook.py
（PreToolUse，綁 `git commit` 命令字面）零命中的路徑：隔離索引提交
（`commit-tree` + `update-ref`）與 `git merge --continue`。

驗證項目：
1. `_is_zero_oid`：全零 oid 判斷（刪除訊號）
2. `_collect_new_commits`：`git rev-list <new> --not --all` 語意——新
   commit（尚未被任何既有 ref 涵蓋）才回傳，純 ref 重新指向既有 commit
   （如 `checkout -b`）回傳空清單
3. main() 整合行為（以 `commit-tree` 建立尚未接上任何 ref 的 commit
   物件，模擬 `prepared` 階段「ref 尚未寫入但新 commit 已在 odb 中」的
   真實狀態，見 git-ref-transaction-content-guard.py 檔頭「判定新內容」
   段落實測依據）：
   - state 非 `prepared`（`committed`/`aborted`）一律 exit 0，即使 stdin
     內容格式錯誤也不解析
   - `refs/heads/*` 新增內容命中 deny 級發現 -> exit 1（中止該次 ref
     transaction），stderr 含逐項訊息
   - `refs/tags/*` 等非 `refs/heads/` ref 一律略過，不觸發掃描
   - `new-oid` 全零（刪除）略過
   - 新分支指向既有已涵蓋的 commit（`checkout -b` 型態）不重新掃描
   - 僅 WARN 級發現 -> exit 0，stderr 含提醒
   - 無發現 -> 靜默 exit 0

Source: 0.2.1-W3-1151（同波次追蹤票，見
`.claude/references/rule-enforcement-binding-points.md`「commit 層：掃
staged 內容」小節的推薦路徑零命中發現）
"""

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE_DIR = HOOKS_DIR.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(CLAUDE_DIR))

_spec = importlib.util.spec_from_file_location(
    "git_ref_transaction_content_guard",
    HOOKS_DIR / "git-ref-transaction-content-guard.py",
)
hook_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook_module)

_ZERO_OID = "0" * 40


def _run_git(args, cwd):
    result = subprocess.run(["git"] + args, cwd=str(cwd), capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def _capture(args, cwd):
    rc, out, err = _run_git(args, cwd)
    assert rc == 0, f"git {args} 失敗: {err}"
    return out.strip()


@pytest.fixture(scope="module")
def _baseline_template(tmp_path_factory):
    """每個測試檔只建一次基準 repo（含一個已 commit 的 HEAD），各測試以目錄
    複製取得隔離副本。

    等待來源是 git 子程序的啟動成本（主機高負載時每個約 70-400ms），建 repo
    的 5 個子程序原本在每個測試重複付一次；複製目錄是檔案系統操作，不啟動
    子程序。分支固定為 main（測試內有 `checkout main`，不依賴全域預設）。
    """
    repo = tmp_path_factory.mktemp("baseline") / "repo"
    repo.mkdir()
    _run_git(["init", "-q", "-b", "main"], cwd=repo)
    _run_git(["config", "user.email", "test@example.com"], cwd=repo)
    _run_git(["config", "user.name", "Test"], cwd=repo)
    (repo / "README.md").write_text("baseline\n", encoding="utf-8")
    _run_git(["add", "README.md"], cwd=repo)
    _run_git(["commit", "-q", "-m", "baseline"], cwd=repo)
    return repo


def _clone_baseline(template, dest):
    shutil.copytree(template, dest, symlinks=True)
    return dest


@pytest.fixture()
def scratch_repo(tmp_path, _baseline_template):
    """最小化隔離 git repo，含一個已 commit 的 HEAD 基準。"""
    return _clone_baseline(_baseline_template, tmp_path / "scratch")


def _run_guard(repo, state, stdin_text):
    result = subprocess.run(
        [sys.executable, str(HOOKS_DIR / "git-ref-transaction-content-guard.py"), state],
        input=stdin_text,
        cwd=str(repo),
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"},
    )
    return result


def _make_dangling_commit(repo, base_sha, rel_path, content):
    """在 `base_sha` 之上以 `commit-tree` 建立一個尚未接上任何 ref 的新
    commit（模擬 `prepared` 階段「新 commit 已在 odb、ref 尚未寫入」的
    真實狀態），回傳新 commit 的 SHA。呼叫端負責之後把 `base_sha` 當
    old-oid、新 SHA 當 new-oid 組成 stdin 傳給 `_run_guard`。
    """
    target = repo / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    _run_git(["add", "."], cwd=repo)
    tree = _capture(["write-tree"], cwd=repo)
    new_sha = _capture(["commit-tree", tree, "-p", base_sha, "-m", "test commit"], cwd=repo)
    # write-tree 之後 reset 掉 index/working tree 的暫存狀態，避免污染後續
    # 呼叫（commit-tree 只讀 index 建物件，不會自動回復 index 到 base_sha，
    # 但 base_sha 本身未變，重複呼叫本函式時 index 會疊加前次殘留）。
    _run_git(["reset", "-q", "--hard", base_sha], cwd=repo)
    return new_sha


class TestIsZeroOid:
    def test_all_zero_is_zero(self):
        assert hook_module._is_zero_oid(_ZERO_OID) is True

    def test_real_sha_is_not_zero(self):
        assert hook_module._is_zero_oid("a" * 40) is False

    def test_empty_string_is_not_zero(self):
        assert hook_module._is_zero_oid("") is False


class TestCollectNewCommits:
    def test_dangling_commit_is_new(self, scratch_repo):
        head = _capture(["rev-parse", "HEAD"], cwd=scratch_repo)
        new_sha = _make_dangling_commit(
            scratch_repo, head, "note.md", "一般內容。\n"
        )
        project_root = scratch_repo
        found = hook_module._collect_new_commits(new_sha, project_root)
        assert new_sha in found

    def test_existing_reachable_commit_is_not_new(self, scratch_repo):
        head = _capture(["rev-parse", "HEAD"], cwd=scratch_repo)
        found = hook_module._collect_new_commits(head, scratch_repo)
        assert found == []


class TestMainIntegration:
    def test_non_prepared_state_short_circuits_even_with_garbage_stdin(self, scratch_repo):
        result = _run_guard(scratch_repo, "committed", "not a valid ref-transaction line\n")
        assert result.returncode == 0

    def test_new_commit_with_violation_denies(self, scratch_repo):
        head = _capture(["rev-parse", "HEAD"], cwd=scratch_repo)
        new_sha = _make_dangling_commit(
            scratch_repo,
            head,
            ".claude/references/y.md",
            "既有內容，不含引用。\n引用 W9-501 的分析結論。\n",
        )
        stdin_text = f"{head} {new_sha} refs/heads/main\n"

        result = _run_guard(scratch_repo, "prepared", stdin_text)

        assert result.returncode == 87
        assert "reference-stability-rule8-guard" in result.stderr
        assert "git-ref-transaction-content-guard" in result.stderr

    def test_clean_content_allows(self, scratch_repo):
        # 路徑用 .claude/ 前綴（branch-verify 對 main 保護分支的豁免前綴之
        # 一），避免與本測試無關的 branch-verify 判斷介入，聚焦本檔負責
        # 的「新 commit 判定」邏輯。
        head = _capture(["rev-parse", "HEAD"], cwd=scratch_repo)
        new_sha = _make_dangling_commit(
            scratch_repo, head, ".claude/notes/clean.md", "無任何違規的一般內容。\n"
        )
        stdin_text = f"{head} {new_sha} refs/heads/main\n"

        result = _run_guard(scratch_repo, "prepared", stdin_text)

        assert result.returncode == 0

    def test_non_heads_ref_is_skipped(self, scratch_repo):
        head = _capture(["rev-parse", "HEAD"], cwd=scratch_repo)
        new_sha = _make_dangling_commit(
            scratch_repo,
            head,
            ".claude/references/z.md",
            "引用 W9-503 的分析結論。\n",
        )
        stdin_text = f"{head} {new_sha} refs/tags/v1\n"

        result = _run_guard(scratch_repo, "prepared", stdin_text)

        assert result.returncode == 0

    def test_deletion_new_oid_zero_is_skipped(self, scratch_repo):
        head = _capture(["rev-parse", "HEAD"], cwd=scratch_repo)
        stdin_text = f"{head} {_ZERO_OID} refs/heads/main\n"

        result = _run_guard(scratch_repo, "prepared", stdin_text)

        assert result.returncode == 0

    def test_new_branch_pointing_to_existing_commit_not_rescanned(self, scratch_repo):
        """模擬 `git checkout -b feature <既有 commit>`：old-oid 全零
        （建立語意），new-oid 是已被 `refs/heads/main` 涵蓋的既有 commit
        ——即使該 commit 內容原本含違規，因非本次 transaction 引入的新
        內容，不應重新掃描。"""
        target = scratch_repo / ".claude" / "references" / "w.md"
        target.parent.mkdir(parents=True)
        target.write_text("引用 W9-504 的分析結論。\n", encoding="utf-8")
        _run_git(["add", "."], cwd=scratch_repo)
        _run_git(["commit", "-q", "-m", "already committed with content"], cwd=scratch_repo)
        head = _capture(["rev-parse", "HEAD"], cwd=scratch_repo)

        stdin_text = f"{_ZERO_OID} {head} refs/heads/feature\n"
        result = _run_guard(scratch_repo, "prepared", stdin_text)

        assert result.returncode == 0

    def test_warn_only_finding_allows_with_stderr_message(self, scratch_repo):
        head = _capture(["rev-parse", "HEAD"], cwd=scratch_repo)
        new_sha = _make_dangling_commit(
            scratch_repo,
            head,
            ".claude/references/clean.md",
            "一般內容，無違規，僅屬 framework 路徑會觸發 WARN 提醒。\n",
        )
        stdin_text = f"{head} {new_sha} refs/heads/main\n"

        result = _run_guard(scratch_repo, "prepared", stdin_text)

        assert result.returncode == 0
        assert "framework-rule-edit-skill-trigger" in result.stderr


def _prepare_merge_commit(repo, feature_path, feature_content):
    """在 `repo` 建一個 feature 分支（`feature/x`）並 commit 一個非豁免路徑
    的變更，回到 main 後以 `git merge --no-ff --no-commit` 完成合併計算
    （寫入 index、建立 `MERGE_HEAD`，但不建立 commit 也不更新 ref，精確
    對應 `reference-transaction` `prepared` 階段的真實狀態），再以
    `commit-tree` 補上尚未接上任何 ref 的合併 commit 物件。

    回傳 (main_head_sha, merge_commit_sha)，呼叫端自行組 stdin。
    """
    main_head = _capture(["rev-parse", "HEAD"], cwd=repo)
    _run_git(["checkout", "-q", "-b", "feature/x"], cwd=repo)
    target = repo / feature_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(feature_content, encoding="utf-8")
    _run_git(["add", "."], cwd=repo)
    _run_git(["commit", "-q", "-m", "feature work"], cwd=repo)
    feature_head = _capture(["rev-parse", "HEAD"], cwd=repo)

    _run_git(["checkout", "-q", "main"], cwd=repo)
    rc, _out, err = _run_git(["merge", "--no-ff", "--no-commit", "feature/x"], cwd=repo)
    assert rc == 0, f"merge --no-commit 失敗: {err}"

    tree = _capture(["write-tree"], cwd=repo)
    merge_sha = _capture(
        ["commit-tree", tree, "-p", main_head, "-p", feature_head, "-m", "merge test"],
        cwd=repo,
    )
    return main_head, merge_sha


class TestMergeExemption:
    """0.1.0-W3-136：branch-verify 對合併 commit（多 parent）豁免，消解
    「框架建議的 `git merge --no-edit`」與「守衛必然 deny 保護分支非豁免
    路徑」之間的矛盾。三案例對應 acceptance 第 5 條。
    """

    def test_merge_commit_on_main_allows_non_exempt_path(self, scratch_repo):
        """main 上 merge：非豁免路徑（`lib/`，不在 `.claude/` / `docs/`
        豁免前綴內）原本必然被 branch-verify deny，豁免後應放行。"""
        main_head, merge_sha = _prepare_merge_commit(
            scratch_repo, "lib/app.dart", "void main() {}\n"
        )
        stdin_text = f"{main_head} {merge_sha} refs/heads/main\n"

        result = _run_guard(scratch_repo, "prepared", stdin_text)

        assert result.returncode == 0, result.stderr

    def test_direct_commit_on_main_to_non_exempt_path_still_denied(self, scratch_repo):
        """main 上逐檔直接提交（單一 parent，非合併）：非豁免路徑仍須被
        branch-verify 擋下，豁免不擴及直接提交，保護意圖不變。"""
        head = _capture(["rev-parse", "HEAD"], cwd=scratch_repo)
        new_sha = _make_dangling_commit(
            scratch_repo, head, "lib/app.dart", "void main() {}\n"
        )
        stdin_text = f"{head} {new_sha} refs/heads/main\n"

        result = _run_guard(scratch_repo, "prepared", stdin_text)

        assert result.returncode == 87
        assert "branch-verify" in result.stderr

    def test_merge_with_other_guard_violation_includes_residue_cleanup_note(
        self, scratch_repo
    ):
        """merge 情境下若其他 guard（非 branch-verify）仍 deny，stderr 須含
        MERGE_HEAD 殘局提醒與 `git merge --abort` 清理指引（acceptance 第 2
        條：即使仍被擋，也不留下無提示的殘局）。"""
        main_head, merge_sha = _prepare_merge_commit(
            scratch_repo,
            ".claude/references/merge-note.md",
            "既有內容，不含引用。\n引用 W9-777 的分析結論。\n",
        )
        stdin_text = f"{main_head} {merge_sha} refs/heads/main\n"

        result = _run_guard(scratch_repo, "prepared", stdin_text)

        assert result.returncode == 87
        assert "reference-stability-rule8-guard" in result.stderr
        assert "merge 殘局提醒" in result.stderr
        assert "git merge --abort" in result.stderr

    def test_commit_on_feature_branch_unaffected(self, scratch_repo):
        """worktree／feature 分支內提交行為不變：目標 ref 非保護分支時，
        merge 與直接提交皆不受 branch-verify 管轄（is_merge_commit 旗標
        對此路徑無作用，維持既有放行行為）。"""
        main_head = _capture(["rev-parse", "HEAD"], cwd=scratch_repo)
        _run_git(["checkout", "-q", "-b", "feature/base"], cwd=scratch_repo)
        (scratch_repo / "lib").mkdir(exist_ok=True)
        (scratch_repo / "lib" / "app.dart").write_text("void main() {}\n", encoding="utf-8")
        _run_git(["add", "."], cwd=scratch_repo)
        _run_git(["commit", "-q", "-m", "feature base"], cwd=scratch_repo)
        feature_head = _capture(["rev-parse", "HEAD"], cwd=scratch_repo)

        stdin_text = f"{main_head} {feature_head} refs/heads/feature/base\n"
        result = _run_guard(scratch_repo, "prepared", stdin_text)

        assert result.returncode == 0, result.stderr


# ============================================================================
# 批次化（子程序數與 F 無關）與新舊路徑等價性
#
# 「舊路徑」= 檔內保留的逐檔實作（`_build_scan_files_legacy` +
# `_check_branch_verify` 不帶 ctx），同時是批次化失敗時的 fallback；
# 「新路徑」= 批次化實作。同一輸入兩者的 StagedFile 與 findings 必須逐項相同。
# ============================================================================


def _make_commit_from_files(repo, base_sha, files, extra_parents=()):
    """在 base_sha 之上以 commit-tree 建立含多檔變更的懸空 commit。
    files: {相對路徑: bytes | None}，None 表示刪除。回傳新 commit SHA。"""
    for rel, data in files.items():
        target = repo / rel
        if data is None:
            if target.exists():
                target.unlink()
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    _run_git(["add", "-A"], cwd=repo)
    tree = _capture(["write-tree"], cwd=repo)
    parent_args = []
    for parent in (base_sha,) + tuple(extra_parents):
        parent_args += ["-p", parent]
    new_sha = _capture(["commit-tree", tree] + parent_args + ["-m", "multi"], cwd=repo)
    _run_git(["reset", "-q", "--hard", base_sha], cwd=repo)
    return new_sha


def _commit_on_main(repo, files):
    for rel, data in files.items():
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    _run_git(["add", "-A"], cwd=repo)
    _run_git(["commit", "-q", "-m", "setup"], cwd=repo)
    return _capture(["rev-parse", "HEAD"], cwd=repo)


_OLD_NOTE = "".join(f"line {i} of the original note\n" for i in range(12)).encode()


def _scenario_violation(repo):
    head = _capture(["rev-parse", "HEAD"], cwd=repo)
    return head, _make_commit_from_files(
        repo, head, {".claude/references/y.md": "既有內容。\n引用 W9-501 的分析結論。\n".encode()}
    ), False


def _scenario_clean(repo):
    head = _capture(["rev-parse", "HEAD"], cwd=repo)
    return head, _make_commit_from_files(
        repo, head, {".claude/notes/clean.md": b"plain content\n"}
    ), False


def _scenario_multi_file(repo):
    """多檔：新增（豁免與非豁免路徑）、修改、刪除、改名+微改、CRLF、
    尾端多重換行、含違規檔。"""
    head = _commit_on_main(
        repo,
        {
            ".claude/notes/old.md": _OLD_NOTE,
            ".claude/notes/edit.md": b"before\n",
            ".claude/notes/gone.md": b"to be deleted\n",
        },
    )
    return head, _make_commit_from_files(
        repo,
        head,
        {
            ".claude/notes/old.md": None,
            ".claude/notes/renamed.md": _OLD_NOTE + b"one more line\n",
            ".claude/notes/edit.md": b"after\r\nsecond\r\n\n\n",
            ".claude/notes/gone.md": None,
            "lib/app.dart": b"void main() {}\n",
            ".claude/references/v.md": "引用 W9-502 的分析結論。\n".encode(),
            ".claude/notes/crlf.md": b"a\r\nb\r\n",
        },
    ), False


def _scenario_root_commit(repo):
    head = _capture(["rev-parse", "HEAD"], cwd=repo)
    tree_file = repo / ".claude" / "notes" / "root.md"
    tree_file.parent.mkdir(parents=True, exist_ok=True)
    tree_file.write_text("root content\n", encoding="utf-8")
    _run_git(["add", "-A"], cwd=repo)
    tree = _capture(["write-tree"], cwd=repo)
    new_sha = _capture(["commit-tree", tree, "-m", "root"], cwd=repo)
    _run_git(["reset", "-q", "--hard", head], cwd=repo)
    return head, new_sha, False


def _scenario_merge(repo):
    main_head, merge_sha = _prepare_merge_commit(repo, "lib/app.dart", "void main() {}\n")
    return main_head, merge_sha, True


_SCENARIOS = {
    "violation": _scenario_violation,
    "clean": _scenario_clean,
    "multi_file": _scenario_multi_file,
    "root_commit": _scenario_root_commit,
    "merge": _scenario_merge,
}


@pytest.fixture(scope="module")
def _scenario_templates(tmp_path_factory, _baseline_template):
    """情境 repo 每個情境整個測試檔只建一次（建構需十餘個 git 子程序），
    各測試取目錄副本；commit 物件與 SHA 隨副本帶走，情境語意不變。"""
    built = {}

    def get(name):
        if name not in built:
            repo = _clone_baseline(
                _baseline_template, tmp_path_factory.mktemp(f"scn-{name}") / "repo"
            )
            built[name] = (repo, *_SCENARIOS[name](repo))
        return built[name]

    return get


@pytest.fixture()
def scenario_repo(tmp_path, _scenario_templates):
    """回傳 build(name) -> (repo_copy, base_sha, new_sha, is_merge)。"""
    def build(name):
        template, base, new_sha, is_merge = _scenario_templates(name)
        return _clone_baseline(template, tmp_path / f"scn-{name}"), base, new_sha, is_merge

    return build


class _Logger:
    def info(self, *a, **k): pass
    def debug(self, *a, **k): pass
    def warning(self, *a, **k): pass


def _legacy_findings(files, project_root, is_merge):
    """舊路徑的 findings：逐檔呼叫不帶 ctx 的 _check_branch_verify（每檔自行
    重查專案根與分支），其餘 per-file 檢查與 wrap 一致性檢查照舊。"""
    from lib import commit_content_guards as ccg

    findings, wrap_checked = [], False
    for sf in files:
        for check in ccg._PER_FILE_CHECKS:
            findings.extend(check(sf, _Logger()))
        findings.extend(ccg._check_branch_verify(sf, _Logger(), is_merge_commit=is_merge))
        if not wrap_checked:
            wrap_findings = ccg._check_wrap_skill_yaml(sf, _Logger(), project_root)
            if wrap_findings:
                findings.extend(wrap_findings)
                wrap_checked = True
    return findings


# gate（hooks-test-gate）只跑本檔：代表情境取成本最低且含 deny 發現者；
# 其餘情境與重量級變體在 test_git_ref_transaction_content_guard_batched.py
_GATE_SCENARIOS = ("violation",)


class TestBatchedEquivalence:
    @pytest.mark.parametrize("name", _GATE_SCENARIOS)
    def test_staged_files_identical_to_legacy(self, scenario_repo, monkeypatch, name):
        scratch_repo, _base, new_sha, _merge = scenario_repo(name)
        monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
        monkeypatch.chdir(scratch_repo)

        legacy = hook_module._build_scan_files_legacy(new_sha, scratch_repo)
        commits = hook_module._collect_new_commits_with_parents([new_sha], scratch_repo)
        batched = hook_module._build_scan_files_batched(commits, scratch_repo)

        assert legacy, "情境應至少有一個變更檔"
        assert batched[new_sha] == legacy

    @pytest.mark.parametrize("name", _GATE_SCENARIOS)
    def test_findings_identical_to_legacy(self, scenario_repo, monkeypatch, name):
        from lib import commit_content_guards as ccg

        scratch_repo, _base, new_sha, is_merge = scenario_repo(name)
        monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
        monkeypatch.chdir(scratch_repo)
        files = hook_module._build_scan_files_legacy(new_sha, scratch_repo)

        old = _legacy_findings(files, scratch_repo, is_merge)
        new = ccg._run_all_checks(files, scratch_repo, _Logger(), is_merge_commit=is_merge)

        assert new == old


class TestWorktreeBranchResolution:
    """W1-028：分支判定以寫入的 ref 與寫入發生的 worktree 為準，不受
    CLAUDE_PROJECT_DIR 指向別的 checkout 影響。走真實 reference-transaction
    路徑（hook 安裝於共用 hooks 目錄，由 git update-ref 觸發）。"""

    _ENV_BASE = {"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "HOME": "/nonexistent"}

    @pytest.fixture()
    def wt_repo(self, tmp_path, _baseline_template):
        main = _clone_baseline(_baseline_template, tmp_path / "main")
        wt = tmp_path / "feat-wt"
        _capture(["worktree", "add", "-q", "-b", "feat/x", str(wt)], cwd=main)
        hook = main / ".git" / "hooks" / "reference-transaction"
        hook.parent.mkdir(exist_ok=True)
        hook.write_text(
            "#!/bin/sh\nexec %s %s \"$1\"\n"
            % (sys.executable, HOOKS_DIR / "git-ref-transaction-content-guard.py"),
            encoding="utf-8",
        )
        hook.chmod(0o755)
        return main, wt

    def _dangling(self, repo, rel_path):
        head = _capture(["rev-parse", "HEAD"], cwd=repo)
        return _make_dangling_commit(repo, head, rel_path, "非豁免路徑內容\n")

    def _update_ref(self, cwd, args, project_dir):
        env = dict(self._ENV_BASE, CLAUDE_PROJECT_DIR=str(project_dir))
        return subprocess.run(
            ["git", "update-ref"] + args, cwd=str(cwd), capture_output=True, text=True, env=env
        )

    def test_b_protected_branch_write_denied_when_env_points_to_feature_worktree(self, wt_repo):
        main, wt = wt_repo
        new_sha = self._dangling(main, "src/violation.txt")
        result = self._update_ref(main, ["refs/heads/main", new_sha], project_dir=wt)
        assert result.returncode != 0, result.stderr
        assert "branch-verify" in result.stderr

    def test_ref_decides_branch_not_worktree_head(self, wt_repo):
        """寫入的 ref 為 refs/heads/main，即使 cwd 在 feature worktree（HEAD=feat/x）也應判為保護分支。"""
        main, wt = wt_repo
        new_sha = self._dangling(wt, "src/violation.txt")
        result = self._update_ref(wt, ["refs/heads/main", new_sha], project_dir=wt)
        assert result.returncode != 0, result.stderr

    def _scan(self, root, monkeypatch, project_dir, rel_path, **kw):
        from lib import commit_content_guards as ccg

        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project_dir))
        monkeypatch.chdir(root)
        sf = ccg.StagedFile(rel_path, "", "內容\n", "內容\n")
        return ccg._run_all_checks([sf], root, _Logger(), **kw)

    def test_a_lib_level_feature_worktree_not_judged_by_env_checkout(self, wt_repo, monkeypatch):
        """A 情境於 lib 層（PreToolUse 呼叫端同路徑）：root=feature worktree，env 指向 main
        checkout，修正前 branch-verify 取 env 的 main 分支而誤擋。"""
        main, wt = wt_repo
        findings = self._scan(wt, monkeypatch, main, "src/legit.txt")
        assert not [f for f in findings if f.source == "branch-verify"]

    def test_b_lib_level_protected_root_denied_despite_env_on_feature(self, wt_repo, monkeypatch):
        main, wt = wt_repo
        findings = self._scan(main, monkeypatch, wt, "src/violation.txt")
        assert [f for f in findings if f.source == "branch-verify" and f.severity == "deny"]

    def test_explicit_branch_overrides_head_branch(self, wt_repo, monkeypatch):
        main, wt = wt_repo
        findings = self._scan(wt, monkeypatch, wt, "src/violation.txt", branch="main")
        assert [f for f in findings if f.source == "branch-verify" and f.severity == "deny"]

    def test_detached_head_write_keeps_head_based_verdict(self, wt_repo):
        """detached HEAD 寫入（ref 為 HEAD，不帶分支名）：維持讀該 worktree HEAD 的現行判定，
        detached 無分支名 -> 不檢查；env 指向 main checkout 不得改變結論。"""
        main, wt = wt_repo
        _capture(["checkout", "-q", "--detach"], cwd=wt)
        new_sha = self._dangling(wt, "src/detached.txt")
        result = self._update_ref(wt, ["--no-deref", "HEAD", new_sha], project_dir=main)
        assert result.returncode == 0, result.stderr


class TestPrevalidateOnlyMode:
    """預驗證模式（GIT_REF_GUARD_PREVALIDATE_ONLY=1）：只有「無任何發現」才輸出
    PREVALIDATE_CLEAN；deny 與 WARN 不得輸出（呼叫端據此不設 GUARD_PREVALIDATED）。"""

    def _run(self, repo, ref, new_sha, old_sha, prevalidate):
        env = {"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"}
        if prevalidate:
            env["GIT_REF_GUARD_PREVALIDATE_ONLY"] = "1"
        return subprocess.run(
            [sys.executable, str(HOOKS_DIR / "git-ref-transaction-content-guard.py"), "prepared"],
            input=f"{old_sha} {new_sha} {ref}\n", cwd=str(repo), capture_output=True,
            text=True, env=env,
        )

    def test_clean_emits_token_only_in_prevalidate_mode(self, scratch_repo):
        _capture(["checkout", "-q", "-b", "feat/z"], cwd=scratch_repo)
        head = _capture(["rev-parse", "HEAD"], cwd=scratch_repo)
        new = _make_dangling_commit(scratch_repo, head, "docs/clean.md", "乾淨\n")
        on = self._run(scratch_repo, "refs/heads/feat/z", new, head, True)
        off = self._run(scratch_repo, "refs/heads/feat/z", new, head, False)
        assert on.returncode == 0 and on.stdout.strip() == "PREVALIDATE_CLEAN", on.stderr
        assert off.returncode == 0 and off.stdout == ""

    def test_deny_never_emits_token(self, scratch_repo):
        head = _capture(["rev-parse", "HEAD"], cwd=scratch_repo)
        new = _make_dangling_commit(scratch_repo, head, "src/violation.txt", "違規\n")
        r = self._run(scratch_repo, "refs/heads/main", new, head, True)
        assert r.returncode == hook_module.EXIT_BLOCK
        assert "PREVALIDATE_CLEAN" not in r.stdout

    def test_ref_decides_branch_in_prevalidate_mode(self, scratch_repo):
        """同一個 commit：寫入 feature 分支為乾淨、寫入 main 為 deny（分支綁定 ref）。"""
        _capture(["checkout", "-q", "-b", "feat/z"], cwd=scratch_repo)
        head = _capture(["rev-parse", "HEAD"], cwd=scratch_repo)
        new = _make_dangling_commit(scratch_repo, head, "src/v.txt", "內容\n")
        ok = self._run(scratch_repo, "refs/heads/feat/z", new, head, True)
        bad = self._run(scratch_repo, "refs/heads/main", new, head, True)
        assert ok.stdout.strip() == "PREVALIDATE_CLEAN"
        assert bad.returncode == hook_module.EXIT_BLOCK and bad.stdout.strip() == ""


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
