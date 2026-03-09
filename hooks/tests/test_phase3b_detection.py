"""
Phase 3b 判斷邏輯測試案例

測試 task-dispatch-readiness-check.py 是否能正確識別 Phase 3b 任務
"""

import logging
from pathlib import Path
import importlib.util

# 動態導入 Hook 腳本
hooks_dir = Path(__file__).parent.parent
spec = importlib.util.spec_from_file_location(
    "task_dispatch_readiness_check",
    str(hooks_dir / "task-dispatch-readiness-check.py")
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_task_dispatch_readiness_module_loaded():
    """驗證 task-dispatch-readiness-check 模組正確載入"""
    assert hasattr(module, 'detect_task_type'), "detect_task_type 函式不存在"
    assert callable(module.detect_task_type), "detect_task_type 應為可呼叫函式"


def test_detect_task_type_signature():
    """驗證 detect_task_type 簽名符合預期"""
    import inspect
    sig = inspect.signature(module.detect_task_type)
    params = list(sig.parameters.keys())

    # 檢查必需的參數
    assert 'prompt' in params, "detect_task_type 應有 prompt 參數"
    assert 'config' in params, "detect_task_type 應有 config 參數"
    assert 'logger' in params, "detect_task_type 應有 logger 參數"
