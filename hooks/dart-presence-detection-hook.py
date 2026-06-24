#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Dart Presence-Detection Hook —— dart profile 綁定 shim（PreToolUse on Edit / Write）

歷史：本 hook 原內含 .dart 專屬偵測規則。1.2.0-W1-036 將通用偵測引擎抽至
presence-detection-hook.py、語言規則抽至 .claude/config/presence_profiles.py，
本檔降為「dart profile 綁定 shim」——把通用引擎的 profile 參數固定為 dart profile，
對外維持原有 dart 介面（detect_violations(content) / should_skip_file(path) /
is_dart_file / extract_changed_content / main）1:1 不變。

為何保留本 shim 而非直接刪除：
  - 既有 34 個 dart 測試（test_dart_presence_detection_hook）以 (content) / (path)
    單參數呼叫並 import 本檔，shim 維持測試契約 1:1 不變。
settings.json 註冊已於 1.2.0-W1-036 改指向通用引擎 presence-detection-hook.py
（引擎依副檔名選 profile，.dart 自動取得 dart profile，runtime 行為等價）。
本檔保留 __main__ 入口供獨立執行 / 既有引用相容，新增語言無須改本檔。
"""

import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent))  # .claude/ — for `from lib import ...`
sys.path.insert(0, str(HOOKS_DIR.parent / "config"))

import importlib.util

from presence_profiles import _DART as _DART_PROFILE

# 載入通用引擎（檔名含連字號，無法直接 import，用 spec 載入）
_engine_spec = importlib.util.spec_from_file_location(
    "presence_detection_engine",
    HOOKS_DIR / "presence-detection-hook.py",
)
_engine = importlib.util.module_from_spec(_engine_spec)
_engine_spec.loader.exec_module(_engine)


def is_dart_file(file_path: str) -> bool:
    return file_path.endswith(".dart")


def should_skip_file(file_path: str) -> bool:
    """檔案是否在偵測範圍外（dart profile sink）。維持原單參數介面。"""
    return _engine.should_skip_file(file_path, _DART_PROFILE)


def detect_violations(content: str) -> list:
    """對變更內容掃描三類缺席（綁 dart profile）。維持原單參數介面。"""
    return _engine.detect_violations(content, _DART_PROFILE)


def extract_changed_content(tool_name: str, tool_input: dict) -> str:
    return _engine.extract_changed_content(tool_name, tool_input)


def build_block_message(file_path: str, violations: list) -> str:
    return _engine.build_block_message(file_path, violations)


# main() 直接委派通用引擎；引擎依副檔名選 profile，.dart 即取得 dart profile，
# 行為與原 dart hook 1:1（hook_name 在引擎內為 "presence-detection"）。
main = _engine.main


if __name__ == "__main__":
    from lib import run_hook_safely
    sys.exit(run_hook_safely(main, "dart-presence-detection"))
