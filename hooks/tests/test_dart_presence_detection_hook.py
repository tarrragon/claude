"""
Test: dart-presence-detection hook（Ticket: 1.2.0-W1-017）

驗證 PreToolUse hook 對 .dart Edit/Write 偵測「應有設施缺席」三類：
  1. 硬編碼 user-facing 字串（排除 log/debug/assert/import/註解/annotation）
  2. 裸 Color() / Colors.xxx（非 theme token）
  3. 魔術數字字面（SizedBox/EdgeInsets/Duration/fontSize/BorderRadius）

並驗證 blocking-with-override 防呆：
  - override marker 豁免
  - 只掃變更內容（remediation 不被癱瘓）
  - warn 降級路徑（PRESENCE_HOOK_MODE=warn）

來源：1.2.0-W1-015 presence-blind 根因；ticket 防呆要求。
"""

import importlib.util
import io
import json
import os
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

_spec = importlib.util.spec_from_file_location(
    "dart_presence_hook",
    HOOKS_DIR / "dart-presence-detection-hook.py",
)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

detect_violations = _module.detect_violations
should_skip_file = _module.should_skip_file
is_dart_file = _module.is_dart_file
extract_changed_content = _module.extract_changed_content
main = _module.main


# ---------- 範圍判定 ----------

def test_is_dart_file():
    assert is_dart_file("app/lib/main.dart")
    assert not is_dart_file("server/main.go")
    assert not is_dart_file("README.md")


def test_skip_generated_and_test_files():
    assert should_skip_file("app/lib/foo.g.dart")
    assert should_skip_file("app/lib/bar.freezed.dart")
    assert should_skip_file("app/test/widget_test.dart")
    assert should_skip_file("app/lib/features/x_test.dart")
    assert should_skip_file("app/lib/l10n/app_localizations.dart")
    assert should_skip_file("app/lib/theme/ui_colors.dart")


def test_does_not_skip_normal_feature_file():
    assert not should_skip_file("app/lib/features/auth/login_screen.dart")


def test_skip_sink_definition_files():
    # 013/014 ANA 選定的集中化 sink 檔（app_*/terminal_* 命名）。
    # 常數定義本體不應被誤攔，否則 018/020 bootstrap 自身被阻塞。
    assert should_skip_file("app/lib/theme/app_spacing.dart")
    assert should_skip_file("app/lib/theme/app_typography.dart")
    assert should_skip_file("app/lib/features/terminal/terminal_constants.dart")


# ---------- 類別 1：硬編碼字串 ----------

def test_detect_cjk_user_facing_string():
    content = 'Text("登入失敗，請重試")'
    v = detect_violations(content)
    assert any(x["category"] == "i18n" for x in v)


def test_detect_english_sentence_string():
    content = 'Text("Login failed please retry")'
    v = detect_violations(content)
    assert any(x["category"] == "i18n" for x in v)


def test_string_in_log_excluded():
    content = 'logger.info("連線建立成功")'
    v = detect_violations(content)
    assert not any(x["category"] == "i18n" for x in v)


def test_string_in_debugprint_excluded():
    content = 'debugPrint("user tapped the retry button")'
    v = detect_violations(content)
    assert not any(x["category"] == "i18n" for x in v)


def test_string_in_assert_excluded():
    content = 'assert(token != null, "token must not be null here")'
    v = detect_violations(content)
    assert not any(x["category"] == "i18n" for x in v)


def test_import_string_excluded():
    content = "import 'package:flutter/material.dart';"
    v = detect_violations(content)
    assert not any(x["category"] == "i18n" for x in v)


def test_comment_string_excluded():
    content = '// 這是註解 "連線中"'
    v = detect_violations(content)
    assert not any(x["category"] == "i18n" for x in v)


def test_single_token_string_not_user_facing():
    # 'utf-8' 類單字 token 不應被當 user-facing
    content = "encoding: 'utf-8'"
    v = detect_violations(content)
    assert not any(x["category"] == "i18n" for x in v)


def test_string_in_argumenterror_excluded():
    # ArgumentError 訊息屬開發者面，非 user-facing（017 觀察過度偵測）
    content = 'throw ArgumentError("port must be a positive integer")'
    v = detect_violations(content)
    assert not any(x["category"] == "i18n" for x in v)


def test_string_in_tostring_excluded():
    # toString 內字串屬開發者除錯輸出，非 user-facing（017 觀察過度偵測）
    content = 'String toString() => "AuthState(status: $status)";'
    v = detect_violations(content)
    assert not any(x["category"] == "i18n" for x in v)


# ---------- 類別 2：裸 Color ----------

