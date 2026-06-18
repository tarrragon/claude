"""Tests for sync-claude-push.py PC 編號撞號對稱（1.2.0-W1-038）。

鏡像 sync-claude-pull.py 的撞號邏輯，補 push 端對稱三規則：
  規則 1：辨識 pull 重編 artifact（含 lineage 標記）不外推。
  規則 2：本地原生 bare 號被上游不同 slug 佔用 → 賦 next-available canonical 號。
  規則 3：首跑對帳——辨識上游既存 mess（同 slug 重複號）+ 不誤報合法同號多 pattern。

涵蓋 acceptance：
  - 三規則
  - dry-run 不寫檔
  - lineage 解析
  - no-op（無撞號時不誤動）
  - 上游當前 6 檔 mess（PC-177×2/178×2/181/182）辨識

參考 PC-APP-002（canonical 賦號方向）、PC-181（lineage 格式）。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-push.py"
_spec = importlib.util.spec_from_file_location("sync_claude_push_pc_collision", _SCRIPT)
assert _spec and _spec.loader
push = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_push_pc_collision"] = push
_spec.loader.exec_module(push)  # type: ignore[union-attr]


# lineage 標記字面（與 sync-pull 的 _build_provenance_note 對稱）
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
# parse_pc_filename — 與 pull 端對稱（bare 認、前綴排除）
# ============================================================================

def test_parse_pc_filename_valid():
    assert push.parse_pc_filename(
        "error-patterns/process-compliance/PC-165-foo-bar.md"
    ) == (165, "foo-bar")


def test_parse_pc_filename_zero_padded():
    # PC-010 與 PC-10 同號（int("010")==10）——zero-padding 不應被當不同號
    assert push.parse_pc_filename(
        "error-patterns/process-compliance/PC-010-task-tracking.md"
    ) == (10, "task-tracking")


def test_parse_pc_filename_non_pc_returns_none():
    assert push.parse_pc_filename("error-patterns/README.md") is None
    assert push.parse_pc_filename("rules/core/quality-baseline.md") is None
    assert push.parse_pc_filename(
        "error-patterns/implementation/IMP-003-foo.md"
    ) is None


def test_parse_pc_filename_prefixed_excluded():
    # 前綴格式（PC-V1-/PC-APP-/PC-TUNL-）刻意排除於 flat 撞號子系統
    assert push.parse_pc_filename(
        "error-patterns/process-compliance/PC-V1-001-foo.md"
    ) is None
    assert push.parse_pc_filename(
        "error-patterns/process-compliance/PC-APP-002-bar.md"
    ) is None


# ============================================================================
# parse_local_lineage — 規則 1 的辨識依據
# ============================================================================

def test_parse_local_lineage_extracts_both_numbers():
    content = _lineage(177, 181) + "\n# PC-181: foo\n"
    assert push.parse_local_lineage(content) == (177, 181)


def test_parse_local_lineage_none_when_absent():
    assert push.parse_local_lineage("# PC-177: bare native pattern\n") is None


# ============================================================================
# build_upstream_pc_index — 容納 mess（同號多 slug）
# ============================================================================

def test_build_upstream_index_maps_number_to_slug_set(tmp_path):
    up = tmp_path / "upstream"
    ep = up / "error-patterns" / "process-compliance"
    _write(ep / "PC-177-defensive-rule.md", "x")
    _write(ep / "PC-177-malformed-tool-call.md", "y")
    idx = push.build_upstream_pc_index(up)
    assert idx["numbers"][177] == {"defensive-rule", "malformed-tool-call"}
    assert idx["by_slug"][(177, "defensive-rule")].endswith(
        "PC-177-defensive-rule.md"
    )


def test_build_upstream_index_empty_when_no_error_patterns(tmp_path):
    idx = push.build_upstream_pc_index(tmp_path / "empty")
    assert idx == {"numbers": {}, "by_slug": {}}


# ============================================================================
# _next_available_canonical_number — reserved 累積避免同輪撞號
# ============================================================================

def test_next_available_skips_occupied():
    numbers = {177: {"a"}, 178: {"b"}}
    assert push._next_available_canonical_number(numbers, 177) == 179


def test_next_available_respects_reserved():
    numbers = {177: {"a"}}
    reserved = {178}
    # 178 已 reserved（本輪賦給別檔）→ 跳到 179
    assert push._next_available_canonical_number(numbers, 177, reserved) == 179


# ============================================================================
# 規則 1：lineage artifact 不外推
# ============================================================================

def test_rule1_lineage_artifact_excluded():
    repo_rel = "error-patterns/process-compliance/PC-181-defensive-rule.md"
    content = _lineage(177, 181) + "\n# PC-181\n"
    upstream = {"numbers": {177: {"defensive-rule"}}, "by_slug": {}}
    plan = push.plan_push_pc_action(repo_rel, content, upstream)
    assert plan["action"] == "exclude_lineage_artifact"
    assert plan["upstream_num"] == 177
    assert plan["local_num"] == 181


# ============================================================================
# 規則 2：本地原生撞號賦 canonical
# ============================================================================

def test_rule2_native_collision_assigns_canonical():
    # 本地 PC-177-malformed（bare、native）；上游 PC-177 被 defensive 佔
    repo_rel = "error-patterns/process-compliance/PC-177-malformed.md"
    content = "# PC-177: malformed native\n"
    upstream = {"numbers": {177: {"defensive-rule"}}, "by_slug": {}}
    plan = push.plan_push_pc_action(repo_rel, content, upstream)
    assert plan["action"] == "assign_canonical"
    assert plan["old_num"] == 177
    assert plan["slug"] == "malformed"
    assert plan["new_num"] == 178  # next-available 跳過 177
    assert plan["new_repo_rel"].endswith("PC-178-malformed.md")
    # 新內容含 lineage 記憶（下次 push 被規則 1 辨識）
    assert push.parse_local_lineage(plan["new_content"]) == (177, 178)


def test_rule2_reserved_prevents_same_new_number():
    # 兩個本地原生撞號同輪賦號，不可都賦 178
    upstream = {"numbers": {177: {"x"}}, "by_slug": {}}
    reserved: set[int] = set()
    p1 = push.plan_push_pc_action(
        "error-patterns/pc/PC-177-aaa.md", "# a\n", upstream, reserved
    )
    p2 = push.plan_push_pc_action(
        "error-patterns/pc/PC-177-bbb.md", "# b\n", upstream, reserved
    )
    assert p1["new_num"] != p2["new_num"]
    assert {p1["new_num"], p2["new_num"]} == {178, 179}


# ============================================================================
# no-op：合法態不誤動（含 zero-padded 同 slug、同號多合法 pattern）
# ============================================================================

def test_noop_when_upstream_number_free():
    repo_rel = "error-patterns/pc/PC-200-brand-new.md"
    upstream = {"numbers": {177: {"x"}}, "by_slug": {}}
    assert push.plan_push_pc_action(repo_rel, "# new\n", upstream)["action"] == "none"


def test_noop_when_local_slug_present_upstream_same_number():
    # 上游 PC-010 同號兩合法 slug；本地 PC-010 同 slug → 同一 pattern，不誤動
    repo_rel = "error-patterns/pc/PC-010-task-tracking-in-memory.md"
    upstream = {
        "numbers": {10: {"task-tracking-in-memory", "pm-skipped-checkpoint"}},
        "by_slug": {},
    }
    assert push.plan_push_pc_action(repo_rel, "# x\n", upstream)["action"] == "none"


def test_noop_non_pc_file():
    assert push.plan_push_pc_action(
        "rules/core/quality-baseline.md", "# x\n", {"numbers": {}, "by_slug": {}}
    )["action"] == "none"


# ============================================================================
# 規則 3：首跑對帳——辨識 mess，不誤報合法同號多 pattern
# ============================================================================

def test_reconcile_detects_same_slug_duplicate_number():
    # 同 slug 在 177 與 181 同時存在 → 高號 181 為誤推鏡像
    up = {
        "numbers": {177: {"defensive-rule"}, 181: {"defensive-rule"}},
        "by_slug": {
            (177, "defensive-rule"): "error-patterns/pc/PC-177-defensive-rule.md",
            (181, "defensive-rule"): "error-patterns/pc/PC-181-defensive-rule.md",
        },
    }
    plan = push.plan_upstream_mess_reconciliation(up)
    assert len(plan) == 1
    item = plan[0]
    assert item["kind"] == "duplicate_renumbered_slug"
    assert item["slug"] == "defensive-rule"
    assert item["canonical_num"] == 177
    assert item["duplicate_num"] == 181


def test_reconcile_does_not_flag_legit_same_number_multi_slug():
    # 同號兩個不同合法 slug（如 PC-010 設計態）→ 不是 mess，不該列入
    up = {
        "numbers": {10: {"task-tracking", "pm-skipped"}},
        "by_slug": {
            (10, "task-tracking"): "error-patterns/pc/PC-010-task-tracking.md",
            (10, "pm-skipped"): "error-patterns/pc/PC-010-pm-skipped.md",
        },
    }
    assert push.plan_upstream_mess_reconciliation(up) == []


def test_reconcile_empty_when_clean():
    up = {"numbers": {177: {"x"}, 178: {"y"}}, "by_slug": {}}
    assert push.plan_upstream_mess_reconciliation(up) == []


# ============================================================================
# 6 檔 mess 端到端辨識（PC-177×2/178×2/181/182）
# ============================================================================

def test_six_file_mess_recognition(tmp_path):
    """模擬上游當前 6 檔 mess，驗證對帳 + push 處置正確辨識。

    上游：PC-177{defensive,malformed} / PC-178{ticket-body,ui-test} / PC-181{defensive}
          / PC-182{ui-test}
    本地：PC-177-malformed（native bare）/ PC-178-ticket-body（native bare）
          / PC-181-defensive（lineage 177）/ PC-182-ui-test（lineage 178）
    """
    up = tmp_path / "upstream"
    ep = up / "error-patterns" / "process-compliance"
    _write(ep / "PC-177-defensive-rule.md", "# canonical defensive\n")
    _write(ep / "PC-177-malformed.md", "# wrongly-pushed native\n")
    _write(ep / "PC-178-ticket-body.md", "# wrongly-pushed native\n")
    _write(ep / "PC-178-ui-test.md", "# canonical ui-test\n")
    _write(ep / "PC-181-defensive-rule.md", _lineage(177, 181) + "\n# dup\n")
    _write(ep / "PC-182-ui-test.md", _lineage(178, 182) + "\n# dup\n")
    idx = push.build_upstream_pc_index(up)

    # 對帳：偵測 181/182 為同 slug 重複號（誤推鏡像）
    recon = push.plan_upstream_mess_reconciliation(idx)
    dup_pairs = {
        (i["slug"], i["canonical_num"], i["duplicate_num"]) for i in recon
    }
    assert ("defensive-rule", 177, 181) in dup_pairs
    assert ("ui-test", 178, 182) in dup_pairs

    # push 處置：本地 lineage 檔排除；本地 native 撞號賦 canonical
    reserved: set[int] = set()
    # 本地 PC-181-defensive（lineage）→ 排除
    p_181 = push.plan_push_pc_action(
        "error-patterns/process-compliance/PC-181-defensive-rule.md",
        _lineage(177, 181), idx, reserved,
    )
    assert p_181["action"] == "exclude_lineage_artifact"
    # 本地 PC-177-malformed（native，上游 177 被 defensive 佔且本地 slug 在上游
    # 177 集合中——malformed 確實也在 mess 上游）。本地 slug 在上游此號集合 →
    # 視為同 pattern 已在上游，no-op（避免重複賦號）。
    p_177m = push.plan_push_pc_action(
        "error-patterns/process-compliance/PC-177-malformed.md",
        "# native\n", idx, reserved,
    )
    # malformed 已在上游 177 集合 → no-op（已誤推，由對帳/clean 處理而非再賦號）
    assert p_177m["action"] == "none"


# ============================================================================
# dry-run 不寫檔（apply 的 dry_run=True 分支）
# ============================================================================

def test_apply_dry_run_does_not_modify_remote(tmp_path):
    remote = tmp_path / "remote"
    ep = remote / "error-patterns" / "process-compliance"
    _write(ep / "PC-181-defensive.md", _lineage(177, 181) + "\n# dup\n")
    _write(ep / "PC-200-native.md", "# native\n")
    upstream = {"numbers": {177: {"defensive"}}, "by_slug": {}}
    before = sorted(p.name for p in ep.rglob("PC-*.md"))
    result = push.apply_push_pc_collision(remote, upstream, dry_run=True)
    after = sorted(p.name for p in ep.rglob("PC-*.md"))
    assert before == after  # dry-run 不動檔
    # 仍正確分類：181 該排除
    assert any(
        e["repo_rel"].endswith("PC-181-defensive.md")
        for e in result["excluded"]
    )


def test_apply_live_excludes_lineage_and_renumbers(tmp_path):
    remote = tmp_path / "remote"
    ep = remote / "error-patterns" / "process-compliance"
    _write(ep / "PC-181-defensive.md", _lineage(177, 181) + "\n# dup\n")
    _write(ep / "PC-177-malformed.md", "# native bare\n")
    # 上游：177 被 defensive 佔（malformed 不在）→ malformed 須賦新號
    upstream = {"numbers": {177: {"defensive"}}, "by_slug": {}}
    result = push.apply_push_pc_collision(remote, upstream, dry_run=False)
    names = sorted(p.name for p in ep.rglob("PC-*.md"))
    # 181 artifact 已移除
    assert "PC-181-defensive.md" not in names
    # 177-malformed 重編為 178（next-available）
    assert "PC-177-malformed.md" not in names
    assert "PC-178-malformed.md" in names
    assert len(result["excluded"]) == 1
    assert len(result["renumbered"]) == 1


def test_apply_noop_when_no_collision(tmp_path):
    # 無撞號時不誤動（no-op acceptance）
    remote = tmp_path / "remote"
    ep = remote / "error-patterns" / "process-compliance"
    _write(ep / "PC-200-brand-new.md", "# new\n")
    upstream = {"numbers": {177: {"x"}}, "by_slug": {}}
    result = push.apply_push_pc_collision(remote, upstream, dry_run=False)
    assert result["excluded"] == []
    assert result["renumbered"] == []
    assert result["untouched"] == 1
    assert (ep / "PC-200-brand-new.md").exists()


# ============================================================================
# writeback：賦 canonical 後套回本地 working tree
# ============================================================================

def test_writeback_renames_local_and_injects_lineage(tmp_path):
    claude = tmp_path / ".claude"
    ep = claude / "error-patterns" / "process-compliance"
    _write(ep / "PC-177-malformed.md", "# native\n")
    plan = {
        "action": "assign_canonical",
        "old_num": 177, "slug": "malformed", "new_num": 178,
        "old_repo_rel": "error-patterns/process-compliance/PC-177-malformed.md",
        "new_repo_rel": "error-patterns/process-compliance/PC-178-malformed.md",
        "new_content": _lineage(177, 178) + "\n# native\n",
    }
    written = push.writeback_local_canonical_assignments(claude, [plan])
    assert written == 1
    assert not (ep / "PC-177-malformed.md").exists()
    new_file = ep / "PC-178-malformed.md"
    assert new_file.exists()
    assert push.parse_local_lineage(new_file.read_text(encoding="utf-8")) == (177, 178)
