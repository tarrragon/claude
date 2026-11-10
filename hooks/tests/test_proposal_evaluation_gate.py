"""Proposal Evaluation Gate Hook 測試（W10-109 + W2-025 升級閘門時機修正）

W2-025：章節檢查改為「升級閘門」——僅在 status 由非 confirmed/approved 升級為
confirmed/approved 時觸發；confirmed→confirmed 維護編輯豁免章節檢查。

- Case 1 (P2): status=draft 自動豁免章節檢查
- Case 2: 升級轉換（含新建檔直接 confirmed）缺章節 → 阻擋
- Case 3 (regression): level=light 仍阻擋（light 已移除）
- Case 4: 缺 / 空 status（非升級目標）→ 豁免章節檢查
- Case 6: status=draft 缺 evaluation_level → 仍阻擋（規則 1 不豁免）
- TestUpgradeGateTiming: confirmed→confirmed 維護豁免 + is_upgrade_transition 真值表
- TestMainUpgradeMicroEditInteraction: 微調豁免不繞過升級閘門

豁免優先序：P1 micro_edit（升級轉換除外）> P2 status=draft > P3 升級閘門（非升級豁免）
"""

import importlib.util
import io
import json
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

    def test_new_file_confirmed_heavy_missing_sections_blocked(self, hook_module, mock_logger):
        """新建檔（old_status=None）直接 confirmed + heavy 缺章節 → 阻擋（視為升級）"""
        content = _make_prop_content(
            [
                "id: PROP-995b",
                "evaluation_level: heavy",
                "status: confirmed",
            ],
            body="只有動機段落。",
        )
        should_block, reason = hook_module.check_prop_content(
            content, mock_logger, old_status=None
        )
        assert should_block is True
        assert "缺以下必填章節" in reason

    def test_upgrade_discussing_to_confirmed_missing_sections_blocked(
        self, hook_module, mock_logger
    ):
        """升級轉換 discussing→confirmed + heavy 缺章節 → 阻擋"""
        content = _make_prop_content(
            [
                "id: PROP-994",
                "evaluation_level: heavy",
                "status: confirmed",
            ],
            body="只有動機。",
        )
        should_block, reason = hook_module.check_prop_content(
            content, mock_logger, old_status="discussing"
        )
        assert should_block is True
        assert "缺以下必填章節" in reason

    def test_discussing_to_discussing_missing_sections_allowed(self, hook_module, mock_logger):
        """非升級（discussing→discussing）缺章節 → 豁免（升級閘門非維護閘門）"""
        content = _make_prop_content(
            [
                "id: PROP-994b",
                "evaluation_level: standard",
                "status: discussing",
            ],
            body="只有動機。",
        )
        should_block, _ = hook_module.check_prop_content(
            content, mock_logger, old_status="discussing"
        )
        assert should_block is False


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
# Case 4: 缺 status 欄位非升級 → 章節檢查豁免（升級閘門語意）
# ============================================================================


class TestMissingStatus:
    def test_no_status_heavy_missing_sections_allowed(self, hook_module, mock_logger):
        """缺 status（非 confirmed/approved 目標）→ 非升級 → 豁免章節檢查"""
        content = _make_prop_content(
            [
                "id: PROP-991",
                "evaluation_level: heavy",
            ],
            body="無 status 欄位。",
        )
        should_block, _ = hook_module.check_prop_content(content, mock_logger)
        assert should_block is False

    def test_empty_status_heavy_missing_sections_allowed(self, hook_module, mock_logger):
        """status 空字串 → 非升級目標 → 豁免章節檢查"""
        content = _make_prop_content(
            [
                "id: PROP-990",
                "evaluation_level: heavy",
                'status: ""',
            ],
            body="空 status",
        )
        should_block, _ = hook_module.check_prop_content(content, mock_logger)
        assert should_block is False


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


