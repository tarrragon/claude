"""error-pattern 來源前綴 ID 分配器測試（1.0.0-W1-019.3）。

allocator 程式碼自包含於 .claude/skills/error-pattern/lib/allocator.py；
測試暫借 hooks pytest env 執行（skill 完整 package 化屬 W1-001 上架範圍）。

驗證：
- identify_project_code：git toplevel basename 對應 registry dir → code
- allocate_pattern_id：掃 <CAT>-<PROJ>-*.md 取 max+1，flat base 不參與遞增
"""

import sys
from pathlib import Path

import pytest

_skill_lib = (
    Path(__file__).resolve().parent.parent.parent
    / "skills"
    / "error-pattern"
    / "lib"
)
if str(_skill_lib) not in sys.path:
    sys.path.insert(0, str(_skill_lib))

from allocator import (  # noqa: E402
    allocate_pattern_id,
    identify_project_code,
)

_REGISTRY = """\
projects:
  - code: V1
    dir: book_overview_v1
  - code: APP
    dir: book_overview_app
reserved_codes: []
"""


def _write_registry(claude_dir: Path) -> Path:
    ep = claude_dir / "error-patterns"
    ep.mkdir(parents=True, exist_ok=True)
    reg = ep / "_project-registry.yaml"
    reg.write_text(_REGISTRY, encoding="utf-8")
    return reg


def _touch_pc(claude_dir: Path, category_dir: str, filename: str) -> None:
    d = claude_dir / "error-patterns" / category_dir
    d.mkdir(parents=True, exist_ok=True)
    (d / filename).write_text("# stub\n", encoding="utf-8")


# --- identify_project_code ---


def test_identify_known_project(tmp_path):
    claude_dir = tmp_path / ".claude"
    reg = _write_registry(claude_dir)
    repo = tmp_path / "book_overview_v1"
    assert identify_project_code(reg, repo) == "V1"


def test_identify_other_project(tmp_path):
    claude_dir = tmp_path / ".claude"
    reg = _write_registry(claude_dir)
    repo = tmp_path / "book_overview_app"
    assert identify_project_code(reg, repo) == "APP"


def test_identify_unknown_project_raises(tmp_path):
    claude_dir = tmp_path / ".claude"
    reg = _write_registry(claude_dir)
    repo = tmp_path / "some_unregistered_repo"
    with pytest.raises(Exception):
        identify_project_code(reg, repo)


# --- allocate_pattern_id ---


def test_first_allocation_starts_001(tmp_path):
    """無既有前綴 PC → 首次分配 001。"""
    claude_dir = tmp_path / ".claude"
    _write_registry(claude_dir)
    assert allocate_pattern_id("PC", claude_dir, "V1") == "PC-V1-001"


def test_increments_from_max(tmp_path):
    """既有 PC-V1-001 / PC-V1-003 → 下一號 004（取 max+1，非 count+1）。"""
    claude_dir = tmp_path / ".claude"
    _write_registry(claude_dir)
    _touch_pc(claude_dir, "process-compliance", "PC-V1-001-foo.md")
    _touch_pc(claude_dir, "process-compliance", "PC-V1-003-bar.md")
    assert allocate_pattern_id("PC", claude_dir, "V1") == "PC-V1-004"


def test_flat_base_not_counted(tmp_path):
    """flat 凍結 base（PC-099）不參與前綴遞增。"""
    claude_dir = tmp_path / ".claude"
    _write_registry(claude_dir)
    _touch_pc(claude_dir, "process-compliance", "PC-099-legacy.md")
    _touch_pc(claude_dir, "process-compliance", "PC-180-legacy.md")
    assert allocate_pattern_id("PC", claude_dir, "V1") == "PC-V1-001"


def test_other_project_prefix_isolated(tmp_path):
    """不同專案前綴命名空間隔離：APP 的號不影響 V1 遞增。"""
    claude_dir = tmp_path / ".claude"
    _write_registry(claude_dir)
    _touch_pc(claude_dir, "process-compliance", "PC-APP-005-x.md")
    assert allocate_pattern_id("PC", claude_dir, "V1") == "PC-V1-001"


def test_category_prefix_mapping(tmp_path):
    """category 前綴對應正確目錄（IMP → implementation）。"""
    claude_dir = tmp_path / ".claude"
    _write_registry(claude_dir)
    _touch_pc(claude_dir, "implementation", "IMP-V1-002-x.md")
    assert allocate_pattern_id("IMP", claude_dir, "V1") == "IMP-V1-003"


def test_unknown_category_raises(tmp_path):
    claude_dir = tmp_path / ".claude"
    _write_registry(claude_dir)
    with pytest.raises(Exception):
        allocate_pattern_id("BOGUS", claude_dir, "V1")
