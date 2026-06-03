#!/usr/bin/env python3
"""測試 Hook 改善效果 - TC-001"""

import sys
import os
import importlib.util

# 直接載入 Hook 腳本
hook_path = os.path.join(os.path.dirname(__file__), 'hooks', 'task-dispatch-readiness-check.py')
spec = importlib.util.spec_from_file_location("hook_module", hook_path)
hook_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook_module)

# 取得函式
detect_task_type = hook_module.detect_task_type

# TC-001: Phase 2 任務誤判為 Phase 1
prompt_tc001 = """
基於 Phase 1 產出的功能設計規格，設計 Import Service 的測試案例。

參考文件：
- docs/work-logs/v0.12.7-subtask-4-import-service.md (Phase 1 產出)

執行 TDD Phase 2: 測試案例設計
"""

result = detect_task_type(prompt_tc001)
print(f"TC-001 結果: {result}")
print(f"預期: Phase 2 測試設計")

if result == "Phase 2 測試設計":
    print("✅ TC-001 測試通過")
    sys.exit(0)
else:
    print("❌ TC-001 測試失敗")
    sys.exit(1)
