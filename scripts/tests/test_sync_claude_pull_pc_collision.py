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


def test_parse_pc_filename_prefixed_excluded_from_collision():
    """Model 1 前綴格式（PC-V1-001）刻意排除於 flat collision 子系統（1.0.0-W1-019.2）。

    前綴格式天生不參與 flat 整數撞號（各專案在自己前綴空間累加，零協調防碰撞）。
    現值 _PC_FILENAME_RE 對前綴檔匹配失敗回 None，正是正確的排除行為。
    """
    assert pull.parse_pc_filename(
        "error-patterns/process-compliance/PC-V1-001-foo.md"
    ) is None
    assert pull.parse_pc_filename(
        "error-patterns/process-compliance/PC-APP-012-bar.md"
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
    assert index["numbers"][165] == {"false-positive-fix-chain"}
    assert index["numbers"][171] == {"auq-dispatch"}


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


# ============================================================================
# 3.5.0-W1-144.1：一號多 slug 與凍結重號組
#
# 根因：build_local_pc_index 以 dict[int, str] 記本地號，同號兩檔只留一個
# slug；resolve_pc_collision 據此把凍結重號組的另一檔誤判為撞號並重編。
# ============================================================================

_METHODOLOGY = (
    Path(__file__).resolve().parent.parent.parent
    / "methodologies" / "error-pattern-numbering-methodology.md"
)
_PC105_A = "feature-implemented-without-doc-integration"
_PC105_B = "pm-cli-syntax-autopilot"


def test_build_local_pc_index_same_number_keeps_all_slugs(tmp_path):
    """同號兩檔都在本地時，索引須同時記住兩個 slug。"""
    claude = tmp_path / ".claude"
    ep = claude / "error-patterns" / "process-compliance"
    _write(ep / f"PC-105-{_PC105_A}.md", "# A\n")
    _write(ep / f"PC-105-{_PC105_B}.md", "# B\n")
    index = pull.build_local_pc_index(claude)
    assert index["numbers"][105] == {_PC105_A, _PC105_B}


def test_frozen_pair_both_local_upstream_returns_either_is_none(tmp_path):
    """對照：凍結組兩檔都在本地，上游帶回任一檔 → none（不重編）。"""
    claude = tmp_path / ".claude"
    ep = claude / "error-patterns" / "process-compliance"
    _write(ep / f"PC-105-{_PC105_A}.md", "# A\n")
    _write(ep / f"PC-105-{_PC105_B}.md", "# B\n")
    index = pull.build_local_pc_index(claude)

    for slug in (_PC105_A, _PC105_B):
        repo_rel = f"error-patterns/process-compliance/PC-105-{slug}.md"
        content = b"---\nid: PC-105\n---\n\nbody\n"
        new_rel, new_content, action = pull.resolve_pc_collision(
            repo_rel, content, index
        )
        assert action == "none", slug
        assert new_rel == repo_rel
        assert new_content == content


def test_frozen_pair_only_one_local_upstream_brings_other_is_none(tmp_path):
    """凍結組本地只有一檔，上游帶回另一檔 → 仍不重編（登記表豁免）。"""
    claude = tmp_path / ".claude"
    ep = claude / "error-patterns" / "process-compliance"
    _write(ep / f"PC-105-{_PC105_A}.md", "# A\n")
    index = pull.build_local_pc_index(claude)

    repo_rel = f"error-patterns/process-compliance/PC-105-{_PC105_B}.md"
    _, _, action = pull.resolve_pc_collision(repo_rel, b"# B\n", index)
    assert action == "none"


def test_frozen_number_with_unregistered_slug_still_renumbers(tmp_path):
    """正向對照：凍結號但 slug 不在登記表 → 屬真撞號，仍重編。"""
    claude = tmp_path / ".claude"
    ep = claude / "error-patterns" / "process-compliance"
    _write(ep / f"PC-105-{_PC105_A}.md", "# A\n")
    _write(ep / f"PC-105-{_PC105_B}.md", "# B\n")
    index = pull.build_local_pc_index(claude)

    repo_rel = "error-patterns/process-compliance/PC-105-brand-new-lesson.md"
    new_rel, _, action = pull.resolve_pc_collision(
        repo_rel, b"---\nid: PC-105\n---\n\nbody\n", index
    )
    assert action == "renumber"
    assert new_rel == "error-patterns/process-compliance/PC-106-brand-new-lesson.md"


def test_non_frozen_same_number_slug_membership(tmp_path):
    """非凍結號的同號多檔：slug 在集合內 → none；不在集合內 → renumber。"""
    claude = tmp_path / ".claude"
    ep = claude / "error-patterns" / "process-compliance"
    _write(ep / "PC-300-alpha.md", "# a\n")
    _write(ep / "PC-300-beta.md", "# b\n")
    index = pull.build_local_pc_index(claude)

    for slug in ("alpha", "beta"):
        _, _, action = pull.resolve_pc_collision(
            f"error-patterns/process-compliance/PC-300-{slug}.md", b"x\n", index
        )
        assert action == "none", slug

    new_rel, _, action = pull.resolve_pc_collision(
        "error-patterns/process-compliance/PC-300-gamma.md", b"x\n", index
    )
    assert action == "renumber"
    assert new_rel == "error-patterns/process-compliance/PC-301-gamma.md"


def test_frozen_constant_matches_methodology_pc_rows():
    """凍結登記常數須與 methodology〈已知 legacy intra-dir 重號〉表格一致。

    只比對 PC 列：本常數服務 PC 撞號對帳，IMP 等其他前綴列不在範圍。
    """
    text = _METHODOLOGY.read_text(encoding="utf-8")
    section = text.split("### 已知 legacy intra-dir 重號", 1)[1].split("\n#", 1)[0]
    row_re = pull._re.compile(
        r"^\|\s*PC-(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$"
    )
    expected: dict[int, frozenset[str]] = {}
    for line in section.splitlines():
        m = row_re.match(line)
        if m:
            expected[int(m.group(1))] = frozenset({m.group(2), m.group(3)})
    assert expected, "methodology 表格未解析出任何 PC 列"
    assert dict(pull.FROZEN_PC_DUPLICATES) == expected


def test_build_local_pc_index_unreadable_file_reports_stderr(tmp_path, capsys):
    """讀檔失敗不可靜默：stderr 須指出檔案，且號與 slug 仍入索引。"""
    claude = tmp_path / ".claude"
    ep = claude / "error-patterns" / "process-compliance"
    ep.mkdir(parents=True)
    (ep / "PC-400-bad-encoding.md").write_bytes(b"\xff\xfe\xfa invalid utf-8")
    index = pull.build_local_pc_index(claude)
    err = capsys.readouterr().err
    assert "PC-400-bad-encoding.md" in err
    assert index["numbers"][400] == {"bad-encoding"}


def test_apply_delta_frozen_pair_not_renumbered(tmp_path):
    """端到端：本地含 PC-105 兩檔，上游修改其一 → 原檔更新，不產生重編副本。"""
    upstream = tmp_path / "upstream"
    _init_repo(upstream)
    ep = upstream / "error-patterns" / "process-compliance"
    ep.mkdir(parents=True)
    (ep / f"PC-105-{_PC105_A}.md").write_text("# A v1\n", encoding="utf-8")
    (ep / f"PC-105-{_PC105_B}.md").write_text("# B v1\n", encoding="utf-8")
    base = _commit_all(upstream, "base")
    (ep / f"PC-105-{_PC105_B}.md").write_text("# B v2\n", encoding="utf-8")
    _commit_all(upstream, "head")

    project_root = tmp_path / "proj"
    lep = project_root / ".claude" / "error-patterns" / "process-compliance"
    lep.mkdir(parents=True)
    (lep / f"PC-105-{_PC105_A}.md").write_text("# A v1\n", encoding="utf-8")
    (lep / f"PC-105-{_PC105_B}.md").write_text("# B v1\n", encoding="utf-8")

    pull.apply_upstream_delta(project_root, upstream, base)

    assert (lep / f"PC-105-{_PC105_B}.md").read_text(encoding="utf-8") == "# B v2\n"
    assert sorted(p.name for p in lep.glob(f"PC-*-{_PC105_B}.md")) == [
        f"PC-105-{_PC105_B}.md"
    ]
