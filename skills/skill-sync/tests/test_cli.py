"""Unit tests for skill_sync.cli exclude-file logic and content-hash sync comparison."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skill_sync.cli import (  # noqa: E402
    _apply_prune,
    _diff_line_counts,
    _diverge_warning,
    _extract_python_narrative_text,
    _is_portable_declared,
    _read_sync_base,
    _record_sync_base,
    _report_portability,
    _resolve_diverge_direction,
    _resolve_hook_logs_dir,
    _scan_line_for_violations,
    _skill_exists_in_canonical,
    _write_portability_force_log,
    _write_sync_base,
    check_portability,
    _classify_sync_status,
    _extract_local_manifest,
    _has_local_override,
    _should_exclude_file,
    build_parser,
    build_push_plan,
    cmd_pull,
    cmd_pull_all,
    cmd_push,
    compute_content_hash,
    compute_diff,
    EXCLUDE_DIRS,
    DivergedSkill,
    fetch_remote_manifest,
    get_skills_dir,
    PortabilityViolation,
    print_diff_preview,
    prune_dst_only,
    SKILL_SYNC_BASE_MARKER,
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


# 0.2.1-W3-860：EXCLUDE_DIRS 原本只排除 .pytest_cache，同類 linter/typechecker/
# coverage 產物目錄（.ruff_cache 等）缺漏，導致任何人跑過這些工具後 sync 比對
# 都會報一筆假分歧（見 ticket Problem Analysis）。
def test_ruff_cache_dir_registered_in_exclude_dirs():
    assert ".ruff_cache" in EXCLUDE_DIRS


def test_ruff_cache_file_excluded():
    assert _should_exclude_file(".ruff_cache/0.14.0/cache.bin") is True


def test_mypy_cache_dir_registered_in_exclude_dirs():
    assert ".mypy_cache" in EXCLUDE_DIRS


def test_mypy_cache_file_excluded():
    assert _should_exclude_file(".mypy_cache/3.14/module.data.json") is True


def test_htmlcov_dir_registered_in_exclude_dirs():
    assert "htmlcov" in EXCLUDE_DIRS


def test_htmlcov_file_excluded():
    assert _should_exclude_file("htmlcov/index.html") is True


# ---------- 憑證檔排除（0.2.1-W3-481：公開 repo 外洩防護） ----------

def test_credential_dotenv_excluded():
    assert _should_exclude_file(".env") is True


def test_credential_dotenv_variant_excluded():
    assert _should_exclude_file(".env.production") is True


def test_credential_secrets_yaml_excluded():
    assert _should_exclude_file("scripts/secrets.yaml") is True


def test_credential_pem_suffix_excluded():
    assert _should_exclude_file("certs/deploy.pem") is True


def test_credential_ssh_private_key_no_suffix_excluded():
    # id_rsa 等 SSH 私鑰慣例檔名無副檔名、不以 env/secret 起頭，
    # suffix/prefix 判準覆蓋不到，須精確列名（PM 實測發現的附帶缺口）。
    assert _should_exclude_file("keys/id_rsa") is True


def test_credential_dotkeys_excluded():
    assert _should_exclude_file("config/.keys") is True


def test_compute_diff_excludes_credential_files_from_added(tmp_path):
    """排除必須發生在 compute_diff（--force 繞過的是互動預覽，不是 compute_diff）。"""
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    (src / "SKILL.md").write_text("hello")
    (src / ".env").write_text("TOKEN=1")
    (src / ".env.production").write_text("TOKEN=1")
    (src / "scripts").mkdir()
    (src / "scripts" / "secrets.yaml").write_text("token: abc")
    (src / "certs").mkdir()
    (src / "certs" / "deploy.pem").write_text("-----BEGIN PRIVATE KEY-----")
    (src / "keys").mkdir()
    (src / "keys" / "id_rsa").write_text("-----BEGIN OPENSSH PRIVATE KEY-----")
    (src / "config").mkdir()
    (src / "config" / ".keys").write_text("token: abc")

    diff = compute_diff(src, dst)

    assert "SKILL.md" in diff["added"]
    credential_rels = {
        ".env",
        ".env.production",
        "scripts/secrets.yaml",
        "certs/deploy.pem",
        "keys/id_rsa",
        "config/.keys",
    }
    assert not (credential_rels & set(diff["added"]))


def test_compute_diff_excludes_credential_files_from_dst_only(tmp_path):
    # dst-only 掃描也走 _should_exclude_file，憑證檔不應被列為「remote-only」
    # 而在預覽/prune 流程中被提及（見 compute_diff 的 dst 端迴圈）。
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    (dst / ".env").write_text("TOKEN=1")

    diff = compute_diff(src, dst)

    assert ".env" not in diff["dst_only"]


def test_regular_skill_file_with_env_substring_not_falsely_excluded():
    # 防過度排除：檔名含 "env" 子字串但非 ".env." 前綴形態，不應被誤判
    # （前綴判準要求緊接開頭的 ".env."，非任意位置的 "env" 子字串）。
    assert _should_exclude_file("scripts/environment_helper.py") is False
    assert _should_exclude_file("docs/openapi.yaml") is False


# ---------- override marker 排除（0.2.1-W3-477：傳染性缺陷防護） ----------
#
# marker 是單一 consumer 的本地宣告，不得被 push 帶上遠端——上游一旦帶有它，
# 所有 consumer pull 後該 skill 會永久落入 overridden、分歧回報全面靜默。
# compute_content_hash 已用獨立寫法排除（f.name == MARKER or ...），本組測試
# 固化 _should_exclude_file 本身也排除 marker，讓兩個消費點共用同一判定點，
# 不再各自處置（IMP-BAL-006 同一排除語意多路徑分歧的模式）。

def test_override_marker_excluded_at_skill_root():
    assert _should_exclude_file(SKILL_SYNC_OVERRIDE_MARKER) is True


def test_override_marker_excluded_nested():
    assert _should_exclude_file(f"some-skill/{SKILL_SYNC_OVERRIDE_MARKER}") is True


def test_compute_diff_excludes_override_marker_from_added(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    (src / "SKILL.md").write_text("hello")
    (src / SKILL_SYNC_OVERRIDE_MARKER).write_text("local customization notice")

    diff = compute_diff(src, dst)

    assert "SKILL.md" in diff["added"]
    assert SKILL_SYNC_OVERRIDE_MARKER not in diff["added"]


def test_compute_diff_excludes_override_marker_from_dst_only(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    (dst / SKILL_SYNC_OVERRIDE_MARKER).write_text("local customization notice")

    diff = compute_diff(src, dst)

    assert SKILL_SYNC_OVERRIDE_MARKER not in diff["dst_only"]


# ---------- sync base marker 排除（0.2.1-W3-668：三態方向判定） ----------
#
# base 記錄檔與 override marker 同理：呼叫端本地寫入，絕不能進 canonical 或
# 影響 content hash，否則寫入 base 本身會改變 hash，造成自我循環。


def test_base_marker_excluded_at_skill_root():
    assert _should_exclude_file(SKILL_SYNC_BASE_MARKER) is True


def test_base_marker_excluded_nested():
    assert _should_exclude_file(f"some-skill/{SKILL_SYNC_BASE_MARKER}") is True


def test_compute_diff_excludes_base_marker_from_added(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    (src / "SKILL.md").write_text("hello")
    (src / SKILL_SYNC_BASE_MARKER).write_text("0" * 64)

    diff = compute_diff(src, dst)

    assert "SKILL.md" in diff["added"]
    assert SKILL_SYNC_BASE_MARKER not in diff["added"]


def test_compute_diff_excludes_base_marker_from_dst_only(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    (dst / SKILL_SYNC_BASE_MARKER).write_text("0" * 64)

    diff = compute_diff(src, dst)

    assert SKILL_SYNC_BASE_MARKER not in diff["dst_only"]


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


def test_content_hash_excludes_base_marker_file(tmp_path):
    skill_dir = _write_skill(tmp_path, "wrap-decision", "2.5.0", "body")
    without_marker = compute_content_hash(skill_dir)

    (skill_dir / SKILL_SYNC_BASE_MARKER).write_text("0" * 64)

    assert compute_content_hash(skill_dir) == without_marker


def test_content_hash_excludes_ruff_cache_dir(tmp_path):
    """acceptance 第一項：含 .ruff_cache 與不含時的內容雜湊必須相同。"""
    skill_dir = _write_skill(tmp_path, "wrap-decision", "2.5.0", "body")
    without_ruff_cache = compute_content_hash(skill_dir)

    ruff_cache = skill_dir / ".ruff_cache"
    ruff_cache.mkdir()
    (ruff_cache / "cache.bin").write_text("linter cache artifact")

    assert compute_content_hash(skill_dir) == without_ruff_cache


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

    up_to_date, diverged, overridden, excluded, skipped, skipped_missing = (
        _classify_sync_status(local_manifest, remote_manifest, tmp_path / "local")
    )

    assert up_to_date == []
    assert overridden == []
    assert excluded == []
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

    up_to_date, diverged, overridden, excluded, skipped, skipped_missing = (
        _classify_sync_status(local_manifest, remote_manifest, tmp_path)
    )

    assert up_to_date == ["foo"]
    assert diverged == []
    assert overridden == []
    assert excluded == []
    assert skipped == []
    assert skipped_missing == []


def test_classify_sync_status_skips_remote_without_hash_field(tmp_path):
    """remote 尚為舊格式（純版本字串）時不誤判為分歧或同步，改列為待更新的 skipped。"""
    local_manifest = {"foo": {"version": "1.0.0", "hash": "abc"}}
    remote_manifest = {"foo": "1.0.0"}  # 舊格式：純字串，無 hash 欄位

    up_to_date, diverged, overridden, excluded, skipped, skipped_missing = (
        _classify_sync_status(local_manifest, remote_manifest, tmp_path)
    )

    assert skipped == ["foo"]
    assert skipped_missing == []
    assert up_to_date == []
    assert diverged == []
    assert excluded == []


def test_classify_sync_status_skips_remote_missing_entirely(tmp_path):
    """remote_manifest 完全沒有此 key 時歸為 skipped_remote_missing，非 skipped_no_hash。"""
    local_manifest = {"foo": {"version": "1.0.0", "hash": "abc"}}
    remote_manifest = {}  # 該 skill 從未被記錄過

    up_to_date, diverged, overridden, excluded, skipped, skipped_missing = (
        _classify_sync_status(local_manifest, remote_manifest, tmp_path)
    )

    assert skipped_missing == ["foo"]
    assert skipped == []
    assert up_to_date == []
    assert diverged == []
    assert excluded == []


def test_classify_sync_status_respects_local_override_marker(tmp_path):
    skill_dir = tmp_path / "foo"
    skill_dir.mkdir()
    (skill_dir / SKILL_SYNC_OVERRIDE_MARKER).write_text("intentional customization")

    local_manifest = {"foo": {"version": "1.0.0", "hash": "local-hash"}}
    remote_manifest = {"foo": {"version": "2.0.0", "hash": "remote-hash"}}

    up_to_date, diverged, overridden, excluded, skipped, skipped_missing = (
        _classify_sync_status(local_manifest, remote_manifest, tmp_path)
    )

    assert overridden == ["foo"]
    assert up_to_date == []
    assert diverged == []
    assert excluded == []
    assert skipped == []
    assert skipped_missing == []


def test_classify_sync_status_excludes_by_policy(tmp_path):
    """excluded_skills 命中的名稱落入 excluded_by_policy，不落入
    skipped_remote_missing（即使 remote_manifest 完全沒有此 key，0.2.1-W3-457）。"""
    local_manifest = {"verify": {"version": "1.0.0", "hash": "abc"}}
    remote_manifest = {}  # 遠端從未記錄過此 skill

    up_to_date, diverged, overridden, excluded, skipped, skipped_missing = (
        _classify_sync_status(
            local_manifest, remote_manifest, tmp_path, excluded_skills=["verify"]
        )
    )

    assert excluded == ["verify"]
    assert skipped_missing == []
    assert up_to_date == []
    assert diverged == []
    assert overridden == []


def test_classify_sync_status_excluded_takes_priority_over_override_marker(tmp_path):
    """一個名稱不會同時落入 excluded_by_policy 與 overridden——排除政策檢查排在
    override 標記之前，即使兩個條件同時成立也只計入前者。"""
    skill_dir = tmp_path / "verify"
    skill_dir.mkdir()
    (skill_dir / SKILL_SYNC_OVERRIDE_MARKER).write_text("intentional customization")

    local_manifest = {"verify": {"version": "1.0.0", "hash": "abc"}}
    remote_manifest = {"verify": {"version": "1.0.0", "hash": "xyz"}}

    up_to_date, diverged, overridden, excluded, skipped, skipped_missing = (
        _classify_sync_status(
            local_manifest, remote_manifest, tmp_path, excluded_skills=["verify"]
        )
    )

    assert excluded == ["verify"]
    assert overridden == []


def test_classify_sync_status_excluded_skills_defaults_to_empty(tmp_path):
    """未傳 excluded_skills 時行為不變（向後相容既有呼叫端）。"""
    local_manifest = {"foo": {"version": "1.0.0", "hash": "abc"}}
    remote_manifest = {}

    up_to_date, diverged, overridden, excluded, skipped, skipped_missing = (
        _classify_sync_status(local_manifest, remote_manifest, tmp_path)
    )

    assert excluded == []
    assert skipped_missing == ["foo"]


def test_has_local_override_false_when_marker_absent(tmp_path):
    (tmp_path / "foo").mkdir()
    assert _has_local_override(tmp_path / "foo") is False


# --- sync base：三態方向判定（0.2.1-W3-668） ---------------------------------
#
# versions.json 只存 hash 與 version，本地無「上次同步到哪個 hash」的記錄；三方
# 資訊（本地／遠端／上次同步基準）塌成兩方，方向因此永遠推不出來而必須人判，
# 一次漏判即以舊版覆蓋 canonical。本節固化：讀寫基準檔的原始行為、
# 純函式方向判定的四種組合、_classify_sync_status 向後相容（無 base 記錄時維持
# 現行 diverged 輸出）、pull/push 成功後的落盤時機。


def test_read_sync_base_returns_none_when_marker_absent(tmp_path):
    assert _read_sync_base(tmp_path) is None


def test_write_then_read_sync_base_round_trips(tmp_path):
    _write_sync_base(tmp_path, "a" * 64)
    assert _read_sync_base(tmp_path) == "a" * 64


def test_record_sync_base_writes_current_content_hash(tmp_path):
    skill_dir = _write_skill(tmp_path, "wrap-decision", "2.5.0", "body")

    _record_sync_base(skill_dir)

    assert _read_sync_base(skill_dir) == compute_content_hash(skill_dir)


def test_record_sync_base_skips_missing_dir(tmp_path):
    # compute_content_hash 回傳 None 時不應嘗試寫入不存在的目錄
    _record_sync_base(tmp_path / "does-not-exist")
    assert not (tmp_path / "does-not-exist").exists()


# --- _resolve_diverge_direction（純函式，四種組合） ---------------------------


def test_direction_unknown_when_no_base_recorded():
    assert _resolve_diverge_direction(None, "local-hash", "remote-hash") == "unknown"


def test_direction_pull_when_local_unchanged_since_base():
    assert _resolve_diverge_direction("base", "base", "remote-moved") == "pull"


def test_direction_push_when_remote_unchanged_since_base():
    assert _resolve_diverge_direction("base", "local-moved", "base") == "push"


def test_direction_conflict_when_both_moved_since_base():
    assert _resolve_diverge_direction("base", "local-moved", "remote-moved") == "conflict"


# --- sync_status_report 整合：diverged 條目攜帶 direction ---------------------


def test_sync_status_report_diverged_direction_pull_when_local_matches_base(
    tmp_path, monkeypatch
):
    skill_dir = _write_skill(tmp_path, "demo-skill", "1.0.0", "local body")
    local_hash = compute_content_hash(skill_dir)
    _write_sync_base(skill_dir, local_hash)
    _stub_manifest(monkeypatch, {"demo-skill": {"hash": "0" * 64, "version": "0.9.0"}})

    entry = sync_status_report(tmp_path).diverged[0]

    assert entry.direction == "pull"


def test_sync_status_report_diverged_direction_push_when_remote_matches_base(
    tmp_path, monkeypatch
):
    skill_dir = _write_skill(tmp_path, "demo-skill", "1.0.0", "local body")
    remote_hash = "0" * 64
    _write_sync_base(skill_dir, remote_hash)
    _stub_manifest(monkeypatch, {"demo-skill": {"hash": remote_hash, "version": "0.9.0"}})

    entry = sync_status_report(tmp_path).diverged[0]

    assert entry.direction == "push"


def test_sync_status_report_diverged_direction_conflict_when_both_moved(
    tmp_path, monkeypatch
):
    skill_dir = _write_skill(tmp_path, "demo-skill", "1.0.0", "local body")
    _write_sync_base(skill_dir, "b" * 64)
    _stub_manifest(monkeypatch, {"demo-skill": {"hash": "0" * 64, "version": "0.9.0"}})

    entry = sync_status_report(tmp_path).diverged[0]

    assert entry.direction == "conflict"


def test_sync_status_report_diverged_direction_unknown_when_no_base_backward_compat(
    tmp_path, monkeypatch
):
    """既有 skill（從未走過 pull/push 記錄 base）維持現行 diverged 輸出：
    local/remote/pull_command/push_command 不變，direction 落回 "unknown"。"""
    _write_skill(tmp_path, "demo-skill", "1.0.0", "local body")
    _stub_manifest(monkeypatch, {"demo-skill": {"hash": "0" * 64, "version": "0.9.0"}})

    entry = sync_status_report(tmp_path).diverged[0]

    assert entry.direction == "unknown"
    assert entry.pull_command == "skill-sync pull demo-skill"
    assert entry.push_command == "skill-sync push demo-skill"


def test_diverged_skill_fields_include_direction_with_default():
    """direction 有預設值，既有只帶前五個欄位的建構呼叫仍合法。"""
    entry = DivergedSkill(
        name="foo", local="1.0", remote="2.0",
        pull_command="skill-sync pull foo", push_command="skill-sync push foo",
    )
    assert entry.direction == "unknown"


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


def test_cmd_push_force_still_excludes_credential_files(tmp_path, monkeypatch):
    """--force 只跳過互動預覽的 [y/N] 確認，不得繞過 compute_diff 的排除判準

    （0.2.1-W3-481 acceptance 2：排除必須發生在 compute_diff，overlay_copy
    只複製 diff["added"] + diff["modified"]，憑證檔不進 added 就不會被複製
    進暫存 clone、也就不會被後續 `git add -A` 帶上）。
    """
    import skill_sync.cli as cli_module

    skills_dir = tmp_path / "skills"
    (skills_dir / "demo-skill").mkdir(parents=True)
    (skills_dir / "demo-skill" / "SKILL.md").write_text("kept")
    (skills_dir / "demo-skill" / ".env").write_text("TOKEN=leaked-if-not-excluded")
    monkeypatch.setattr(cli_module, "get_skills_dir", lambda: skills_dir)

    scratch = tmp_path / "scratch"
    remote_skill = scratch / "repo" / "demo-skill"
    remote_skill.mkdir(parents=True)
    (remote_skill / "SKILL.md").write_text("outdated")
    _stub_fixed_tempdir(monkeypatch, scratch)

    git_calls, _ = _stub_git_recording(monkeypatch)

    args = _RecordingArgs(name="demo-skill", prune=False, force=True)
    cmd_push(args)

    assert not (remote_skill / ".env").exists()
    assert ["commit", "-m", "Update skill: demo-skill"] in git_calls
    assert ["push"] in git_calls


def test_cmd_push_never_pushes_override_marker(tmp_path, monkeypatch):
    """0.2.1-W3-477：marker 是單一 consumer 的本地宣告，push 絕不能把它帶上遠端

    ——上游一旦帶有 marker，所有 consumer pull 後該 skill 會永久落入
    overridden、分歧回報全面靜默（單一本地宣告變成全體的靜默開關）。
    """
    import skill_sync.cli as cli_module

    skills_dir = tmp_path / "skills"
    (skills_dir / "demo-skill").mkdir(parents=True)
    (skills_dir / "demo-skill" / "SKILL.md").write_text("kept")
    (skills_dir / "demo-skill" / SKILL_SYNC_OVERRIDE_MARKER).write_text(
        "local customization notice"
    )
    monkeypatch.setattr(cli_module, "get_skills_dir", lambda: skills_dir)

    scratch = tmp_path / "scratch"
    remote_skill = scratch / "repo" / "demo-skill"
    remote_skill.mkdir(parents=True)
    (remote_skill / "SKILL.md").write_text("outdated")
    _stub_fixed_tempdir(monkeypatch, scratch)

    git_calls, _ = _stub_git_recording(monkeypatch)

    args = _RecordingArgs(name="demo-skill", prune=False, force=True)
    cmd_push(args)

    assert not (remote_skill / SKILL_SYNC_OVERRIDE_MARKER).exists()
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


def test_cmd_push_records_sync_base_after_successful_push(tmp_path, monkeypatch):
    """完整 push（有變更、有 commit/push）成功後，local 端須留下這次的 canonical
    hash，供下次同步的三態判定使用（0.2.1-W3-668）。"""
    import skill_sync.cli as cli_module

    skills_dir = tmp_path / "skills"
    (skills_dir / "demo-skill").mkdir(parents=True)
    (skills_dir / "demo-skill" / "SKILL.md").write_text("kept")
    monkeypatch.setattr(cli_module, "get_skills_dir", lambda: skills_dir)

    scratch = tmp_path / "scratch"
    remote_skill = scratch / "repo" / "demo-skill"
    remote_skill.mkdir(parents=True)
    (remote_skill / "SKILL.md").write_text("outdated")
    _stub_fixed_tempdir(monkeypatch, scratch)

    _stub_git_recording(monkeypatch)

    source = skills_dir / "demo-skill"
    args = _RecordingArgs(name="demo-skill", prune=False, force=True)
    cmd_push(args)

    assert _read_sync_base(source) == compute_content_hash(source)


def test_cmd_push_records_sync_base_on_no_changes_fast_path(tmp_path, monkeypatch):
    """diff/prunable 皆空的快速返回路徑（已知 local 與 remote 一致）也要記錄 base，
    否則這個 skill 永遠停在無 base 記錄、退化為現行 diverged 輸出。"""
    import skill_sync.cli as cli_module

    skills_dir = tmp_path / "skills"
    (skills_dir / "demo-skill").mkdir(parents=True)
    (skills_dir / "demo-skill" / "SKILL.md").write_text("same")
    monkeypatch.setattr(cli_module, "get_skills_dir", lambda: skills_dir)

    scratch = tmp_path / "scratch"
    remote_skill = scratch / "repo" / "demo-skill"
    remote_skill.mkdir(parents=True)
    (remote_skill / "SKILL.md").write_text("same")
    _stub_fixed_tempdir(monkeypatch, scratch)
    monkeypatch.setattr(
        cli_module, "run_git", lambda args, cwd=None: _FakeCompletedProcess(returncode=0)
    )

    source = skills_dir / "demo-skill"
    args = _RecordingArgs(name="demo-skill", prune=False, force=True)
    cmd_push(args)

    assert _read_sync_base(source) == compute_content_hash(source)


# --- cmd_pull 記錄 sync base（0.2.1-W3-668） ----------------------------------


def _stub_git_noop(monkeypatch):
    """cmd_pull 只需 run_git 不觸網，不像 cmd_push 需要記錄呼叫序列或 subprocess.run。"""
    import skill_sync.cli as cli_module

    monkeypatch.setattr(
        cli_module, "run_git", lambda args, cwd=None: _FakeCompletedProcess(returncode=0)
    )


def test_cmd_pull_records_sync_base_after_applying_changes(tmp_path, monkeypatch):
    import skill_sync.cli as cli_module

    skills_dir = tmp_path / "skills"
    monkeypatch.setattr(cli_module, "get_skills_dir", lambda: skills_dir)

    scratch = tmp_path / "scratch"
    remote_skill = scratch / "repo" / "demo-skill"
    remote_skill.mkdir(parents=True)
    (remote_skill / "SKILL.md").write_text("fresh remote content")
    _stub_fixed_tempdir(monkeypatch, scratch)
    _stub_git_noop(monkeypatch)

    args = argparse.Namespace(name="demo-skill", force=True)
    cmd_pull(args)

    target = skills_dir / "demo-skill"
    assert _read_sync_base(target) == compute_content_hash(target)
    assert _read_sync_base(target) == compute_content_hash(remote_skill)


def test_cmd_pull_records_sync_base_when_already_up_to_date(tmp_path, monkeypatch):
    import skill_sync.cli as cli_module

    skills_dir = tmp_path / "skills"
    target = skills_dir / "demo-skill"
    target.mkdir(parents=True)
    (target / "SKILL.md").write_text("same content")
    monkeypatch.setattr(cli_module, "get_skills_dir", lambda: skills_dir)

    scratch = tmp_path / "scratch"
    remote_skill = scratch / "repo" / "demo-skill"
    remote_skill.mkdir(parents=True)
    (remote_skill / "SKILL.md").write_text("same content")
    _stub_fixed_tempdir(monkeypatch, scratch)
    _stub_git_noop(monkeypatch)

    args = argparse.Namespace(name="demo-skill", force=True)
    cmd_pull(args)

    assert _read_sync_base(target) == compute_content_hash(target)


# --- cmd_pull_all 依 direction 分組列印（0.2.1-W3-668） -----------------------


def test_cmd_pull_all_groups_diverged_entries_by_direction(monkeypatch, capsys):
    import skill_sync.cli as cli_module

    def _entry(name: str, direction: str) -> DivergedSkill:
        return DivergedSkill(
            name=name, local=f"local-{name}", remote=f"remote-{name}",
            pull_command=f"skill-sync pull {name}",
            push_command=f"skill-sync push {name}",
            direction=direction,
        )

    status = SyncStatus(
        repo_url="https://example.com/repo.git",
        remote_count=4,
        up_to_date=[],
        diverged=[
            _entry("a", "pull"),
            _entry("b", "push"),
            _entry("c", "conflict"),
            _entry("d", "unknown"),
        ],
        overridden=[],
        excluded_by_policy=[],
        skipped_no_hash=[],
        skipped_remote_missing=[],
    )
    monkeypatch.setattr(cli_module, "sync_status_report", lambda skills_dir: status)
    monkeypatch.setattr(cli_module, "get_skills_dir", lambda: Path("/does-not-matter"))

    cmd_pull_all(argparse.Namespace())

    out = capsys.readouterr().out
    assert "[SHOULD PULL]" in out and "skill-sync pull a" in out
    assert "[SHOULD PUSH]" in out and "skill-sync push b" in out
    assert "[CONFLICT]" in out
    assert "skill-sync pull c" in out and "skill-sync push c" in out
    assert "[DIVERGED]" in out
    assert "skill-sync pull d" in out and "skill-sync push d" in out


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
        "excluded_by_policy",
        "skipped_no_hash",
        "skipped_remote_missing",
    )
    assert DivergedSkill._fields == (
        "name",
        "local",
        "remote",
        "pull_command",
        "push_command",
        "direction",
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


def test_sync_status_report_passes_excluded_skills_through(tmp_path, monkeypatch):
    """excluded_skills 由公開入口原樣傳給分類器，落入 excluded_by_policy 而非
    skipped_remote_missing（0.2.1-W3-457：呼叫端注入排除政策）。"""
    _write_skill(tmp_path, "verify", "1.0.0", "body")
    _stub_manifest(monkeypatch, {})

    status = sync_status_report(tmp_path, excluded_skills=["verify"])

    assert status.excluded_by_policy == ["verify"]
    assert status.skipped_remote_missing == []


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


# --- _diff_line_counts（0.2.1-W3-671：preview 變更可見性） -------------------
#
# 兩次真實事故都是 preview 只顯示檔名所致：push 顯示「~ SKILL.md」兩行卻以
# 舊版覆蓋 canonical、pull 顯示「31 file(s) updated」卻刪掉 1782 行。增刪行數
# 才是區分「例行同步」與「大幅回退」的數字，本節固化 _diff_line_counts 本身
# 的正確性——特別是「總行數相同但內容互換」不得誤報為無變化。


def test_diff_line_counts_identical_content_is_zero_zero(tmp_path):
    a = tmp_path / "a.md"
    b = tmp_path / "b.md"
    a.write_text("line1\nline2\n")
    b.write_text("line1\nline2\n")

    assert _diff_line_counts(a, b) == (0, 0)


def test_diff_line_counts_pure_addition(tmp_path):
    a = tmp_path / "a.md"
    b = tmp_path / "b.md"
    a.write_text("line1\n")
    b.write_text("line1\nline2\nline3\n")

    assert _diff_line_counts(a, b) == (2, 0)


def test_diff_line_counts_pure_removal(tmp_path):
    a = tmp_path / "a.md"
    b = tmp_path / "b.md"
    a.write_text("line1\nline2\nline3\n")
    b.write_text("line1\n")

    assert _diff_line_counts(a, b) == (0, 2)


def test_diff_line_counts_same_total_lines_but_different_content_not_reported_as_zero(
    tmp_path,
):
    """回歸關鍵案例：總行數相同，內容整份替換，不得誤報 (0, 0)。"""
    a = tmp_path / "a.md"
    b = tmp_path / "b.md"
    a.write_text("old line 1\nold line 2\nold line 3\n")
    b.write_text("brand new 1\nbrand new 2\nbrand new 3\n")

    added, removed = _diff_line_counts(a, b)

    assert added > 0
    assert removed > 0


def test_diff_line_counts_returns_none_for_binary_content(tmp_path):
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(b"\xff\xfe\x00\x01binary")
    b.write_bytes(b"\xff\xfe\x00\x02binary")

    assert _diff_line_counts(a, b) is None


def test_diff_line_counts_returns_none_for_missing_file(tmp_path):
    a = tmp_path / "does-not-exist.md"
    b = tmp_path / "b.md"
    b.write_text("content\n")

    assert _diff_line_counts(a, b) is None


# --- print_diff_preview 行數顯示（0.2.1-W3-671） ------------------------------


def test_preview_shows_line_counts_when_src_dst_provided(tmp_path, capsys):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    (src / "SKILL.md").write_text("line1\nline2\nline3\n")
    (dst / "SKILL.md").write_text("line1\n")

    diff = compute_diff(src, dst)
    print_diff_preview(diff, direction="pull", src=src, dst=dst)

    out = capsys.readouterr().out
    assert "+2/-0 lines" in out


def test_preview_omits_line_counts_when_src_dst_not_provided(capsys):
    """向後相容（acceptance 3）：既有呼叫端（未傳 src/dst）輸出格式不變。"""
    diff = {
        "added": [], "modified": ["SKILL.md"], "unchanged": [], "dst_only": [],
    }

    print_diff_preview(diff, direction="pull")

    out = capsys.readouterr().out
    assert "~ SKILL.md" in out
    assert "lines)" not in out


# --- _diverge_warning（純函式，0.2.1-W3-671） --------------------------------


def test_diverge_warning_none_when_direction_matches_expected():
    assert _diverge_warning("pull", expected="pull") is None
    assert _diverge_warning("push", expected="push") is None


def test_diverge_warning_none_when_unknown():
    assert _diverge_warning("unknown", expected="pull") is None
    assert _diverge_warning("unknown", expected="push") is None


def test_diverge_warning_when_pushing_but_should_pull():
    """事故一：push 時本地其實落後於遠端（base 顯示遠端已前進），應建議改 pull。"""
    warning = _diverge_warning("pull", expected="push")
    assert warning is not None
    assert "pull" in warning


def test_diverge_warning_when_pulling_but_should_push():
    """事故二：pull 時本地其實領先於遠端（base 顯示本地已前進），應建議改 push。"""
    warning = _diverge_warning("push", expected="pull")
    assert warning is not None
    assert "push" in warning


def test_diverge_warning_conflict_mentions_both_sides():
    warning = _diverge_warning("conflict", expected="push")
    assert warning is not None
    assert "independently" in warning


# --- cmd_pull / cmd_push 方向警示整合（0.2.1-W3-671） ------------------------


def test_cmd_push_warns_when_local_lags_remote(tmp_path, monkeypatch, capsys):
    """事故一重現：push 時 base==local（本地自上次同步後未變）而 remote 已前進，
    繼續 push 會以舊內容覆蓋 canonical，preview 必須顯著標示。"""
    import skill_sync.cli as cli_module

    skills_dir = tmp_path / "skills"
    local_skill = skills_dir / "demo-skill"
    local_skill.mkdir(parents=True)
    (local_skill / "SKILL.md").write_text("stale content\n")
    monkeypatch.setattr(cli_module, "get_skills_dir", lambda: skills_dir)

    base_hash = compute_content_hash(local_skill)
    _write_sync_base(local_skill, base_hash)

    scratch = tmp_path / "scratch"
    remote_skill = scratch / "repo" / "demo-skill"
    remote_skill.mkdir(parents=True)
    (remote_skill / "SKILL.md").write_text("remote moved on\n")
    _stub_fixed_tempdir(monkeypatch, scratch)
    _stub_git_noop(monkeypatch)
    monkeypatch.setattr("builtins.input", lambda *_: "n")  # 不套用，只看 preview

    args = _RecordingArgs(name="demo-skill", prune=False, force=False)
    cmd_push(args)

    err = capsys.readouterr().err
    assert "WARNING" in err
    assert "pull" in err


def test_cmd_pull_warns_when_local_leads_remote(tmp_path, monkeypatch, capsys):
    """事故二重現：pull 時 base==remote（遠端自上次同步後未變）而本地已獨立前進，
    繼續 pull 會以舊內容覆蓋本地新增內容，preview 必須顯著標示。"""
    import skill_sync.cli as cli_module

    skills_dir = tmp_path / "skills"
    local_skill = skills_dir / "demo-skill"
    local_skill.mkdir(parents=True)
    (local_skill / "SKILL.md").write_text("local grew a lot\nline2\nline3\n")
    monkeypatch.setattr(cli_module, "get_skills_dir", lambda: skills_dir)

    scratch = tmp_path / "scratch"
    remote_skill = scratch / "repo" / "demo-skill"
    remote_skill.mkdir(parents=True)
    (remote_skill / "SKILL.md").write_text("original content\n")
    _stub_fixed_tempdir(monkeypatch, scratch)
    _stub_git_noop(monkeypatch)

    base_hash = compute_content_hash(remote_skill)  # base == remote（遠端未變）
    _write_sync_base(local_skill, base_hash)
    monkeypatch.setattr("builtins.input", lambda *_: "n")  # 不套用，只看 preview

    args = argparse.Namespace(name="demo-skill", force=False)
    cmd_pull(args)

    err = capsys.readouterr().err
    assert "WARNING" in err
    assert "push" in err


def test_cmd_push_silent_when_no_base_recorded(tmp_path, monkeypatch, capsys):
    """無 base 記錄（既有 skill 從未走過本機制）時不應出現方向警示（向後相容）。"""
    import skill_sync.cli as cli_module

    skills_dir = tmp_path / "skills"
    local_skill = skills_dir / "demo-skill"
    local_skill.mkdir(parents=True)
    (local_skill / "SKILL.md").write_text("local content\n")
    monkeypatch.setattr(cli_module, "get_skills_dir", lambda: skills_dir)

    scratch = tmp_path / "scratch"
    remote_skill = scratch / "repo" / "demo-skill"
    remote_skill.mkdir(parents=True)
    (remote_skill / "SKILL.md").write_text("remote content\n")
    _stub_fixed_tempdir(monkeypatch, scratch)
    _stub_git_noop(monkeypatch)
    monkeypatch.setattr("builtins.input", lambda *_: "n")

    args = _RecordingArgs(name="demo-skill", prune=False, force=False)
    cmd_push(args)

    err = capsys.readouterr().err
    assert "WARNING" not in err


def test_cmd_push_silent_when_direction_matches_push(tmp_path, monkeypatch, capsys):
    """base==remote（遠端未變、本地已前進）而正在 push：方向與操作一致，不應警示。"""
    import skill_sync.cli as cli_module

    skills_dir = tmp_path / "skills"
    local_skill = skills_dir / "demo-skill"
    local_skill.mkdir(parents=True)
    (local_skill / "SKILL.md").write_text("local moved on\n")
    monkeypatch.setattr(cli_module, "get_skills_dir", lambda: skills_dir)

    scratch = tmp_path / "scratch"
    remote_skill = scratch / "repo" / "demo-skill"
    remote_skill.mkdir(parents=True)
    (remote_skill / "SKILL.md").write_text("original content\n")
    _stub_fixed_tempdir(monkeypatch, scratch)
    _stub_git_noop(monkeypatch)
    monkeypatch.setattr("builtins.input", lambda *_: "n")

    base_hash = compute_content_hash(remote_skill)
    _write_sync_base(local_skill, base_hash)

    args = _RecordingArgs(name="demo-skill", prune=False, force=False)
    cmd_push(args)

    err = capsys.readouterr().err
    assert "WARNING" not in err


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


# --- Portability check (W3-621) -------------------------------------------------


def _write_portable_skill(root: Path, name: str, skill_md: str, **extra: str) -> Path:
    skill = root / name
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(skill_md)
    for rel, text in extra.items():
        f = skill / (rel.replace("__", "/") + ".md")
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text)
    return skill


PORTABLE_FRONTMATTER = """---
name: demo
metadata:
  portable: true
