"""
ac_parser 模組測試（RED 階段 — 尚未實作）

覆蓋 Phase 1 §7 的 7 個 ac_parser 測試場景：
1. 正常 Ticket：5 項 acceptance 全未勾選
2. 已部分勾選：checked 欄位正確反映 [x] / [ ]
3. 無 acceptance 欄位：回傳 []
4. 空 acceptance 清單：回傳 []
5. 型別錯誤：acceptance 為 str/dict 時 raise ValueError
6. 找不到 Ticket：raise FileNotFoundError
7. raw 欄位保真：含特殊字元時 raw 與原始 YAML 值一致

測試對象：
- .claude/skills/ticket/ticket_system/lib/ac_parser.py（Phase 3b 才會實作）
- 預期 import：parse_ac, AC
"""

from pathlib import Path
from textwrap import dedent

import pytest

# 下列 import 在 Phase 3b 實作前會 ImportError，使本檔案所有測試保持 RED。
from ticket_system.lib.ac_parser import parse_ac, AC  # noqa: E402


def _write_ticket(
    project_root: Path,
    version: str,
    ticket_id: str,
    frontmatter_yaml: str,
    body: str = "",
) -> Path:
    """於 temp_project_dir 建立符合 ticket_loader 路徑慣例的 Ticket 檔案。

    frontmatter_yaml 為已序列化的 YAML 字串（含 `---` 分隔符外層）。
    """
    tickets_dir = project_root / "docs" / "work-logs" / f"v{version}" / "tickets"
    tickets_dir.mkdir(parents=True, exist_ok=True)
    ticket_path = tickets_dir / f"{ticket_id}.md"
    content = f"---\n{frontmatter_yaml.strip()}\n---\n\n{body}\n"
    ticket_path.write_text(content, encoding="utf-8")
    return ticket_path


@pytest.fixture
def project_env(temp_project_dir, monkeypatch):
    """將 CLAUDE_PROJECT_DIR 指向 temp_project_dir，隔離 parse_ac 的檔案載入。"""
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(temp_project_dir))
    return temp_project_dir


class TestParseAcNormalTicket:
    """場景 1：正常 Ticket（5 項 acceptance 全未勾選）。"""

    def test_returns_five_ac_with_sequential_index_and_unchecked(self, project_env):
        fm = dedent(
            """
            id: 0.31.0-W1-001
            title: 測試 Ticket
            version: 0.31.0
            acceptance:
              - '[ ] 新增 ac_parser.py 模組能解析 frontmatter acceptance list'
              - '[ ] 新增 validation_templates.py 規則庫至少含 5 個模板'
              - '[ ] 單元測試覆蓋所有規則庫模板，測試通過率 100%'
              - '[ ] 提供 API 讓後續 claim 命令呼叫'
              - '[ ] 不破壞既有 CLI 行為'
            """
        )
        _write_ticket(project_env, "0.31.0", "0.31.0-W1-001", fm)

        result = parse_ac("0.31.0-W1-001")

        assert isinstance(result, list), f"預期回傳 list，實際 {type(result)}"
        assert len(result) == 5, f"預期 5 個 AC，實際 {len(result)}"
        for i, ac in enumerate(result):
            assert isinstance(ac, AC), f"第 {i} 項應為 AC 物件"
            assert ac.index == i, f"第 {i} 項 index 應為 {i}，實際 {ac.index}"
            assert ac.checked is False, f"第 {i} 項 checked 應為 False"
            assert ac.text, f"第 {i} 項 text 不應為空"
            # text 應已剝除 "[ ]" 前綴
            assert not ac.text.startswith("["), (
                f"text 應剝除 checkbox 標記，實際保留：{ac.text!r}"
            )


class TestParseAcPartiallyChecked:
    """場景 2：已部分勾選（W5-002 依賴 checked 欄位）。"""

    def test_checked_field_reflects_x_vs_space(self, project_env):
        fm = dedent(
            """
            id: 0.31.0-W1-002
            title: 測試 Ticket
            version: 0.31.0
            acceptance:
              - '[x] 已完成的項目 A'
              - '[ ] 未完成的項目 B'
              - '[x] 已完成的項目 C'
              - '[ ] 未完成的項目 D'
            """
        )
        _write_ticket(project_env, "0.31.0", "0.31.0-W1-002", fm)

        result = parse_ac("0.31.0-W1-002")

        assert len(result) == 4
        assert result[0].checked is True, "第 1 項 [x] 應為 checked=True"
        assert result[1].checked is False, "第 2 項 [ ] 應為 checked=False"
        assert result[2].checked is True, "第 3 項 [x] 應為 checked=True"
        assert result[3].checked is False, "第 4 項 [ ] 應為 checked=False"


class TestParseAcMissingAcceptanceField:
    """場景 3：無 acceptance 欄位（非 TDD 類型 Ticket 可能無 AC）。"""

    def test_missing_acceptance_returns_empty_list_without_raise(self, project_env):
        fm = dedent(
            """
            id: 0.31.0-W1-003
            title: 無 acceptance 欄位的 Ticket
            version: 0.31.0
            """
        )
        _write_ticket(project_env, "0.31.0", "0.31.0-W1-003", fm)

        result = parse_ac("0.31.0-W1-003")

        assert result == [], f"預期 []，實際 {result}"


