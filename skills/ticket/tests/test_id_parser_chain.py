"""
測試 id_parser.calculate_chain_info 的序號前導 0 保留

來源 Ticket: 0.18.0-W10-037
問題：calculate_chain_info 透過 parse_sequence 將序號轉為 int 後再 format 回字串，
      導致前導 0 遺失（例如 "036" 被 int 化為 36，再 str 化為 "36"）。
      結果：migrate W10-036.4 的 parent_id 被錯誤計算為 "0.18.0-W10-36" 而非 "0.18.0-W10-036"。

測試範圍：
- 三位數序號根任務與子任務的 root/parent 保留前導 0
- 單位數序號根任務不受影響
- 多層深度子任務的序號格式保留
"""

import pytest

from ticket_system.lib.id_parser import calculate_chain_info


class TestChainInfoPreservesLeadingZero:
    """calculate_chain_info 必須保留序號前導 0（Bug 1）"""

    def test_three_digit_root_preserves_zero_in_root_id(self):
        """三位數根任務 ID，root 應保留 '036' 而非 '36'"""
        info = calculate_chain_info("0.18.0-W10-036")
        assert info["root"] == "0.18.0-W10-036", (
            f"root 應保留前導 0，實際: {info['root']}"
        )
        assert info["parent"] is None
        assert info["depth"] == 0

    def test_three_digit_subtask_preserves_zero_in_parent(self):
        """三位數子任務 ID，parent 應保留前導 0（驗收條件核心）"""
        info = calculate_chain_info("0.18.0-W10-036.1")
        assert info["root"] == "0.18.0-W10-036", (
            f"root 應為 '0.18.0-W10-036'，實際: {info['root']}"
        )
        assert info["parent"] == "0.18.0-W10-036", (
            f"parent 應為 '0.18.0-W10-036' 而非 typo，實際: {info['parent']}"
        )
        assert info["depth"] == 1

    def test_three_digit_grandchild_preserves_zero_in_chain(self):
        """三位數孫任務 ID，root 和 parent 皆保留前導 0"""
        info = calculate_chain_info("0.18.0-W10-036.4.1")
        assert info["root"] == "0.18.0-W10-036"
        assert info["parent"] == "0.18.0-W10-036.4"
        assert info["depth"] == 2

    def test_single_digit_root_remains_unchanged(self):
        """單位數根 ID 格式仍正確（回歸防護）"""
        info = calculate_chain_info("0.1.0-W3-001")
        assert info["root"] == "0.1.0-W3-001"
        assert info["parent"] is None

    def test_single_digit_subtask_preserves_zero(self):
        """單位數根 + 子任務：parent 必須保留 '001' 前導 0"""
        info = calculate_chain_info("0.1.0-W3-001.1")
        assert info["root"] == "0.1.0-W3-001", (
            f"root 應為 '0.1.0-W3-001'，實際: {info['root']}"
        )
        assert info["parent"] == "0.1.0-W3-001"

    def test_double_digit_wave_with_padded_sequence(self):
        """雙位數 wave + 三位數序號（驗收條件明確列出的情境）"""
        info = calculate_chain_info("0.18.0-W10-036.2")
        assert info["root"] == "0.18.0-W10-036"
        assert info["parent"] == "0.18.0-W10-036"

    def test_triple_digit_wave_with_padded_sequence(self):
        """W99（雙位數邊界）+ 三位數序號"""
        info = calculate_chain_info("1.0.0-W99-007.3")
        assert info["root"] == "1.0.0-W99-007"
        assert info["parent"] == "1.0.0-W99-007"

    def test_sequence_list_remains_int_type_for_api_compatibility(self):
        """sequence 欄位仍維持 int list（API 相容性，不破壞既有使用者）"""
        info = calculate_chain_info("0.18.0-W10-036.4.1")
        assert info["sequence"] == [36, 4, 1]

    def test_invalid_id_returns_empty_dict(self):
        """無效 ID 回傳空 dict（回歸防護）"""
        info = calculate_chain_info("invalid")
        assert info == {}
