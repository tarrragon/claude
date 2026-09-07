"""Tests for sync-claude-pull.py 三方合併衝突標記寫回 SKILL.md frontmatter（0.2.1-W3-1287）。

涵蓋 acceptance：
  - metadata.version 三方衝突（local 與 upstream 各自獨立 bump 版號）後，
    工作區 SKILL.md 可被 YAML 解析且不含衝突標記（`<<<<<<<`）
  - 版號差異之外仍有真實內容衝突時，不得被誤判為「僅版號差異」而靜默吃掉
    ——落回標準三方合併，維持既有標記行為（回歸防護）
  - pull 收尾的正式檔標記殘留掃描（scan_conflict_marker_residue）：命中一般
    衝突檔、排除 .sync-conflicts/ 對照副本、不誤判原始碼中描述標記格式的散文
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location(
    "sync_claude_pull_three_way_merge", _SCRIPT
)
assert _spec and _spec.loader
pull = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_three_way_merge"] = pull
_spec.loader.exec_module(pull)  # type: ignore[union-attr]


# ============================================================================
# Helpers：建立可控的 git upstream repo fixture
# ============================================================================

def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(
        ["git", *args], cwd=str(cwd), check=True,
        capture_output=True, text=True,
    )


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(["init", "-q"], repo)
    _git(["config", "user.email", "t@t.t"], repo)
    _git(["config", "user.name", "t"], repo)
    _git(["config", "commit.gpgsign", "false"], repo)


def _commit_all(repo: Path, msg: str) -> str:
    _git(["add", "-A"], repo)
    _git(["commit", "-q", "-m", msg], repo)
    out = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo),
        check=True, capture_output=True, text=True,
    )
    return out.stdout.strip()


def _skill_md(version: str, body: str = "# demo\n\n內文不變。\n") -> str:
    return (
        "---\n"
        "name: demo\n"
        "description: 測試用 skill\n"
        "metadata:\n"
        "  portable: true\n"
        f"  version: {version}\n"
        "  category: test\n"
        "---\n\n"
        f"{body}"
    )


# ============================================================================
# 情境 1：metadata.version 三方衝突 → three_way_merge_file 自動解決，無標記
# ============================================================================

def test_metadata_version_conflict_resolves_without_markers(tmp_path):
    """local 與 upstream 各自獨立 bump 版號（其餘內容相同）→ 自動取較大版號，
    不產生任何 `<<<<<<<` 標記，結果仍為合法 YAML frontmatter。"""
    base_bytes = _skill_md("1.7.0").encode("utf-8")
    local_path = tmp_path / "local" / "SKILL.md"
    upstream_path = tmp_path / "upstream" / "SKILL.md"
    local_path.parent.mkdir(parents=True)
    upstream_path.parent.mkdir(parents=True)
    # 本地已透過 skill-sync 通道 bump 至 1.9.1
    local_path.write_text(_skill_md("1.9.1"), encoding="utf-8")
    # canonical 上游仍停留於較舊的 1.8.0（consumer 實測樣本重現）
    upstream_path.write_text(_skill_md("1.8.0"), encoding="utf-8")

    merged, conflict = pull.three_way_merge_file(
        base_content=base_bytes,
        local_path=local_path,
        upstream_path=upstream_path,
    )

    assert conflict is False
    assert merged is not None
    assert b"<<<<<<<" not in merged
    assert b"=======" not in merged
    assert b">>>>>>>" not in merged

    parsed = yaml.safe_load(merged.decode("utf-8").split("---\n", 2)[1])
    assert parsed["metadata"]["version"] == "1.9.1"  # 兩者取較大版號


def test_metadata_version_conflict_takes_larger_when_upstream_ahead(tmp_path):
    """upstream 版號較大時，解決結果採 upstream 版號（非固定偏向某一側）。"""
    base_bytes = _skill_md("1.0.0").encode("utf-8")
    local_path = tmp_path / "local" / "SKILL.md"
    upstream_path = tmp_path / "upstream" / "SKILL.md"
    local_path.parent.mkdir(parents=True)
    upstream_path.parent.mkdir(parents=True)
    local_path.write_text(_skill_md("1.0.1"), encoding="utf-8")
    upstream_path.write_text(_skill_md("2.0.0"), encoding="utf-8")

    merged, conflict = pull.three_way_merge_file(
        base_content=base_bytes,
        local_path=local_path,
        upstream_path=upstream_path,
    )

    assert conflict is False
    parsed = yaml.safe_load(merged.decode("utf-8").split("---\n", 2)[1])
    assert parsed["metadata"]["version"] == "2.0.0"


# ============================================================================
# 情境 2：真實內容衝突不得被誤判為「僅版號差異」（回歸防護）
# ============================================================================

def test_real_content_conflict_still_marked(tmp_path):
    """版號之外的 body 內容三方皆不同 → 仍是真衝突，落回標準標記行為。"""
    local_path = tmp_path / "local" / "SKILL.md"
    upstream_path = tmp_path / "upstream" / "SKILL.md"
    local_path.parent.mkdir(parents=True)
    upstream_path.parent.mkdir(parents=True)
    base_bytes = _skill_md("1.0.0", body="line1\nline2\nline3\n").encode("utf-8")
    local_path.write_text(
        _skill_md("1.0.1", body="line1\nLOCAL\nline3\n"), encoding="utf-8"
    )
    upstream_path.write_text(
        _skill_md("1.0.2", body="line1\nUPSTREAM\nline3\n"), encoding="utf-8"
    )

    merged, conflict = pull.three_way_merge_file(
        base_content=base_bytes,
        local_path=local_path,
        upstream_path=upstream_path,
    )

    assert conflict is True
    assert b"<<<<<<<" in merged


def test_non_skill_md_file_not_affected(tmp_path):
    """非 SKILL.md 檔名不觸發版號專屬解衝突，維持既有行為。"""
    local_path = tmp_path / "local.md"
    upstream_path = tmp_path / "upstream.md"
    base_bytes = _skill_md("1.0.0").encode("utf-8")
    local_path.write_text(_skill_md("1.9.1"), encoding="utf-8")
    upstream_path.write_text(_skill_md("1.8.0"), encoding="utf-8")

    merged, conflict = pull.three_way_merge_file(
        base_content=base_bytes,
        local_path=local_path,
        upstream_path=upstream_path,
    )

    # 非 SKILL.md：metadata.version 差異落回標準三方合併判斷（此處版號行
    # 本身即為 diff 的唯一行，git merge-file 通常仍可乾淨合併其中一側，
    # 但不得走 skill 版號專屬邏輯——以 mock 驗證專屬函式未被呼叫更直接）。
    assert True  # 行為交由下方 monkeypatch 測試驗證是否呼叫專屬邏輯


def test_non_skill_md_skips_version_resolution_helper(tmp_path, monkeypatch):
    """非 SKILL.md 路徑不得呼叫 skill 版號專屬解衝突函式。"""
    called = []
    original = pull._resolve_skill_metadata_version_conflict

    def _spy(*args, **kwargs):
        called.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(pull, "_resolve_skill_metadata_version_conflict", _spy)

    local_path = tmp_path / "local.md"
    upstream_path = tmp_path / "upstream.md"
    base_bytes = _skill_md("1.0.0").encode("utf-8")
    local_path.write_text(_skill_md("1.9.1"), encoding="utf-8")
    upstream_path.write_text(_skill_md("1.8.0"), encoding="utf-8")

    pull.three_way_merge_file(
        base_content=base_bytes, local_path=local_path, upstream_path=upstream_path,
    )

    assert called == []


# ============================================================================
# 情境 3：apply_upstream_delta 端到端重現 consumer 實測樣本
# ============================================================================

def test_apply_delta_skill_md_version_conflict_end_to_end(tmp_path):
    """端到端重現：component-contract-design 的 SKILL.md 版號衝突拉取後，
    工作區檔案可被 YAML 解析且無衝突標記；不計入 conflicts 清單（已自動解決）。"""
    upstream = tmp_path / "upstream"
    _init_repo(upstream)
    skill_dir = upstream / "skills" / "component-contract-design"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(_skill_md("1.7.0"), encoding="utf-8")
    base = _commit_all(upstream, "base")

    (skill_dir / "SKILL.md").write_text(_skill_md("1.8.0"), encoding="utf-8")
    _commit_all(upstream, "head")

    project_root = tmp_path / "proj"
    claude = project_root / ".claude"
    local_skill_dir = claude / "skills" / "component-contract-design"
    local_skill_dir.mkdir(parents=True)
    (local_skill_dir / "SKILL.md").write_text(_skill_md("1.9.1"), encoding="utf-8")

    _applied, conflicts, _residue = pull.apply_upstream_delta(
        project_root, upstream, base
    )

    assert "skills/component-contract-design/SKILL.md" not in conflicts
    result_text = (local_skill_dir / "SKILL.md").read_text(encoding="utf-8")
    assert "<<<<<<<" not in result_text
    parsed = yaml.safe_load(result_text.split("---\n", 2)[1])
    assert parsed["metadata"]["version"] == "1.9.1"


# ============================================================================
# 情境 4：pull 收尾標記殘留掃描（acceptance 2）
# ============================================================================

def test_scan_conflict_marker_residue_detects_hit(tmp_path):
    claude = tmp_path / ".claude"
    (claude / "rules").mkdir(parents=True)
    (claude / "rules" / "conflict.md").write_text(
        "a\n<<<<<<< local\nLOCAL\n=======\nUPSTREAM\n>>>>>>> upstream\nc\n",
        encoding="utf-8",
    )
    hits = pull.scan_conflict_marker_residue(claude)
    assert hits == ["rules/conflict.md"]


def test_scan_conflict_marker_residue_excludes_sync_conflicts_dir(tmp_path):
    claude = tmp_path / ".claude"
    conflicts_dir = claude / ".sync-conflicts" / "rules"
    conflicts_dir.mkdir(parents=True)
    (conflicts_dir / "conflict.md").write_text(
        "<<<<<<< local\nLOCAL\n=======\nUPSTREAM\n>>>>>>> upstream\n",
        encoding="utf-8",
    )
    hits = pull.scan_conflict_marker_residue(claude)
    assert hits == []


def test_scan_conflict_marker_residue_ignores_prose_mentions(tmp_path):
    """原始碼/文件中描述標記格式的散文字串（非行首）不誤判為殘留。"""
    claude = tmp_path / ".claude"
    claude.mkdir(parents=True)
    (claude / "note.md").write_text(
        "衝突標記格式為 `<<<<<<<`，範例：if b\"<<<<<<<\" not in merged_bytes:\n"
        "    do_something()\n",
        encoding="utf-8",
    )
    hits = pull.scan_conflict_marker_residue(claude)
    assert hits == []


def test_scan_conflict_marker_residue_no_hits_when_clean(tmp_path):
    claude = tmp_path / ".claude"
    claude.mkdir(parents=True)
    (claude / "clean.md").write_text("正常內容，無標記。\n", encoding="utf-8")
    hits = pull.scan_conflict_marker_residue(claude)
    assert hits == []
