#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
file-ownership-guard-hook 測試套件

測試覆蓋：
- 路徑規範化（normailize_path）
- Ticket ID 提取（extract_ticket_id）
- 觸發條件（is_valid_trigger）
- 衝突偵測（detect_path_conflicts, find_file_ownership_conflicts）
- 訊息格式化（format_conflict_warning）
- Hook 生命週期（main）
"""

import json
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch
from tempfile import TemporaryDirectory
import importlib.util

import pytest

# 設定路徑並動態導入（檔案名含 dash）
hooks_path = Path(__file__).parent.parent
hook_file = hooks_path / "file-ownership-guard-hook.py"
spec = importlib.util.spec_from_file_location("file_ownership_guard_hook", hook_file)
file_ownership_guard_hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(file_ownership_guard_hook)

# 從導入的模組提取符號
normalize_path = file_ownership_guard_hook.normalize_path
extract_ticket_id = file_ownership_guard_hook.extract_ticket_id
is_valid_trigger = file_ownership_guard_hook.is_valid_trigger
detect_path_conflicts = file_ownership_guard_hook.detect_path_conflicts
find_file_ownership_conflicts = file_ownership_guard_hook.find_file_ownership_conflicts
format_conflict_warning = file_ownership_guard_hook.format_conflict_warning
get_active_tickets = file_ownership_guard_hook.get_active_tickets
_extract_version_wave = file_ownership_guard_hook._extract_version_wave
ConflictInfo = file_ownership_guard_hook.ConflictInfo
TicketInfo = file_ownership_guard_hook.TicketInfo
CONFLICT_TYPE_BROTHER = file_ownership_guard_hook.CONFLICT_TYPE_BROTHER
CONFLICT_TYPE_UNRELATED = file_ownership_guard_hook.CONFLICT_TYPE_UNRELATED
CONFLICT_TYPE_PARENT = file_ownership_guard_hook.CONFLICT_TYPE_PARENT
DEFAULT_OUTPUT = file_ownership_guard_hook.DEFAULT_OUTPUT
HOOK_NAME = file_ownership_guard_hook.HOOK_NAME


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_project_root(tmp_path):
    """建立臨時項目根目錄結構"""
    tickets_dir = tmp_path / "docs" / "work-logs" / "v0.1.2" / "tickets"
    tickets_dir.mkdir(parents=True)
    (tmp_path / ".claude" / "hooks").mkdir(parents=True)
    (tmp_path / ".claude" / "skills" / "ticket" / "ticket_system").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def mock_logger():
    """建立 Mock logger"""
    logger = MagicMock()
    return logger


@pytest.fixture
def make_ticket_yaml():
    """建立 Ticket YAML frontmatter 的工廠函式"""
    def _factory(
        ticket_id,
        where_files=None,
        status="pending",
        parent_id=None,
    ):
        # 格式化 where.files 為 YAML 清單格式
        if where_files:
            files_yaml = "\n".join([f"    - {f}" for f in where_files])
            where_section = f"""where:
  files:
{files_yaml}"""
        else:
            where_section = """where:
  files: []"""

        parent_section = f"\nparent_id: {parent_id}" if parent_id else ""

        return f"""---
id: {ticket_id}
title: Test Ticket {ticket_id}
type: IMP
status: {status}
created: 2026-03-24
updated: 2026-03-24
{where_section}{parent_section}
---

# {ticket_id}

