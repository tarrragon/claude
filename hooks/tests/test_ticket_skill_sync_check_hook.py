"""
ticket-skill-sync-check-hook 測試套件

驗證偵測流程 + meta 防護的 5+ 情境：
1. feat commit + ticket skill src 改動 → 觸發提示
2. fix commit + ticket skill src 改動 → 不觸發
3. feat commit + ticket skill src + 同 commit 含 decision-tree.md 改動 → 已同步豁免
4. hook 自身路徑改動 → meta 自我引用豁免
5. feat commit 不含 ticket skill src → 不觸發
6. 純函式驗證：is_git_commit_command / extract_commit_type
"""

import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

# 動態導入（檔名含 dash）
hooks_path = Path(__file__).parent.parent
# W10-092: ticket-skill-sync-check-hook 已遷至 .claude/skills/ticket/hooks/
ticket_skill_hooks_path = hooks_path.parent / "skills" / "ticket" / "hooks"
hook_file = ticket_skill_hooks_path / "ticket-skill-sync-check-hook.py"
spec = importlib.util.spec_from_file_location("ticket_skill_sync_check_hook", hook_file)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


# ----------------------------------------------------------------------------
# 純函式單元測試
# ----------------------------------------------------------------------------


def test_is_git_commit_command_positive():
    assert hook.is_git_commit_command('git commit -m "feat: x"') is True


def test_is_git_commit_command_excludes_amend():
    assert hook.is_git_commit_command('git commit --amend -m "x"') is False


def test_is_git_commit_command_excludes_log():
    assert hook.is_git_commit_command("git log --oneline") is False


def test_extract_commit_type_simple():
    assert hook.extract_commit_type('git commit -m "feat: add x"') == "feat"


def test_extract_commit_type_with_scope():
    assert hook.extract_commit_type('git commit -m "refactor(ticket): y"') == "refactor"


def test_extract_commit_type_heredoc():
    cmd = "git commit -m \"$(cat <<'EOF'\nfeat(0.18.0-W17-115.3): hook impl\n\nbody\nEOF\n)\""
    assert hook.extract_commit_type(cmd) == "feat"


def test_extract_commit_type_unknown():
    assert hook.extract_commit_type("git commit -m 'no colon here'") == ""


def test_is_commit_successful_true():
    assert hook.is_commit_successful("3 files changed, 10 insertions(+)") is True


def test_is_commit_successful_false():
    assert hook.is_commit_successful("nothing to commit") is False


def test_has_ticket_skill_src_change_filter():
    files = [
        ".claude/skills/ticket/ticket_system/lifecycle.py",
        ".claude/hooks/foo.py",
        "docs/README.md",
    ]
    result = hook.has_ticket_skill_src_change(files)
    assert result == [".claude/skills/ticket/ticket_system/lifecycle.py"]


def test_has_sync_exempt_change_pmrules():
    assert hook.has_sync_exempt_change([".claude/pm-rules/decision-tree.md"]) is True


def test_has_sync_exempt_change_skillmd():
    assert hook.has_sync_exempt_change([".claude/skills/ticket/SKILL.md"]) is True


def test_has_sync_exempt_change_negative():
    assert hook.has_sync_exempt_change([".claude/skills/ticket/ticket_system/x.py"]) is False


def test_is_meta_self_only_positive():
    assert hook.is_meta_self_only([".claude/skills/ticket/hooks/ticket-skill-sync-check-hook.py"]) is True


def test_is_meta_self_only_negative():
    assert hook.is_meta_self_only([".claude/skills/ticket/ticket_system/x.py"]) is False


# ----------------------------------------------------------------------------
# 主流程整合測試（mock subprocess + stdin）
# ----------------------------------------------------------------------------


def _make_input(command: str, stdout: str) -> str:
    return json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "tool_response": {"stdout": stdout},
    })


def _run_main(stdin_text: str, commit_files: list, capsys):
    """執行 main()，mock get_commit_files 回傳指定 list。"""
    with patch.object(hook, "get_commit_files", return_value=commit_files), \
         patch("sys.stdin.read", return_value=stdin_text):
        rc = hook.main()
    captured = capsys.readouterr()
    return rc, captured.out


