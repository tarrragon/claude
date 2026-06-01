"""Proposal Evaluation Gate Hook 測試（W10-109）

對應 W10-099 多視角審查仲裁採方案 D（C + light 收斂純語意）：
- Case 1 (P2): status=draft 自動豁免章節檢查
- Case 2 (P4): status=confirmed + heavy 缺章節仍阻擋
- Case 3 (P3 regression): status=confirmed + light 既有豁免不破壞
- Case 4: 缺 status 欄位 + heavy 缺章節 → 阻擋
- Case 5: status=DRAFT 大寫 → 豁免（lower 寬容）
- Case 6: status=draft 缺 evaluation_level → 仍阻擋（規則 1 不豁免）

豁免優先序：P1 micro_edit > P2 status=draft > P3 level=light > P4 嚴格檢查
"""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest


_HOOKS_DIR = Path(__file__).parent.parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))


@pytest.fixture
def hook_module():
    """動態載入 proposal-evaluation-gate-hook 模組（檔名含連字號）"""
    spec = importlib.util.spec_from_file_location(
        "proposal_evaluation_gate_hook",
        _HOOKS_DIR / "proposal-evaluation-gate-hook.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mock_logger():
    return MagicMock()


def _make_prop_content(frontmatter_lines, body=""):
    """組裝 PROP markdown 內容（frontmatter + body）"""
    fm = "\n".join(frontmatter_lines)
    return f"---\n{fm}\n---\n\n{body}"


# ============================================================================
# Case 1: P2 豁免 — status=draft + level=heavy + 缺所有 heavy 章節 → allow
# ============================================================================


class TestStatusDraftExemption:
    def test_draft_heavy_missing_sections_allowed(self, hook_module, mock_logger):
        """status=draft 即使 level=heavy 缺所有章節也應豁免"""
        content = _make_prop_content(
            [
                "id: PROP-999",
                "evaluation_level: heavy",
                "status: draft",
            ],
            body="# Draft 探索期 PROP\n\n尚未完成評估章節。",
        )
        should_block, reason = hook_module.check_prop_content(content, mock_logger)
        assert should_block is False, f"draft 應豁免，但被阻擋：{reason}"

    def test_draft_standard_missing_sections_allowed(self, hook_module, mock_logger):
        """status=draft + level=standard 缺章節同樣豁免"""
        content = _make_prop_content(
            [
                "id: PROP-998",
                "evaluation_level: standard",
                "status: draft",
            ],
            body="尚未完成 standard 章節",
        )
        should_block, reason = hook_module.check_prop_content(content, mock_logger)
        assert should_block is False

    def test_draft_uppercase_still_exempt(self, hook_module, mock_logger):
        """Case 5: status=DRAFT 大寫經 lower 後應豁免"""
        content = _make_prop_content(
            [
                "id: PROP-997",
                "evaluation_level: heavy",
                "status: DRAFT",
            ],
            body="大寫 status 測試",
        )
        should_block, _ = hook_module.check_prop_content(content, mock_logger)
        assert should_block is False

    def test_draft_with_whitespace_still_exempt(self, hook_module, mock_logger):
        """status=' draft ' 含空白經 strip 後應豁免"""
        content = _make_prop_content(
            [
                "id: PROP-996",
                "evaluation_level: heavy",
                "status: ' draft '",
            ],
            body="含空白測試",
        )
        should_block, _ = hook_module.check_prop_content(content, mock_logger)
        assert should_block is False


# ============================================================================
# Case 2: P4 嚴格路徑 — status=confirmed + heavy 缺章節 → deny
# ============================================================================


class TestStrictPathConfirmed:
    def test_confirmed_heavy_missing_sections_blocked(self, hook_module, mock_logger):
        """status=confirmed + level=heavy 缺多視角/機會成本 → 阻擋"""
        content = _make_prop_content(
            [
                "id: PROP-995",
                "evaluation_level: heavy",
                "status: confirmed",
            ],
            body="只有動機段落，無評估內容。",
        )
        should_block, reason = hook_module.check_prop_content(content, mock_logger)
        assert should_block is True
        assert "缺以下必填章節" in reason

    def test_discussing_standard_missing_sections_blocked(self, hook_module, mock_logger):
        """status=discussing + level=standard 缺章節 → 阻擋"""
        content = _make_prop_content(
            [
                "id: PROP-994",
                "evaluation_level: standard",
                "status: discussing",
            ],
            body="只有動機。",
        )
        should_block, reason = hook_module.check_prop_content(content, mock_logger)
        assert should_block is True


# ============================================================================
# Case 3: P3 既有 light 豁免不破壞（regression guard）
# ============================================================================


class TestLightRemovedRegression:
    def test_confirmed_light_now_blocked(self, hook_module, mock_logger):
        """status=confirmed + level=light → 阻擋（light 已移除，W3-093）"""
        content = _make_prop_content(
            [
                "id: PROP-993",
                "evaluation_level: light",
                "status: confirmed",
            ],
            body="light 級別，無章節。",
        )
        should_block, reason = hook_module.check_prop_content(content, mock_logger)
        assert should_block is True
        assert "light" in reason

    def test_approved_light_now_blocked(self, hook_module, mock_logger):
        """status=approved + level=light → 阻擋（light 已移除，W3-093）"""
        content = _make_prop_content(
            [
                "id: PROP-992",
                "evaluation_level: light",
                "status: approved",
            ],
            body="",
        )
        should_block, reason = hook_module.check_prop_content(content, mock_logger)
        assert should_block is True
        assert "light" in reason


# ============================================================================
# Case 4: 缺 status 欄位不豁免
# ============================================================================


class TestMissingStatus:
    def test_no_status_heavy_missing_sections_blocked(self, hook_module, mock_logger):
        """缺 status + level=heavy 缺章節 → 阻擋（fall-through P4）"""
        content = _make_prop_content(
            [
                "id: PROP-991",
                "evaluation_level: heavy",
            ],
            body="無 status 欄位。",
        )
        should_block, _ = hook_module.check_prop_content(content, mock_logger)
        assert should_block is True

    def test_empty_status_heavy_missing_sections_blocked(self, hook_module, mock_logger):
        """status 空字串 + level=heavy 缺章節 → 阻擋"""
        content = _make_prop_content(
            [
                "id: PROP-990",
                "evaluation_level: heavy",
                'status: ""',
            ],
            body="空 status",
        )
        should_block, _ = hook_module.check_prop_content(content, mock_logger)
        assert should_block is True


# ============================================================================
# Case 6: status=draft 缺 evaluation_level 仍阻擋（規則 1 不豁免）
# ============================================================================


class TestDraftStillRequiresLevel:
    def test_draft_without_level_blocked(self, hook_module, mock_logger):
        """status=draft 但缺 evaluation_level → 阻擋（規則 1 強制）"""
        content = _make_prop_content(
            [
                "id: PROP-989",
                "status: draft",
            ],
            body="缺 level。",
        )
        should_block, reason = hook_module.check_prop_content(content, mock_logger)
        assert should_block is True
        assert "evaluation_level" in reason

    def test_draft_invalid_level_blocked(self, hook_module, mock_logger):
        """status=draft + level=invalid → 阻擋"""
        content = _make_prop_content(
            [
                "id: PROP-988",
                "evaluation_level: super_heavy",
                "status: draft",
            ],
            body="非法 level",
        )
        should_block, reason = hook_module.check_prop_content(content, mock_logger)
        assert should_block is True


# ============================================================================
# 完整章節覆蓋的 confirmed/heavy 應通過（合規路徑 sanity check）
# ============================================================================


class TestFullCompliance:
    def test_confirmed_heavy_full_sections_allowed(self, hook_module, mock_logger):
        """status=confirmed + heavy + 所有章節齊全 → allow"""
        body = """
## 替代方案
候選 A / 候選 B / 候選 C

## 失敗防護
失敗情境 1 / 失敗情境 2 / 失敗情境 3

## Reality Test
觸發案例與實證

## 多視角審查
linux + basil 視角已執行

## 機會成本
延後其他 ticket 的成本
"""
        content = _make_prop_content(
            [
                "id: PROP-987",
                "evaluation_level: heavy",
                "status: confirmed",
            ],
            body=body,
        )
        should_block, reason = hook_module.check_prop_content(content, mock_logger)
        assert should_block is False, f"完整章節 heavy 應通過：{reason}"
