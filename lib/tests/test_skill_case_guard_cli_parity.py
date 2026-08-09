"""對照測試：`.claude/lib/skill_case_guard.py` 與
`.claude/skills/skill-sync/skill_sync/cli.py` 兩份 skill.md 大小寫判準實作
須對同一 fixture 給出相同判定（0.2.1-W3-373）。

兩份實作刻意不共用程式碼（skill-sync 打包為獨立 wheel，不含 .claude/ 樹），
判準邏輯變更時須人工同步；本測試把「同步義務」轉為機械檢查，改一邊忘另一邊
即轉紅。

比較介面：cli 版以 `print(..., file=sys.stderr)` 輸出、lib 版回傳 list。
本測試以 `capsys` 擷取 cli 版 stderr，僅比對「被標記的目錄名集合」而非逐字
文案。此取捨在 ticket Solution 說明：目錄名集合較穩健（文案調整不誤報），
但無法偵測純文案分岔——文案一致性另由本檔的
`test_warning_text_matches_between_implementations` 覆蓋。
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest

from lib.skill_case_guard import warn_skill_md_case_mismatch

CLI_PATH = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "skill-sync"
    / "skill_sync"
    / "cli.py"
)


def _load_cli_module() -> ModuleType:
    """以檔案路徑載入 cli.py，不經 package import（避開 skill-sync wheel 邊界）。"""
    spec = importlib.util.spec_from_file_location("skill_sync_cli_under_test", CLI_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_cli = _load_cli_module()


def _lib_flagged_dirs(base_dir: Path) -> set[str]:
    """從 lib 版告警字串抽出被標記的目錄名（字串開頭 "{name}: "）。"""
    return {w.split(":", 1)[0] for w in warn_skill_md_case_mismatch(base_dir)}


def _cli_flagged_dirs(base_dir: Path, capsys: pytest.CaptureFixture[str]) -> set[str]:
    """呼叫 cli 版並從擷取的 stderr 抽出被標記的目錄名。"""
    _cli._warn_skill_md_case_mismatch(base_dir)
    captured = capsys.readouterr()
    dirs: set[str] = set()
    for line in captured.err.splitlines():
        m = re.match(r"\s*\[WARN\]\s*([^:]+):", line)
        if m:
            dirs.add(m.group(1))
    return dirs


CASES: list[tuple[str, dict[str, list[str]]]] = [
    ("純小寫 skill.md", {"foo": ["skill.md"]}),
    ("混合大寫 Skill.md", {"foo": ["Skill.md"]}),
    ("全大寫變體 SKILL.MD", {"foo": ["SKILL.MD"]}),
    ("正確 SKILL.md 不告警", {"foo": ["SKILL.md"]}),
    ("同時存在大小寫兩檔", {"foo": ["SKILL.md", "skill.md"]}),
    ("目錄內無任何 skill 檔", {"foo": ["README.md"]}),
    ("多個 skill 目錄混合", {"alpha": ["skill.md"], "beta": ["SKILL.md"], "gamma": ["Skill.MD"]}),
]


@pytest.mark.parametrize("label,layout", CASES, ids=[c[0] for c in CASES])
def test_two_implementations_agree(
    label: str,
    layout: dict[str, list[str]],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    base_dir = tmp_path / "skills"
    for dirname, filenames in layout.items():
        d = base_dir / dirname
        d.mkdir(parents=True)
        for fname in filenames:
            (d / fname).write_text("# body\n", encoding="utf-8")

    lib_result = _lib_flagged_dirs(base_dir)
    cli_result = _cli_flagged_dirs(base_dir, capsys)

    assert lib_result == cli_result, (
        f"[{label}] 判定分岔：lib={lib_result} cli={cli_result}"
    )


def test_missing_base_dir_agrees(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    base_dir = tmp_path / "no-such-dir"

    lib_result = _lib_flagged_dirs(base_dir)
    cli_result = _cli_flagged_dirs(base_dir, capsys)

    assert lib_result == cli_result == set()


def test_warning_text_matches_between_implementations(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """告警文案的「不會進入 manifest 掃描」核心敘述須兩份一致。

    0.2.1-W3-373 修正前，兩份都寫「case-sensitive glob 永遠掃不到」，該敘述
    已被實測推翻（glob 行為依 Python 版本而異）。本測試鎖定修正後的準確敘述，
    只改一份會轉紅。
    """
    base_dir = tmp_path / "skills"
    (base_dir / "foo").mkdir(parents=True)
    (base_dir / "foo" / "skill.md").write_text("# body\n", encoding="utf-8")

    lib_warnings = warn_skill_md_case_mismatch(base_dir)
    _cli._warn_skill_md_case_mismatch(base_dir)
    cli_stderr = capsys.readouterr().err

    assert len(lib_warnings) == 1
    expected_fragment = "case-sensitive glob 在 Python 3.13 前恆漏，3.13 起依檔案系統大小寫敏感性而定"
    assert expected_fragment in lib_warnings[0]
    assert expected_fragment in cli_stderr
