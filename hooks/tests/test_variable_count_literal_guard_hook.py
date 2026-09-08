"""
variable-count-literal-guard-hook 測試套件

驗證規則 10（可變計數不實例化）偵測邏輯：
1. 命中案例：範圍內檔案新增行含可變計數字面 → 觸發 INFO 提示
2. 豁免案例：變更歷史 / footer 版本行 / 規則編號 / 版本號 → 不觸發
3. 無新增行 / 非範圍檔案 → 不觸發
4. 純函式驗證：is_in_scope / scan_line_for_count_literal / is_exempt_line
"""

import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

hooks_path = Path(__file__).parent.parent
hook_file = hooks_path / "variable-count-literal-guard-hook.py"
spec = importlib.util.spec_from_file_location("variable_count_literal_guard_hook", hook_file)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


# ----------------------------------------------------------------------------
# 純函式單元測試：is_in_scope
# ----------------------------------------------------------------------------


def test_is_in_scope_rules_dir():
    assert hook.is_in_scope(".claude/rules/core/quality-baseline.md") is True


def test_is_in_scope_references_dir():
    assert hook.is_in_scope(".claude/references/reference-stability-rules.md") is True


def test_is_in_scope_methodologies_dir():
    assert hook.is_in_scope(".claude/methodologies/foo-methodology.md") is True


def test_is_in_scope_skill_md():
    assert hook.is_in_scope(".claude/skills/ticket/SKILL.md") is True


def test_is_in_scope_skill_non_skillmd_excluded():
    assert hook.is_in_scope(".claude/skills/ticket/ticket_system/cli.py") is False


def test_is_in_scope_out_of_scope():
    assert hook.is_in_scope("docs/spec/ui/SPEC-001.md") is False


def test_is_in_scope_hooks_dir_excluded():
    assert hook.is_in_scope(".claude/hooks/some-hook.py") is False


# ----------------------------------------------------------------------------
# 純函式單元測試：scan_line_for_count_literal / is_exempt_line
# ----------------------------------------------------------------------------


def test_scan_detects_arabic_count_literal():
    assert hook.scan_line_for_count_literal("本表共有 17 檔，逐一列出如下") is True


def test_scan_detects_chinese_numeral_count_literal():
    assert hook.scan_line_for_count_literal("十一欄位表如下所示") is True


def test_scan_no_match_without_unit_word():
    assert hook.scan_line_for_count_literal("這裡有 17 個東西但沒有單位詞") is False


def test_scan_exempt_changelog_line():
    line = "本次變更歷史：17 檔 60 餘處字面已修正"
    assert hook.scan_line_for_count_literal(line) is False


def test_scan_exempt_version_footer_line():
    line = "**Version**: 3.5.0 — 新增 17 條規則"
    assert hook.scan_line_for_count_literal(line) is False


def test_scan_exempt_rule_number_reference():
    line = "依規則 10 判準，本表共 17 條需檢查"
    assert hook.scan_line_for_count_literal(line) is False


def test_scan_exempt_error_pattern_id():
    line = "PC-050 案例中列出 17 項觀察"
    assert hook.scan_line_for_count_literal(line) is False


def test_scan_exempt_version_number_line():
    line = "升級至 0.29.0 後新增 17 檔"
    assert hook.scan_line_for_count_literal(line) is False


def test_scan_exempt_measurement_record():
    line = "（量測環境：2026-08-10）1607 個受掃描框架檔中 714 檔含票號"
    assert hook.scan_line_for_count_literal(line) is False


def test_scan_exempt_actual_measurement_marker():
    line = "實測顯示目前共有 17 檔符合條件"
    assert hook.scan_line_for_count_literal(line) is False


def test_is_exempt_line_no_marker_returns_false():
    assert hook.is_exempt_line("本表共有 17 檔，逐一列出如下") is False


# ----------------------------------------------------------------------------
# 主流程整合測試（mock subprocess + stdin）
# ----------------------------------------------------------------------------


def _make_input(command: str, stdout: str) -> str:
    return json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "tool_response": {"stdout": stdout},
    })


def _run_main(stdin_text: str, commit_files: list, added_lines_map: dict, capsys):
    """執行 main()，mock get_commit_files 與 get_added_lines。"""

    def _fake_get_added_lines(project_root, file_path, logger):
        return added_lines_map.get(file_path, [])

    with patch.object(hook, "get_commit_files", return_value=commit_files), \
         patch.object(hook, "get_added_lines", side_effect=_fake_get_added_lines), \
         patch("sys.stdin.read", return_value=stdin_text):
        rc = hook.main()
    captured = capsys.readouterr()
    return rc, captured.out


