"""Tests for sync-claude-push.py lineage-aware 孤兒守衛（1.2.0-W1-039）。

背景：native intruder 讓位後（PC-177-malformed → PC-184），純檔名比對的孤兒偵測
（detect_uncleaned_deletions / clean_stale_files）無法區分：
  - 上游 PC-177-defensive（框架 canonical，被本地 PC-181 以 lineage 認領，應保留）
  - 上游 PC-177-malformed（讓位後的 native intruder，無人認領，應清）
兩者本地皆無同名檔，會同列孤兒——--clean 誤刪 canonical（PC-APP-002 近失）。

修正：compute_lineage_claimed_upstream_files 重建「本地 lineage 檔認領的上游
(號, slug)」集合，孤兒偵測排除之，使 canonical 受保護、intruder 為真孤兒可清。

涵蓋 acceptance：
  - 本地索引對照辨識 native intruder（lineage 認領 vs 真孤兒）
  - intruder 讓位賦新號不誤刪框架 canonical
  - 不誤動合法同號多 pattern（lineage 認領只保護被認領的上游檔）

參考 PC-APP-002（--clean 過刪 canonical 近失）、PC-181/182（lineage 格式）。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-push.py"
_spec = importlib.util.spec_from_file_location("sync_claude_push_lineage_orphan", _SCRIPT)
assert _spec and _spec.loader
push = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_push_lineage_orphan"] = push
_spec.loader.exec_module(push)  # type: ignore[union-attr]


def _lineage(upstream_num: int, local_num: int) -> str:
    return (
        f"> **編號溯源**：本 pattern 在上游框架 repo（tarrragon/claude.git）"
        f"編號為 PC-{upstream_num}。因本專案 PC-{upstream_num} 已被既有 pattern 佔用，"
        f"於本專案重新編號為 PC-{local_num}。下次 sync-pull 仍會帶回上游 "
        f"PC-{upstream_num}，屆時應辨識為同一 pattern 並去重。\n"
    )


def _write(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


# ============================================================================
# compute_lineage_claimed_upstream_files — 本地 lineage 認領的上游 canonical 集合
# ============================================================================

def test_lineage_file_claims_upstream_canonical(tmp_path: Path):
    """PC-181-defensive（lineage 177）認領上游 PC-177-defensive。"""
    claude = tmp_path / ".claude"
    ep = claude / "error-patterns" / "process-compliance"
    _write(ep / "PC-181-defensive-rule.md", _lineage(177, 181) + "\n# dup\n")
    claimed = push.compute_lineage_claimed_upstream_files(claude)
    assert claimed == {
        "error-patterns/process-compliance/PC-177-defensive-rule.md"
    }


def test_native_bare_file_claims_nothing(tmp_path: Path):
    """讓位後的 native（PC-184-malformed，無 lineage）不認領任何上游檔。"""
    claude = tmp_path / ".claude"
    ep = claude / "error-patterns" / "process-compliance"
    _write(ep / "PC-184-malformed.md", "# native, no lineage\n")
    claimed = push.compute_lineage_claimed_upstream_files(claude)
    assert claimed == set()


def test_mixed_lineage_and_native(tmp_path: Path):
    """混合：兩 lineage 認領兩上游 canonical，兩 native 不認領。"""
    claude = tmp_path / ".claude"
    ep = claude / "error-patterns" / "process-compliance"
    _write(ep / "PC-181-defensive-rule.md", _lineage(177, 181) + "\n# d\n")
    _write(ep / "PC-182-ui-test.md", _lineage(178, 182) + "\n# u\n")
    _write(ep / "PC-184-malformed.md", "# native\n")
    _write(ep / "PC-185-ticket-body.md", "# native\n")
    claimed = push.compute_lineage_claimed_upstream_files(claude)
    assert claimed == {
        "error-patterns/process-compliance/PC-177-defensive-rule.md",
        "error-patterns/process-compliance/PC-178-ui-test.md",
    }


def test_no_error_patterns_dir(tmp_path: Path):
    """無 error-patterns 目錄回空集合，不崩。"""
    claude = tmp_path / ".claude"
    claude.mkdir(parents=True)
    assert push.compute_lineage_claimed_upstream_files(claude) == set()


# ============================================================================
# detect_uncleaned_deletions / clean_stale_files — lineage_claimed 排除
# ============================================================================

def _setup_post_renumber_world(tmp_path: Path):
    """模擬 native 讓位後狀態：
    上游 clone（temp_dir）：PC-177-defensive（canonical）+ PC-177-malformed（intruder
        殘留）+ PC-178-ui-test（canonical）+ PC-178-ticket-body（intruder 殘留）。
    本地 staging（tracked 樹）：PC-181-defensive(lineage 177) / PC-182-ui-test(lineage
        178) / PC-184-malformed(native) / PC-185-ticket-body(native)。
        即上游四檔名在本地皆無同名檔（181/182/184/185）。
    回 (temp_dir, staging, lineage_claimed)。
    """
    temp = tmp_path / "remote"
    staging = tmp_path / "staging"
    ep_r = temp / "error-patterns" / "process-compliance"
    _write(ep_r / "PC-177-defensive-rule.md", "# upstream canonical\n")
    _write(ep_r / "PC-177-malformed.md", "# wrongly-pushed native intruder\n")
    _write(ep_r / "PC-178-ui-test.md", "# upstream canonical\n")
    _write(ep_r / "PC-178-ticket-body.md", "# wrongly-pushed native intruder\n")
    # staging（push 端 git tracked 樹的鏡像）含讓位後的本地檔名
    ep_s = staging / "error-patterns" / "process-compliance"
    _write(ep_s / "PC-181-defensive-rule.md", _lineage(177, 181) + "\n# d\n")
    _write(ep_s / "PC-182-ui-test.md", _lineage(178, 182) + "\n# u\n")
    _write(ep_s / "PC-184-malformed.md", "# native\n")
    _write(ep_s / "PC-185-ticket-body.md", "# native\n")
    # lineage_claimed 在 production 由 claude_dir 計算；此處用 staging 作 claude_dir
    # 等價（兩者皆含本地 lineage 檔）。
    lineage_claimed = push.compute_lineage_claimed_upstream_files(staging)
    return temp, staging, lineage_claimed


def test_orphan_detection_protects_canonical_flags_intruder(tmp_path: Path):
    """孤兒偵測：上游 canonical（被 lineage 認領）不列孤兒；native intruder 列孤兒。"""
    temp, staging, lineage_claimed = _setup_post_renumber_world(tmp_path)
    orphans = push.detect_uncleaned_deletions(temp, staging, None, lineage_claimed)
    orphan_names = {Path(o).name for o in orphans}
    # 受保護的 canonical 不在孤兒清單
    assert "PC-177-defensive-rule.md" not in orphan_names
    assert "PC-178-ui-test.md" not in orphan_names
    # native intruder 為真孤兒
    assert "PC-177-malformed.md" in orphan_names
    assert "PC-178-ticket-body.md" in orphan_names


def test_clean_deletes_only_intruder_not_canonical(tmp_path: Path):
    """--clean：只刪 native intruder，保留 lineage 認領的 canonical（PC-APP-002 防護）。"""
    temp, staging, lineage_claimed = _setup_post_renumber_world(tmp_path)
    deleted = push.clean_stale_files(temp, staging, None, lineage_claimed)
    ep_r = temp / "error-patterns" / "process-compliance"
    # canonical 保留
    assert (ep_r / "PC-177-defensive-rule.md").exists()
    assert (ep_r / "PC-178-ui-test.md").exists()
    # intruder 刪除
    assert not (ep_r / "PC-177-malformed.md").exists()
    assert not (ep_r / "PC-178-ticket-body.md").exists()
    assert deleted >= 2


def test_clean_without_lineage_guard_would_delete_canonical(tmp_path: Path):
    """負向錨點：不傳 lineage_claimed 時 canonical 與 intruder 同列孤兒（證明守衛必要）。"""
    temp, staging, _ = _setup_post_renumber_world(tmp_path)
    orphans = push.detect_uncleaned_deletions(temp, staging, None, None)
    orphan_names = {Path(o).name for o in orphans}
    # 無守衛時 canonical 亦被誤列——這正是 PC-APP-002 近失，守衛存在的理由
    assert "PC-177-defensive-rule.md" in orphan_names
    assert "PC-177-malformed.md" in orphan_names


# ============================================================================
# 不誤動合法同號多 pattern：lineage 認領只保護「被認領的」上游檔
# ============================================================================

def test_lineage_guard_does_not_overprotect_unrelated_canonical(tmp_path: Path):
    """lineage 認領 PC-177-defensive 不連帶保護無關上游檔（如 PC-010-foo）。"""
    temp, staging, lineage_claimed = _setup_post_renumber_world(tmp_path)
    # 上游另有一個本地真的 git rm 掉的檔 → 應仍列孤兒
    ep_r = temp / "error-patterns" / "process-compliance"
    _write(ep_r / "PC-010-genuinely-removed.md", "# locally git-rm'd\n")
    orphans = push.detect_uncleaned_deletions(temp, staging, None, lineage_claimed)
    orphan_names = {Path(o).name for o in orphans}
    assert "PC-010-genuinely-removed.md" in orphan_names
    assert "PC-177-defensive-rule.md" not in orphan_names
