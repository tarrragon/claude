"""Unit tests for skill_sync.cli exclude-file logic and content-hash sync comparison."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skill_sync.cli import (  # noqa: E402
    _classify_sync_status,
    _extract_local_manifest,
    _has_local_override,
    _should_exclude_file,
    compute_content_hash,
    compute_diff,
    EXCLUDE_DIRS,
    SKILL_SYNC_OVERRIDE_MARKER,
    update_sync_manifest,
)


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

    up_to_date, diverged, overridden, skipped = _classify_sync_status(
        local_manifest, remote_manifest, tmp_path / "local"
    )

    assert up_to_date == []
    assert overridden == []
    assert skipped == []
    assert len(diverged) == 1
    name, local_display, remote_display = diverged[0]
    assert name == "wrap-decision"
    assert local_display == "2.5.0"
    assert remote_display == "2.5.0"


# --- _classify_sync_status ---------------------------------------------------


def test_classify_sync_status_up_to_date_when_hash_matches(tmp_path):
    local_manifest = {"foo": {"version": "1.0.0", "hash": "same-hash"}}
    remote_manifest = {"foo": {"version": "1.0.0", "hash": "same-hash"}}

    up_to_date, diverged, overridden, skipped = _classify_sync_status(
        local_manifest, remote_manifest, tmp_path
    )

    assert up_to_date == ["foo"]
    assert diverged == []
    assert overridden == []
    assert skipped == []


def test_classify_sync_status_skips_remote_without_hash_field(tmp_path):
    """remote 尚為舊格式（純版本字串）時不誤判為分歧或同步，改列為待更新的 skipped。"""
    local_manifest = {"foo": {"version": "1.0.0", "hash": "abc"}}
    remote_manifest = {"foo": "1.0.0"}  # 舊格式：純字串，無 hash 欄位

    up_to_date, diverged, overridden, skipped = _classify_sync_status(
        local_manifest, remote_manifest, tmp_path
    )

    assert skipped == ["foo"]
    assert up_to_date == []
    assert diverged == []


def test_classify_sync_status_respects_local_override_marker(tmp_path):
    skill_dir = tmp_path / "foo"
    skill_dir.mkdir()
    (skill_dir / SKILL_SYNC_OVERRIDE_MARKER).write_text("intentional customization")

    local_manifest = {"foo": {"version": "1.0.0", "hash": "local-hash"}}
    remote_manifest = {"foo": {"version": "2.0.0", "hash": "remote-hash"}}

    up_to_date, diverged, overridden, skipped = _classify_sync_status(
        local_manifest, remote_manifest, tmp_path
    )

    assert overridden == ["foo"]
    assert up_to_date == []
    assert diverged == []
    assert skipped == []


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
