#!/usr/bin/env python3
"""測試 Hook 改善效果 - 完整測試套件"""

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

# 測試案例定義
test_cases = [
    {
        "id": "TC-001",
        "description": "Phase 2 任務誤判為 Phase 1",
        "prompt": """
基於 Phase 1 產出的功能設計規格，設計 Import Service 的測試案例。

參考文件：
- docs/work-logs/v0.12.7-subtask-4-import-service.md (Phase 1 產出)

執行 TDD Phase 2: 測試案例設計
""",
        "expected": "Phase 2 測試設計"
    },
    {
        "id": "TC-002",
        "description": "Hook 改善任務識別為 Hook 開發",
        "prompt": """
基於 Phase 1 完成的問題分析，實作 Hook 改善方案。

Phase 1 設計文件分析了三大根因問題。

執行 Phase 3b: basil-hook-architect 實作 Hook 腳本改善
""",
        "expected": "Hook 開發"
    },
    {
        "id": "TC-003",
        "description": "向後相容性 - 純 Phase 1 任務仍識別為 Phase 1",
        "prompt": """
設計 Import Service 的功能規格。

執行 TDD Phase 1: 功能設計
""",
        "expected": "Phase 1 設計"
    },
    {
        "id": "TC-004",
        "description": "Phase 4 重構任務正確識別",
        "prompt": """
基於 Phase 3 完成的實作，執行重構評估。

參考 Phase 3 產出的程式碼。

執行 TDD Phase 4: 重構評估
""",
        "expected": "Phase 4 重構"
    }
]

# 執行測試
passed = 0
failed = 0
results = []

print("=" * 60)
print("Hook 改善效果測試報告")
print("=" * 60)
print()

for test in test_cases:
    test_id = test["id"]
    description = test["description"]
    prompt = test["prompt"]
    expected = test["expected"]

    result = detect_task_type(prompt)
    is_pass = result == expected

    status = "✅ 通過" if is_pass else "❌ 失敗"
    results.append({
        "id": test_id,
        "description": description,
        "expected": expected,
        "actual": result,
        "status": status
    })

    if is_pass:
        passed += 1
    else:
        failed += 1

    print(f"{test_id}: {description}")
    print(f"  預期: {expected}")
    print(f"  實際: {result}")
    print(f"  {status}")
    print()

# 總結
print("=" * 60)
print(f"測試總結: {passed}/{len(test_cases)} 通過")
print("=" * 60)

if failed > 0:
    print()
    print("失敗案例詳情:")
    for r in results:
        if r["status"] == "❌ 失敗":
            print(f"  - {r['id']}: {r['description']}")
            print(f"    預期: {r['expected']}, 實際: {r['actual']}")

sys.exit(0 if failed == 0 else 1)
