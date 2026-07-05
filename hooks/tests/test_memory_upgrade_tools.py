"""memory promote/scan 升級工具測試（1.5.0-W5-011.3）。

程式碼自包含於 .claude/skills/continuous-learning/scripts/memory_upgrade.py；
測試暫借 hooks pytest env 執行（樣板同 test_error_pattern_allocator.py）。

驗證六函式：classify_memory 三態、find_dangling_pointers（前綴號 dangling /
flat 號不誤報）、scan_memory_dir、annotate_upgraded（格式對齊 + 冪等）、
prune_memory_index（graceful False）、promote_memory（整合）。
"""

import sys
from pathlib import Path
from unittest.mock import patch

_scripts_dir = (
    Path(__file__).resolve().parent.parent.parent
    / "skills"
    / "continuous-learning"
    / "scripts"
)
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

from memory_upgrade import (  # noqa: E402
    annotate_upgraded,
    classify_memory,
    find_dangling_pointers,
    promote_memory,
    prune_memory_index,
    scan_memory_dir,
)

_version_release_scripts_dir = (
    Path(__file__).resolve().parent.parent.parent
    / "skills"
    / "version-release"
    / "scripts"
)
if str(_version_release_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_version_release_scripts_dir))

import version_release  # noqa: E402

_REGISTRY = """\
projects:
  - code: V1
    dir: book_overview_v1
reserved_codes: []
"""


def _write_registry(claude_dir: Path) -> None:
    ep = claude_dir / "error-patterns"
    ep.mkdir(parents=True, exist_ok=True)
    (ep / "_project-registry.yaml").write_text(_REGISTRY, encoding="utf-8")


def _write_memory(memory_dir: Path, name: str, body: str) -> Path:
    memory_dir.mkdir(parents=True, exist_ok=True)
    path = memory_dir / name
    path.write_text(body, encoding="utf-8")
    return path


# --- classify_memory ---


def test_classify_unevaluated_no_upgrade_key(tmp_path):
    mem = _write_memory(
        tmp_path,
        "feedback_x.md",
        "---\ntype: feedback\nname: x\n---\n\n內容\n",
    )
    assert classify_memory(mem) == "unevaluated"


def test_classify_deferred(tmp_path):
    mem = _write_memory(
        tmp_path,
        "feedback_y.md",
        "---\ntype: feedback\nupgrade: deferred\n---\n\n內容\n",
    )
    assert classify_memory(mem) == "deferred"


def test_classify_upgraded_via_frontmatter(tmp_path):
    mem = _write_memory(
        tmp_path,
        "feedback_z.md",
        "---\ntype: feedback\nupgrade: done\n---\n\n內容\n",
    )
    assert classify_memory(mem) == "upgraded"


def test_classify_malformed_frontmatter_treated_unevaluated(tmp_path, capsys):
    """真實資料常見未引號冒號值（PC-165：測試綠燈遮蔽 runtime）不應崩潰。"""
    mem = _write_memory(
        tmp_path,
        "feedback_malformed.md",
        "---\ntype: feedback\n"
        "description: 值內含 backtick 或 originSessionId: 334448a4-xxx\n"
        "---\n\n內容\n",
    )
    assert classify_memory(mem) == "unevaluated"
    captured = capsys.readouterr()
    assert "feedback_malformed.md" in captured.err


def test_classify_upgraded_via_top_annotation(tmp_path):
    mem = _write_memory(
        tmp_path,
        "feedback_w.md",
        "---\ntype: feedback\n---\n\n"
        "> **Status**: Upgraded — 已升級至框架共用層\n"
        "> **Upgraded To**: `.claude/rules/core/x.md`\n"
        "> **Upgraded Date**: 2026-07-05\n\n內容\n",
    )
    assert classify_memory(mem) == "upgraded"


# --- find_dangling_pointers ---


def test_dangling_prefix_id_not_found(tmp_path):
    ep_dir = tmp_path / "error-patterns"
    mem = _write_memory(
        tmp_path, "feedback_a.md", "見 PC-V1-001 詳細案例\n"
    )
    assert find_dangling_pointers(mem, ep_dir) == ["PC-V1-001"]