def test_detect_bare_color_hex():
    content = "color: Color(0xFF2196F3)"
    v = detect_violations(content)
    assert any(x["category"] == "color" for x in v)


def test_detect_colors_named():
    content = "color: Colors.blue"
    v = detect_violations(content)
    assert any(x["category"] == "color" for x in v)


def test_theme_token_color_not_flagged():
    content = "color: UIColors.primary"
    v = detect_violations(content)
    assert not any(x["category"] == "color" for x in v)


def test_colorscheme_color_not_flagged():
    content = "color: Theme.of(context).colorScheme.primary"
    v = detect_violations(content)
    assert not any(x["category"] == "color" for x in v)


# ---------- 類別 3：魔術數字 ----------

def test_detect_sizedbox_magic_number():
    content = "SizedBox(height: 16)"
    v = detect_violations(content)
    assert any(x["category"] == "magic-number" for x in v)


def test_detect_edgeinsets_magic_number():
    content = "padding: EdgeInsets.all(24)"
    v = detect_violations(content)
    assert any(x["category"] == "magic-number" for x in v)


def test_detect_fontsize_magic_number():
    content = "TextStyle(fontSize: 18)"
    v = detect_violations(content)
    assert any(x["category"] == "magic-number" for x in v)


def test_detect_duration_magic_number():
    content = "Duration(milliseconds: 300)"
    v = detect_violations(content)
    assert any(x["category"] == "magic-number" for x in v)


def test_uispacing_not_flagged():
    content = "SizedBox(height: UISpacing.medium)"
    v = detect_violations(content)
    assert not any(x["category"] == "magic-number" for x in v)


# ---------- 防呆：override marker ----------

def test_override_marker_same_line():
    content = 'Text("登入失敗") // i18n-exempt'
    v = detect_violations(content)
    assert not v


def test_override_marker_previous_line():
    content = '// color-exempt\ncolor: Colors.blue'
    v = detect_violations(content)
    assert not any(x["category"] == "color" for x in v)


def test_generic_presence_exempt_marker():
    content = "SizedBox(height: 16) // presence-exempt"
    v = detect_violations(content)
    assert not v


# ---------- 防呆：只掃變更內容 ----------

def test_extract_edit_uses_new_string_only():
    tool_input = {
        "file_path": "x.dart",
        "old_string": 'Text("登入失敗")',  # 舊問題不該被掃
        "new_string": "Text(l10n.loginFailed)",  # 新內容乾淨
    }
    changed = extract_changed_content("Edit", tool_input)
    assert changed == "Text(l10n.loginFailed)"
    assert not detect_violations(changed)


def test_extract_write_uses_content():
    tool_input = {"file_path": "x.dart", "content": "SizedBox(height: 8)"}
    changed = extract_changed_content("Write", tool_input)
    assert changed == "SizedBox(height: 8)"


def test_extract_multiedit_joins_new_strings():
    tool_input = {
        "edits": [
            {"old_string": "a", "new_string": "Colors.red"},
            {"old_string": "b", "new_string": "UIColors.primary"},
        ]
    }
    changed = extract_changed_content("MultiEdit", tool_input)
    v = detect_violations(changed)
    assert any(x["category"] == "color" for x in v)  # 只第一筆命中


# ---------- main() 整合：block / warn / allow ----------

def _run_main(stdin_payload, env=None):
    old_stdin = sys.stdin
    old_argv = sys.argv
    old_env = dict(os.environ)
    sys.stdin = io.StringIO(json.dumps(stdin_payload))
    sys.argv = ["dart-presence-detection-hook.py"]
    if env:
        os.environ.update(env)
    else:
        os.environ.pop("PRESENCE_HOOK_MODE", None)
    try:
        return main()
    finally:
        sys.stdin = old_stdin
        sys.argv = old_argv
        os.environ.clear()
        os.environ.update(old_env)


def test_main_blocks_on_violation_default_mode():
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": "app/lib/login.dart", "content": 'Text("登入失敗")'},
    }
    assert _run_main(payload) == 2


def test_main_warn_mode_does_not_block():
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": "app/lib/login.dart", "content": 'Text("登入失敗")'},
    }
    assert _run_main(payload, env={"PRESENCE_HOOK_MODE": "warn"}) == 0


def test_main_allows_clean_content():
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": "app/lib/login.dart", "content": "Text(l10n.loginFailed)"},
    }
    assert _run_main(payload) == 0


def test_main_skips_non_dart():
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": "server/main.go", "content": 'Text("登入失敗")'},
    }
    assert _run_main(payload) == 0


def test_main_skips_generated_dart():
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": "app/lib/x.g.dart", "content": 'Text("登入失敗")'},
    }
    assert _run_main(payload) == 0