class TestParseAcEmptyAcceptanceList:
    """場景 4：空 acceptance 清單（型別邊界）。"""

    def test_empty_list_returns_empty_list(self, project_env):
        fm = dedent(
            """
            id: 0.31.0-W1-004
            title: 空 acceptance Ticket
            version: 0.31.0
            acceptance: []
            """
        )
        _write_ticket(project_env, "0.31.0", "0.31.0-W1-004", fm)

        result = parse_ac("0.31.0-W1-004")

        assert result == [], f"預期 []，實際 {result}"


class TestParseAcTypeError:
    """場景 5：型別錯誤（防止 Ticket 格式腐化靜默通過）。"""

    def test_acceptance_as_string_raises_value_error(self, project_env):
        fm = dedent(
            """
            id: 0.31.0-W1-005
            title: 型別錯誤（str）
            version: 0.31.0
            acceptance: "這是一個錯誤的字串型別"
            """
        )
        _write_ticket(project_env, "0.31.0", "0.31.0-W1-005", fm)

        with pytest.raises(ValueError) as exc_info:
            parse_ac("0.31.0-W1-005")
        # 錯誤訊息應提及 acceptance 欄位或型別，幫助 PM 定位
        assert "acceptance" in str(exc_info.value).lower() or "type" in str(exc_info.value).lower(), (
            f"ValueError 訊息應描述型別問題，實際：{exc_info.value}"
        )

    def test_acceptance_as_dict_raises_value_error(self, project_env):
        fm = dedent(
            """
            id: 0.31.0-W1-006
            title: 型別錯誤（dict）
            version: 0.31.0
            acceptance:
              key1: value1
              key2: value2
            """
        )
        _write_ticket(project_env, "0.31.0", "0.31.0-W1-006", fm)

        with pytest.raises(ValueError):
            parse_ac("0.31.0-W1-006")


class TestParseAcTicketNotFound:
    """場景 6：找不到 Ticket（錯誤傳遞正確）。"""

    def test_nonexistent_ticket_id_raises_file_not_found(self, project_env):
        with pytest.raises(FileNotFoundError):
            parse_ac("0.99.0-W99-999")


class TestParseAcNoCheckboxPrefix:
    """場景 L1/Comp1：無 checkbox 前綴的 AC 視為未勾選，text 保留原文。"""

    def test_no_checkbox_prefix_defaults_to_unchecked(self, project_env):
        fm = dedent(
            """
            id: 0.31.0-W1-008
            title: 無 checkbox 前綴
            version: 0.31.0
            acceptance:
              - 'AC without checkbox'
            """
        )
        _write_ticket(project_env, "0.31.0", "0.31.0-W1-008", fm)

        result = parse_ac("0.31.0-W1-008")

        assert len(result) == 1
        assert result[0].checked is False
        assert result[0].text == "AC without checkbox"
        assert result[0].raw == "AC without checkbox"


class TestParseAcYamlError:
    """場景 P3：load_ticket 回傳含 _yaml_error 的 dict 時應 raise ValueError。"""

    def test_yaml_error_raises_value_error(self, project_env, monkeypatch):
        from ticket_system.lib import ac_parser

        def _mock_load_ticket(version, ticket_id):
            return {
                "id": ticket_id,
                "_path": "/fake/path",
                "_yaml_error": "mock YAML parse error at line 3",
            }

        monkeypatch.setattr(ac_parser.parser, "load_ticket", _mock_load_ticket)

        with pytest.raises(ValueError) as exc_info:
            parse_ac("0.31.0-W1-009")

        msg = str(exc_info.value)
        assert "YAML" in msg or "_yaml_error" in msg, (
            f"ValueError 訊息應提及 YAML 或 _yaml_error，實際：{msg}"
        )


class TestParseAcRawFidelity:
    """場景 7：raw 欄位保真（未來回寫 frontmatter 的基礎）。"""

    def test_raw_preserves_original_yaml_value_with_special_chars(self, project_env):
        fm = dedent(
            """
            id: 0.31.0-W1-007
            title: raw 保真測試
            version: 0.31.0
            acceptance:
              - '[ ] 測試通過率 100%（含邊界案例）'
              - '[x] 覆蓋率 >= 80%'
              - '[ ] lint 通過，無 warning'
            """
        )
        _write_ticket(project_env, "0.31.0", "0.31.0-W1-007", fm)

        result = parse_ac("0.31.0-W1-007")

        assert len(result) == 3
        # raw 應保留原始 checkbox 標記與特殊字元
        assert "[ ]" in result[0].raw or "[x]" not in result[0].raw, (
            f"第 1 項 raw 應保留 '[ ]'，實際：{result[0].raw!r}"
        )
        assert "100%" in result[0].raw, f"特殊字元 '%' 應於 raw 中保留：{result[0].raw!r}"
        assert "[x]" in result[1].raw, f"第 2 項 raw 應保留 '[x]'：{result[1].raw!r}"
        assert ">=" in result[1].raw, f"比較符號應保留：{result[1].raw!r}"
        # text 應已剝除 checkbox 但保留業務文字
        assert "100%" in result[0].text, f"text 應保留 '100%'：{result[0].text!r}"
        assert result[0].text != result[0].raw, "text 應與 raw 不同（text 剝除 checkbox）"
