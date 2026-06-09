"""Tests for detect_pc_collision.py（1.0.0-W1-022）。

涵蓋三偵測軸各正反案例：
  軸 1 同號異義（same number / different slug）
  軸 2 同 slug 異號（same slug / different number）
  軸 3 異號同義（different number / same normalized content）

仿 test_sync_claude_pull_pc_collision.py 的 importlib + tmp_path fixture 風格。
執行：uv run --project .claude/hooks pytest .claude/scripts/tests/test_detect_pc_collision.py
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "detect_pc_collision.py"
_spec = importlib.util.spec_from_file_location("detect_pc_collision", _SCRIPT)
assert _spec and _spec.loader
det = importlib.util.module_from_spec(_spec)
sys.modules["detect_pc_collision"] = det
_spec.loader.exec_module(det)  # type: ignore[union-attr]


def _write(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _ep(tmp_path: Path) -> Path:
    return tmp_path / ".claude" / "error-patterns" / "process-compliance"


# ============================================================================
# parse_filename
# ============================================================================

def test_parse_filename_flat():
    assert det.parse_filename("PC-165-false-positive-fix-chain.md") == (
        "PC", None, "165", "false-positive-fix-chain"
    )


def test_parse_filename_prefixed():
    assert det.parse_filename("PC-V1-001-foo-bar.md") == (
        "PC", "V1", "001", "foo-bar"
    )


def test_parse_filename_non_pattern_returns_none():
    assert det.parse_filename("README.md") is None
    assert det.parse_filename("quality-baseline.md") is None


# ============================================================================
# 軸 1：同號異義
# ============================================================================

def test_axis1_same_number_different_slug_detected(tmp_path):
    ep = _ep(tmp_path)
    _write(ep / "PC-010-task-tracking-in-memory.md", "# A: 任務追蹤\n內容 A\n")
    _write(ep / "PC-010-pm-skipped-checkpoint.md", "# B: 跳過檢查點\n內容 B\n")
    result = det.scan(ep.parent)
    assert ("PC-010", ["pm-skipped-checkpoint", "task-tracking-in-memory"]) in result[
        "same_number"
    ]
    assert det.has_collision(result) is True


def test_axis1_distinct_numbers_no_collision(tmp_path):
    ep = _ep(tmp_path)
    _write(ep / "PC-010-foo.md", "# foo\n內容\n")
    _write(ep / "PC-011-bar.md", "# bar\n其他內容\n")
    result = det.scan(ep.parent)
    assert result["same_number"] == []


# ============================================================================
# 軸 2：同 slug 異號
# ============================================================================

def test_axis2_same_slug_different_number_detected(tmp_path):
    ep = _ep(tmp_path)
    _write(ep / "ARCH-010-module-assembly-omission.md", "# ARCH-010\n內容 A\n")
    _write(ep / "ARCH-021-module-assembly-omission.md", "# ARCH-021\n內容 B\n")
    result = det.scan(ep.parent)
    assert (
        ("ARCH", "module-assembly-omission"),
        ["ARCH-010", "ARCH-021"],
    ) in result["same_slug"]
    assert det.has_collision(result) is True


def test_axis2_distinct_slugs_no_collision(tmp_path):
    ep = _ep(tmp_path)
    _write(ep / "ARCH-010-foo.md", "# foo\n內容\n")
    _write(ep / "ARCH-021-bar.md", "# bar\n其他\n")
    result = det.scan(ep.parent)
    assert result["same_slug"] == []


# ============================================================================
# 軸 3：異號同義（正規化首行後內容相同）
# ============================================================================

def test_axis3_different_number_same_content_detected(tmp_path):
    ep = _ep(tmp_path)
    # 首行含不同編號，正文相同 → 正規化首行後雜湊相同
    _write(
        ep / "PC-177-defensive-rule.md",
        "# PC-177: defensive rule\n\n## 根因\n相同的正文段落內容。\n",
    )
    _write(
        ep / "PC-200-defensive-rule.md",
        "# PC-200: defensive rule\n\n## 根因\n相同的正文段落內容。\n",
    )
    result = det.scan(ep.parent)
    assert len(result["same_content"]) == 1
    _, nums = result["same_content"][0]
    assert nums == ["PC-177", "PC-200"]
    assert det.has_collision(result) is True


def test_axis3_different_content_no_collision(tmp_path):
    ep = _ep(tmp_path)
    _write(ep / "PC-177-foo.md", "# PC-177\n\n完全不同的正文一。\n")
    _write(ep / "PC-200-bar.md", "# PC-200\n\n完全不同的正文二。\n")
    result = det.scan(ep.parent)
    assert result["same_content"] == []


def test_axis3_normalization_strips_only_number_not_real_diff(tmp_path):
    """正規化僅剝編號字面；正文不同則不應誤判為同義。"""
    ep = _ep(tmp_path)
    _write(ep / "PC-177-a.md", "# PC-177\n正文 X\n")
    _write(ep / "PC-200-b.md", "# PC-200\n正文 Y\n")
    result = det.scan(ep.parent)
    assert result["same_content"] == []


# ============================================================================
# has_collision / main 整合
# ============================================================================

def test_no_collision_overall(tmp_path):
    ep = _ep(tmp_path)
    _write(ep / "PC-010-foo.md", "# foo\n獨特內容一\n")
    _write(ep / "PC-011-bar.md", "# bar\n獨特內容二\n")
    result = det.scan(ep.parent)
    assert det.has_collision(result) is False


def test_main_exit_0_when_clean(tmp_path):
    ep = _ep(tmp_path)
    _write(ep / "PC-010-foo.md", "# foo\n獨特一\n")
    assert det.main([str(ep.parent)]) == 0


def test_main_exit_1_when_collision(tmp_path):
    ep = _ep(tmp_path)
    _write(ep / "PC-010-foo.md", "# A\n內容 A\n")
    _write(ep / "PC-010-bar.md", "# B\n內容 B\n")
    assert det.main([str(ep.parent)]) == 1


def test_main_exit_2_when_dir_missing(tmp_path):
    missing = tmp_path / "nonexistent"
    assert det.main([str(missing)]) == 2
