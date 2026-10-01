"""hooks 測試包 rootdir conftest：載入 testpaths 覆蓋警告外掛。

命令列路徑未涵蓋 pyproject 全部 testpaths 時，pytest 終端摘要印警告（不改 exit code）。
單檔 / `::` 呼叫（hooks-test-gate）不警告。邏輯見 testpaths_coverage_warning.py。
"""

from testpaths_coverage_warning import (  # noqa: F401
    pytest_collection_modifyitems,
    pytest_terminal_summary,
)