Test content
"""

    return _factory


@pytest.fixture
def make_ticket_file(make_ticket_yaml):
    """在臨時目錄建立 Ticket 檔案"""
    def _factory(
        temp_root,
        ticket_id,
        where_files=None,
        status="pending",
        parent_id=None,
    ):
        tickets_dir = temp_root / "docs" / "work-logs" / "v0.1.2" / "tickets"
        ticket_file = tickets_dir / f"{ticket_id}.md"

        yaml_content = make_ticket_yaml(
            ticket_id=ticket_id,
            where_files=where_files,
            status=status,
            parent_id=parent_id,
        )

        ticket_file.write_text(yaml_content)
        return ticket_file

    return _factory


# ============================================================================
# 測試：路徑規範化
# ============================================================================

class TestNormalizePath:
    """normalize_path 函式測試"""

    def test_backslash_to_slash(self):
        """Windows 路徑分隔符轉換"""
        assert normalize_path("lib\\create.py") == "lib/create.py"
        assert normalize_path("lib\\\\create.py") == "lib/create.py"

    def test_remove_double_slashes(self):
        """簡化多重斜線"""
        assert normalize_path("lib//create.py") == "lib/create.py"
        assert normalize_path("lib///create.py") == "lib/create.py"

    def test_remove_dot_slash_prefix(self):
        """移除 ./ 前綴"""
        assert normalize_path("./lib/create.py") == "lib/create.py"
        assert normalize_path("././lib/create.py") == "lib/create.py"

    def test_remove_trailing_slash(self):
        """移除目錄尾斜線"""
        assert normalize_path("lib/") == "lib"
        assert normalize_path("lib/create.py/") == "lib/create.py"

    def test_lowercase(self):
        """轉為小寫"""
        assert normalize_path("Lib/Create.py") == "lib/create.py"
        assert normalize_path("LIB/CREATE.PY") == "lib/create.py"

    def test_combined_rules(self):
        """多個規則組合"""
        assert normalize_path(".\\Lib//Create.py/") == "lib/create.py"

    def test_empty_string(self):
        """空字串不崩潰"""
        assert normalize_path("") == ""
        assert normalize_path(None) == ""

    # ========================================================================
    # 新增：.. 路徑遍歷防護測試（Stack Pop 策略）
    # ========================================================================

    def test_parent_directory_single_level(self):
        """單層 .. 遍歷：a/../b → b"""
        assert normalize_path("a/../b") == "b"

    def test_parent_directory_leading(self):
        """前綴 .. 遍歷：../config → config"""
        assert normalize_path("../config") == "config"

    def test_parent_directory_multiple_levels(self):
        """多層 .. 遍歷：a/b/../../c → c"""
        assert normalize_path("a/b/../../c") == "c"

    def test_parent_directory_nested(self):
        """巢狀 .. 遍歷：a/b/../c/d/../../e → a/e"""
        assert normalize_path("a/b/../c/d/../../e") == "a/e"

    def test_parent_directory_excessive(self):
        """超過路徑深度的 .. 遍歷：../../../a → a"""
        assert normalize_path("../../../a") == "a"

    def test_parent_directory_with_dot_slash(self):
        """.. 與 ./ 組合：./a/../b → b"""
        assert normalize_path("./a/../b") == "b"

    def test_parent_directory_preserves_other_rules(self):
        """.. 遍歷與其他規則組合：.\\A\\..//B/"""
        assert normalize_path(".\\A\\..//B/") == "b"


# ============================================================================
# 測試：Ticket ID 提取
# ============================================================================

class TestExtractTicketId:
    """extract_ticket_id 函式測試"""

    def test_extract_from_target_id(self):
        """提取 toolInput.target_id"""
        input_data = {
            "toolInput": {"target_id": "0.1.2-W2-003"}
        }
        assert extract_ticket_id(input_data) == "0.1.2-W2-003"

    def test_extract_from_ticket_id(self):
        """提取 toolInput.ticket_id"""
        input_data = {
            "toolInput": {"ticket_id": "0.1.2-W2-001"}
        }
        assert extract_ticket_id(input_data) == "0.1.2-W2-001"

    def test_reject_invalid_format(self):
        """拒絕非法 Ticket ID 格式"""
        input_data = {
            "toolInput": {"target_id": "invalid-id"}
        }
        assert extract_ticket_id(input_data) is None

    def test_no_tool_input(self):
        """無 toolInput 欄位"""
        input_data = {}
        assert extract_ticket_id(input_data) is None

    def test_empty_input(self):
        """空輸入"""
        assert extract_ticket_id(None) is None
        assert extract_ticket_id({}) is None


