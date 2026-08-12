"""機器專屬絕對路徑偵測（承接 PC-BAL-029 預防措施）。

Why: ticket 以 `/Users/<name>/...` 記錄實測得到的環境事實，換機後全數解析
不到，而 `No such file or directory` 只描述結果不含成因——接手者最省力的
解釋是自己弄錯，不會懷疑 ticket。建票與認領當下即時提示，可在源頭攔截，
不需等到換機後由人工全量盤點。

設計：警告不阻擋（比照 spec_reference_checker / detect_srp_violations 的
輕量提示定位）。通用佔位符（/Users/me、/Users/<user> 等）不誤報，否則
說明文件裡的示例路徑會逐一觸發警告，使該警告很快被當雜訊忽略。
"""

import argparse

import yaml

from ticket_system.lib.machine_path_detector import (
    detect_machine_specific_paths,
    find_machine_specific_paths,
    scan_ticket_file_for_machine_paths,
)


# ============================================================
# 單元：find_machine_specific_paths 形態判定
# ============================================================


def test_detects_macos_user_path():
    assert find_machine_specific_paths("見 /Users/alice/project/x.md") == ["/Users/alice"]


def test_detects_linux_home_path():
    assert find_machine_specific_paths("cd /home/bob/repo") == ["/home/bob"]


def test_detects_windows_user_path():
    assert find_machine_specific_paths(r"C:\Users\carol\repo") == [r"C:\Users\carol"]


def test_deduplicates_and_preserves_first_seen_order():
    text = "/Users/zoe/a 與 /Users/adam/b 又見 /Users/zoe/c"
    assert find_machine_specific_paths(text) == ["/Users/zoe", "/Users/adam"]


def test_generic_placeholders_not_flagged():
    """說明文件的示例路徑不得誤報，否則警告會很快被當雜訊忽略。"""
    for placeholder in (
        "/Users/me/x", "/Users/x/y", "/Users/foo/bar", "/Users/dev/repo",
        "/Users/user/repo", "/Users/username/repo", "/Users/test/repo",
        "/Users/tester/repo", "/Users/xxx/repo", "/Users/youruser/repo",
        "/home/user/repo", "/Users/<user>/repo", "/Users/{user}/repo",
    ):
        assert find_machine_specific_paths(placeholder) == [], placeholder


def test_home_relative_and_project_relative_not_flagged():
    assert find_machine_specific_paths("~/.claude/skills/x") == []
    assert find_machine_specific_paths("docs/work-logs/v0/tickets/a.md") == []
    assert find_machine_specific_paths(".claude/hooks/foo.py") == []


def test_env_var_form_not_flagged():
    assert find_machine_specific_paths("$CLAUDE_PROJECT_DIR/.claude/hooks") == []
    assert find_machine_specific_paths("$HOME/.claude") == []


def test_bare_users_prefix_without_name_not_flagged():
    """`/Users/` 本身（無使用者名）不構成機器專屬路徑。"""
    assert find_machine_specific_paths("路徑格式為 /Users/ 開頭") == []
    assert find_machine_specific_paths("見 /home/ 底下") == []


def test_detects_bare_home_dir_in_prose():
    """散文中的裸家目錄（使用者名後接空格或標點）必須命中。

    記錄環境事實最常見的寫法就是這種形態——「實測在 HOME 為 /Users/alice
    的環境完成」——使用者名後面沒有路徑分隔符。漏掉它等於對本偵測的主要
    來源失效。
    """
    assert find_machine_specific_paths("實測在 HOME 為 /Users/alice 的環境完成") == [
        "/Users/alice"
    ]
    assert find_machine_specific_paths("當前環境 HOME 為 /Users/bob。") == ["/Users/bob"]
    assert find_machine_specific_paths("`$HOME=/home/carol`") == ["/home/carol"]
    assert find_machine_specific_paths("ls -d /Users/dave 回報不存在") == ["/Users/dave"]


def test_bare_home_dir_still_respects_placeholder_allowlist():
    """裸形態同樣套用佔位符白名單，不因放寬而引入誤報。"""
    assert find_machine_specific_paths("例如 HOME 為 /Users/me 時") == []
    assert find_machine_specific_paths("設 $HOME=/home/user 後") == []


def test_trailing_ascii_period_not_captured():
    """ASCII 句點結尾不得併入使用者名，否則佔位符白名單被繞過。

    `_is_generic` 取路徑最後一段比對白名單；若句點被吃進使用者名，
    `/Users/me.` 得到的是 `me.` 而非 `me`，白名單失效導致示例路徑誤報——
    正好打在本模組宣告的關鍵設計約束上。先前測資全用全形句號或斜線結尾，
    因此未暴露此缺口。
    """
    assert find_machine_specific_paths("例如 /Users/me.") == []
    assert find_machine_specific_paths("see /Users/alice.") == ["/Users/alice"]
    # 同一機器的兩種寫法必須去重為單一前綴
    assert find_machine_specific_paths("/Users/alice/a 與 /Users/alice.") == ["/Users/alice"]


def test_anonymized_ellipsis_form_not_flagged():
    """框架既有的匿名化省略號寫法 `/Users/.../x` 不得誤報。

    該形態是框架文件用來表示「任意使用者」的既有慣例（AGENT_PRELOAD、
    hook-specs 皆在用），語意上等同佔位符。
    """
    assert find_machine_specific_paths("路徑如 /Users/.../project/x") == []
    assert find_machine_specific_paths("/Users/...") == []


