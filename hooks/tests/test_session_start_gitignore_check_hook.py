"""
session-start-gitignore-check-hook 測試套件

驗證 6 情境：
1. 完整 gitignore（含所有必要 entry + 無 tracked）→ suppressOutput=True
2. 缺失 entry（缺 .claude/pm-status.json）→ missing 含該項，輸出 WARN
3. 等效 broader pattern（用 logs/ 取代 .claude/logs/）→ 該項視為已覆蓋
4. 已 tracked runtime state（git ls-files 含 .claude/pm-status.json）→ tracked 含該項 + 修復 cmd
5. .gitignore 不存在 → WARN 訊息提示建立
6. 註解行與空行不影響 parse

Ticket：0.19.0-W3-077
"""

import importlib.util
import json
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock


HOOK_PATH = (
    Path(__file__).parent.parent / "session-start-gitignore-check-hook.py"
)


def load_hook_module():
    spec = importlib.util.spec_from_file_location(
        "session_start_gitignore_check_hook", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_gitignore(tmp_path: Path, content: str) -> Path:
    gi = tmp_path / ".gitignore"
    gi.write_text(content, encoding="utf-8")
    return gi


def _mk_ls_files(stdout: str, returncode: int = 0):
    m = MagicMock(spec=subprocess.CompletedProcess)
    m.stdout = stdout
    m.stderr = ""
    m.returncode = returncode
    return m


# ---------------------------------------------------------------------------
# 1. 完整 gitignore 通過（無缺失、無 tracked）→ suppressOutput
# ---------------------------------------------------------------------------
def test_complete_gitignore_passes(tmp_path):
    hook = load_hook_module()
    complete_content = (
        "\n".join(sorted(hook.REQUIRED_GITIGNORE_ENTRIES)) + "\ndocs/**/*.md.lock\n"
    )
    _make_gitignore(tmp_path, complete_content)
    with patch.object(
        hook.subprocess, "run", return_value=_mk_ls_files("src/main.js\nREADME.md\n")
    ):
        missing, tracked, exists = hook.run_checks(tmp_path, MagicMock())
    assert exists is True
    assert missing == []
    assert tracked == []
    output = hook.build_hook_output(missing, tracked, exists)
    assert output == {"suppressOutput": True}


# ---------------------------------------------------------------------------
# 2. 缺失 entry → missing 含該項
# ---------------------------------------------------------------------------
def test_missing_entry_warns(tmp_path):
    hook = load_hook_module()
    # 故意缺 pm-status.json 的必要條目（巢狀形式 .claude/**/pm-status.json）
    entry = ".claude/**/pm-status.json"
    entries = sorted(hook.REQUIRED_GITIGNORE_ENTRIES - {entry})
    _make_gitignore(tmp_path, "\n".join(entries) + "\n")
    with patch.object(hook.subprocess, "run", return_value=_mk_ls_files("")):
        missing, tracked, exists = hook.run_checks(tmp_path, MagicMock())
    assert exists is True
    assert entry in missing
    assert tracked == []
    output = hook.build_hook_output(missing, tracked, exists)
    assert "suppressOutput" in output
    assert output["suppressOutput"] is False
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert entry in ctx
    assert "WARNING" in ctx


# ---------------------------------------------------------------------------
# 3. 等效 broader pattern（logs/ 取代 .claude/logs）→ 正規化後視為已覆蓋
# ---------------------------------------------------------------------------
def test_equivalent_broader_pattern_passes(tmp_path):
    hook = load_hook_module()
    # derive 後 REQUIRED 為無斜線格式 `.claude/logs`；移除後改用 broader `logs/` 覆蓋
    entries = sorted(hook.REQUIRED_GITIGNORE_ENTRIES - {".claude/logs"})
    content = "\n".join(entries) + "\nlogs/\n"
    _make_gitignore(tmp_path, content)
    with patch.object(hook.subprocess, "run", return_value=_mk_ls_files("")):
        missing, _, _ = hook.run_checks(tmp_path, MagicMock())
    assert ".claude/logs" not in missing


# ---------------------------------------------------------------------------
# 4. 已 tracked runtime state → tracked 清單含該項 + 修復 cmd
# ---------------------------------------------------------------------------
def test_tracked_runtime_state_warns(tmp_path):
    hook = load_hook_module()
    complete_content = "\n".join(sorted(hook.REQUIRED_GITIGNORE_ENTRIES)) + "\n"
    _make_gitignore(tmp_path, complete_content)
    ls_output = (
        "src/main.js\0"
        ".claude/pm-status.json\0"
        ".claude/state/marker.json\0"
        "README.md\0"
    )
    with patch.object(
        hook.subprocess, "run", return_value=_mk_ls_files(ls_output)
    ):
        missing, tracked, exists = hook.run_checks(tmp_path, MagicMock())
    assert ".claude/pm-status.json" in tracked
    assert ".claude/state/marker.json" in tracked
    output = hook.build_hook_output(missing, tracked, exists)
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert "git rm --cached .claude/pm-status.json" in ctx
    assert "git rm --cached .claude/state/marker.json" in ctx


# ---------------------------------------------------------------------------
# 5. .gitignore 不存在 → WARN 提示建立
# ---------------------------------------------------------------------------
def test_no_gitignore_file_warns(tmp_path):
    hook = load_hook_module()
    # 不建立 .gitignore
    with patch.object(hook.subprocess, "run", return_value=_mk_ls_files("")):
        missing, tracked, exists = hook.run_checks(tmp_path, MagicMock())
    assert exists is False
    # 所有 REQUIRED 都應在 missing
    # REQUIRED 全缺，另加推導出的票庫 lock 必要項
    assert set(missing) == hook.REQUIRED_GITIGNORE_ENTRIES | {"docs/work-logs/**/*.md.lock"}
    output = hook.build_hook_output(missing, tracked, exists)
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert "未偵測到" in ctx or "未偵測到 `.gitignore`" in ctx


# ---------------------------------------------------------------------------
# 6. 註解行與空行不影響 parse
# ---------------------------------------------------------------------------
def test_comment_lines_ignored(tmp_path):
    hook = load_hook_module()
    content = (
        "# Comment line\n"
        "\n"
        "  # indented comment\n"
        + "\n".join(sorted(hook.REQUIRED_GITIGNORE_ENTRIES))
        + "\n"
    )
    gi = _make_gitignore(tmp_path, content)
    entries = hook.parse_gitignore(gi, MagicMock())
    # 註解與空行被過濾
    assert "# Comment line" not in entries
    assert "" not in entries
    # 實際 entry 都在
    for required in hook.REQUIRED_GITIGNORE_ENTRIES:
        assert required in entries


# ---------------------------------------------------------------------------
# 7. 完整輸出為合法 JSON 且 hookEventName=SessionStart
# ---------------------------------------------------------------------------
def test_output_is_valid_json_with_session_start_event(tmp_path):
    hook = load_hook_module()
    entries = sorted(hook.REQUIRED_GITIGNORE_ENTRIES - {".claude/pm-status.json"})
    _make_gitignore(tmp_path, "\n".join(entries) + "\n")
    with patch.object(hook.subprocess, "run", return_value=_mk_ls_files("")):
        missing, tracked, exists = hook.run_checks(tmp_path, MagicMock())
    output = hook.build_hook_output(missing, tracked, exists)
    # JSON serializable
    serialized = json.dumps(output, ensure_ascii=False)
    parsed = json.loads(serialized)
    assert parsed["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert isinstance(parsed["hookSpecificOutput"]["additionalContext"], str)


# ---------------------------------------------------------------------------
# 8. REQUIRED 直接 derive 自 manifest GITIGNORE_EXPECTED（單一 SOT，防雙清單漂移）
# ---------------------------------------------------------------------------
def test_required_derived_from_manifest_sot():
    hook = load_hook_module()
    import sys
    sys.path.insert(0, str(HOOK_PATH.parent.parent / "lib"))
    from sync_exclude_manifest import (
        GITIGNORE_EXPECTED,
        GITIGNORE_EXTRA_ENTRIES,
        NESTED_LOCAL_ONLY_NAMES,
    )

    def entry(n):
        return f".claude/**/{n}" if n in NESTED_LOCAL_ONLY_NAMES else f".claude/{n}"

    # manifest 每個裸名都應以 `.claude/<name>`（巢狀名稱為 `.claude/**/<name>`）出現在 REQUIRED
    for name in GITIGNORE_EXPECTED:
        assert entry(name) in hook.REQUIRED_GITIGNORE_ENTRIES, (
            f"manifest 名稱 {name} 未被 derive 進 REQUIRED（雙 SOT 漂移）"
        )
    # 反向：REQUIRED 除 lib 明列的 GITIGNORE_EXTRA_ENTRIES 外，全部源自 manifest
    manifest_derived = {entry(n) for n in GITIGNORE_EXPECTED}
    assert hook.REQUIRED_GITIGNORE_ENTRIES - GITIGNORE_EXTRA_ENTRIES == manifest_derived


# ---------------------------------------------------------------------------
# onboard 同源：REQUIRED 即 lib 的 required_gitignore_entries()（project-init onboard 讀同一函式）
# ---------------------------------------------------------------------------
def test_required_is_shared_lib_function():
    import sys
    hook = load_hook_module()
    sys.path.insert(0, str(HOOK_PATH.parent.parent / "lib"))
    from sync_exclude_manifest import required_gitignore_entries

    assert hook.REQUIRED_GITIGNORE_ENTRIES == required_gitignore_entries()


def test_missing_local_only_entry_reported_and_user_visible():
    """正向對照：缺 settings.local.json 條目時報缺，且 systemMessage 列出該條目."""
    import logging
    hook = load_hook_module()
    target = ".claude/**/settings.local.json"
    entries = set(hook.REQUIRED_GITIGNORE_ENTRIES) - {target}

    missing = hook.check_missing_entries(entries, logging.getLogger("t"))
    output = hook.build_hook_output(missing, [], True)

    assert missing == [target]
    assert target in output["systemMessage"]
    assert target in output["hookSpecificOutput"]["additionalContext"]


def test_user_message_lists_tracked_and_missing_gitignore():
    hook = load_hook_module()
    output = hook.build_hook_output([".claude/logs"], [".claude/pm-status.json"], False)

    message = output["systemMessage"]
    assert "沒有 .gitignore" in message
    assert ".claude/logs" in message
    assert ".claude/pm-status.json" in message


def test_clean_result_has_no_user_message():
    hook = load_hook_module()
    assert "systemMessage" not in hook.build_hook_output([], [], True)


# ---------------------------------------------------------------------------
# 票庫 lock sentinel 涵蓋（{票庫}/**/*.md.lock 推導必要項）
# ---------------------------------------------------------------------------
def _base_content(hook) -> str:
    return "\n".join(sorted(hook.REQUIRED_GITIGNORE_ENTRIES)) + "\n"


def _lock_missing(hook, tmp_path, extra: str, root_dir="docs/work-logs"):
    _make_gitignore(tmp_path, _base_content(hook) + extra)
    with patch.object(hook, "resolve_ticket_root_dir", return_value=root_dir):
        return hook.check_ticket_lock_entry(
            hook.parse_gitignore(tmp_path / ".gitignore", MagicMock()),
            tmp_path,
            MagicMock(),
        )


def test_ticket_lock_missing_is_detected(tmp_path):
    """E2 正向對照：缺票庫 lock 涵蓋必須被檢出，且不含寫死 docs/ 以外的推導。"""
    hook = load_hook_module()
    assert _lock_missing(hook, tmp_path, "") == ["docs/work-logs/**/*.md.lock"]


def test_ticket_lock_custom_root_derived(tmp_path):
    hook = load_hook_module()
    assert _lock_missing(hook, tmp_path, "", root_dir="tracking/tix") == [
        "tracking/tix/**/*.md.lock"
    ]


def test_ticket_lock_covered_variants_not_reported(tmp_path):
    """E1 對照：直寫與等價寫法皆不提示。"""
    hook = load_hook_module()
    for i, line in enumerate(
        [
            "docs/work-logs/**/*.md.lock",
            "docs/**/*.md.lock",
            "**/*.md.lock",
            "*.md.lock",
            "**/*.lock",
            "*.lock",
        ]
    ):
        sub = tmp_path / f"c{i}"
        sub.mkdir()
        assert _lock_missing(hook, sub, line + "\n") == [], line


def test_ticket_root_under_claude_not_reported(tmp_path):
    hook = load_hook_module()
    assert _lock_missing(hook, tmp_path, "", root_dir=".claude/tickets") == []


def test_resolve_ticket_root_dir_failure_falls_back(tmp_path):
    """設定讀取失敗（constants.py 缺席）：退回預設並寫日誌，不拋例外。"""
    hook = load_hook_module()
    logger = MagicMock()
    assert hook.resolve_ticket_root_dir(tmp_path, logger) == "docs/work-logs"
    assert logger.info.called or logger.warning.called


def test_resolve_ticket_root_dir_reads_constants(tmp_path):
    hook = load_hook_module()
    d = tmp_path / ".claude/skills/ticket/ticket_system"
    d.mkdir(parents=True)
    (d / "constants.py").write_text('WORK_LOGS_DIR: str = "tracking/tix"\n')
    assert hook.resolve_ticket_root_dir(tmp_path, MagicMock()) == "tracking/tix"


def test_run_checks_includes_ticket_lock(tmp_path):
    hook = load_hook_module()
    _make_gitignore(tmp_path, _base_content(hook))
    with patch.object(hook.subprocess, "run", return_value=_mk_ls_files("")):
        missing, _, _ = hook.run_checks(tmp_path, MagicMock())
    assert "docs/work-logs/**/*.md.lock" in missing


def test_claude_scoped_lock_rules_do_not_cover_ticket_root(tmp_path):
    """E2：只含 .claude/ 範圍 lock 規則（框架預設）時，票庫在 docs/ 下必須檢出缺失。"""
    hook = load_hook_module()
    for i, line in enumerate(
        [".claude/**/*.lock", ".claude/*.lock", "/.claude/**/*.lock", "other/**/*.md.lock", "docs/*.lock"]
    ):
        sub = tmp_path / f"m{i}"
        sub.mkdir()
        assert _lock_missing(hook, sub, line + "\n") == ["docs/work-logs/**/*.md.lock"], line


def test_leading_slash_global_forms_cover(tmp_path):
    hook = load_hook_module()
    for i, line in enumerate(["/*.lock", "/**/*.md.lock", "docs/work-logs/**/*.lock"]):
        sub = tmp_path / f"s{i}"
        sub.mkdir()
        assert _lock_missing(hook, sub, line + "\n") == [], line


# ---------------------------------------------------------------------------
# .skill-sync-base：條目須實際忽略 skills/<name>/ 底下的標記
# ---------------------------------------------------------------------------
def test_skill_sync_base_required_entry_ignores_nested_marker(tmp_path):
    hook = load_hook_module()
    entries = [e for e in hook.REQUIRED_GITIGNORE_ENTRIES if e.endswith(".skill-sync-base")]
    assert entries == [".claude/**/.skill-sync-base"]
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("\n".join(entries) + "\n", encoding="utf-8")

    def ignored(rel):
        return subprocess.run(["git", "-C", str(tmp_path), "check-ignore", "-q", rel]).returncode == 0

    assert ignored(".claude/skills/doc/.skill-sync-base")
    assert not ignored(".claude/skills/doc/SKILL.md")


def test_skill_sync_base_root_form_not_accepted_as_covering():
    import logging
    hook = load_hook_module()
    log = logging.getLogger("t")
    for bad in (".claude/.skill-sync-base", ".claude/skills/*/.skill-sync-base"):
        assert ".claude/**/.skill-sync-base" in hook.check_missing_entries({bad}, log)
    assert ".claude/**/.skill-sync-base" not in hook.check_missing_entries(
        {".claude/**/.skill-sync-base"}, log
    )


# __pycache__：只有根層條目須報缺漏（W1-176）
def test_pycache_required_entry_is_nested_form():
    hook = load_hook_module()
    entries = [e for e in hook.REQUIRED_GITIGNORE_ENTRIES if e.endswith("__pycache__")]
    assert entries == [".claude/**/__pycache__"]


def test_pycache_root_only_entry_reported_missing():
    import logging
    hook = load_hook_module()
    log = logging.getLogger("t")
    for bad in (".claude/__pycache__", ".claude/__pycache__/"):
        assert ".claude/**/__pycache__" in hook.check_missing_entries({bad}, log)


def test_pycache_nested_or_bare_entry_not_reported():
    import logging
    hook = load_hook_module()
    log = logging.getLogger("t")
    for good in (".claude/**/__pycache__", "__pycache__/", "__pycache__"):
        assert ".claude/**/__pycache__" not in hook.check_missing_entries({good}, log)