def test_dangling_prefix_id_found_not_dangling(tmp_path):
    ep_dir = tmp_path / "error-patterns" / "process-compliance"
    ep_dir.mkdir(parents=True)
    (ep_dir / "PC-V1-001-foo.md").write_text("# stub\n", encoding="utf-8")
    mem = _write_memory(
        tmp_path, "feedback_b.md", "見 PC-V1-001 詳細案例\n"
    )
    assert find_dangling_pointers(mem, tmp_path / "error-patterns") == []


def test_flat_id_never_flagged_dangling(tmp_path):
    """flat base（PC-099）不在 find_dangling_pointers 掃描範圍內，不誤報。"""
    ep_dir = tmp_path / "error-patterns"
    mem = _write_memory(
        tmp_path, "feedback_c.md", "已升級為 PC-099（flat）\n"
    )
    assert find_dangling_pointers(mem, ep_dir) == []


def test_dangling_dedup_and_sorted(tmp_path):
    ep_dir = tmp_path / "error-patterns"
    mem = _write_memory(
        tmp_path,
        "feedback_d.md",
        "見 IMP-V1-002 與 PC-V1-001，再提一次 IMP-V1-002\n",
    )
    assert find_dangling_pointers(mem, ep_dir) == ["IMP-V1-002", "PC-V1-001"]


# --- scan_memory_dir ---


def test_scan_memory_dir_three_categories(tmp_path):
    memory_dir = tmp_path / "memory"
    ep_dir = tmp_path / "error-patterns"
    _write_memory(
        memory_dir,
        "feedback_unevaluated.md",
        "---\ntype: feedback\n---\n\n無 upgrade 鍵\n",
    )
    _write_memory(
        memory_dir,
        "feedback_deferred.md",
        "---\ntype: feedback\nupgrade: deferred\n---\n\n內容\n",
    )
    _write_memory(
        memory_dir,
        "feedback_dangling.md",
        "---\ntype: feedback\n---\n\n見 PC-V1-999 已不存在\n",
    )
    result = scan_memory_dir(memory_dir, ep_dir)
    assert result["unevaluated"] == [
        "feedback_dangling.md",
        "feedback_unevaluated.md",
    ]
    assert result["deferred"] == ["feedback_deferred.md"]
    assert result["dangling"] == [
        {"file": "feedback_dangling.md", "ids": ["PC-V1-999"]}
    ]


def test_scan_memory_dir_survives_malformed_frontmatter(tmp_path):
    """單一壞檔（未引號冒號值）不應中斷整批掃描（PC-165 runtime 缺口修復）。"""
    memory_dir = tmp_path / "memory"
    ep_dir = tmp_path / "error-patterns"
    _write_memory(
        memory_dir,
        "feedback_ok.md",
        "---\ntype: feedback\n---\n\n無 upgrade 鍵\n",
    )
    _write_memory(
        memory_dir,
        "feedback_malformed.md",
        "---\ntype: feedback\n"
        "description: 值內含 backtick 或 originSessionId: 334448a4-xxx\n"
        "---\n\n內容\n",
    )
    result = scan_memory_dir(memory_dir, ep_dir)
    assert result["unevaluated"] == ["feedback_malformed.md", "feedback_ok.md"]


def test_scan_memory_dir_ignores_non_feedback_files(tmp_path):
    memory_dir = tmp_path / "memory"
    ep_dir = tmp_path / "error-patterns"
    _write_memory(memory_dir, "MEMORY.md", "- 索引\n")
    result = scan_memory_dir(memory_dir, ep_dir)
    assert result == {"unevaluated": [], "deferred": [], "dangling": []}


# --- annotate_upgraded ---


def test_annotate_upgraded_inserts_three_lines(tmp_path):
    mem = _write_memory(
        tmp_path,
        "feedback_e.md",
        "---\ntype: feedback\nname: e\n---\n\n原內容\n",
    )
    annotate_upgraded(mem, ".claude/rules/core/x.md", "2026-07-05")
    text = mem.read_text(encoding="utf-8")
    assert "> **Status**: Upgraded — 已升級至框架共用層" in text
    assert "> **Upgraded To**: `.claude/rules/core/x.md`" in text
    assert "> **Upgraded Date**: 2026-07-05" in text
    assert "原內容" in text