---

# Demo
"""

PLAIN_FRONTMATTER = """---
name: demo
---

# Demo
"""


def test_portable_declaration_read_from_frontmatter(tmp_path):
    skill = _write_portable_skill(tmp_path, "demo", PORTABLE_FRONTMATTER)
    assert _is_portable_declared(skill) is True


def test_missing_declaration_defaults_to_not_portable(tmp_path):
    skill = _write_portable_skill(tmp_path, "demo", PLAIN_FRONTMATTER)
    assert _is_portable_declared(skill) is False


def test_consumer_path_reference_reported_with_line_number(tmp_path):
    skill = _write_portable_skill(
        tmp_path,
        "demo",
        PORTABLE_FRONTMATTER + "\nSee `.claude/pm-rules/tdd-flow.md` for the flow.\n",
    )
    violations = check_portability(skill)
    assert len(violations) == 1
    assert violations[0].kind == "consumer-path"
    assert violations[0].line == 9
    assert ".claude/pm-rules/tdd-flow.md" in violations[0].text


def test_ticket_id_reported(tmp_path):
    skill = _write_portable_skill(
        tmp_path,
        "demo",
        PORTABLE_FRONTMATTER + "\n**Version**: 0.8.0 — refined (1.5.0-W5-009.7)\n",
    )
    violations = check_portability(skill)
    assert [v.kind for v in violations] == ["ticket-id"]
    assert "1.5.0-W5-009" in violations[0].text


def test_clean_skill_has_no_violations(tmp_path):
    skill = _write_portable_skill(
        tmp_path,
        "demo",
        PORTABLE_FRONTMATTER + "\nSee [rules](./references/rules.md).\n",
        references__rules="# Rules\n",
    )
    assert check_portability(skill) == []


def test_excluded_dirs_are_not_scanned(tmp_path):
    skill = _write_portable_skill(
        tmp_path,
        "demo",
        PORTABLE_FRONTMATTER,
        **{"references__project-integration__map": "`.claude/pm-rules/tdd-flow.md`\n"},
    )
    assert check_portability(skill) == []


def test_relative_skill_internal_reference_is_not_a_violation(tmp_path):
    skill = _write_portable_skill(
        tmp_path,
        "demo",
        PORTABLE_FRONTMATTER + "\nSee `references/principles/x.md` and ./y.md.\n",
    )
    assert check_portability(skill) == []


def test_push_aborts_on_declared_portable_skill_with_violations(tmp_path, monkeypatch, capsys):
    skills = tmp_path / "skills"
    _write_portable_skill(
        skills,
        "demo",
        PORTABLE_FRONTMATTER + "\nSee `.claude/pm-rules/tdd-flow.md`.\n",
    )
    monkeypatch.setattr("skill_sync.cli.get_skills_dir", lambda: skills)
    args = argparse.Namespace(name="demo", message=None, force=False, prune=False)

    with pytest.raises(SystemExit) as exc:
        cmd_push(args)

    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "SKILL.md:9" in err
    assert "consumer-path" in err


def test_push_proceeds_for_undeclared_skill_and_reports_only(tmp_path, monkeypatch, capsys):
    skills = tmp_path / "skills"
    skill = _write_portable_skill(
        skills,
        "demo",
        PLAIN_FRONTMATTER + "\nSee `.claude/pm-rules/tdd-flow.md`.\n",
    )
    monkeypatch.setattr("skill_sync.cli.get_skills_dir", lambda: skills)

    # 閘門本身不得中止未宣告 portable 的 skill；clone 之後的行為不在本測試範圍。
    _report_portability(skill, "demo", force=False)

    err = capsys.readouterr().err
    assert "Not declared portable" in err


def test_portability_allow_marker_exempts_its_own_line(tmp_path):
    skill = _write_portable_skill(
        tmp_path,
        "demo",
        PORTABLE_FRONTMATTER
        + "\nSee `.claude/pm-rules/x.md` (portability-allow: bridges to the framework rule).\n"
        + "See `.claude/pm-rules/y.md` without a marker.\n",
    )
    violations = check_portability(skill)
    assert len(violations) == 1
    assert ".claude/pm-rules/y.md" in violations[0].text


def test_broken_link_exempt_marker_also_exempts(tmp_path):
    skill = _write_portable_skill(
        tmp_path,
        "demo",
        PORTABLE_FRONTMATTER
        + "\n**Source**: .claude/skills/gone/SKILL.md <!-- broken-link-exempt: 歷史遷移軌跡 -->\n",
    )
    assert check_portability(skill) == []


# --- --force 繞過記錄（0.2.1-W3-635 缺口一） -----------------------------------
#
# --force 繞過閘門先前不留任何記錄，違規來源無從追溯。比照
# ticket_system.lib.precondition 的既有慣例（HOOK_LOGS_DIR env var + JSONL
# append-only），但不引入該模組的 import——skill-sync 是零框架依賴的獨立套件。


def test_write_portability_force_log_appends_jsonl_record(tmp_path, monkeypatch):
    monkeypatch.setenv("HOOK_LOGS_DIR", str(tmp_path / "hook-logs"))
    violation = PortabilityViolation("SKILL.md", 9, "consumer-path", ".claude/pm-rules/x.md")

    _write_portability_force_log("demo", declared=True, already_shared=False, violations=[violation])

    log_files = list((tmp_path / "hook-logs").glob("*.jsonl"))
    assert len(log_files) == 1
    record = json.loads(log_files[0].read_text().splitlines()[0])
    assert record["skill"] == "demo"
    assert record["declared_portable"] is True
    assert record["violation_count"] == 1
    assert record["violations"][0]["text"] == ".claude/pm-rules/x.md"


def test_write_portability_force_log_appends_not_overwrites(tmp_path, monkeypatch):
    monkeypatch.setenv("HOOK_LOGS_DIR", str(tmp_path / "hook-logs"))
    v = PortabilityViolation("SKILL.md", 1, "ticket-id", "1.0.0-W1-001")

    _write_portability_force_log("first", declared=True, already_shared=False, violations=[v])
    _write_portability_force_log("second", declared=True, already_shared=False, violations=[v])

    log_files = list((tmp_path / "hook-logs").glob("*.jsonl"))
    lines = log_files[0].read_text().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["skill"] == "first"
    assert json.loads(lines[1])["skill"] == "second"


def test_resolve_hook_logs_dir_honours_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("HOOK_LOGS_DIR", str(tmp_path / "custom-logs"))
    assert _resolve_hook_logs_dir() == tmp_path / "custom-logs"


def test_push_with_force_on_declared_violation_writes_force_log(tmp_path, monkeypatch, capsys):
    """cmd_push --force 繞過已宣告 portable 的違規時，違規清單必須落地到記錄檔。"""
    skills = tmp_path / "skills"
    _write_portable_skill(
        skills,
        "demo",
        PORTABLE_FRONTMATTER + "\nSee `.claude/pm-rules/tdd-flow.md`.\n",
    )
    monkeypatch.setattr("skill_sync.cli.get_skills_dir", lambda: skills)
    log_dir = tmp_path / "hook-logs"
    monkeypatch.setenv("HOOK_LOGS_DIR", str(log_dir))
    args = argparse.Namespace(name="demo", message=None, force=True, prune=False)

    # 只驗證閘門本身（clone 之後的行為不在本測試範圍，同既有的 undeclared 測試）。
    _report_portability(skills / "demo", "demo", force=True)

    err = capsys.readouterr().err
    assert "--force given" in err
    log_files = list(log_dir.glob("*.jsonl"))
    assert len(log_files) == 1
    record = json.loads(log_files[0].read_text().splitlines()[0])
    assert record["skill"] == "demo"
    assert record["violation_count"] == 1


# --- 已跨 consumer 使用但未宣告 portable（0.2.1-W3-635 缺口二） ----------------
#
# 未宣告 portable 但已存在於 canonical repo 的 skill，代表它已經在被跨
# consumer 散布，閘門先前對它只印一行計數。已存在於 canonical 是可從既有
# fetch_remote_manifest 取得的結構性事實，不是新猜測——凡是 versions.json
# 收錄的 skill 名稱，定義上就是已經在被多個 consumer 拉取的 skill。


def test_skill_exists_in_canonical_true_when_manifest_has_name(monkeypatch):
    import skill_sync.cli as cli_module

    monkeypatch.setattr(
        cli_module, "fetch_remote_manifest", lambda url: {"demo": {"hash": "abc"}}
    )
    assert _skill_exists_in_canonical("demo", "https://example.com/repo.git") is True


def test_skill_exists_in_canonical_false_when_name_absent(monkeypatch):
    import skill_sync.cli as cli_module

    monkeypatch.setattr(cli_module, "fetch_remote_manifest", lambda url: {"other": {}})
    assert _skill_exists_in_canonical("demo", "https://example.com/repo.git") is False


def test_skill_exists_in_canonical_fails_open_on_network_error(monkeypatch):
    """查詢失敗時回傳 False（fail open）：本函式只升級嚴重度，查詢失敗不該
    連帶讓 push 卡住或誤判未跨 consumer 使用的 skill。"""
    import skill_sync.cli as cli_module

    def _raise(url):
        raise OSError("network unreachable")

    monkeypatch.setattr(cli_module, "fetch_remote_manifest", _raise)
    assert _skill_exists_in_canonical("demo", "https://example.com/repo.git") is False


def test_report_portability_without_repo_url_keeps_report_only_behavior(tmp_path, monkeypatch, capsys):
    """向後相容：未傳 repo_url（如既有呼叫端）維持原「未宣告只報告」行為，不查詢遠端。"""
    skill = _write_portable_skill(
        tmp_path,
        "demo",
        PLAIN_FRONTMATTER + "\nSee `.claude/pm-rules/tdd-flow.md`.\n",
    )

    _report_portability(skill, "demo", force=False)

    err = capsys.readouterr().err
    assert "Not declared portable" in err


def test_report_portability_notes_but_does_not_abort_when_already_in_canonical(
    tmp_path, monkeypatch, capsys
):
    """未宣告 portable，repo_url 查得到它已在 canonical repo：只多印一行建議，
    不中止、不升級嚴重度。

    修正記錄：初版曾以「存在於 canonical」升級為中止，PM 驗收時指出這是過度
    推論——canonical 只是散佈通道，一個 skill 在裡面只代表曾被 push 過，不
    代表任何其他 consumer 真的安裝了它（實測：canonical 64 個 skill 中，一線
    消費專案僅裝 23 個；doc/ticket/worktree 等框架專屬工具全在 canonical 但
    該專案一個都沒裝）。據此中止會誤擋大量未共用的框架工具 push，且反轉
    「未宣告者高命中率、故只報告不阻擋」的既有設計取捨。改為僅提示。
    """
    import skill_sync.cli as cli_module

    skill = _write_portable_skill(
        tmp_path,
        "demo",
        PLAIN_FRONTMATTER + "\nSee `.claude/pm-rules/tdd-flow.md`.\n",
    )
    monkeypatch.setattr(
        cli_module, "fetch_remote_manifest", lambda url: {"demo": {"hash": "abc"}}
    )

    _report_portability(skill, "demo", force=False, repo_url="https://example.com/repo.git")

    err = capsys.readouterr().err
    assert "Not declared portable" in err
    assert "canonical" in err.lower()
    assert "declare metadata.portable" in err


def test_report_portability_no_escalation_when_not_in_canonical(tmp_path, monkeypatch, capsys):
    """repo_url 有傳，但這個 skill 名稱不在 canonical manifest：維持報告only，不中止。"""
    import skill_sync.cli as cli_module

    skill = _write_portable_skill(
        tmp_path,
        "demo",
        PLAIN_FRONTMATTER + "\nSee `.claude/pm-rules/tdd-flow.md`.\n",
    )
    monkeypatch.setattr(cli_module, "fetch_remote_manifest", lambda url: {})

    _report_portability(skill, "demo", force=False, repo_url="https://example.com/repo.git")

    err = capsys.readouterr().err
    assert "Not declared portable" in err


def test_framework_only_skills_in_canonical_never_abort_push(tmp_path, monkeypatch, capsys):
    """框架專屬工具（全都在 canonical 但目標 consumer 未安裝）不得被本閘門
    誤擋——即使它們的違規數量很高（doc/continuous-learning/broken-link-check
    等實測命中數十處）。"""
    import skill_sync.cli as cli_module

    framework_only_names = [
        "doc", "ticket", "worktree", "continuous-learning", "broken-link-check",
    ]
    monkeypatch.setattr(
        cli_module,
        "fetch_remote_manifest",
        lambda url: {n: {"hash": "x"} for n in framework_only_names},
    )

    for name in framework_only_names:
        skill = _write_portable_skill(
            tmp_path,
            name,
            PLAIN_FRONTMATTER
            + "\n".join(
                f"See `.claude/pm-rules/rule-{i}.md`." for i in range(5)
            ),
        )
        _report_portability(skill, name, force=False, repo_url="https://example.com/repo.git")
        capsys.readouterr()  # 每輪清空，只確認不拋 SystemExit


# --- .py 敘述性文字掃描（docstring / # 註解，0.2.1-W3-635 缺口三） -------------
#
# 掃描先前只吃 .md，hook/scripts 的 docstring 與註解不在範圍。實測 tdd、
# wrap-decision 兩個已宣告 metadata.portable: true 的 skill，其 hooks/scripts
# 內確有以自然語言描述 .claude/ 路徑的註解行，完全未被閘門捕捉。改用 ast 精確
# 定位 docstring（不誤判一般字串字面值）+ 簡化的 # 註解擷取，範圍限縮於「敘述性
# 文字」而非全部程式碼——一般程式碼的路徑常是真實執行期依賴（如 sys.path
# 操作），全掃會招致大量誤判。


def _write_python_file(skill_dir: Path, rel: str, content: str) -> Path:
    f = skill_dir / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(content)
    return f


def test_extract_python_narrative_text_finds_module_docstring():
    source = '"""模組說明，引用 .claude/pm-rules/tdd-flow.md。"""\n\nx = 1\n'
    entries = _extract_python_narrative_text(source)
    assert any(".claude/pm-rules/tdd-flow.md" in text for _, text in entries)


def test_extract_python_narrative_text_finds_function_docstring():
    source = (
        "def foo():\n"
        '    """參考 .claude/pm-rules/tdd-flow.md 的流程。"""\n'
        "    return 1\n"
    )
    entries = _extract_python_narrative_text(source)
    assert any(".claude/pm-rules/tdd-flow.md" in text for _, text in entries)


def test_extract_python_narrative_text_finds_hash_comment():
    source = "x = 1  # 見 .claude/pm-rules/tdd-flow.md\n"
    entries = _extract_python_narrative_text(source)
    assert any(".claude/pm-rules/tdd-flow.md" in text for _, text in entries)


def test_extract_python_narrative_text_ignores_plain_code_without_comment():
    """一般程式碼的字串字面值（無 # 註解、非 docstring）不視為敘述性文字。"""
    source = 'path = ".claude/lib/foo.py"\n'
    entries = _extract_python_narrative_text(source)
    assert entries == []


