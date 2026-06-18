"""
Test: presence-detection 通用引擎 + language profile 機制（Ticket: 1.2.0-W1-036）

驗證 dart-presence hook 泛化為 language-pluggable 後：
  1. profile 載入機制：依副檔名選 profile（get_profile_for_path）
  2. no-op 路徑：無對應副檔名 profile → main 回 0、引擎不誤觸（安全上游關鍵）
  3. dart 行為不變：既有 dart 測試另檔 test_dart_presence_detection_hook 全綠（此處再驗引擎層）
  4. 第 2 profile（python）可擴充：CJK 字串 / 魔術數字偵測、無顏色概念跳過 color

來源：1.2.0-W1-036 泛化需求；1.2.0-W1-012 sync 評估（裸推會洩漏 Flutter 假設）。
"""

import importlib.util
import io
import json
import os
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = HOOKS_DIR.parent / "config"
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(CONFIG_DIR))

# 通用引擎（檔名含連字號）
_spec = importlib.util.spec_from_file_location(
    "presence_detection_engine",
    HOOKS_DIR / "presence-detection-hook.py",
)
_engine = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_engine)

import presence_profiles as profiles

detect_violations = _engine.detect_violations
should_skip_file = _engine.should_skip_file
extract_changed_content = _engine.extract_changed_content
main = _engine.main

get_profile_for_path = profiles.get_profile_for_path
DART = profiles._DART
PYTHON = profiles._PYTHON


# ---------- 1. profile 載入機制 ----------

def test_profile_selected_by_dart_extension():
    p = get_profile_for_path("app/lib/login.dart")
    assert p is not None and p.name == "dart"


def test_profile_selected_by_py_extension():
    p = get_profile_for_path("scripts/foo.py")
    assert p is not None and p.name == "python"


def test_no_profile_for_unknown_extension():
    assert get_profile_for_path("src/index.js") is None
    assert get_profile_for_path("server/main.go") is None
    assert get_profile_for_path("README.md") is None


def test_registry_indexes_all_extensions():
    # 每個 profile 的副檔名都應可被選到（registry 完整性）
    for profile in profiles.PROFILES:
        for ext in profile.extensions:
            assert get_profile_for_path("x" + ext) is profile


# ---------- 2. no-op 路徑（安全上游關鍵） ----------

def _run_main(stdin_payload, env=None):
    old_stdin, old_argv, old_env = sys.stdin, sys.argv, dict(os.environ)
    sys.stdin = io.StringIO(json.dumps(stdin_payload))
    sys.argv = ["presence-detection-hook.py"]
    if env:
        os.environ.update(env)
    else:
        os.environ.pop("PRESENCE_HOOK_MODE", None)
    try:
        return main()
    finally:
        sys.stdin, sys.argv = old_stdin, old_argv
        os.environ.clear()
        os.environ.update(old_env)


def test_main_noop_on_js_file_even_with_violation_text():
    # .js 無對應 profile：即使內容像硬編碼字串也 no-op（非 Flutter 專案不誤觸）
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": "src/app.js", "content": 'alert("登入失敗，請重試")'},
    }
    assert _run_main(payload) == 0


def test_main_noop_on_go_file():
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": "server/main.go", "content": 'fmt.Println("登入失敗，請重試")'},
    }
    assert _run_main(payload) == 0


# ---------- 3. dart 行為（引擎層再驗，與 shim 測試互補） ----------

def test_engine_dart_detects_cjk_string():
    v = detect_violations('Text("登入失敗，請重試")', DART)
    assert any(x["category"] == "i18n" for x in v)


def test_engine_dart_skip_sink_file():
    assert should_skip_file("app/lib/theme/app_spacing.dart", DART)


def test_main_blocks_dart_violation():
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": "app/lib/login.dart", "content": 'Text("登入失敗")'},
    }
    assert _run_main(payload) == 2


def test_main_warn_mode_dart():
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": "app/lib/login.dart", "content": 'Text("登入失敗")'},
    }
    assert _run_main(payload, env={"PRESENCE_HOOK_MODE": "warn"}) == 0


# ---------- 4. 第 2 profile（python）可擴充 ----------

def test_python_profile_detects_cjk_string():
    v = detect_violations('message = "登入失敗，請重試"', PYTHON)
    assert any(x["category"] == "i18n" for x in v)


def test_python_profile_excludes_comment():
    v = detect_violations('# 這是中文註解 "連線中"', PYTHON)
    assert not any(x["category"] == "i18n" for x in v)


def test_python_profile_excludes_logger():
    v = detect_violations('logger.info("連線建立成功")', PYTHON)
    assert not any(x["category"] == "i18n" for x in v)


def test_python_profile_detects_magic_sleep():
    v = detect_violations("time.sleep(30)", PYTHON)
    assert any(x["category"] == "magic-number" for x in v)


def test_python_profile_skips_color_class():
    # Python profile color_detect 留空：dart 會命中的 Color 字面在 python 下不偵測
    v = detect_violations("Color(0xFF2196F3)", PYTHON)
    assert not any(x["category"] == "color" for x in v)


def test_python_profile_override_marker():
    v = detect_violations('message = "登入失敗"  # i18n-exempt', PYTHON)
    assert not v


def test_main_blocks_python_violation():
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": "app/messages.py", "content": 'msg = "登入失敗，請重試"'},
    }
    assert _run_main(payload) == 2


def test_main_skips_python_test_file():
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": "tests/test_foo.py", "content": 'msg = "登入失敗，請重試"'},
    }
    assert _run_main(payload) == 0


# ---------- dogfooding 回歸（1.2.0-W1-036）：framework 自身 .py 不誤觸 ----------

def test_python_profile_skips_framework_hooks():
    # framework hook 含開發者面 CJK 字串（block 訊息組裝），非 application user-facing
    assert should_skip_file(".claude/hooks/foo.py", PYTHON)
    assert should_skip_file("/abs/.claude/hooks/foo.py", PYTHON)


def test_python_profile_skips_framework_skills_and_config():
    assert should_skip_file(".claude/skills/x/bar.py", PYTHON)
    assert should_skip_file(".claude/config/baz.py", PYTHON)


def test_python_profile_does_not_skip_application_py():
    # application 程式碼路徑不在 framework skip 範圍，仍會生效
    assert not should_skip_file("app/messages.py", PYTHON)


def test_main_skips_framework_hook_with_cjk_devstring():
    payload = {
        "tool_name": "Edit",
        "tool_input": {"file_path": ".claude/hooks/foo.py",
                       "new_string": 'lines.append("修復選項（擇一）：")'},
    }
    assert _run_main(payload) == 0