# ============================================================================
# 測試：觸發條件
# ============================================================================

class TestIsValidTrigger:
    """is_valid_trigger 函式測試"""

    def test_valid_trigger(self):
        """PreToolUse + Agent"""
        input_data = {
            "hookEventName": "PreToolUse",
            "toolName": "Agent",
        }
        assert is_valid_trigger(input_data) is True

    def test_invalid_event_name(self):
        """事件名稱不符"""
        input_data = {
            "hookEventName": "PostToolUse",
            "toolName": "Agent",
        }
        assert is_valid_trigger(input_data) is False

    def test_invalid_tool_name(self):
        """工具名稱不符"""
        input_data = {
            "hookEventName": "PreToolUse",
            "toolName": "Bash",
        }
        assert is_valid_trigger(input_data) is False

    def test_empty_input_is_invalid(self):
        """空輸入"""
        assert is_valid_trigger(None) is False
        assert is_valid_trigger({}) is False


# ============================================================================
# 測試：路徑衝突偵測
# ============================================================================

class TestDetectPathConflicts:
    """detect_path_conflicts 函式測試"""

    def test_identical_paths(self):
        """完全相同的路徑"""
        where = ["lib/create.py"]
        other = ["lib/create.py"]
        assert detect_path_conflicts(where, other) == ["lib/create.py"]

    def test_parent_to_child(self):
        """父目錄 → 子檔案（已規範化路徑）"""
        where = ["lib"]
        other = ["lib/create.py"]
        assert detect_path_conflicts(where, other) == ["lib"]

    def test_child_to_parent(self):
        """子檔案 ← 父目錄（已規範化路徑）"""
        where = ["lib/create.py"]
        other = ["lib"]
        assert detect_path_conflicts(where, other) == ["lib/create.py"]

    def test_no_conflicts(self):
        """完全獨立（已規範化路徑）"""
        where = ["lib"]
        other = [".claude/hooks"]
        assert detect_path_conflicts(where, other) == []

    def test_partial_conflicts(self):
        """多個檔案，部分衝突"""
        where = ["lib/create.py", ".claude/hooks/hook.py", "docs/readme.md"]
        other = ["lib/create.py", ".claude/skills/skill.py"]
        conflicts = detect_path_conflicts(where, other)
        assert "lib/create.py" in conflicts
        assert ".claude/hooks/hook.py" not in conflicts


# ============================================================================
# 測試：版本 Wave 提取
# ============================================================================

class TestExtractVersionWave:
    """_extract_version_wave 函式測試"""

    def test_extract_normal(self):
        """提取版本和 Wave"""
        version, wave = _extract_version_wave("0.1.2-W2-003")
        assert version == "0.1.2"
        assert wave == 2

    def test_extract_with_subtask(self):
        """多層序號"""
        version, wave = _extract_version_wave("0.1.2-W3-001.1.2")
        assert version == "0.1.2"
        assert wave == 3

    def test_extract_invalid_format(self):
        """非法格式"""
        version, wave = _extract_version_wave("invalid-id")
        assert version is None
        assert wave is None


# ============================================================================
# 測試：Ticket 讀取與篩選
# ============================================================================

