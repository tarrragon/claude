"""Unit tests for skill_sync.cli exclude-file logic and content-hash sync comparison."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skill_sync.cli import (  # noqa: E402
    _apply_prune,
    _classify_sync_status,
    _extract_local_manifest,
    _has_local_override,
    _should_exclude_file,
    build_parser,
    build_push_plan,
    cmd_push,
    compute_content_hash,
    compute_diff,
    EXCLUDE_DIRS,
    DivergedSkill,
    fetch_remote_manifest,
    get_skills_dir,
    print_diff_preview,
    prune_dst_only,
    SKILL_SYNC_OVERRIDE_MARKER,
    sync_status_report,
    SyncStatus,
    update_sync_manifest,
    _warn_skill_md_case_mismatch,
)


def test_get_skills_dir_resolves_to_git_toplevel_from_repo_root(tmp_path, monkeypatch):
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    monkeypatch.chdir(repo)

    result = get_skills_dir()

    assert result == repo / ".claude" / "skills"


def test_get_skills_dir_resolves_to_git_toplevel_from_subdirectory(tmp_path, monkeypatch):
    import subprocess

    repo = tmp_path / "repo"
    subdir = repo / ".claude" / "skills" / "skill-sync"
    subdir.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    monkeypatch.chdir(subdir)

    result = get_skills_dir()

    assert result == repo / ".claude" / "skills"


def test_get_skills_dir_falls_back_to_cwd_outside_git_repo(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    result = get_skills_dir()

    assert result == tmp_path / ".claude" / "skills"
    captured = capsys.readouterr()
    assert "Warning" in captured.err


def test_hook_logs_top_level_jsonl_excluded():
    assert _should_exclude_file(".claude/hook-logs/cli-force-usage.jsonl") is True


def test_hook_logs_nested_subdir_excluded():
    assert _should_exclude_file(".claude/hook-logs/identity-guard/usage.log") is True


def test_hook_logs_dir_registered_in_exclude_dirs():
    assert "hook-logs" in EXCLUDE_DIRS


def test_regular_skill_file_not_excluded():
    assert _should_exclude_file("SKILL.md") is False
    assert _should_exclude_file("scripts/run.py") is False


def test_existing_exclude_dirs_still_work():
    assert _should_exclude_file(".venv/lib/site-packages/foo.py") is True
    assert _should_exclude_file("__pycache__/cli.cpython-314.pyc") is True
    assert _should_exclude_file(".pytest_cache/v/cache/nodeids") is True


def test_compute_diff_excludes_hook_logs_from_added(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    (src / "SKILL.md").write_text("hello")
    hook_logs_dir = src / ".claude" / "hook-logs" / "identity-guard"
    hook_logs_dir.mkdir(parents=True)
    (hook_logs_dir / "usage.log").write_text("runtime state")
    (src / ".claude" / "hook-logs" / "cli-force-usage.jsonl").write_text("{}")

    diff = compute_diff(src, dst)

    assert "SKILL.md" in diff["added"]
    assert not any("hook-logs" in f for f in diff["added"])
    assert not any("hook-logs" in f for f in diff["modified"])
    assert not any("hook-logs" in f for f in diff["dst_only"])


def _write_skill(base: Path, name: str, version: str, body: str) -> Path:
    """建立測試用 skill 目錄，SKILL.md 含指定版本字串與內文，回傳該目錄路徑。"""
    skill_dir = base / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"# {name}\n\n**Version**: {version}\n\n{body}\n"
    )
    return skill_dir


class _FakeCompletedProcess:
    """替代 subprocess.CompletedProcess，讓 update_sync_manifest 的測試不觸發真實 git/網路操作。"""

    def __init__(self, returncode: int = 0) -> None:
        self.returncode = returncode
        self.stdout = ""
        self.stderr = ""


# --- compute_content_hash ---------------------------------------------------


def test_content_hash_identical_content_produces_identical_hash(tmp_path):
    a = _write_skill(tmp_path / "a", "wrap-decision", "2.5.0", "same body")
    b = _write_skill(tmp_path / "b", "wrap-decision", "2.5.0", "same body")

    assert compute_content_hash(a) == compute_content_hash(b)


def test_content_hash_different_content_produces_different_hash(tmp_path):
    a = _write_skill(tmp_path / "a", "wrap-decision", "2.5.0", "content A")
    b = _write_skill(tmp_path / "b", "wrap-decision", "2.5.0", "content B")

    assert compute_content_hash(a) != compute_content_hash(b)


def test_content_hash_ignores_mtime(tmp_path):
    skill_dir = _write_skill(tmp_path, "wrap-decision", "2.5.0", "body")
    first = compute_content_hash(skill_dir)

    (skill_dir / "SKILL.md").touch()  # 更新 mtime，不改內容

    assert compute_content_hash(skill_dir) == first


def test_content_hash_excludes_override_marker_file(tmp_path):
    skill_dir = _write_skill(tmp_path, "wrap-decision", "2.5.0", "body")
    without_marker = compute_content_hash(skill_dir)

    (skill_dir / SKILL_SYNC_OVERRIDE_MARKER).write_text("local customization notice")

    assert compute_content_hash(skill_dir) == without_marker


def test_content_hash_excludes_hook_logs_dir(tmp_path):
    skill_dir = _write_skill(tmp_path, "wrap-decision", "2.5.0", "body")
    without_logs = compute_content_hash(skill_dir)

    hook_logs = skill_dir / "hook-logs"
    hook_logs.mkdir()
    (hook_logs / "usage.log").write_text("runtime state")

    assert compute_content_hash(skill_dir) == without_logs


def test_content_hash_returns_none_for_missing_dir(tmp_path):
    assert compute_content_hash(tmp_path / "does-not-exist") is None


# --- regression: 同號不同內容不再被判為 up_to_date（0.2.1-W3-124 §11.2） ------


def test_blog_and_canonical_2_5_0_same_version_different_content_are_diverged(tmp_path):
    """blog 的 2.5.0（基礎設施累積型絆腳索）與 canonical 的 2.5.0（行前預想配早期警訊）
    版本字串相同、內容不同；修改前的字串比對會誤判為 up_to_date，本測試證明
    改用內容雜湊後兩者被正確識別為分歧。"""
    local_dir = _write_skill(
        tmp_path / "local", "wrap-decision", "2.5.0",
        "基礎設施累積型絆腳索：blog 專案本地演化內容",
    )
    remote_dir = _write_skill(
        tmp_path / "remote", "wrap-decision", "2.5.0",
        "行前預想配早期警訊：canonical 演化內容",
    )

    local_manifest = {
        "wrap-decision": {
            "version": "2.5.0",
            "hash": compute_content_hash(local_dir),
        }
    }
    remote_manifest = {
        "wrap-decision": {
            "version": "2.5.0",
            "hash": compute_content_hash(remote_dir),
        }
    }

    up_to_date, diverged, overridden, skipped, skipped_missing = _classify_sync_status(
        local_manifest, remote_manifest, tmp_path / "local"
    )

    assert up_to_date == []
    assert overridden == []
    assert skipped == []
    assert skipped_missing == []
    assert len(diverged) == 1
    name, local_display, remote_display = diverged[0]
    assert name == "wrap-decision"
    assert local_display == "2.5.0"
    assert remote_display == "2.5.0"


# --- _classify_sync_status ---------------------------------------------------


def test_classify_sync_status_up_to_date_when_hash_matches(tmp_path):
    local_manifest = {"foo": {"version": "1.0.0", "hash": "same-hash"}}
    remote_manifest = {"foo": {"version": "1.0.0", "hash": "same-hash"}}

    up_to_date, diverged, overridden, skipped, skipped_missing = _classify_sync_status(
        local_manifest, remote_manifest, tmp_path
    )

    assert up_to_date == ["foo"]
    assert diverged == []
    assert overridden == []
    assert skipped == []
    assert skipped_missing == []


def test_classify_sync_status_skips_remote_without_hash_field(tmp_path):
    """remote 尚為舊格式（純版本字串）時不誤判為分歧或同步，改列為待更新的 skipped。"""
    local_manifest = {"foo": {"version": "1.0.0", "hash": "abc"}}
    remote_manifest = {"foo": "1.0.0"}  # 舊格式：純字串，無 hash 欄位

    up_to_date, diverged, overridden, skipped, skipped_missing = _classify_sync_status(
        local_manifest, remote_manifest, tmp_path
    )

    assert skipped == ["foo"]
    assert skipped_missing == []
    assert up_to_date == []
    assert diverged == []


def test_classify_sync_status_skips_remote_missing_entirely(tmp_path):
    """remote_manifest 完全沒有此 key 時歸為 skipped_remote_missing，非 skipped_no_hash。"""
    local_manifest = {"foo": {"version": "1.0.0", "hash": "abc"}}
    remote_manifest = {}  # 該 skill 從未被記錄過

    up_to_date, diverged, overridden, skipped, skipped_missing = _classify_sync_status(
        local_manifest, remote_manifest, tmp_path
    )

    assert skipped_missing == ["foo"]
    assert skipped == []
    assert up_to_date == []
    assert diverged == []


def test_classify_sync_status_respects_local_override_marker(tmp_path):
    skill_dir = tmp_path / "foo"
    skill_dir.mkdir()
    (skill_dir / SKILL_SYNC_OVERRIDE_MARKER).write_text("intentional customization")

    local_manifest = {"foo": {"version": "1.0.0", "hash": "local-hash"}}
    remote_manifest = {"foo": {"version": "2.0.0", "hash": "remote-hash"}}

    up_to_date, diverged, overridden, skipped, skipped_missing = _classify_sync_status(
        local_manifest, remote_manifest, tmp_path
    )

    assert overridden == ["foo"]
    assert up_to_date == []
    assert diverged == []
    assert skipped == []
    assert skipped_missing == []


def test_has_local_override_false_when_marker_absent(tmp_path):
    (tmp_path / "foo").mkdir()
    assert _has_local_override(tmp_path / "foo") is False


# --- _extract_local_manifest -------------------------------------------------


def test_extract_local_manifest_builds_hash_and_version(tmp_path):
    skills_dir = tmp_path / "skills"
    skill_dir = _write_skill(skills_dir, "wrap-decision", "2.7.0", "body")

    manifest = _extract_local_manifest(skills_dir)

    assert manifest["wrap-decision"]["version"] == "2.7.0"
    assert manifest["wrap-decision"]["hash"] == compute_content_hash(skill_dir)


def test_extract_local_manifest_empty_dir_returns_empty(tmp_path):
    assert _extract_local_manifest(tmp_path / "no-such-dir") == {}


# --- _warn_skill_md_case_mismatch（0.2.1-W3-370） ----------------------------


def test_warn_case_mismatch_emits_warning_for_lowercase_variant(tmp_path, capsys):
    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "error-pattern"
    skill_dir.mkdir(parents=True)
    (skill_dir / "skill.md").write_text("# error-pattern\n")

    _warn_skill_md_case_mismatch(skills_dir)

    captured = capsys.readouterr()
    assert "error-pattern" in captured.err
    assert "skill.md" in captured.err


def test_warn_case_mismatch_silent_for_correct_uppercase(tmp_path, capsys):
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "wrap-decision", "2.7.0", "body")

    _warn_skill_md_case_mismatch(skills_dir)

    captured = capsys.readouterr()
    assert captured.err == ""


def test_warn_case_mismatch_missing_base_dir_no_error(tmp_path):
    _warn_skill_md_case_mismatch(tmp_path / "no-such-dir")


# --- prune_dst_only（--prune 刪除傳播，0.2.1-W3-350） ------------------------
#
# push 對 remote-only 檔案的預設是保留（避免誤刪上游內容），代價是本地的刪除與
# 更名永遠傳不到遠端，殘留檔會被其他 consumer 專案 pull 下去。--prune 是顯式
# opt-in 的刪除路徑，預設行為不變。


def test_prune_deletes_dst_only_files(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    (src / "SKILL.md").write_text("kept")
    (dst / "SKILL.md").write_text("kept")
    (dst / "obsolete-hook.py").write_text("removed locally")

    diff = compute_diff(src, dst)
    removed = prune_dst_only(dst, diff)

    assert removed == 1
    assert not (dst / "obsolete-hook.py").exists()
    assert (dst / "SKILL.md").exists()


def test_prune_removes_directories_left_empty(tmp_path):
    """刪光某目錄下所有檔案後該目錄應一併消失，否則遠端留下空殼目錄。"""
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    (src / "SKILL.md").write_text("kept")
    hooks = dst / "hooks"
    hooks.mkdir(parents=True)
    (dst / "SKILL.md").write_text("kept")
    (hooks / "old-a.py").write_text("gone")
    (hooks / "old-b.py").write_text("gone")

    diff = compute_diff(src, dst)
    prune_dst_only(dst, diff)

    assert not hooks.exists()


def test_prune_leaves_excluded_dirs_untouched(tmp_path):
    """project-integration 等排除目錄不進 dst_only，故 prune 不得波及。"""
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    (src / "SKILL.md").write_text("kept")
    (dst / "SKILL.md").write_text("kept")
    (dst / "obsolete-hook.py").write_text("removed locally")
    integration = dst / "project-integration"
    integration.mkdir(parents=True)
    (integration / "triggers.md").write_text("consumer-specific")

    diff = compute_diff(src, dst)
    removed = prune_dst_only(dst, diff)

    # removed > 0 使空目錄清理實際執行，確認該掃描不會波及排除目錄
    assert removed == 1
    assert (integration / "triggers.md").exists()


def test_prune_returns_zero_when_no_dst_only(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    (src / "SKILL.md").write_text("same")
    (dst / "SKILL.md").write_text("same")

    diff = compute_diff(src, dst)

    assert prune_dst_only(dst, diff) == 0


def test_prune_leaves_already_empty_excluded_dir_untouched(tmp_path):
    """空的排除目錄（非本次 prune 清空）不應被空目錄清理波及（0.2.1-W3-354）。

    SKILL.md 對外宣稱 project-integration/ 對 --prune 不可及；先前的空目錄清理是
    對 dst 底下所有目錄無差別掃描，未套用 _should_exclude_file，故本已為空的
    project-integration/ 仍會被判定為「清空後留下的空殼」而 rmdir。
    """
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    (src / "SKILL.md").write_text("kept")
    (dst / "SKILL.md").write_text("kept")
    (dst / "obsolete-hook.py").write_text("removed locally")
    integration = dst / "project-integration"
    integration.mkdir(parents=True)

    diff = compute_diff(src, dst)
    removed = prune_dst_only(dst, diff)

    assert removed == 1
    assert integration.exists()


def test_prune_survives_symlink_pointing_to_directory(tmp_path):
    """指向目錄的 symlink 不得中斷 push（0.2.1-W3-354）。

    空目錄清理對 dst 底下所有目錄無差別掃描（含 is_dir() 為 True 的
    symlink-to-dir）；對這類 symlink 呼叫 rmdir() 在 POSIX 上拋
    NotADirectoryError，未被捕捉時會在 overlay_copy 已改動暫存 clone 之後
    中斷 push。
    """
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    (src / "SKILL.md").write_text("kept")
    (dst / "SKILL.md").write_text("kept")
    (dst / "obsolete-hook.py").write_text("removed locally")

    real_target = tmp_path / "outside-empty-dir"
    real_target.mkdir()
    (dst / "linked-dir").symlink_to(real_target, target_is_directory=True)

    diff = compute_diff(src, dst)

    removed = prune_dst_only(dst, diff)  # 不應拋例外

    assert removed == 1


def test_build_push_plan_marks_dst_only_prunable_when_enabled():
    """cmd_push 的 diff+prune 收斂為單一 plan：prunable 欄位取代獨立的 prune 旗標。"""
    diff = {"added": [], "modified": [], "unchanged": [], "dst_only": ["a.py", "b.py"]}

    plan_enabled = build_push_plan(diff, prune=True)
    plan_disabled = build_push_plan(diff, prune=False)

    assert plan_enabled["prunable"] == ["a.py", "b.py"]
    assert plan_disabled["prunable"] == []
    assert plan_enabled["dst_only"] == ["a.py", "b.py"]


def test_apply_prune_warns_on_count_mismatch(tmp_path, capsys, monkeypatch):
    """印出的刪除數與預覽承諾數不一致時要有訊號（0.2.1-W3-354）。"""
    import skill_sync.cli as cli_module

    monkeypatch.setattr(cli_module, "prune_dst_only", lambda dst, diff: 0)
    plan = {"dst_only": ["a.py"], "prunable": ["a.py"]}

    _apply_prune(tmp_path, plan)

    err = capsys.readouterr().err
    assert "WARNING" in err


def test_apply_prune_silent_when_count_matches(tmp_path, capsys, monkeypatch):
    import skill_sync.cli as cli_module

    monkeypatch.setattr(cli_module, "prune_dst_only", lambda dst, diff: 1)
    plan = {"dst_only": ["a.py"], "prunable": ["a.py"]}

    _apply_prune(tmp_path, plan)

    err = capsys.readouterr().err
    assert "WARNING" not in err


# --- cmd_push（0.2.1-W3-355：先前零覆蓋，變異測試證實移除 prunable guard 後 27
# 個測試仍全綠）-----------------------------------------------------------------
#
# 隔離策略：run_git 與 subprocess.run 皆改記錄呼叫、不觸網；tempfile.TemporaryDirectory
# 換成指向測試自建的固定目錄，事先在其中放好「clone 後」應有的遠端內容，因為 clone
# 本身被 no-op 掉，程式碼看到的仍是同一個 target 目錄。update_sync_manifest 另有專屬
# 測試覆蓋，此處只 no-op 避免它自己的 git 呼叫混進斷言。


class _RecordingArgs:
    def __init__(self, name, prune, force, message=None):
        self.name = name
        self.prune = prune
        self.force = force
        self.message = message


def _stub_git_recording(monkeypatch):
    """記錄每次 run_git 呼叫的子命令與 subprocess.run 呼叫，回傳 (git_calls, diff_calls)。"""
    import skill_sync.cli as cli_module

    git_calls: list[list[str]] = []
    diff_calls: list[None] = []

    def _fake_run_git(args, cwd=None):
        git_calls.append(args)
        return _FakeCompletedProcess(returncode=0)

    def _fake_subprocess_run(*a, **k):
        diff_calls.append(None)
        return _FakeCompletedProcess(returncode=1)  # 有 staged 變更

    monkeypatch.setattr(cli_module, "run_git", _fake_run_git)
    monkeypatch.setattr(cli_module.subprocess, "run", _fake_subprocess_run)
    monkeypatch.setattr(cli_module, "update_sync_manifest", lambda tmp: None)
    return git_calls, diff_calls


def _stub_fixed_tempdir(monkeypatch, scratch_dir: Path) -> None:
    """讓 cmd_push 的 `with tempfile.TemporaryDirectory()` 落在測試預先佈置好的固定目錄。"""
    import contextlib

    import skill_sync.cli as cli_module

    @contextlib.contextmanager
    def _fixed():
        yield str(scratch_dir)

    monkeypatch.setattr(cli_module.tempfile, "TemporaryDirectory", _fixed)


def test_cmd_push_prune_only_deletion_still_commits(tmp_path, monkeypatch):
    """僅有刪除（無 added/modified）時，--prune 仍必須提交，不得回報「無變更」。"""
    import skill_sync.cli as cli_module

    skills_dir = tmp_path / "skills"
    (skills_dir / "demo-skill").mkdir(parents=True)
    (skills_dir / "demo-skill" / "SKILL.md").write_text("kept")
    monkeypatch.setattr(cli_module, "get_skills_dir", lambda: skills_dir)

    scratch = tmp_path / "scratch"
    remote_skill = scratch / "repo" / "demo-skill"
    remote_skill.mkdir(parents=True)
    (remote_skill / "SKILL.md").write_text("kept")
    (remote_skill / "obsolete.py").write_text("removed locally")
    _stub_fixed_tempdir(monkeypatch, scratch)

    git_calls, _ = _stub_git_recording(monkeypatch)

    args = _RecordingArgs(name="demo-skill", prune=True, force=True)
    cmd_push(args)

    assert not (remote_skill / "obsolete.py").exists()
    assert ["commit", "-m", "Update skill: demo-skill"] in git_calls
    assert ["push"] in git_calls


def test_cmd_push_without_force_rejects_and_skips_deletion(tmp_path, monkeypatch):
    """非 force 模式下使用者拒絕確認時，不得刪除也不得提交。"""
    import skill_sync.cli as cli_module

    skills_dir = tmp_path / "skills"
    (skills_dir / "demo-skill").mkdir(parents=True)
    (skills_dir / "demo-skill" / "SKILL.md").write_text("kept")
    monkeypatch.setattr(cli_module, "get_skills_dir", lambda: skills_dir)

    scratch = tmp_path / "scratch"
    remote_skill = scratch / "repo" / "demo-skill"
    remote_skill.mkdir(parents=True)
    (remote_skill / "SKILL.md").write_text("kept")
    (remote_skill / "obsolete.py").write_text("removed locally")
    _stub_fixed_tempdir(monkeypatch, scratch)

    git_calls, _ = _stub_git_recording(monkeypatch)
    monkeypatch.setattr("builtins.input", lambda *_: "n")

    args = _RecordingArgs(name="demo-skill", prune=True, force=False)
    cmd_push(args)

    assert (remote_skill / "obsolete.py").exists()
    assert not any(call and call[0] == "commit" for call in git_calls)
    assert not any(call and call[0] == "push" for call in git_calls)


def test_push_parser_accepts_prune_flag():
    """--prune 必須是 push 的合法旗標，且預設關閉（安全預設不因新增旗標改變）。"""
    parser = build_parser()

    with_prune = parser.parse_args(["push", "demo-skill", "--prune"])
    without_prune = parser.parse_args(["push", "demo-skill"])

    assert with_prune.prune is True
    assert without_prune.prune is False


def test_pull_parser_has_no_prune_flag():
    """prune 僅適用 push 方向；pull 誤帶會刪本地檔案，故不提供此旗標。"""
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["pull", "demo-skill", "--prune"])


# --- sync_status_report（對外契約，0.2.1-W3-353） ----------------------------
#
# 此函式是 skill-sync 對消費端的公開介面。先前消費端（sync-claude-push）取用
# 底線私有名並自行重寫取檔與來源設定，造成兩端對同一批 skill 比對不同 repo。
# 這組測試釘住的是「單一入口涵蓋 repo 解析 + 取檔 + 分類」這個契約本身。


def test_public_contract_names_exist_for_consumers(tmp_path, monkeypatch):
    """契約斷言放在 skill-sync 自身套件內：改名這些名稱時 skill 側測試也必須轉紅。

    先前這組名稱只在 consumer 側（sync-claude-push 測試）被斷言存在；依 W3-350
    的驗收工作流改名私有函式時，skill 側全綠、consumer 側才靜默降級（0.2.1-W3-355）。
    """
    assert hasattr(sync_status_report, "__call__")
    assert SyncStatus._fields == (
        "repo_url",
        "remote_count",
        "up_to_date",
        "diverged",
        "overridden",
        "skipped_no_hash",
        "skipped_remote_missing",
    )
    assert DivergedSkill._fields == (
        "name",
        "local",
        "remote",
        "pull_command",
        "push_command",
    )


def _stub_manifest(monkeypatch, payload):
    """替換取檔層，讓分類測試不觸網。"""
    import skill_sync.cli as cli_module

    monkeypatch.setattr(cli_module, "fetch_remote_manifest", lambda url: payload)


def test_sync_status_report_resolves_repo_url_from_environment(tmp_path, monkeypatch):
    """repo 來源必須走 get_repo_url，消費端才不會各自硬編出第二個來源。"""
    monkeypatch.setenv("SKILL_SYNC_REPO", "https://github.com/example/other.git")
    _write_skill(tmp_path, "demo-skill", "1.0.0", "body")
    _stub_manifest(monkeypatch, {})

    status = sync_status_report(tmp_path)

    assert status.repo_url == "https://github.com/example/other.git"


def test_sync_status_report_classifies_matching_hash_as_up_to_date(tmp_path, monkeypatch):
    skill_dir = _write_skill(tmp_path, "demo-skill", "1.0.0", "body")
    _stub_manifest(
        monkeypatch,
        {"demo-skill": {"hash": compute_content_hash(skill_dir), "version": "1.0.0"}},
    )

    status = sync_status_report(tmp_path)

    assert status.up_to_date == ["demo-skill"]
    assert status.diverged == []


def test_sync_status_report_carries_remediation_commands_per_skill(tmp_path, monkeypatch):
    """分歧項目自帶命令字串，消費端不需要（也不該）自己拼一份指引。"""
    _write_skill(tmp_path, "demo-skill", "1.0.0", "local body")
    _stub_manifest(monkeypatch, {"demo-skill": {"hash": "0" * 64, "version": "0.9.0"}})

    entry = sync_status_report(tmp_path).diverged[0]

    assert entry.pull_command == "skill-sync pull demo-skill"
    assert entry.push_command == "skill-sync push demo-skill"


def test_remediation_commands_are_accepted_by_the_parser(tmp_path, monkeypatch):
    """命令字串由本模組產出，仍須能被自己的 parser 接受，否則指引再次成為死字串。"""
    _write_skill(tmp_path, "demo-skill", "1.0.0", "local body")
    _stub_manifest(monkeypatch, {"demo-skill": {"hash": "0" * 64, "version": "0.9.0"}})
    parser = build_parser()

    entry = sync_status_report(tmp_path).diverged[0]

    for command in (entry.pull_command, entry.push_command):
        tokens = command.split()
        assert tokens[0] == "skill-sync"
        parser.parse_args(tokens[1:])


def test_sync_status_report_rejects_non_mapping_manifest(tmp_path, monkeypatch):
    """遠端回 list/None 時給出可辨識的錯誤，而非讓 .get 在下游炸成 AttributeError。"""
    _write_skill(tmp_path, "demo-skill", "1.0.0", "body")
    _stub_manifest(monkeypatch, ["not", "a", "mapping"])

    with pytest.raises(ValueError, match="versions.json"):
        sync_status_report(tmp_path)


def test_sync_status_report_reports_empty_remote_as_zero_entries(tmp_path, monkeypatch):
    """遠端回空 dict 不得讀起來像檢查通過——remote_count 讓消費端能分辨。"""
    _write_skill(tmp_path, "demo-skill", "1.0.0", "body")
    _stub_manifest(monkeypatch, {})

    status = sync_status_report(tmp_path)

    assert status.remote_count == 0
    assert status.skipped_remote_missing == ["demo-skill"]


def test_sync_status_report_handles_missing_skills_dir(tmp_path, monkeypatch):
    _stub_manifest(monkeypatch, {})

    status = sync_status_report(tmp_path / "absent")

    assert status.up_to_date == []
    assert status.skipped_no_hash == []
    assert status.skipped_remote_missing == []


def test_fetch_remote_manifest_builds_raw_url_from_repo_url(monkeypatch):
    """URL 拼裝只此一份；消費端複製這段正是 repo 不一致的來源。"""
    captured = {}

    class _Resp:
        def read(self):
            return b"{}"

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def _fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        return _Resp()

    import skill_sync.cli as cli_module

    monkeypatch.setattr(cli_module.urllib.request, "urlopen", _fake_urlopen)

    fetch_remote_manifest("https://github.com/owner/repo.git")

    assert captured["url"] == (
        "https://raw.githubusercontent.com/owner/repo/main/versions.json"
    )


def test_preview_labels_dst_only_as_prune_when_enabled(capsys):
    """預覽標籤必須隨 plan 的 prunable 欄位改變，否則使用者看到 preserved 卻發生刪除。"""
    plan_pruning = {
        "added": [], "modified": [], "unchanged": [],
        "dst_only": ["hooks/old.py"], "prunable": ["hooks/old.py"],
    }
    plan_preserving = {
        "added": [], "modified": [], "unchanged": [],
        "dst_only": ["hooks/old.py"], "prunable": [],
    }

    print_diff_preview(plan_pruning, direction="push")
    pruning_output = capsys.readouterr().out

    print_diff_preview(plan_preserving, direction="push")
    preserving_output = capsys.readouterr().out

    assert "prune" in pruning_output.lower()
    assert "preserved" in preserving_output.lower()
    assert "preserved" not in pruning_output.lower()


def test_print_diff_preview_rejects_prune_kwarg():
    """print_diff_preview 不再接收 prune 旗標：判斷改由 plan 的 prunable 欄位承擔。"""
    diff = {"added": [], "modified": [], "unchanged": [], "dst_only": []}

    with pytest.raises(TypeError):
        print_diff_preview(diff, direction="push", prune=True)


# --- update_sync_manifest（不觸發真實 git/網路操作） -------------------------


def test_update_sync_manifest_writes_hash_matching_extract_local_manifest(tmp_path, monkeypatch):
    skill_dir = _write_skill(tmp_path, "wrap-decision", "2.5.0", "canonical content")

    monkeypatch.setattr(
        "skill_sync.cli.subprocess.run",
        lambda *a, **k: _FakeCompletedProcess(returncode=0),
    )

    update_sync_manifest(tmp_path)

    written = json.loads((tmp_path / "versions.json").read_text())
    assert written["wrap-decision"]["version"] == "2.5.0"
    assert written["wrap-decision"]["hash"] == compute_content_hash(skill_dir)