def test_scenario_1_feat_with_skill_src_triggers(capsys):
    """情境 1: feat commit + ticket skill src 改動 → 觸發提示"""
    stdin = _make_input(
        'git commit -m "feat(W17-001): change lifecycle"',
        "2 files changed, 30 insertions(+)",
    )
    files = [".claude/skills/ticket/ticket_system/lifecycle.py"]
    rc, out = _run_main(stdin, files, capsys)
    assert rc == 0
    payload = json.loads(out)
    assert "additionalContext" in payload["hookSpecificOutput"]
    assert "Ticket Skill 行為變更同步檢查提醒" in payload["hookSpecificOutput"]["additionalContext"]
    assert ".claude/skills/ticket/ticket_system/lifecycle.py" in payload["hookSpecificOutput"]["additionalContext"]


def test_scenario_2_fix_with_skill_src_no_trigger(capsys):
    """情境 2: fix commit + ticket skill src 改動 → 不觸發（fix 不在白名單）"""
    stdin = _make_input(
        'git commit -m "fix(W17-001): patch lifecycle bug"',
        "1 file changed, 2 insertions(+)",
    )
    files = [".claude/skills/ticket/ticket_system/lifecycle.py"]
    rc, out = _run_main(stdin, files, capsys)
    assert rc == 0
    payload = json.loads(out)
    assert "additionalContext" not in payload["hookSpecificOutput"]


def test_scenario_3_feat_with_decision_tree_synced(capsys):
    """情境 3: feat commit + skill src + 同 commit 含 decision-tree.md → 已同步豁免"""
    stdin = _make_input(
        'git commit -m "feat(W17-001): change + sync"',
        "2 files changed, 30 insertions(+)",
    )
    files = [
        ".claude/skills/ticket/ticket_system/lifecycle.py",
        ".claude/pm-rules/decision-tree.md",
    ]
    rc, out = _run_main(stdin, files, capsys)
    assert rc == 0
    payload = json.loads(out)
    assert "additionalContext" not in payload["hookSpecificOutput"]


def test_scenario_4_meta_self_reference_exempt(capsys):
    """情境 4: hook 自身路徑改動 → meta 自我引用豁免"""
    stdin = _make_input(
        'git commit -m "feat: add ticket-skill-sync-check-hook"',
        "1 file changed, 200 insertions(+)",
    )
    files = [".claude/skills/ticket/hooks/ticket-skill-sync-check-hook.py"]
    rc, out = _run_main(stdin, files, capsys)
    assert rc == 0
    payload = json.loads(out)
    assert "additionalContext" not in payload["hookSpecificOutput"]


def test_scenario_5_feat_without_skill_src_no_trigger(capsys):
    """情境 5: feat commit 不含 ticket skill src → 不觸發"""
    stdin = _make_input(
        'git commit -m "feat(ui): add button"',
        "3 files changed, 50 insertions(+)",
    )
    files = ["src/ui/Button.js", "src/ui/Button.test.js"]
    rc, out = _run_main(stdin, files, capsys)
    assert rc == 0
    payload = json.loads(out)
    assert "additionalContext" not in payload["hookSpecificOutput"]


def test_scenario_6_non_bash_tool_skip(capsys):
    """補充: 非 Bash 工具 → 直接跳過"""
    stdin = json.dumps({"tool_name": "Edit", "tool_input": {}, "tool_response": {}})
    rc, out = _run_main(stdin, [], capsys)
    assert rc == 0
    payload = json.loads(out)
    assert "additionalContext" not in payload["hookSpecificOutput"]


def test_scenario_7_chore_commit_no_trigger(capsys):
    """補充: chore commit 含 skill src → 不觸發（chore 非行為變更）"""
    stdin = _make_input(
        'git commit -m "chore(W17-001): rename var"',
        "1 file changed, 1 insertion(+)",
    )
    files = [".claude/skills/ticket/ticket_system/lifecycle.py"]
    rc, out = _run_main(stdin, files, capsys)
    assert rc == 0
    payload = json.loads(out)
    assert "additionalContext" not in payload["hookSpecificOutput"]


def test_scenario_8_refactor_with_skill_md_synced(capsys):
    """補充: refactor + skill src + SKILL.md 同步 → 豁免"""
    stdin = _make_input(
        'git commit -m "refactor(ticket): split lifecycle"',
        "3 files changed, 100 insertions(+)",
    )
    files = [
        ".claude/skills/ticket/ticket_system/lifecycle.py",
        ".claude/skills/ticket/SKILL.md",
    ]
    rc, out = _run_main(stdin, files, capsys)
    assert rc == 0
    payload = json.loads(out)
    assert "additionalContext" not in payload["hookSpecificOutput"]