class TestGetActiveTickets:
    """get_active_tickets 函式測試"""

    def test_no_other_ticket_in_wave(self, temp_project_root, make_ticket_file, mock_logger):
        """無同 Wave 其他活躍 Ticket"""
        make_ticket_file(temp_project_root, "0.1.2-W2-001", where_files=["lib/create.py"])

        result = get_active_tickets("0.1.2-W2-001", temp_project_root, mock_logger)
        assert result == []

    def test_filter_same_wave(self, temp_project_root, make_ticket_file, mock_logger):
        """篩選同 Wave 的 Ticket"""
        make_ticket_file(temp_project_root, "0.1.2-W2-001", where_files=["lib/create.py"])
        make_ticket_file(temp_project_root, "0.1.2-W2-002", where_files=["lib/delete.py"])

        result = get_active_tickets("0.1.2-W2-001", temp_project_root, mock_logger)
        assert len(result) == 1
        assert result[0].ticket_id == "0.1.2-W2-002"

    def test_filter_active_status(self, temp_project_root, make_ticket_file, mock_logger):
        """篩選活躍狀態"""
        make_ticket_file(
            temp_project_root, "0.1.2-W2-001",
            where_files=["lib/create.py"], status="pending"
        )
        make_ticket_file(
            temp_project_root, "0.1.2-W2-002",
            where_files=["lib/delete.py"], status="completed"
        )

        result = get_active_tickets("0.1.2-W2-001", temp_project_root, mock_logger)
        assert len(result) == 0

    def test_normalize_paths(self, temp_project_root, make_ticket_file, mock_logger):
        """where.files 規範化"""
        make_ticket_file(temp_project_root, "0.1.2-W2-001", where_files=["lib/create.py"])
        make_ticket_file(
            temp_project_root, "0.1.2-W2-002",
            where_files=["./Lib/Delete.py"], status="pending"
        )

        result = get_active_tickets("0.1.2-W2-001", temp_project_root, mock_logger)
        assert len(result) == 1
        assert result[0].where_files == ["lib/delete.py"]


# ============================================================================
# 測試：主衝突檢查函式
# ============================================================================

class TestFindFileOwnershipConflicts:
    """find_file_ownership_conflicts 函式測試"""

    def test_no_conflicts(self, temp_project_root, make_ticket_file, mock_logger):
        """無衝突情況"""
        make_ticket_file(temp_project_root, "0.1.2-W2-001", where_files=["lib/create.py"])
        make_ticket_file(temp_project_root, "0.1.2-W2-002", where_files=[".claude/hooks/hook.py"])

        result = find_file_ownership_conflicts("0.1.2-W2-001", temp_project_root, mock_logger)
        assert result == []

    def test_unrelated_ticket_conflicts(self, temp_project_root, make_ticket_file, mock_logger):
        """無關 Ticket 衝突"""
        make_ticket_file(temp_project_root, "0.1.2-W2-001", where_files=["lib/create.py"])
        make_ticket_file(
            temp_project_root, "0.1.2-W2-002",
            where_files=["lib/create.py"], status="pending"
        )

        result = find_file_ownership_conflicts("0.1.2-W2-001", temp_project_root, mock_logger)
        assert len(result) == 1
        assert result[0].conflicting_ticket_id == "0.1.2-W2-002"
        assert result[0].conflict_type == CONFLICT_TYPE_UNRELATED

    def test_brother_ticket_conflicts(self, temp_project_root, make_ticket_file, mock_logger):
        """兄弟 Ticket 衝突（同父）"""
        make_ticket_file(temp_project_root, "0.1.2-W2-001", where_files=["lib/create.py"])
        make_ticket_file(
            temp_project_root, "0.1.2-W2-001.1",
            where_files=["lib/create.py"], status="pending", parent_id="0.1.2-W2-001"
        )
        make_ticket_file(
            temp_project_root, "0.1.2-W2-001.2",
            where_files=["lib/create.py"], status="pending", parent_id="0.1.2-W2-001"
        )

        result = find_file_ownership_conflicts("0.1.2-W2-001.1", temp_project_root, mock_logger)
        assert len(result) == 1
        assert result[0].conflicting_ticket_id == "0.1.2-W2-001.2"
        assert result[0].conflict_type == CONFLICT_TYPE_BROTHER

    def test_parent_child_overlap_filtered(self, temp_project_root, make_ticket_file, mock_logger):
        """父子重疊不報警"""
        make_ticket_file(temp_project_root, "0.1.2-W2-001", where_files=["lib/create.py"])
        make_ticket_file(
            temp_project_root, "0.1.2-W2-001.1",
            where_files=["lib/create.py"], status="pending", parent_id="0.1.2-W2-001"
        )

        result = find_file_ownership_conflicts("0.1.2-W2-001.1", temp_project_root, mock_logger)
        # 親子關係會被檢出但標記為 is_parent_child=True
        # main() 中會篩選掉
        assert len(result) == 1
        assert result[0].is_parent_child is True