def test_extract_python_narrative_text_tolerates_syntax_error():
    """語法有誤的 .py 不得讓掃描整體中斷；退化為僅擷取 # 註解。"""
    source = "def broken(:\n    # 見 .claude/pm-rules/tdd-flow.md\n"
    entries = _extract_python_narrative_text(source)
    assert any(".claude/pm-rules/tdd-flow.md" in text for _, text in entries)


def test_scan_line_for_violations_respects_allow_marker():
    assert _scan_line_for_violations(
        "x.py", 1, ".claude/pm-rules/x.md (portability-allow: bridge)"
    ) == []


def test_check_portability_detects_violation_in_python_docstring(tmp_path):
    skill = _write_portable_skill(tmp_path, "demo", PORTABLE_FRONTMATTER)
    _write_python_file(
        skill, "hooks/example-hook.py",
        '"""說明：見 .claude/pm-rules/tdd-flow.md。"""\n',
    )

    violations = check_portability(skill)

    assert len(violations) == 1
    assert violations[0].file == "hooks/example-hook.py"
    assert violations[0].kind == "consumer-path"


def test_check_portability_detects_ticket_id_in_python_comment(tmp_path):
    skill = _write_portable_skill(tmp_path, "demo", PORTABLE_FRONTMATTER)
    _write_python_file(
        skill, "scripts/run.py",
        "x = 1  # 修正於 1.5.0-W5-009.7\n",
    )

    violations = check_portability(skill)

    assert [v.kind for v in violations] == ["ticket-id"]


def test_check_portability_python_file_with_no_narrative_violation_is_clean(tmp_path):
    skill = _write_portable_skill(tmp_path, "demo", PORTABLE_FRONTMATTER)
    _write_python_file(
        skill, "scripts/run.py",
        'path = ".claude/lib/foo.py"\n\ndef run():\n    return path\n',
    )

    assert check_portability(skill) == []
