"""file_lock.py 重複 top-level 定義防護回歸測試（ARCH-V1-002 / W1-086）。

Why（設計緣由）：
    W1-086 發現 file_lock.py 內 reap_stale_locks / _try_acquire_create_lock /
    create_id_allocation_lock 等函式各定義兩次（前套 FileLock 死碼被後套
    fcntl 活碼 shadow，Python 取最後 def）。根因為 overlay sync 文字層合併
    把兩套後端都保留（無文字衝突）。Python 靜默取最後定義，故重複定義不會
    報錯，但讓死碼長期潛伏並可能 shadow 預期實作（ARCH-V1-002）。

    本測試以 AST 掃描 file_lock.py 所有 module-level 函式/賦值名稱，斷言無
    重名，使「同名 top-level 定義唯一」成為可驗證契約，防止 overlay 合併
    或手動編輯重新引入重複定義。
"""

import ast
from collections import Counter
from pathlib import Path

FILE_LOCK_PATH = (
    Path(__file__).resolve().parents[1]
    / "ticket_system"
    / "lib"
    / "file_lock.py"
)


def _module_level_def_names(source: str) -> list[str]:
    """回傳模組頂層的函式、async 函式、類別與簡單賦值目標名稱清單。"""
    tree = ast.parse(source)
    names: list[str] = []
    for node in tree.body:
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            names.append(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.append(target.id)
    return names


def test_no_duplicate_top_level_definitions():
    """file_lock.py 內不得有重名的 top-level 定義（ARCH-V1-002 復發防護）。"""
    source = FILE_LOCK_PATH.read_text(encoding="utf-8")
    names = _module_level_def_names(source)
    duplicates = {
        name: count for name, count in Counter(names).items() if count > 1
    }
    assert not duplicates, (
        "file_lock.py 出現重複 top-level 定義（死碼 shadow 風險，"
        f"ARCH-V1-002）：{duplicates}"
    )


def test_critical_lock_functions_defined_once():
    """三個併發鎖核心函式各須恰好定義一次。"""
    source = FILE_LOCK_PATH.read_text(encoding="utf-8")
    names = Counter(_module_level_def_names(source))
    for fn in (
        "file_lock",
        "reap_stale_locks",
        "_try_acquire_create_lock",
        "create_id_allocation_lock",
    ):
        assert names[fn] == 1, f"{fn} 應恰好定義一次，實得 {names[fn]} 次"
