"""
Agent Ticket Validation Hook - 白名單豁免與驗證測試（W17-046.1）

對應 Ticket 0.18.0-W17-046.1 AC：
- TICKET_EXEMPT_AGENT_TYPES 新增 claude-code-guide/general-purpose/Plan/feature-dev:code-explorer
- 每個白名單 agent type（5 個）派發時豁免，即使無 Ticket ID 也允許
- 非白名單 agent type（如 thyme-python-developer）派發仍要求 Ticket ID
- 既有行為保留：有 Ticket ID 時正常驗證（有效允許、無效拒絕）
- Handoff 恢復模式豁免邏輯不受影響（regression guard）
"""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ============================================================================
# Module 載入與共用 fixtures
# ============================================================================

_HOOKS_DIR = Path(__file__).parent.parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))


@pytest.fixture
def hook_module():
    """動態載入 agent-ticket-validation-hook 模組（檔名含連字號）"""
    spec = importlib.util.spec_from_file_location(
        "agent_ticket_validation_hook",
        _HOOKS_DIR / "agent-ticket-validation-hook.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mock_logger():
    """建立模擬 Logger"""
    logger = MagicMock()
    logger.debug = MagicMock()
    logger.info = MagicMock()
    logger.warning = MagicMock()
    logger.error = MagicMock()
    logger.critical = MagicMock()
    return logger


# 白名單中所有應豁免的 agent type（W17-046.1 擴充後）
EXEMPT_AGENT_TYPES = [
    "Explore",
    "claude-code-guide",
    "general-purpose",
    "Plan",
    "feature-dev:code-explorer",
]

# 非白名單 agent type（應要求 Ticket ID）
NON_EXEMPT_AGENT_TYPES = [
    "thyme-python-developer",
    "parsley-flutter-developer",
    "rosemary-project-manager",
    "bay-quality-auditor",
    "basil-hook-architect",
]


# ============================================================================
# 白名單常數測試（結構驗證）
# ============================================================================

class TestWhitelistConstant:
    """驗證 TICKET_EXEMPT_AGENT_TYPES 常數包含預期的 agent type"""

    def test_whitelist_contains_all_five_exempt_types(self, hook_module):
        """白名單應包含 5 個情報蒐集類 agent type"""
        whitelist = hook_module.TICKET_EXEMPT_AGENT_TYPES
        assert len(whitelist) == 5, (
            "白名單應恰好包含 5 個項目（Explore + 4 個新增）；"
            "若超過 10 應考慮升級為動態分類（見 Hook 註解）"
        )

    @pytest.mark.parametrize("agent_type", EXEMPT_AGENT_TYPES)
    def test_whitelist_contains_expected_agent_type(self, hook_module, agent_type):
        """每個預期的豁免 agent type 都在白名單中"""
        assert agent_type in hook_module.TICKET_EXEMPT_AGENT_TYPES

    def test_explore_is_preserved(self, hook_module):
        """Explore 豁免（既有）必須保留，避免 regression"""
        assert "Explore" in hook_module.TICKET_EXEMPT_AGENT_TYPES


# ============================================================================
# is_exempt_agent_type 函式測試
# ============================================================================

class TestIsExemptAgentType:
    """is_exempt_agent_type 函式的單元測試"""

    @pytest.mark.parametrize("agent_type", EXEMPT_AGENT_TYPES)
    def test_whitelisted_agent_returns_true(self, hook_module, mock_logger, agent_type):
        """白名單內的 agent type 應回傳 True"""
        assert hook_module.is_exempt_agent_type(agent_type, mock_logger) is True

    @pytest.mark.parametrize("agent_type", NON_EXEMPT_AGENT_TYPES)
    def test_non_whitelisted_agent_returns_false(self, hook_module, mock_logger, agent_type):
        """非白名單的 agent type 應回傳 False"""
        assert hook_module.is_exempt_agent_type(agent_type, mock_logger) is False

    def test_empty_agent_type_returns_false(self, hook_module, mock_logger):
        """空字串應回傳 False"""
        assert hook_module.is_exempt_agent_type("", mock_logger) is False

    def test_none_agent_type_returns_false(self, hook_module, mock_logger):
        """None 應回傳 False（防禦性處理）"""
        assert hook_module.is_exempt_agent_type(None, mock_logger) is False

    def test_whitelisted_logs_info(self, hook_module, mock_logger):
        """豁免成功時應記錄 info 日誌"""
        hook_module.is_exempt_agent_type("claude-code-guide", mock_logger)
        mock_logger.info.assert_called()


# ============================================================================
# validate_task_dispatch 派發驗證整合測試
# ============================================================================

class TestValidateTaskDispatchExemption:
    """驗證白名單 agent 即使無 Ticket ID 也允許派發"""

    @pytest.mark.parametrize("agent_type", EXEMPT_AGENT_TYPES)
    def test_exempt_agent_without_ticket_id_allowed(self, hook_module, mock_logger, agent_type):
        """白名單 agent 無 Ticket ID 時應允許派發"""
        tool_input = {
            "prompt": "請分析專案架構並提供建議",  # 無 Ticket ID
            "subagent_type": agent_type,
        }
        # is_handoff_recovery_mode 需 mock 回 False，確保走豁免分支
        with patch.object(hook_module, "is_handoff_recovery_mode", return_value=False):
            is_valid, error_msg, ticket_id = hook_module.validate_task_dispatch(
                tool_input, mock_logger
            )
        assert is_valid is True, f"白名單 agent '{agent_type}' 應豁免"
        assert error_msg is None
        assert ticket_id is None  # 豁免路徑不提取 ticket_id

    @pytest.mark.parametrize("agent_type", EXEMPT_AGENT_TYPES)
    def test_exempt_agent_with_ticket_id_still_allowed(self, hook_module, mock_logger, agent_type):
        """白名單 agent 即使附上 Ticket ID 仍豁免（豁免優先於驗證）"""
        tool_input = {
            "prompt": "Ticket: 0.18.0-W17-046.1\n請分析並實作",
            "subagent_type": agent_type,
        }
        with patch.object(hook_module, "is_handoff_recovery_mode", return_value=False):
            is_valid, error_msg, ticket_id = hook_module.validate_task_dispatch(
                tool_input, mock_logger
            )
        # 豁免路徑在 ticket 提取之前，因此 ticket_id 不應被提取
        assert is_valid is True
        assert error_msg is None
        assert ticket_id is None


class TestValidateTaskDispatchNonExempt:
    """驗證非白名單 agent 仍須引用有效 Ticket ID"""

    @pytest.mark.parametrize("agent_type", NON_EXEMPT_AGENT_TYPES)
    def test_non_exempt_agent_without_ticket_id_denied(self, hook_module, mock_logger, agent_type):
        """非白名單 agent 無 Ticket ID 應被拒絕"""
        tool_input = {
            "prompt": "請實作功能 X",  # 無 Ticket ID
            "subagent_type": agent_type,
        }
        with patch.object(hook_module, "is_handoff_recovery_mode", return_value=False):
            is_valid, error_msg, ticket_id = hook_module.validate_task_dispatch(
                tool_input, mock_logger
            )
        assert is_valid is False, f"非白名單 agent '{agent_type}' 無 Ticket 應被擋"
        assert error_msg is not None
        assert "Ticket" in error_msg
        assert ticket_id is None

    def test_non_exempt_agent_with_valid_ticket_id_allowed(self, hook_module, mock_logger):
        """非白名單 agent 附有效 Ticket ID 應允許"""
        tool_input = {
            "prompt": "Ticket: 0.18.0-W17-046.1\n請實作",
            "subagent_type": "thyme-python-developer",
        }
        # Mock 掉 handoff 檢查 + validate_ticket 回成功
        with patch.object(hook_module, "is_handoff_recovery_mode", return_value=False), \
             patch.object(hook_module, "validate_ticket", return_value=(True, None)):
            is_valid, error_msg, ticket_id = hook_module.validate_task_dispatch(
                tool_input, mock_logger
            )
        assert is_valid is True
        assert error_msg is None
        assert ticket_id == "0.18.0-W17-046.1"

    def test_non_exempt_agent_with_invalid_ticket_id_denied(self, hook_module, mock_logger):
        """非白名單 agent 附無效 Ticket ID 應被拒絕"""
        tool_input = {
            "prompt": "Ticket: 9.99.9-W999-999\n實作",
            "subagent_type": "thyme-python-developer",
        }
        with patch.object(hook_module, "is_handoff_recovery_mode", return_value=False), \
             patch.object(hook_module, "validate_ticket", return_value=(False, "找不到 Ticket")):
            is_valid, error_msg, ticket_id = hook_module.validate_task_dispatch(
                tool_input, mock_logger
            )
        assert is_valid is False
        assert error_msg == "找不到 Ticket"
        assert ticket_id == "9.99.9-W999-999"


# ============================================================================
# Handoff 恢復模式豁免（regression guard）
# ============================================================================

class TestHandoffRecoveryMode:
    """Handoff 恢復模式應豁免所有 Ticket 驗證（與白名單機制獨立）"""

    def test_handoff_mode_bypasses_validation_for_non_exempt_agent(self, hook_module, mock_logger):
        """Handoff 恢復模式下，即使非白名單 agent 無 Ticket 也應允許"""
        tool_input = {
            "prompt": "恢復中斷的任務",
            "subagent_type": "thyme-python-developer",
        }
        with patch.object(hook_module, "is_handoff_recovery_mode", return_value=True):
            is_valid, error_msg, ticket_id = hook_module.validate_task_dispatch(
                tool_input, mock_logger
            )
        assert is_valid is True
        assert error_msg is None
        assert ticket_id is None

    def test_handoff_mode_bypasses_before_whitelist_check(self, hook_module, mock_logger):
        """Handoff 檢查優先於白名單檢查（順序保證）"""
        tool_input = {
            "prompt": "恢復",
            "subagent_type": "Explore",  # 白名單
        }
        with patch.object(hook_module, "is_handoff_recovery_mode", return_value=True):
            is_valid, error_msg, ticket_id = hook_module.validate_task_dispatch(
                tool_input, mock_logger
            )
        assert is_valid is True
        assert error_msg is None
        # Handoff 優先，應透過 handoff 路徑返回（不進入白名單分支）
        mock_logger.info.assert_any_call("Handoff 恢復模式: 略過 Ticket 驗證")
