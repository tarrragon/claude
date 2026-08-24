#!/usr/bin/env python3
"""
pre-test-hook - 測試程式碼

涵蓋 check_dependencies() 的 pubspec.yaml / pubspec.lock mtime 容差比較
（0.2.1-W3-987）：同批寫入（如 git checkout）產生的毫秒級 mtime 順序差
不應誤報，真正過期（使用者編輯後未執行 pub get）仍須告警。
"""

import os
import sys
import time
from pathlib import Path

# 將 Hook 腳本路徑加入 sys.path
hook_dir = Path(__file__).parent.parent
sys.path.insert(0, str(hook_dir))

# 動態導入 Hook 模組（檔名含連字號，無法直接 import）
import importlib.util

spec = importlib.util.spec_from_file_location(
    "pre_test_hook_module",
    hook_dir / "pre-test-hook.py",
)
pre_test_hook_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pre_test_hook_module)

check_dependencies = pre_test_hook_module.check_dependencies
PUBSPEC_MTIME_TOLERANCE_SECONDS = pre_test_hook_module.PUBSPEC_MTIME_TOLERANCE_SECONDS


def _make_project(tmp_path: Path) -> Path:
    (tmp_path / ".dart_tool").mkdir()
    (tmp_path / ".dart_tool" / "package_config.json").write_text("{}")
    return tmp_path


def test_same_batch_write_does_not_warn(tmp_path):
    """Given yaml 與 lock 為同批寫入（毫秒級順序差）
    When 檢查依賴
    Then 不應告警（避免 git checkout 產生的假警告）"""
    project = _make_project(tmp_path)
    (project / "pubspec.lock").write_text("packages: {}\n")
    (project / "pubspec.yaml").write_text("name: x\n")

    lock_mtime = (project / "pubspec.lock").stat().st_mtime
    # 模擬 git checkout 依序寫入產生的毫秒級順序差（實測本專案為 0.34ms）
    os.utime(project / "pubspec.yaml", (lock_mtime + 0.0003, lock_mtime + 0.0003))

    warnings = check_dependencies(project)

    assert warnings == []


def test_actually_stale_yaml_warns(tmp_path):
    """Given yaml 比 lock 晚寫入超過容差（秒級差距，模擬使用者編輯後未 pub get）
    When 檢查依賴
    Then 應告警"""
    project = _make_project(tmp_path)
    (project / "pubspec.lock").write_text("packages: {}\n")
    lock_mtime = (project / "pubspec.lock").stat().st_mtime
    stale_mtime = lock_mtime + PUBSPEC_MTIME_TOLERANCE_SECONDS + 1
    (project / "pubspec.yaml").write_text("name: x\ndependencies:\n  foo: 2.0.0\n")
    os.utime(project / "pubspec.yaml", (stale_mtime, stale_mtime))

    warnings = check_dependencies(project)

    assert warnings == [pre_test_hook_module.ValidationMessages.PRE_TEST_PUBSPEC_OUTDATED]


def test_missing_lock_keeps_existing_behavior(tmp_path):
    """Given pubspec.lock 不存在
    When 檢查依賴
    Then 應回報 lock 缺失，不受本次容差變更影響"""
    project = tmp_path
    (project / "pubspec.yaml").write_text("name: x\n")

    warnings = check_dependencies(project)

    assert warnings == [pre_test_hook_module.ValidationMessages.PRE_TEST_PUBSPEC_LOCK_MISSING]