# ============================================================================
# 測試：訊息格式化
# ============================================================================

class TestFormatConflictWarning:
    """format_conflict_warning 函式測試"""

    def test_no_conflicts_returns_empty(self):
        """無衝突返回空字串"""
        result = format_conflict_warning("0.1.2-W2-001", [])
        assert result == ""

    def test_message_structure_complete(self):
        """訊息結構包含必要部分"""
        conflict = ConflictInfo(
            target_ticket_id="0.1.2-W2-001",
            conflicting_ticket_id="0.1.2-W2-002",
            conflicting_files=["lib/create.py"],
            is_parent_child=False,
            conflict_type=CONFLICT_TYPE_UNRELATED,
        )

        result = format_conflict_warning("0.1.2-W2-001", [conflict])

        # 檢查必要部分
        assert "0.1.2-W2-001" in result
        assert "0.1.2-W2-002" in result
        assert "lib/create.py" in result
        assert "A" in result
        assert "B" in result
        assert "============" in result

    def test_message_length_limit(self):
        """訊息長度控制在 2000 字元以內"""
        conflicts = [
            ConflictInfo(
                target_ticket_id="0.1.2-W2-001",
                conflicting_ticket_id=f"0.1.2-W2-{i:03d}",
                conflicting_files=[f"file{i}.py"],
                is_parent_child=False,
                conflict_type=CONFLICT_TYPE_UNRELATED,
            )
            for i in range(100)
        ]

        result = format_conflict_warning("0.1.2-W2-001", conflicts)
        assert len(result) <= 2100  # 允許 100 字元緩衝


# ============================================================================
# 測試：整合測試（Hook 生命週期）
# ============================================================================

class TestHookIntegration:
    """Hook 生命週期整合測試"""

    def test_silent_pass_without_conflicts(self, temp_project_root, capsys):
        """無衝突情況靜默通過"""
        main = file_ownership_guard_hook.main

        with patch.object(file_ownership_guard_hook, 'setup_hook_logging') as mock_setup_logging, \
             patch.object(file_ownership_guard_hook, 'read_json_from_stdin') as mock_read_stdin, \
             patch.object(file_ownership_guard_hook, 'get_project_root') as mock_get_root:

            # Setup mocks
            mock_logger = MagicMock()
            mock_setup_logging.return_value = mock_logger

            mock_read_stdin.return_value = {
                "hookEventName": "PreToolUse",
                "toolName": "Agent",
                "toolInput": {"target_id": "0.1.2-W2-001"},
            }

            mock_get_root.return_value = temp_project_root

            # Create Ticket without conflicts
            tickets_dir = temp_project_root / "docs" / "work-logs" / "v0.1.2" / "tickets"
            ticket_file = tickets_dir / "0.1.2-W2-001.md"
            ticket_file.write_text("""---
id: 0.1.2-W2-001
status: pending
where:
  files: ["lib/create.py"]
---
""")

            # Exec hook
            result = main()

            # Verify
            assert result == 0
            captured = capsys.readouterr()
            output = json.loads(captured.out)
            assert output == DEFAULT_OUTPUT

    def test_invalid_trigger_silent_exit(self, capsys):
        """非目標觸發靜默退出"""
        main = file_ownership_guard_hook.main

        with patch.object(file_ownership_guard_hook, 'setup_hook_logging') as mock_setup_logging, \
             patch.object(file_ownership_guard_hook, 'read_json_from_stdin') as mock_read_stdin:

            mock_logger = MagicMock()
            mock_setup_logging.return_value = mock_logger

            mock_read_stdin.return_value = {
                "hookEventName": "PostToolUse",  # 不是 PreToolUse
                "toolName": "Agent",
            }

            result = main()

            assert result == 0
            captured = capsys.readouterr()
            output = json.loads(captured.out)
            assert output == DEFAULT_OUTPUT


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
