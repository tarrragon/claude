"""Tests for sync-claude-pull.py PC 編號撞號偵測與自動重編號（0.19.1-W1-017 / 瑕疵 D）。

涵蓋 acceptance：
  - pull 偵測 error-patterns PC 編號與本地衝突（同編號不同 pattern）
  - 衝突時自動重編為本地下一個可用號
  - 重編檔案內加上游溯源註記
  - 無衝突時不改動既有行為
  - dedup：上游帶回的已是先前重編過的同一 pattern → 識別並跳過（不重複匯入）

對應本 session 手動 PC-171 重編號流程的自動化（W1-014 瑕疵 D / D3 import-time）。
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location("sync_claude_pull_pc_collision", _SCRIPT)
assert _spec and _spec.loader
pull = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_pc_collision"] = pull
_spec.loader.exec_module(pull)  # type: ignore[union-attr]


# ============================================================================
# parse_pc_filename
# ============================================================================

def test_parse_pc_filename_valid():
    assert pull.parse_pc_filename(
        "error-patterns/process-compliance/PC-165-foo-bar.md"
    ) == (165, "foo-bar")


def test_parse_pc_filename_non_pc_returns_none():
    assert pull.parse_pc_filename("error-patterns/README.md") is None
    assert pull.parse_pc_filename("rules/core/quality-baseline.md") is None
    # IMP/TEST/ARCH 等其他 error-pattern 前綴不在本 ticket 範圍（僅 PC）
    assert pull.parse_pc_filename(
        "error-patterns/implementation/IMP-003-foo.md"
    ) is None


# ============================================================================
# build_local_pc_index
# ============================================================================

def _write(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def test_build_local_pc_index_maps_number_to_slug(tmp_path):
    claude = tmp_path / ".claude"
    ep = claude / "error-patterns" / "process-compliance"
    _write(ep / "PC-165-false-positive-fix-chain.md", "# PC-165\n")
    _write(ep / "PC-171-auq-dispatch.md", "# PC-171\n")
    index = pull.build_local_pc_index(claude)
    assert index["numbers"][165] == "false-positive-fix-chain"
    assert index["numbers"][171] == "auq-dispatch"


def test_build_local_pc_index_records_provenance(tmp_path):
    """重編後的本地檔含溯源註記，索引應記錄 (上游號, slug) → 本地號。"""
    claude = tmp_path / ".claude"
    ep = claude / "error-patterns" / "process-compliance"
    content = (
        "---\nid: PC-171\n---\n\n"
        "> **編號溯源**：本 pattern 在上游框架 repo（tarrragon/claude.git）"
        "編號為 PC-165。因本專案 PC-165 已被佔用，於本專案重新編號為 PC-171。\n"
    )
    _write(ep / "PC-171-auq-dispatch.md", content)
    index = pull.build_local_pc_index(claude)
    # provenance：上游 PC-165 + slug auq-dispatch 已在本地以 171 收錄
    assert index["provenance"][(165, "auq-dispatch")] == 171


# ============================================================================
# resolve_pc_collision
# ============================================================================

def test_no_collision_keeps_path_and_content(tmp_path):
    claude = tmp_path / ".claude"
    index = pull.build_local_pc_index(claude)  # 空
    repo_rel = "error-patterns/process-compliance/PC-200-new-pattern.md"
    content = b"# PC-200\n"
    new_rel, new_content_out, action = pull.resolve_pc_collision(
        repo_rel, content, index
    )
    assert action == "none"
    assert new_rel == repo_rel
    assert new_content_out == content


def test_collision_different_slug_renumbers_and_adds_provenance(tmp_path):
    claude = tmp_path / ".claude"
    ep = claude / "error-patterns" / "process-compliance"
    _write(ep / "PC-165-false-positive-fix-chain.md", "# local PC-165\n")
    _write(ep / "PC-171-existing.md", "# local PC-171\n")
    index = pull.build_local_pc_index(claude)

    repo_rel = "error-patterns/process-compliance/PC-165-auq-dispatch.md"
    content = b"---\nid: PC-165\n---\n\n# PC-165: AUQ dispatch\n\nbody\n"
    new_rel, new_content, action = pull.resolve_pc_collision(
        repo_rel, content, index
    )
    assert action == "renumber"
    # 下一個可用號：165 與 171 已佔用 → 172
    assert new_rel == "error-patterns/process-compliance/PC-172-auq-dispatch.md"
    text = new_content.decode("utf-8")
    assert "編號溯源" in text
    assert "PC-165" in text  # 溯源提及上游號
    assert "PC-172" in text  # 提及本地新號
    # frontmatter id 已更新為新號
    assert "id: PC-172" in text


def test_collision_same_slug_is_dedup_skip(tmp_path):
    """上游帶回先前已重編過的同一 pattern（同 slug）→ dedup，不重複匯入。"""
    claude = tmp_path / ".claude"
    ep = claude / "error-patterns" / "process-compliance"
    provenance_note = (
        "---\nid: PC-171\n---\n\n"
        "> **編號溯源**：本 pattern 在上游框架 repo 編號為 PC-165。"
        "於本專案重新編號為 PC-171。\n"
    )
    _write(ep / "PC-171-auq-dispatch.md", provenance_note)
    # 並佔用 165（不同 pattern）
    _write(ep / "PC-165-false-positive-fix-chain.md", "# local\n")
    index = pull.build_local_pc_index(claude)

    repo_rel = "error-patterns/process-compliance/PC-165-auq-dispatch.md"
    content = b"# upstream PC-165 auq-dispatch\n"
    new_rel, new_content, action = pull.resolve_pc_collision(
        repo_rel, content, index
    )
    assert action == "dedup_skip"


def test_collision_same_number_same_slug_no_local_provenance_is_noop(tmp_path):
    """上游與本地同號同 slug（本就是同一檔，非衝突）→ none，正常三方合併。"""
    claude = tmp_path / ".claude"
    ep = claude / "error-patterns" / "process-compliance"
    _write(ep / "PC-165-false-positive-fix-chain.md", "# local PC-165\n")
    index = pull.build_local_pc_index(claude)

    repo_rel = "error-patterns/process-compliance/PC-165-false-positive-fix-chain.md"
    content = b"# upstream PC-165 same\n"
    new_rel, new_content, action = pull.resolve_pc_collision(
        repo_rel, content, index
    )
    assert action == "none"
    assert new_rel == repo_rel


# ============================================================================
# 整合：apply_upstream_delta 端到端撞號重編
# ============================================================================

def _git(args, cwd):
    subprocess.run(["git", *args], cwd=str(cwd), check=True,
                   capture_output=True, text=True)


def _init_repo(repo):
    repo.mkdir(parents=True, exist_ok=True)
    _git(["init", "-q"], repo)
    _git(["config", "user.email", "t@t.t"], repo)
    _git(["config", "user.name", "t"], repo)
    _git(["config", "commit.gpgsign", "false"], repo)


def _commit_all(repo, msg):
    _git(["add", "-A"], repo)
    _git(["commit", "-q", "-m", msg], repo)
    out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo),
                         check=True, capture_output=True, text=True)
    return out.stdout.strip()


def test_apply_delta_renumbers_colliding_pc(tmp_path):
    """端到端：上游新增 PC-165-auq 撞本地既有 PC-165-fpfc → 自動重編。"""
    upstream = tmp_path / "upstream"
    _init_repo(upstream)
    ep = upstream / "error-patterns" / "process-compliance"
    ep.mkdir(parents=True)
    (ep / "PC-200-unrelated.md").write_text("# PC-200\n", encoding="utf-8")
    base = _commit_all(upstream, "base")
    (ep / "PC-165-auq-dispatch.md").write_text(
        "---\nid: PC-165\n---\n\n# PC-165: AUQ dispatch\n\nbody\n",
        encoding="utf-8",
    )
    _commit_all(upstream, "head")

    project_root = tmp_path / "proj"
    claude = project_root / ".claude"
    lep = claude / "error-patterns" / "process-compliance"
    lep.mkdir(parents=True)
    (lep / "PC-165-false-positive-fix-chain.md").write_text(
        "# local PC-165\n", encoding="utf-8"
    )

    pull.apply_upstream_delta(project_root, upstream, base)

    assert (lep / "PC-165-false-positive-fix-chain.md").read_text() == "# local PC-165\n"
    # 重編針對「本地」已佔用號（僅 165）→ 下一可用為 166（PC-200 屬上游非本地）
    renamed = lep / "PC-166-auq-dispatch.md"
    assert renamed.exists()
    text = renamed.read_text(encoding="utf-8")
    assert "編號溯源" in text
    assert "id: PC-166" in text


def test_apply_delta_no_pc_collision_unchanged(tmp_path):
    """無撞號：上游 PC 號本地未佔用 → 正常套用，不重編。"""
    upstream = tmp_path / "upstream"
    _init_repo(upstream)
    ep = upstream / "error-patterns" / "process-compliance"
    ep.mkdir(parents=True)
    (ep / "seed.md").write_text("seed\n", encoding="utf-8")
    base = _commit_all(upstream, "base")
    (ep / "PC-300-fresh.md").write_text(
        "---\nid: PC-300\n---\n\nbody\n", encoding="utf-8"
    )
    _commit_all(upstream, "head")

    project_root = tmp_path / "proj"
    claude = project_root / ".claude"
    lep = claude / "error-patterns" / "process-compliance"
    lep.mkdir(parents=True)

    pull.apply_upstream_delta(project_root, upstream, base)

    applied_file = lep / "PC-300-fresh.md"
    assert applied_file.exists()
    text = applied_file.read_text(encoding="utf-8")
    assert "編號溯源" not in text
    assert "id: PC-300" in text