def test_annotate_upgraded_idempotent(tmp_path):
    mem = _write_memory(
        tmp_path,
        "feedback_f.md",
        "---\ntype: feedback\n---\n\n原內容\n",
    )
    annotate_upgraded(mem, ".claude/rules/core/x.md", "2026-07-05")
    first = mem.read_text(encoding="utf-8")
    annotate_upgraded(mem, ".claude/rules/core/x.md", "2026-07-05")
    second = mem.read_text(encoding="utf-8")
    assert first == second
    assert second.count("> **Status**: Upgraded") == 1


# --- prune_memory_index ---


def test_prune_memory_index_removes_matching_line(tmp_path):
    idx = tmp_path / "MEMORY.md"
    idx.write_text(
        "- [A](feedback_a.md) — hook\n"
        "- [B](feedback_b.md) — hook\n",
        encoding="utf-8",
    )
    assert prune_memory_index(idx, "feedback_a.md") is True
    text = idx.read_text(encoding="utf-8")
    assert "feedback_a.md" not in text
    assert "feedback_b.md" in text


def test_prune_memory_index_graceful_when_missing(tmp_path):
    idx = tmp_path / "MEMORY.md"
    idx.write_text("- [B](feedback_b.md) — hook\n", encoding="utf-8")
    assert prune_memory_index(idx, "feedback_notfound.md") is False


# --- promote_memory (整合) ---


def test_promote_memory_integration(tmp_path):
    claude_dir = tmp_path / ".claude"
    _write_registry(claude_dir)
    memory_dir = tmp_path / "memory"
    mem = _write_memory(
        memory_dir,
        "feedback_g.md",
        "---\ntype: feedback\nname: g\n---\n\n內容摘要\n",
    )
    idx = memory_dir / "MEMORY.md"
    idx.write_text("- [G](feedback_g.md) — hook\n", encoding="utf-8")

    result = promote_memory(
        memory_file=mem,
        category="PC",
        claude_dir=claude_dir,
        project_code="V1",
        dest_title="測試升級標題",
        date="2026-07-05",
        memory_dir=memory_dir,
    )

    assert result["pattern_id"] == "PC-V1-001"
    dest_path = Path(result["dest_path"])
    assert dest_path.is_file()
    assert result["index_pruned"] is True

    annotated = mem.read_text(encoding="utf-8")
    assert "> **Status**: Upgraded" in annotated
    assert "feedback_g.md" not in idx.read_text(encoding="utf-8")


# --- check_memory_upgrade_status（1.5.0-W5-011.4） ---


def test_check_memory_upgrade_status_all_upgraded():
    """全 upgraded：unevaluated == 0 → passed True。"""
    with patch.object(
        version_release,
        "scan_memory_dir",
        return_value={"unevaluated": [], "deferred": [], "dangling": []},
    ), patch.object(
        version_release, "_count_memory_feedback", return_value=(3, 3)
    ):
        passed, messages = version_release.check_memory_upgrade_status("1.5.0")

    assert passed is True
    assert "遵循率: 100%" in messages[0]


def test_check_memory_upgrade_status_has_unevaluated():
    """有 unevaluated：passed False，並附決策 trigger 提示。"""
    with patch.object(
        version_release,
        "scan_memory_dir",
        return_value={
            "unevaluated": ["feedback_x.md"],
            "deferred": [],
            "dangling": [],
        },
    ), patch.object(
        version_release, "_count_memory_feedback", return_value=(2, 3)
    ):
        passed, messages = version_release.check_memory_upgrade_status("1.5.0")

    assert passed is False
    assert any("決策 trigger" in m for m in messages)
    assert any("feedback_x.md" in m for m in messages)


def test_check_memory_upgrade_status_has_dangling():
    """有 dangling pointer：附於未通過訊息中。"""
    with patch.object(
        version_release,
        "scan_memory_dir",
        return_value={
            "unevaluated": ["feedback_y.md"],
            "deferred": [],
            "dangling": [{"file": "feedback_y.md", "ids": ["PC-V1-999"]}],
        },
    ), patch.object(
        version_release, "_count_memory_feedback", return_value=(1, 2)
    ):
        passed, messages = version_release.check_memory_upgrade_status("1.5.0")

    assert passed is False
    assert any("dangling pointer" in m and "PC-V1-999" in m for m in messages)