def test_placeholder_followed_by_angle_bracket_not_flagged():
    """`/Users/me-<name>` 不得取到 `me-` 而繞過白名單（尾端 `-` 同句點問題）。"""
    assert find_machine_specific_paths("路徑如 /Users/me-<name>/x") == []


def test_bracket_placeholders_excluded_at_regex_level():
    """角括號 / 大括號佔位在正則階段即不匹配，非靠白名單過濾。

    鎖住這個機制歸屬：若日後放寬字元集使 `<user>` 能匹配，本測項會紅燈，
    提醒白名單並未涵蓋該形態。
    """
    import re as _re

    module_re = _re.compile(
        find_machine_specific_paths.__globals__["_POSIX_RE"].pattern
    )
    assert module_re.findall("/Users/<user>/x") == []
    assert module_re.findall("/Users/{user}/x") == []
    assert module_re.findall("/Users/.../x") == []


def test_requires_left_boundary():
    """`/home/` 片段須位於路徑起點，不得由字串中段誤命中。"""
    assert find_machine_specific_paths("x/home/bob/y") == []
    assert find_machine_specific_paths("$PROJ/home/user2/x") == []
    # 真正的絕對路徑仍須命中
    assert find_machine_specific_paths("cd /home/bob/y") == ["/home/bob"]


# ============================================================
# 建票路徑：detect_machine_specific_paths(ticket_fields)
# ============================================================


def test_detect_scans_where_files():
    fields = {"where": {"layer": "待定義", "files": ["/Users/alice/repo/a.py"]}}
    warnings = detect_machine_specific_paths(fields)
    assert len(warnings) == 1
    assert "/Users/alice" in warnings[0]


def test_detect_scans_free_text_fields():
    fields = {
        "why": "實測 /Users/bob/.claude/skills 為空",
        "how": {"strategy": "讀 /home/carol/repo/x.md"},
    }
    warnings = detect_machine_specific_paths(fields)
    assert len(warnings) == 1
    assert "/Users/bob" in warnings[0]
    assert "/home/carol" in warnings[0]


def test_detect_scans_acceptance():
    fields = {"acceptance": ["[ ] 確認 /Users/dave/x 存在"]}
    warnings = detect_machine_specific_paths(fields)
    assert len(warnings) == 1
    assert "/Users/dave" in warnings[0]


def test_warning_states_rewrite_and_measurement_options():
    """警告須同時給出兩條處置路徑，否則讀者只會知道被禁止、不知道改成什麼。"""
    fields = {"why": "/Users/alice/x"}
    text = detect_machine_specific_paths(fields)[0]
    assert "~" in text
    assert "專案相對路徑" in text
    assert "量測環境" in text


def test_detect_returns_empty_for_clean_fields():
    fields = {
        "why": "改用 ~/.claude/skills 判定",
        "where": {"layer": "Domain", "files": ["lib/domain/x.dart"]},
        "acceptance": ["[ ] grep 計數為 0"],
    }
    assert detect_machine_specific_paths(fields) == []


def test_detect_handles_empty_and_malformed_input():
    """欄位缺失或型別異常時不得拋例外——本檢查不可成為建票失敗的來源。"""
    assert detect_machine_specific_paths({}) == []
    assert detect_machine_specific_paths({"where": "壓扁為 string 的舊格式"}) == []
    assert detect_machine_specific_paths({"acceptance": None}) == []
    assert detect_machine_specific_paths({"why": 123}) == []


# ============================================================
# 認領路徑：scan_ticket_file_for_machine_paths
# ============================================================


def _write_ticket(tmp_path, frontmatter, body=""):
    path = tmp_path / "ticket.md"
    path.write_text(
        "---\n" + yaml.dump(frontmatter, allow_unicode=True) + "---\n\n" + body,
        encoding="utf-8",
    )
    return path


def test_scan_file_detects_paths_in_frontmatter_and_body(tmp_path):
    path = _write_ticket(
        tmp_path,
        {"id": "1.0.0-W1-001", "where": {"files": ["/Users/erin/a.py"]}},
        body="# Execution Log\n\n見 /home/frank/notes.md\n",
    )
    warnings = scan_ticket_file_for_machine_paths(path)
    assert len(warnings) == 1
    assert "/Users/erin" in warnings[0]
    assert "/home/frank" in warnings[0]


def test_scan_file_clean_ticket_returns_empty(tmp_path):
    path = _write_ticket(
        tmp_path,
        {"id": "1.0.0-W1-002", "where": {"files": ["docs/a.md"]}},
        body="# Execution Log\n\n見 ~/.claude/skills\n",
    )
    assert scan_ticket_file_for_machine_paths(path) == []


def test_scan_file_missing_path_returns_empty(tmp_path):
    """檔案不存在或不可讀時回傳空清單，不拋例外（認領流程不可因此中斷）。"""
    assert scan_ticket_file_for_machine_paths(tmp_path / "nonexistent.md") == []


def test_scan_file_unreadable_returns_empty(tmp_path):
    import os
    import stat

    path = _write_ticket(tmp_path, {"id": "1.0.0-W1-003"}, body="/Users/gina/x\n")
    os.chmod(path, 0o000)
    try:
        assert scan_ticket_file_for_machine_paths(path) == []
    finally:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
