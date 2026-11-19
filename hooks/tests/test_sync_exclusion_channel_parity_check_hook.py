"""sync 排除兩通道同構檢查 hook 測試（3.4.0-W1-307.3）。

涵蓋：
1. AST 解析 cli.py 的兩個集合與 `.endswith` 後綴
2. 逐類別比對：一致時無差異；任一側缺名稱即報出（正向對照）
3. runtime state 與已知分歧不列為差異
4. 真實 cli.py 對真實 manifest 現況一致，且刪掉一個成員後檢查會翻紅
5. 解析失敗回報具體原因
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).parent.parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

_spec = importlib.util.spec_from_file_location(
    "sync_exclusion_channel_parity_check_hook",
    _HOOKS_DIR / "sync-exclusion-channel-parity-check-hook.py",
)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

_REAL_CLI = _HOOKS_DIR.parent / "skills" / "skill-sync" / "skill_sync" / "cli.py"

CLI_SOURCE = '''
TOOL_ARTIFACT_DIRS = frozenset({".venv", ".ruff_cache", "build", "hook-logs"})
POLICY_EXCLUDE_DIRS = frozenset({"project-integration"})
EXCLUDE_DIRS = TOOL_ARTIFACT_DIRS | POLICY_EXCLUDE_DIRS

def _should_exclude_file(rel_path):
    for part in rel_path.split("/"):
        if part in EXCLUDE_DIRS or part.endswith(".egg-info"):
            return True
    return False
'''


def _compare(sets, *, tool=frozenset({".venv", ".ruff_cache"}), suffixes=frozenset({".egg-info"}),
             policy=frozenset({"project-integration", ".version-release.yaml"}),
             runtime=frozenset({"hook-logs", ".venv"})):
    return hook.compare(sets, tool, suffixes, policy, runtime)


def test_parse_extracts_sets_and_suffixes():
    sets = hook.parse_skill_sync_sets(CLI_SOURCE)
    assert sets.tool_dirs == {".venv", ".ruff_cache", "build", "hook-logs"}
    assert sets.policy_dirs == {"project-integration"}
    assert sets.suffixes == {".egg-info"}


def test_consistent_sets_report_no_divergence_and_list_known_baseline():
    report = _compare(hook.parse_skill_sync_sets(CLI_SOURCE))
    assert report.divergences == []
    assert {(c, n) for c, n, _ in report.known} == {
        (hook.CATEGORY_TOOL_DIRS, "build"),
        (hook.CATEGORY_POLICY, ".version-release.yaml"),
    }


def test_positive_control_framework_only_name_is_reported():
    """正向對照：框架多一個工具產物、skill-sync 沒有 → 必須報出。"""
    report = _compare(hook.parse_skill_sync_sets(CLI_SOURCE),
                      tool=frozenset({".venv", ".ruff_cache", ".mypy_cache"}))
    assert report.divergences == [
        hook.Divergence(hook.CATEGORY_TOOL_DIRS, ".mypy_cache", "框架")
    ]


def test_positive_control_skill_sync_only_name_is_reported():
    source = CLI_SOURCE.replace('"build",', '"build", "htmlcov",')
    report = _compare(hook.parse_skill_sync_sets(source))
    assert hook.Divergence(hook.CATEGORY_TOOL_DIRS, "htmlcov", "skill-sync") in report.divergences


def test_suffix_and_policy_divergences_are_reported():
    source = CLI_SOURCE.replace('.endswith(".egg-info")', '.endswith(".dist-info")')
    report = _compare(hook.parse_skill_sync_sets(source),
                      policy=frozenset({"project-integration", ".version-release.yaml", "local-notes"}))
    assert set(report.divergences) == {
        hook.Divergence(hook.CATEGORY_TOOL_SUFFIXES, ".dist-info", "skill-sync"),
        hook.Divergence(hook.CATEGORY_TOOL_SUFFIXES, ".egg-info", "框架"),
        hook.Divergence(hook.CATEGORY_POLICY, "local-notes", "框架"),
    }


def test_runtime_state_name_only_in_skill_sync_is_not_reported():
    report = _compare(hook.parse_skill_sync_sets(CLI_SOURCE), runtime=frozenset())
    # 去掉 runtime state 豁免後 hook-logs 才會被報出，證明豁免確實在作用
    assert hook.Divergence(hook.CATEGORY_TOOL_DIRS, "hook-logs", "skill-sync") in report.divergences
    assert _compare(hook.parse_skill_sync_sets(CLI_SOURCE)).divergences == []


@pytest.mark.parametrize("source, needle", [
    ("def broken(:\n", "語法錯誤"),
    ('POLICY_EXCLUDE_DIRS = frozenset({"p"})\ndef _should_exclude_file(p):\n    return False\n',
     "TOOL_ARTIFACT_DIRS"),
    ('TOOL_ARTIFACT_DIRS = frozenset({"a"})\nPOLICY_EXCLUDE_DIRS = frozenset({"p"})\n',
     "_should_exclude_file"),
])
def test_parse_errors_name_the_cause(source, needle):
    with pytest.raises(hook.ParseError, match=needle):
        hook.parse_skill_sync_sets(source)


def _real_compare(source):
    return hook.compare(
        hook.parse_skill_sync_sets(source),
        hook.ALL_TOOL_ARTIFACT_PATTERNS,
        hook.TOOL_ARTIFACT_DIR_SUFFIXES,
        hook.PER_PROJECT_PATTERNS,
        hook.LOCAL_ONLY_PATTERNS,
    )


def test_real_channels_are_consistent_today():
    report = _real_compare(_REAL_CLI.read_text(encoding="utf-8"))
    assert report.divergences == []


def test_real_channels_drift_is_detected():
    """真實 cli.py 刪掉 .mypy_cache 後，檢查必須翻紅。"""
    source = _REAL_CLI.read_text(encoding="utf-8")
    drifted = source.replace('    ".mypy_cache",\n', "", 1)
    assert drifted != source
    assert hook.Divergence(hook.CATEGORY_TOOL_DIRS, ".mypy_cache", "框架") in _real_compare(drifted).divergences


def test_sync_base_is_exempted_only_by_its_known_divergence_entry(monkeypatch):
    """正向對照：拿掉 sync-base.json 的已知分歧條目，真實通道就報出這個差異。"""
    source = _REAL_CLI.read_text(encoding="utf-8")
    assert _real_compare(source).divergences == []
    trimmed = {
        key: reason
        for key, reason in hook.KNOWN_DIVERGENCES.items()
        if key != (hook.CATEGORY_POLICY, "sync-base.json")
    }
    assert len(trimmed) == len(hook.KNOWN_DIVERGENCES) - 1
    monkeypatch.setattr(hook, "KNOWN_DIVERGENCES", trimmed)
    assert _real_compare(source).divergences == [
        hook.Divergence(hook.CATEGORY_POLICY, "sync-base.json", "框架")
    ]


def test_unlisted_policy_divergence_still_reported_with_current_known_list():
    """正向對照：已知分歧清單現況下，不在清單內的類型 E 名稱仍被報出。"""
    report = hook.compare(
        hook.parse_skill_sync_sets(_REAL_CLI.read_text(encoding="utf-8")),
        hook.ALL_TOOL_ARTIFACT_PATTERNS,
        hook.TOOL_ARTIFACT_DIR_SUFFIXES,
        hook.PER_PROJECT_PATTERNS | {"unlisted-declaration.json"},
        hook.LOCAL_ONLY_PATTERNS,
    )
    assert report.divergences == [
        hook.Divergence(hook.CATEGORY_POLICY, "unlisted-declaration.json", "框架")
    ]


def test_format_warning_lists_each_divergence():
    report = hook.ParityReport([hook.Divergence(hook.CATEGORY_TOOL_DIRS, ".mypy_cache", "框架")], [])
    text = hook.format_warning(report)
    assert "`.mypy_cache` 只在框架側排除" in text
    assert "KNOWN_DIVERGENCES" in text
