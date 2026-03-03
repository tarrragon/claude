#!/usr/bin/env python3
"""
Tests for command-entrance-gate-hook.py

測試命令入口驗證閘門 Hook 的阻塞式驗證功能。
"""

import json
import sys
import tempfile
from pathlib import Path
from io import StringIO
from unittest.mock import patch, MagicMock

# 導入要測試的模組
hook_dir = Path(__file__).parent.parent
sys.path.insert(0, str(hook_dir))

# 動態執行 Hook 檔案以載入函式
hook_file = hook_dir / "command-entrance-gate-hook.py"
with open(hook_file) as f:
    hook_code = f.read()

# 建立臨時命名空間並執行 Hook 程式碼
hook_namespace = {}
exec(hook_code, hook_namespace)

# 提取需要的函式
is_development_command = hook_namespace['is_development_command']
is_management_operation = hook_namespace['is_management_operation']
validate_ticket_has_decision_tree = hook_namespace['validate_ticket_has_decision_tree']
extract_ticket_status = hook_namespace['extract_ticket_status']
check_ticket_status = hook_namespace['check_ticket_status']
generate_hook_output = hook_namespace['generate_hook_output']


def test_is_development_command():
    """測試開發命令識別"""
    # 開發命令應返回 True
    assert is_development_command("實作新功能") is True
    assert is_development_command("修復 Bug") is True
    assert is_development_command("建立 Ticket") is True
    assert is_development_command("重構程式碼") is True

    # 非開發命令應返回 False
    assert is_development_command("查詢進度") is False
    assert is_development_command("這是什麼？") is False
    assert is_development_command("") is False
    assert is_development_command(None) is False

    print("[PASS] test_is_development_command")


def test_is_management_operation_dispatch_patterns():
    """測試管理操作識別 - 調度類詞彙"""
    # 調度類詞彙應返回 True
    assert is_management_operation("並行處理") is True
    assert is_management_operation("派發代理人") is True
    assert is_management_operation("繼續 W21") is True
    assert is_management_operation("序列派發") is True
    assert is_management_operation("開始處理") is True
    assert is_management_operation("恢復任務") is True
    assert is_management_operation("接手任務") is True

    print("[PASS] test_is_management_operation_dispatch_patterns")


def test_is_management_operation_short_answers():
    """測試管理操作識別 - 短回答白名單"""
    # 短回答應返回 True
    assert is_management_operation("是") is True
    assert is_management_operation("好") is True
    assert is_management_operation("確認") is True
    assert is_management_operation("同意") is True
    assert is_management_operation("ok") is True
    assert is_management_operation("yes") is True
    assert is_management_operation("y") is True
    assert is_management_operation("1") is True
    assert is_management_operation("2") is True
    assert is_management_operation("3") is True
    assert is_management_operation("對") is True
    assert is_management_operation("沒錯") is True

    # 含空白的短回答也應返回 True
    assert is_management_operation("  是  ") is True
    assert is_management_operation("  確認  ") is True

    # 較長的短回答應返回 False（長度 > 10）
    assert is_management_operation("是的沒錯確認同意") is False

    print("[PASS] test_is_management_operation_short_answers")


def test_validate_ticket_has_decision_tree():
    """測試決策樹欄位驗證"""
    # 有 decision_tree_path 應返回 True
    content_with_frontmatter = """---
id: 0.30.1-W2-002
title: 更新 command-entrance-gate-hook.py
decision_tree_path: /path/to/decision/tree
---
"""
    assert validate_ticket_has_decision_tree(content_with_frontmatter) is True

    # 有「## 決策樹」應返回 True
    content_with_section = """---
id: 0.30.1-W2-002
---

## 決策樹
[決策過程]
"""
    assert validate_ticket_has_decision_tree(content_with_section) is True

    # 有「## Decision Tree」應返回 True
    content_with_english = """## Decision Tree
Decision process here
"""
    assert validate_ticket_has_decision_tree(content_with_english) is True

    # 無決策樹應返回 False
    content_without = """---
id: 0.30.1-W2-002
---
無決策樹
"""
    assert validate_ticket_has_decision_tree(content_without) is False

    # 空內容應返回 False
    assert validate_ticket_has_decision_tree("") is False
    assert validate_ticket_has_decision_tree(None) is False

    print("[PASS] test_validate_ticket_has_decision_tree")


