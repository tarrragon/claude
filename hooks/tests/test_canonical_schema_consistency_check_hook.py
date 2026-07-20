"""
Canonical Schema 清單一致性檢查 Hook 測試

涵蓋範圍：
1. CANONICAL_BODY_SECTIONS 擷取（constants.py）
2. _SCHEMA_SECTION_NAMES 擷取（驗證端 .py 檔，含有無型別註解兩種寫法）
3. ticket-body-schema.md 第一張表格擷取（含跳過「狀態定義」第二張表格）
4. agent-definition-standard-details.md 行內 backtick 清單擷取
5. 差集比對（缺漏 / 多餘 / 一致）
6. 掃描彙整（scan_schema_drifts）與警告訊息格式化
"""

import importlib.util
import sys
from pathlib import Path


_HOOKS_DIR = Path(__file__).parent.parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

_spec = importlib.util.spec_from_file_location(
    "canonical_schema_consistency_check_hook",
    _HOOKS_DIR / "canonical-schema-consistency-check-hook.py",
)
_hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hook)


CANONICAL_CONSTANTS_PY = '''
CANONICAL_BODY_SECTIONS: tuple = (
    "Task Summary",
    "Problem Analysis",
    "Solution",
    "Test Results",
    "Completion Info",
)
'''

VALIDATOR_WITH_TYPE_ANNOTATION = '''
_SCHEMA_SECTION_NAMES: List[str] = [
    "Task Summary",
    "Problem Analysis",
    "Solution",
]
'''

VALIDATOR_WITHOUT_ANNOTATION = '''
_SCHEMA_SECTION_NAMES = [
    "Task Summary",
    "Problem Analysis",
]
'''

TICKET_BODY_SCHEMA_MD_ALIGNED = """## Schema 對照表

| Section | ANA | IMP | DOC |
|---------|-----|-----|-----|
| Task Summary | 必填 | 必填 | 必填 |
| 重現實驗結果（三子節） | 必填 | 免填 | 免填 |
| Completion Info | 必填 | 必填 | 必填 |

**狀態定義**：

| 狀態 | 語義 | 填寫要求 |
|------|------|---------|
| 必填 | 章節存在 | claim/complete 時應驗證 |
| 選填 | 章節存在 | 有助後人查閱 |

## 各 type 重點說明
"""

AGENT_DEFINITION_MD = (
    "**Schema 章節清單**（來源 `.claude/pm-rules/ticket-body-schema.md`）："
    "`Task Summary` / `Problem Analysis` / `Completion Info`"
)


# ---------------------------------------------------------------------------
# extract_canonical_sections
# ---------------------------------------------------------------------------


def test_extract_canonical_sections_preserves_order():
    result = _hook.extract_canonical_sections(CANONICAL_CONSTANTS_PY)
    assert result == [
        "Task Summary",
        "Problem Analysis",
        "Solution",
        "Test Results",
        "Completion Info",
    ]


def test_extract_canonical_sections_missing_returns_none():
    assert _hook.extract_canonical_sections("no constant here") is None


# ---------------------------------------------------------------------------
# extract_schema_section_names
# ---------------------------------------------------------------------------


def test_extract_schema_section_names_with_type_annotation():
    result = _hook.extract_schema_section_names(VALIDATOR_WITH_TYPE_ANNOTATION)
    assert result == ["Task Summary", "Problem Analysis", "Solution"]


def test_extract_schema_section_names_without_annotation():
    result = _hook.extract_schema_section_names(VALIDATOR_WITHOUT_ANNOTATION)
    assert result == ["Task Summary", "Problem Analysis"]


def test_extract_schema_section_names_missing_returns_none():
    assert _hook.extract_schema_section_names("no list here") is None


# ---------------------------------------------------------------------------
# extract_ticket_body_schema_sections
# ---------------------------------------------------------------------------


def test_extract_ticket_body_schema_sections_first_table_only():
    result = _hook.extract_ticket_body_schema_sections(TICKET_BODY_SCHEMA_MD_ALIGNED)
    # 「狀態定義」表格的「必填/選填」不應混入（第二張表格）
    assert result == ["Task Summary", "重現實驗結果", "Completion Info"]


def test_extract_ticket_body_schema_sections_missing_heading_returns_none():
    assert _hook.extract_ticket_body_schema_sections("無此標題") is None


