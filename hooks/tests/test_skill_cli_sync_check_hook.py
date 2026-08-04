"""
skill-cli-sync-check-hook 測試套件（0.2.1-W3-239 泛化：ticket 單一 skill -> 7-skill registry）

驗證偵測流程 + meta 防護 + 多 skill registry 情境：
1. feat commit + ticket skill src 改動 → 觸發提示
2. fix commit + ticket skill src 改動 → 不觸發
3. feat commit + ticket skill src + 同 commit 含 pm-rules 改動 → 已同步豁免
4. hook 自身路徑改動 → meta 自我引用豁免
5. feat commit 不含任何 registry skill src → 不觸發
6. 純函式驗證：is_git_commit_command / extract_commit_type
7. 非 ticket skill（doc / skill-sync）行為變更 → 亦觸發（泛化驗證，0.2.1-W3-131 gap 迴歸）
8. 同 commit 跨多個 skill，僅未同步者出現於提示
"""

import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

# 動態導入（檔名含 dash）
# 0.2.1-W3-239: 由 .claude/skills/ticket/hooks/ 泛化搬遷至 .claude/hooks/
hooks_path = Path(__file__).parent.parent
hook_file = hooks_path / "skill-cli-sync-check-hook.py"
spec = importlib.util.spec_from_file_location("skill_cli_sync_check_hook", hook_file)
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


def test_registry_has_seven_skills():
    """0.2.1-W3-136 ANA 盤點：7 個具 CLI 入口點的 skill"""
    names = {entry["name"] for entry in hook.SKILL_CLI_REGISTRY}
    assert names == {
        "ticket", "doc", "skill-sync", "worktree",
        "version-release", "project-init", "mermaid-ascii",
    }


def test_find_skill_src_changes_single_skill():
    files = [
        ".claude/skills/ticket/ticket_system/lifecycle.py",
        ".claude/hooks/foo.py",
        "docs/README.md",
    ]
    result = hook.find_skill_src_changes(files)
    assert result == {"ticket": [".claude/skills/ticket/ticket_system/lifecycle.py"]}


def test_find_skill_src_changes_non_ticket_skill():
    """泛化驗證：doc / skill-sync 等非 ticket skill 亦應被偵測（0.2.1-W3-131 gap 迴歸）"""
    files = [".claude/skills/skill-sync/skill_sync/cli.py"]
    result = hook.find_skill_src_changes(files)
    assert result == {"skill-sync": [".claude/skills/skill-sync/skill_sync/cli.py"]}


def test_find_skill_src_changes_multi_skill():
    files = [
        ".claude/skills/ticket/ticket_system/lifecycle.py",
        ".claude/skills/doc/doc_system/cli.py",
    ]
    result = hook.find_skill_src_changes(files)
    assert result == {
        "ticket": [".claude/skills/ticket/ticket_system/lifecycle.py"],
        "doc": [".claude/skills/doc/doc_system/cli.py"],
    }


def test_find_skill_src_changes_no_match():
    files = ["docs/README.md", "src/ui/Button.js"]
    assert hook.find_skill_src_changes(files) == {}


def test_is_sync_exempt_for_skill_ticket_pmrules():
    assert hook.is_sync_exempt_for_skill([".claude/pm-rules/decision-tree.md"], "ticket") is True


def test_is_sync_exempt_for_skill_ticket_skillmd():
    assert hook.is_sync_exempt_for_skill([".claude/skills/ticket/SKILL.md"], "ticket") is True


def test_is_sync_exempt_for_skill_ticket_negative():
    assert hook.is_sync_exempt_for_skill([".claude/skills/ticket/ticket_system/x.py"], "ticket") is False


def test_is_sync_exempt_for_skill_doc_own_skillmd():
    assert hook.is_sync_exempt_for_skill([".claude/skills/doc/SKILL.md"], "doc") is True


def test_is_sync_exempt_for_skill_doc_not_exempt_by_ticket_skillmd():
    """doc skill 的同步豁免不應被 ticket 的 SKILL.md 誤判滿足"""
    assert hook.is_sync_exempt_for_skill([".claude/skills/ticket/SKILL.md"], "doc") is False