def test_extract_ticket_status():
    """測試 Ticket 狀態提取"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        ticket_content = """---
id: 0.30.1-W2-001
title: 測試 Ticket
status: in_progress
decision_tree_path: /path/to/tree
---

## 內容
Test content
"""
        f.write(ticket_content)
        f.flush()

        ticket_id, status, content = extract_ticket_status(Path(f.name))

        assert ticket_id == Path(f.name).stem
        assert status == "in_progress"
        assert content == ticket_content

        Path(f.name).unlink()

    print("[PASS] test_extract_ticket_status")


def test_generate_hook_output_blocking():
    """測試 Hook 輸出生成 - 阻塞情況"""
    # 開發命令但 Ticket 驗證失敗 → should_block = True
    output = generate_hook_output(
        prompt="實作新功能",
        is_dev_cmd=True,
        is_valid=False,
        error_msg="錯誤：未找到 Ticket",
        ticket_id=None
    )

    assert output["check_result"]["is_development_command"] is True
    assert output["check_result"]["ticket_validation_passed"] is False
    assert output["check_result"]["should_block"] is True
    assert output["check_result"]["exit_code"] == "EXIT_BLOCK"
    assert "錯誤：未找到 Ticket" in output["hookSpecificOutput"]["additionalContext"]

    print("[PASS] test_generate_hook_output_blocking")


def test_generate_hook_output_allowing():
    """測試 Hook 輸出生成 - 允許情況"""
    # 開發命令且 Ticket 驗證通過 → should_block = False
    output = generate_hook_output(
        prompt="實作新功能",
        is_dev_cmd=True,
        is_valid=True,
        error_msg=None,
        ticket_id="0.30.1-W2-001"
    )

    assert output["check_result"]["is_development_command"] is True
    assert output["check_result"]["ticket_validation_passed"] is True
    assert output["check_result"]["should_block"] is False
    assert output["check_result"]["exit_code"] == "EXIT_SUCCESS"
    assert "additionalContext" not in output["hookSpecificOutput"]

    print("[PASS] test_generate_hook_output_allowing")


def test_generate_hook_output_non_dev_command():
    """測試 Hook 輸出生成 - 非開發命令"""
    # 非開發命令 → 不檢查 Ticket，should_block = False
    output = generate_hook_output(
        prompt="查詢進度",
        is_dev_cmd=False,
        is_valid=True,  # 不被檢查
        error_msg=None,
        ticket_id=None
    )

    assert output["check_result"]["is_development_command"] is False
    assert output["check_result"]["should_block"] is False
    assert output["check_result"]["exit_code"] == "EXIT_SUCCESS"

    print("[PASS] test_generate_hook_output_non_dev_command")


def test_blocking_error_messages():
    """測試阻塞時的錯誤訊息清晰度"""
    # 測試無 Ticket 的錯誤訊息
    with tempfile.TemporaryDirectory() as tmpdir:
        # 模擬空的 Ticket 目錄
        project_path = Path(tmpdir)
        tickets_path = project_path / ".claude" / "tickets"
        tickets_path.mkdir(parents=True, exist_ok=True)

        with patch("os.getenv") as mock_getenv:
            def getenv_side_effect(key, default=None):
                if key == "CLAUDE_PROJECT_DIR":
                    return str(project_path)
                return default

            mock_getenv.side_effect = getenv_side_effect

            # 未找到 Ticket 的情況（check_ticket_status 返回 4 個值）
            is_valid, error_msg, ticket_id, relevance_warning = check_ticket_status()

            assert is_valid is False
            assert ticket_id is None
            assert error_msg is not None
            assert "未找到待處理的 Ticket" in error_msg
            assert "/ticket create" in error_msg
            assert "詳見" in error_msg

    print("[PASS] test_blocking_error_messages")


def run_all_tests():
    """執行所有測試"""
    print("開始執行 command-entrance-gate-hook 測試...\n")

    test_is_development_command()
    test_is_management_operation_dispatch_patterns()
    test_is_management_operation_short_answers()
    test_validate_ticket_has_decision_tree()
    test_extract_ticket_status()
    test_generate_hook_output_blocking()
    test_generate_hook_output_allowing()
    test_generate_hook_output_non_dev_command()
    test_blocking_error_messages()

    print("\n所有測試通過！")


if __name__ == "__main__":
    try:
        run_all_tests()
    except Exception as e:
        print(f"\n[FAIL] 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