# ---------------------------------------------------------------------------
# extract_agent_definition_sections
# ---------------------------------------------------------------------------


def test_extract_agent_definition_sections_parses_backtick_list():
    result = _hook.extract_agent_definition_sections(AGENT_DEFINITION_MD)
    assert result == ["Task Summary", "Problem Analysis", "Completion Info"]


def test_extract_agent_definition_sections_missing_marker_returns_none():
    assert _hook.extract_agent_definition_sections("無此標記") is None


# ---------------------------------------------------------------------------
# _diff
# ---------------------------------------------------------------------------


def test_diff_detects_missing():
    canonical = {"A", "B", "C"}
    result = _hook._diff("target", canonical, ["A", "B"])
    assert result is not None
    assert result.missing == ["C"]
    assert result.extra == []


def test_diff_detects_extra():
    canonical = {"A", "B"}
    result = _hook._diff("target", canonical, ["A", "B", "Z"])
    assert result is not None
    assert result.missing == []
    assert result.extra == ["Z"]


def test_diff_consistent_returns_none():
    canonical = {"A", "B"}
    assert _hook._diff("target", canonical, ["B", "A"]) is None


# ---------------------------------------------------------------------------
# scan_schema_drifts（整合，使用 tmp_path 構造專案結構）
# ---------------------------------------------------------------------------


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_project(tmp_path: Path, *, spawn_in_docs: bool) -> Path:
    """建構最小可用的專案結構，供 scan_schema_drifts 讀取。"""
    claude_dir = tmp_path / ".claude"

    canonical = '''
CANONICAL_BODY_SECTIONS: tuple = (
    "Task Summary",
    "Solution",
    "Spawn Requests",
)
'''
    _write(claude_dir / _hook.CONSTANTS_PY, canonical)

    validator_missing_spawn = '''
_SCHEMA_SECTION_NAMES = [
    "Task Summary",
    "Solution",
]
'''
    for _, rel_path in _hook.VALIDATOR_TARGETS:
        _write(claude_dir / rel_path, validator_missing_spawn)

    spawn_item = ' / `Spawn Requests`' if spawn_in_docs else ''
    agent_md = (
        "**Schema 章節清單**（來源 x）：`Task Summary` / `Solution`" + spawn_item
    )
    _write(claude_dir / _hook.AGENT_DEFINITION_STANDARD_MD, agent_md)

    spawn_row = "| Spawn Requests | 選填 | 選填 | 選填 |\n" if spawn_in_docs else ""
    schema_md = f"""## Schema 對照表

| Section | ANA | IMP | DOC |
|---------|-----|-----|-----|
| Task Summary | 必填 | 必填 | 必填 |
| Solution | 必填 | 選填 | 免填 |
{spawn_row}
## 各 type 重點說明
"""
    _write(claude_dir / _hook.TICKET_BODY_SCHEMA_MD, schema_md)

    return tmp_path


def test_scan_schema_drifts_docs_aligned_only_validators_flagged(tmp_path):
    project_root = _build_project(tmp_path, spawn_in_docs=True)

    drifts = _hook.scan_schema_drifts(project_root)

    labels = {d.label for d in drifts}
    assert labels == {label for label, _ in _hook.VALIDATOR_TARGETS}
    for drift in drifts:
        assert drift.missing == ["Spawn Requests"]


def test_scan_schema_drifts_docs_misaligned_also_flagged(tmp_path):
    project_root = _build_project(tmp_path, spawn_in_docs=False)

    drifts = _hook.scan_schema_drifts(project_root)

    labels = {d.label for d in drifts}
    assert _hook.TICKET_BODY_SCHEMA_MD in labels
    assert _hook.AGENT_DEFINITION_STANDARD_MD in labels


def test_scan_schema_drifts_missing_constants_file_returns_empty(tmp_path):
    # 沒有 constants.py 時應優雅返回空清單（不拋例外）
    assert _hook.scan_schema_drifts(tmp_path) == []


# ---------------------------------------------------------------------------
# format_drift_warning
# ---------------------------------------------------------------------------


def test_format_drift_warning_includes_label_and_diff():
    drift = _hook.DriftResult(label="custom_h2_checker.py", missing=["Spawn Requests"], extra=[])
    warning = _hook.format_drift_warning([drift])

    assert "custom_h2_checker.py" in warning
    assert "Spawn Requests" in warning
    assert "PC-BAL-001" in warning
