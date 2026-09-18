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


@pytest.fixture()
def scratch_repo(tmp_path):
    """最小化隔離 git repo，含一個已 commit 的 HEAD 基準。"""
    repo = tmp_path / "scratch"
    repo.mkdir()
    _run_git(["init", "-q"], cwd=repo)
    _run_git(["config", "user.email", "test@example.com"], cwd=repo)
    _run_git(["config", "user.name", "Test"], cwd=repo)
    (repo / "README.md").write_text("baseline\n", encoding="utf-8")
    _run_git(["add", "README.md"], cwd=repo)
    _run_git(["commit", "-q", "-m", "baseline"], cwd=repo)
    return repo


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

        assert result.returncode == 1
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

        assert result.returncode == 1
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

        assert result.returncode == 1
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


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
