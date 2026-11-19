"""onboard 的 .gitignore 必要規則與 SessionStart 檢查同源.

受檢專案帶有 .claude/lib/sync_exclude_manifest.py 時，onboard 以其
required_gitignore_entries() 為必要規則，涵蓋判定以 git check-ignore 探測。
缺 local-only 名稱（如 settings.local.json）的 .gitignore 必須被報缺。
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from project_init.lib.onboard_checker import check_gitignore_completeness

REAL_MANIFEST = Path(__file__).resolve().parents[3] / "lib" / "sync_exclude_manifest.py"


def _load_real_manifest():
    import importlib.util

    spec = importlib.util.spec_from_file_location("_real_manifest", REAL_MANIFEST)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def project(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    lib_dir = tmp_path / ".claude" / "lib"
    lib_dir.mkdir(parents=True)
    shutil.copy(REAL_MANIFEST, lib_dir / "sync_exclude_manifest.py")
    return tmp_path


@pytest.fixture
def required() -> list[str]:
    return sorted(_load_real_manifest().required_gitignore_entries())


def _write_gitignore(project: Path, lines: list[str]) -> None:
    (project / ".gitignore").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_complete_manifest_entries_pass(project: Path, required: list[str]) -> None:
    _write_gitignore(project, required)

    result = check_gitignore_completeness(project)

    assert result.missing_rules == []
    assert result.all_required_complete


def test_missing_local_only_entry_is_reported(project: Path, required: list[str]) -> None:
    """正向對照：少了 settings.local.json 的條目必須被報缺（舊的內建清單不含此項）."""
    target = ".claude/**/settings.local.json"
    assert target in required
    _write_gitignore(project, [e for e in required if e != target])

    result = check_gitignore_completeness(project)

    assert result.missing_rules == [target]
    assert not result.all_required_complete


def test_root_only_entry_does_not_cover_nested_name(project: Path, required: list[str]) -> None:
    """`.claude/settings.local.json` 只忽略根層，巢狀位置未涵蓋，仍報缺."""
    target = ".claude/**/settings.local.json"
    lines = [e for e in required if e != target] + [".claude/settings.local.json"]
    _write_gitignore(project, lines)

    result = check_gitignore_completeness(project)

    assert target in result.missing_rules


def test_missing_gitignore_lists_manifest_entries(project: Path, required: list[str]) -> None:
    result = check_gitignore_completeness(project)

    assert not result.exists
    assert result.missing_rules == required


def test_without_manifest_falls_back_with_stderr(tmp_path: Path, capsys) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    _write_gitignore(tmp_path, ["coverage/"])

    result = check_gitignore_completeness(tmp_path)

    assert ".claude/worktrees/" in result.missing_rules
    assert "改用內建的退回清單" in capsys.readouterr().err


# 3.4.0-W1-300.1：sync-preserve.yaml、sync-skills.yaml 改為進版控，舊規則列為可移除
def test_retired_rules_listed_and_not_counted_missing(project: Path, required: list[str]) -> None:
    """正向對照：完整規則另含兩條舊規則 → 列入 retired_rules，必要規則仍完整。"""
    _write_gitignore(
        project, required + [".claude/**/sync-preserve.yaml", ".claude/**/sync-skills.yaml"]
    )

    result = check_gitignore_completeness(project)

    assert result.all_required_complete
    assert result.retired_rules == [".claude/**/sync-preserve.yaml", ".claude/**/sync-skills.yaml"]


def test_no_retired_rules_when_absent(project: Path, required: list[str]) -> None:
    _write_gitignore(project, required)

    assert check_gitignore_completeness(project).retired_rules == []


def test_old_manifest_without_retired_helper_skips(project: Path, required: list[str]) -> None:
    """受檢專案是舊版框架（manifest 沒有 retired_gitignore_lines）→ 不報可移除。"""
    manifest_path = project / ".claude" / "lib" / "sync_exclude_manifest.py"
    text = manifest_path.read_text(encoding="utf-8")
    manifest_path.write_text(
        text.replace("def retired_gitignore_lines(", "def _removed_retired_gitignore_lines("),
        encoding="utf-8",
    )
    _write_gitignore(project, required + [".claude/**/sync-preserve.yaml"])

    assert check_gitignore_completeness(project).retired_rules == []


# 3.4.0-W1-100：票庫 lock 必要項由 lib/ticket_lock_gitignore.py 推導，onboard 與 hook 共用
TICKET_LOCK_LIB = Path(__file__).resolve().parents[3] / "lib" / "ticket_lock_gitignore.py"
HOOK_PATH = Path(__file__).resolve().parents[3] / "hooks" / "session-start-gitignore-check-hook.py"
LOCK_ENTRY = "docs/work-logs/**/*.md.lock"


@pytest.fixture
def project_with_lock_lib(project: Path) -> Path:
    shutil.copy(TICKET_LOCK_LIB, project / ".claude" / "lib" / "ticket_lock_gitignore.py")
    return project


def _hook_missing(project: Path) -> list[str]:
    import importlib.util
    from unittest.mock import MagicMock

    spec = importlib.util.spec_from_file_location("_gitignore_check_hook", HOOK_PATH)
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)
    missing, _tracked, _exists = hook.run_checks(project, MagicMock())
    return sorted(missing)


def test_lock_entry_missing_reported_by_both(project_with_lock_lib: Path, required: list[str]) -> None:
    """正向對照：缺票庫 lock 項時 onboard 與 hook 都報缺，且清單一致."""
    project = project_with_lock_lib
    _write_gitignore(project, required)

    onboard_missing = sorted(check_gitignore_completeness(project).missing_rules)

    assert onboard_missing == [LOCK_ENTRY]
    assert _hook_missing(project) == onboard_missing


def test_lock_entry_covered_reported_by_neither(project_with_lock_lib: Path, required: list[str]) -> None:
    """反向對照：有涵蓋時兩邊都不報."""
    project = project_with_lock_lib
    _write_gitignore(project, required + [LOCK_ENTRY])

    assert check_gitignore_completeness(project).missing_rules == []
    assert _hook_missing(project) == []


def test_missing_lock_and_other_entry_lists_match(project_with_lock_lib: Path, required: list[str]) -> None:
    """同一份 .gitignore 缺 local-only 項與 lock 項：兩邊缺項清單完全一致."""
    project = project_with_lock_lib
    target = ".claude/**/settings.local.json"
    _write_gitignore(project, [e for e in required if e != target])

    onboard_missing = sorted(check_gitignore_completeness(project).missing_rules)

    assert onboard_missing == sorted([target, LOCK_ENTRY])
    assert _hook_missing(project) == onboard_missing


def test_missing_gitignore_lists_lock_entry_in_both(project_with_lock_lib: Path) -> None:
    project = project_with_lock_lib

    onboard_missing = sorted(check_gitignore_completeness(project).missing_rules)

    assert LOCK_ENTRY in onboard_missing
    assert _hook_missing(project) == onboard_missing


@pytest.fixture
def claude_tix_project(project_with_lock_lib: Path) -> Path:
    """票庫在 .claude/ 下（WORK_LOGS_DIR=".claude/tix"）."""
    d = project_with_lock_lib / ".claude" / "skills" / "ticket" / "ticket_system"
    d.mkdir(parents=True)
    (d / "constants.py").write_text('WORK_LOGS_DIR = ".claude/tix"\n', encoding="utf-8")
    return project_with_lock_lib


def test_claude_ticket_root_uncovered_reported_by_both(claude_tix_project: Path, required: list[str]) -> None:
    _write_gitignore(claude_tix_project, required)

    onboard_missing = sorted(check_gitignore_completeness(claude_tix_project).missing_rules)

    assert onboard_missing == [".claude/tix/**/*.md.lock"]
    assert _hook_missing(claude_tix_project) == onboard_missing


def test_claude_ticket_root_covered_by_lock_glob_reported_by_neither(
    claude_tix_project: Path, required: list[str]
) -> None:
    _write_gitignore(claude_tix_project, required + [".claude/**/*.lock"])

    assert check_gitignore_completeness(claude_tix_project).missing_rules == []
    assert _hook_missing(claude_tix_project) == []


def test_claude_ticket_root_without_gitignore_lists_lock_in_both(claude_tix_project: Path) -> None:
    onboard_missing = sorted(check_gitignore_completeness(claude_tix_project).missing_rules)

    assert ".claude/tix/**/*.md.lock" in onboard_missing
    assert _hook_missing(claude_tix_project) == onboard_missing


def test_old_framework_without_lock_module_skips_with_stderr(
    project: Path, required: list[str], capsys
) -> None:
    """舊版框架（無 ticket_lock_gitignore.py）：寫 stderr 並略過 lock 項，其餘檢查照常."""
    _write_gitignore(project, required)

    result = check_gitignore_completeness(project)

    assert result.missing_rules == []
    assert result.all_required_complete
    assert result.undetermined_rules == ["{票庫}/**/*.md.lock"]
    assert "ticket_lock_gitignore.py" in capsys.readouterr().err


def test_old_framework_report_body_says_undetermined(
    project: Path, required: list[str], capsys
) -> None:
    """舊版框架：報告本文標「無法判定」，待辦另列一則，且不算缺漏."""
    from project_init.commands.onboard import _collect_gitignore_items, _print_gitignore_section

    _write_gitignore(project, required)
    info = check_gitignore_completeness(project)
    capsys.readouterr()

    _print_gitignore_section(info)
    out = capsys.readouterr().out

    assert "無法判定以下規則" in out
    assert "{票庫}/**/*.md.lock" in out
    assert any("無法判定" in item.description for item in _collect_gitignore_items(info))


def test_new_framework_report_has_no_undetermined_line(
    project_with_lock_lib: Path, required: list[str], capsys
) -> None:
    """反向對照：新版框架（有模組）報告不出現「無法判定」."""
    from project_init.commands.onboard import _collect_gitignore_items, _print_gitignore_section

    _write_gitignore(project_with_lock_lib, required + [LOCK_ENTRY])
    info = check_gitignore_completeness(project_with_lock_lib)
    capsys.readouterr()

    _print_gitignore_section(info)

    assert "無法判定" not in capsys.readouterr().out
    assert _collect_gitignore_items(info) == []