class TestUpgradeGateTiming:
    """W2-025: 章節檢查改為僅在升級轉換時觸發（升級閘門，非維護閘門）。"""

    def test_confirmed_to_confirmed_missing_sections_allowed(self, hook_module, mock_logger):
        """confirmed→confirmed 維護編輯，缺章節 → 豁免（核心解凍情境）"""
        content = _make_prop_content(
            [
                "id: PROP-007",
                "evaluation_level: heavy",
                "status: confirmed",
            ],
            body="只改 §7 一段，缺多視角審查/機會成本等章節。",
        )
        should_block, reason = hook_module.check_prop_content(
            content, mock_logger, old_status="confirmed"
        )
        assert should_block is False, f"confirmed 維護編輯不應被章節檢查阻擋：{reason}"

    def test_approved_to_approved_missing_sections_allowed(self, hook_module, mock_logger):
        """approved→approved 維護編輯，缺章節 → 豁免"""
        content = _make_prop_content(
            [
                "id: PROP-100",
                "evaluation_level: heavy",
                "status: approved",
            ],
            body="維護編輯，章節不全。",
        )
        should_block, _ = hook_module.check_prop_content(
            content, mock_logger, old_status="approved"
        )
        assert should_block is False

    def test_upgrade_draft_to_confirmed_treated_as_draft_exempt(self, hook_module, mock_logger):
        """old=draft 但編輯後仍 draft → P2 draft 豁免優先（非升級路徑）"""
        content = _make_prop_content(
            [
                "id: PROP-101",
                "evaluation_level: heavy",
                "status: draft",
            ],
            body="仍在 draft。",
        )
        should_block, _ = hook_module.check_prop_content(
            content, mock_logger, old_status="draft"
        )
        assert should_block is False

    def test_is_upgrade_transition_matrix(self, hook_module):
        """is_upgrade_transition 真值表"""
        f = hook_module.is_upgrade_transition
        # 升級：非 confirmed/approved → confirmed/approved
        assert f("draft", "confirmed") is True
        assert f("discussing", "approved") is True
        assert f(None, "confirmed") is True  # 新建檔直接 confirmed
        assert f("", "approved") is True
        # 非升級：維護編輯
        assert f("confirmed", "confirmed") is False
        assert f("approved", "approved") is False
        assert f("confirmed", "approved") is False  # confirmed→approved 皆已升級態
        # 非升級：目標非 confirmed/approved
        assert f("confirmed", "discussing") is False  # 降級
        assert f("draft", "discussing") is False
        assert f(None, "draft") is False


class TestMainUpgradeMicroEditInteraction:
    """W2-025: main() 端整合 — 微調豁免不可繞過升級閘門。

    一行 status flip（< 30 字元）屬語意升級而非格式微調，必須觸發章節檢查。
    """

    def _write_prop(self, tmp_path, name, status):
        d = tmp_path / "docs" / "proposals"
        d.mkdir(parents=True, exist_ok=True)
        f = d / name
        f.write_text(
            f"---\nid: {name}\nevaluation_level: heavy\nstatus: {status}\n---\n\n"
            "# 動機\n只有動機，缺所有 heavy 章節。\n",
            encoding="utf-8",
        )
        return f

    def _run_main(self, hook_module, monkeypatch, capsys, payload):
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        rc = hook_module.main()
        return rc, capsys.readouterr().out

    def test_micro_status_flip_upgrade_blocked(
        self, hook_module, monkeypatch, capsys, tmp_path
    ):
        """discussing→confirmed 的微小 status flip（缺章節）→ 仍 deny"""
        f = self._write_prop(tmp_path, "PROP-300.md", "discussing")
        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(f),
                "old_string": "status: discussing",
                "new_string": "status: confirmed",
            },
        }
        _, out = self._run_main(hook_module, monkeypatch, capsys, payload)
        assert '"permissionDecision": "deny"' in out
        assert "缺以下必填章節" in out

    def test_micro_confirmed_maintenance_allowed(
        self, hook_module, monkeypatch, capsys, tmp_path
    ):
        """confirmed→confirmed 的微小維護編輯（缺章節）→ 不 deny（無輸出）"""
        f = self._write_prop(tmp_path, "PROP-301.md", "confirmed")
        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(f),
                "old_string": "只有動機",
                "new_string": "已修訂動機",
            },
        }
        rc, out = self._run_main(hook_module, monkeypatch, capsys, payload)
        assert rc == 0
        assert '"permissionDecision": "deny"' not in out


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