def test_is_sync_exempt_for_skill_unknown_skill():
    assert hook.is_sync_exempt_for_skill([".claude/skills/ticket/SKILL.md"], "not-a-skill") is False


def test_is_meta_self_only_positive():
    assert hook.is_meta_self_only([".claude/hooks/skill-cli-sync-check-hook.py"]) is True


def test_is_meta_self_only_negative():
    assert hook.is_meta_self_only([".claude/skills/ticket/ticket_system/x.py"]) is False


def test_find_unsynced_skills_filters_synced_out():
    files = [
        ".claude/skills/ticket/ticket_system/lifecycle.py",
        ".claude/skills/doc/doc_system/cli.py",
        ".claude/skills/doc/SKILL.md",  # doc 已同步
    ]
    result = hook.find_unsynced_skills(files)
    assert result == {"ticket": [".claude/skills/ticket/ticket_system/lifecycle.py"]}


def test_build_reminder_contains_all_unsynced_skills():
    unsynced = {
        "ticket": [".claude/skills/ticket/ticket_system/lifecycle.py"],
        "doc": [".claude/skills/doc/doc_system/cli.py"],
    }
    message = hook.build_reminder(unsynced)
    assert "[ticket]" in message
    assert "[doc]" in message
    assert ".claude/skills/ticket/ticket_system/lifecycle.py" in message
    assert ".claude/skills/doc/doc_system/cli.py" in message
    assert ".claude/skills/doc/SKILL.md" in message


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


def test_scenario_1_feat_with_ticket_skill_src_triggers(capsys):
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
    assert "Skill CLI 行為變更同步檢查提醒" in payload["hookSpecificOutput"]["additionalContext"]
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


def test_scenario_3_feat_with_pmrules_synced(capsys):
    """情境 3: feat commit + skill src + 同 commit 含 pm-rules → 已同步豁免"""
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
        'git commit -m "feat: add skill-cli-sync-check-hook"',
        "1 file changed, 200 insertions(+)",
    )
    files = [".claude/hooks/skill-cli-sync-check-hook.py"]
    rc, out = _run_main(stdin, files, capsys)
    assert rc == 0
    payload = json.loads(out)
    assert "additionalContext" not in payload["hookSpecificOutput"]


def test_scenario_5_feat_without_registry_skill_src_no_trigger(capsys):
    """情境 5: feat commit 不含任何 registry skill src → 不觸發"""
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


def test_scenario_9_non_ticket_skill_triggers(capsys):
    """情境 9（泛化）: feat commit + skill-sync src 改動（非 ticket）→ 觸發提示
    迴歸驗證 0.2.1-W3-131：舊版 hook 對此情境零提示。
    """
    stdin = _make_input(
        'git commit -m "feat(skill-sync): change pull_all behavior"',
        "1 file changed, 20 insertions(+)",
    )
    files = [".claude/skills/skill-sync/skill_sync/cli.py"]
    rc, out = _run_main(stdin, files, capsys)
    assert rc == 0
    payload = json.loads(out)
    assert "additionalContext" in payload["hookSpecificOutput"]
    context = payload["hookSpecificOutput"]["additionalContext"]
    assert "[skill-sync]" in context
    assert ".claude/skills/skill-sync/SKILL.md" in context


def test_scenario_10_multi_skill_only_unsynced_reported(capsys):
    """情境 10（泛化）: 同 commit 跨 ticket + doc 兩個 skill，僅 doc 未同步 → 提示僅含 doc"""
    stdin = _make_input(
        'git commit -m "feat: cross-skill change"',
        "3 files changed, 60 insertions(+)",
    )
    files = [
        ".claude/skills/ticket/ticket_system/lifecycle.py",
        ".claude/skills/ticket/SKILL.md",  # ticket 已同步
        ".claude/skills/doc/doc_system/cli.py",  # doc 未同步
    ]
    rc, out = _run_main(stdin, files, capsys)
    assert rc == 0
    payload = json.loads(out)
    context = payload["hookSpecificOutput"]["additionalContext"]
    assert "[doc]" in context
    assert "[ticket]" not in context