def test_scenario_hit_in_scope_file_triggers(capsys):
    """情境 1: 範圍內檔案新增行含可變計數字面 → 觸發 INFO 提示"""
    stdin = _make_input(
        'git commit -m "docs: update rules"',
        "1 file changed, 1 insertion(+)",
    )
    files = [".claude/rules/core/quality-baseline.md"]
    added = {
        ".claude/rules/core/quality-baseline.md": [
            (42, "本規則共有 17 檔需要遵守"),
        ]
    }
    rc, out = _run_main(stdin, files, added, capsys)
    assert rc == 0
    output = json.loads(out)
    context = output["hookSpecificOutput"].get("additionalContext", "")
    assert "可變計數字面偵測" in context
    assert ".claude/rules/core/quality-baseline.md:42" in context


def test_scenario_exempt_lines_do_not_trigger(capsys):
    """情境 2: 命中 pattern 但落入例外表 → 不觸發"""
    stdin = _make_input(
        'git commit -m "docs: update rules"',
        "1 file changed, 1 insertion(+)",
    )
    files = [".claude/rules/core/quality-baseline.md"]
    added = {
        ".claude/rules/core/quality-baseline.md": [
            (10, "**Version**: 3.5.0 — 新增 17 條規則"),
            (11, "依規則 10 判準，本表共 17 條需檢查"),
        ]
    }
    rc, out = _run_main(stdin, files, added, capsys)
    assert rc == 0
    output = json.loads(out)
    assert "additionalContext" not in output["hookSpecificOutput"]


def test_scenario_out_of_scope_file_not_scanned(capsys):
    """情境 3: 非範圍檔案（如 docs/spec/）即使含計數字面也不掃描"""
    stdin = _make_input(
        'git commit -m "docs: update spec"',
        "1 file changed, 1 insertion(+)",
    )
    files = ["docs/spec/ui/SPEC-001.md"]
    added = {
        "docs/spec/ui/SPEC-001.md": [
            (5, "本規格含 17 個欄位"),
        ]
    }
    rc, out = _run_main(stdin, files, added, capsys)
    assert rc == 0
    output = json.loads(out)
    assert "additionalContext" not in output["hookSpecificOutput"]


def test_scenario_no_added_lines_not_triggered(capsys):
    """情境 4: 範圍內檔案但無新增行命中 → 不觸發"""
    stdin = _make_input(
        'git commit -m "docs: update rules"',
        "1 file changed, 1 insertion(+)",
    )
    files = [".claude/rules/core/quality-baseline.md"]
    added = {".claude/rules/core/quality-baseline.md": [(1, "無關的一行文字")]}
    rc, out = _run_main(stdin, files, added, capsys)
    assert rc == 0
    output = json.loads(out)
    assert "additionalContext" not in output["hookSpecificOutput"]


def test_scenario_non_bash_tool_skipped(capsys):
    """非 Bash 工具直接跳過"""
    stdin = json.dumps({"tool_name": "Edit"})
    with patch("sys.stdin.read", return_value=stdin):
        rc = hook.main()
    captured = capsys.readouterr()
    assert rc == 0
    output = json.loads(captured.out)
    assert "additionalContext" not in output["hookSpecificOutput"]


def test_scenario_non_commit_command_skipped(capsys):
    """非 git commit 命令跳過"""
    stdin = _make_input("git status", "")
    rc, out = _run_main(stdin, [], {}, capsys)
    assert rc == 0
    output = json.loads(out)
    assert "additionalContext" not in output["hookSpecificOutput"]


def test_scenario_meta_self_reference_exempt(capsys):
    """情境: commit 含本 hook 自身路徑改動 → meta 自我引用豁免"""
    stdin = _make_input(
        'git commit -m "feat: update hook"',
        "1 file changed, 1 insertion(+)",
    )
    files = [".claude/hooks/variable-count-literal-guard-hook.py"]
    rc, out = _run_main(stdin, files, {}, capsys)
    assert rc == 0
    output = json.loads(out)
    assert "additionalContext" not in output["hookSpecificOutput"]


def test_scenario_subagent_environment_skipped(capsys):
    """subagent 環境跳過（PC-V1-004 防護）"""
    stdin = json.dumps({
        "tool_name": "Bash",
        "agent_id": "some-agent-id",
        "tool_input": {"command": 'git commit -m "docs: x"'},
        "tool_response": {"stdout": "1 file changed, 1 insertion(+)"},
    })
    with patch("sys.stdin.read", return_value=stdin):
        rc = hook.main()
    captured = capsys.readouterr()
    assert rc == 0
    output = json.loads(captured.out)
    assert "additionalContext" not in output["hookSpecificOutput"]
