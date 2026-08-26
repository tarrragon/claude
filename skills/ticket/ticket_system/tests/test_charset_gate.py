"""
test_charset_gate
==================

save_ticket 落盤前字元驗證閘的行為測試（language-constraints 規則 3 寫入端防線）。

覆蓋三情境（依驗收條件）：
1. 合法配對逸出：高低代理位相鄰成對，組合後落在 emoji 範圍外 → 放行
2. 孤立代理位：無法配對的代理碼位 → 拒絕，訊息含違規碼位
3. emoji：字面 emoji 字元 → 拒絕，訊息引用 language-constraints 規則 3

另覆蓋：化石豁免（既有含 emoji 的化石票，未觸碰欄位的寫入不被阻擋）、
新建票（無載入快照）全欄位驗證、deny 後 dict 由 finally 恢復。

環境：autouse `_isolate_project_root` 將 CLAUDE_PROJECT_DIR 導向 tmp，
get_ticket_path / get_project_root（charset-gate.log 落點）皆解析於隔離 root。
"""
import os
from pathlib import Path

import pytest

from ticket_system.lib.parser import (
    CHARSET_SNAPSHOT_FIELD,
    CharsetGateViolation,
    _format_charset_violation,
    load_ticket,
    save_ticket,
)
from ticket_system.lib.paths import get_ticket_path

_VERSION = "9.9.9"

# 合法配對逸出：高低代理位相鄰成對，組合為 U+1D400（Mathematical Bold
# Capital A），落在所有 EMOJI_RANGES 之外，屬非 emoji 的正常星面字元。
_LEGIT_PAIR_NON_EMOJI = chr(0xD835) + chr(0xDC00)

# emoji 字面字元（U+1F600，落在 EMOJI_RANGES 內）
_EMOJI_CHAR = "\U0001F600"

# 孤立代理位（無配對的高代理位）
_LONE_SURROGATE = chr(0xD83D)


def _write_ticket_file(ticket_id: str, why: str = "原始描述") -> Path:
    """在隔離 root 下寫入含指定 why 值的最小合法 ticket 檔。"""
    path = get_ticket_path(_VERSION, ticket_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        f"id: {ticket_id}\n"
        "title: charset gate fixture\n"
        "type: IMP\n"
        "status: pending\n"
        "priority: P2\n"
        "what: 原始描述\n"
        f"why: {why}\n"
        "---\n\n# Execution Log\n",
        encoding="utf-8",
    )
    return path


def _gate_log_path() -> Path:
    return Path(os.environ["CLAUDE_PROJECT_DIR"]) / ".claude" / "hook-logs" / "charset-gate.log"


# ---------------------------------------------------------------------------
# 情境 1：合法配對逸出（非 emoji）→ 放行
# ---------------------------------------------------------------------------


def test_legit_paired_escape_non_emoji_accepted(capsys):
    path = _write_ticket_file("9.9.9-C1-001")
    ticket = load_ticket(_VERSION, "9.9.9-C1-001")

    ticket["why"] = f"含合法配對逸出星面字元 {_LEGIT_PAIR_NON_EMOJI}"
    save_ticket(ticket, path)  # 不應拋出 CharsetGateViolation

    assert "[charset-gate" not in capsys.readouterr().err
    # 寫入端字元閘只負責放行/拒絕，不正規化內容：PyYAML 將代理對序列化為
    # \\uXXXX 逸出文字，重新載入時既有 _sanitize_surrogates 才組合回單一
    # 星面字元（讀取端既有機制，本票不變動）。
    reloaded = load_ticket(_VERSION, "9.9.9-C1-001")
    assert reloaded["why"] == f"含合法配對逸出星面字元 {chr(0x1D400)}"


# ---------------------------------------------------------------------------
# 情境 2：孤立代理位 → 拒絕，訊息含違規碼位
# ---------------------------------------------------------------------------


def test_lone_surrogate_rejected_with_codepoint_in_message(capsys):
    path = _write_ticket_file("9.9.9-C1-002")
    ticket = load_ticket(_VERSION, "9.9.9-C1-002")

    ticket["why"] = f"含孤立代理位{_LONE_SURROGATE}"
    with pytest.raises(CharsetGateViolation) as exc_info:
        save_ticket(ticket, path)

    # 違規明細可供呼叫端消費：field_path、char、codepoint、kind
    kinds = [v[3] for v in exc_info.value.violations]
    assert kinds == ["surrogate"]
    codes = [v[2] for v in exc_info.value.violations]
    assert codes == [0xD83D]

    err = capsys.readouterr().err
    assert "[charset-gate" in err
    assert "U+D83D" in err
    # 不落盤：檔案維持載入前狀態
    assert "原始描述" in path.read_text(encoding="utf-8")
    assert _gate_log_path().read_text(encoding="utf-8").count("surrogate") == 1


# ---------------------------------------------------------------------------
# 情境 3：emoji → 拒絕，訊息引用 language-constraints 規則 3
# ---------------------------------------------------------------------------


def test_emoji_rejected_with_rule_reference(capsys):
    path = _write_ticket_file("9.9.9-C1-003")
    ticket = load_ticket(_VERSION, "9.9.9-C1-003")

    ticket["why"] = f"含 emoji {_EMOJI_CHAR}"
    with pytest.raises(CharsetGateViolation) as exc_info:
        save_ticket(ticket, path)

    kinds = [v[3] for v in exc_info.value.violations]
    assert kinds == ["emoji"]

    err = capsys.readouterr().err
    assert "language-constraints.md 規則 3" in err
    # 不落盤
    assert "原始描述" in path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# _format_charset_violation：中英文交界排版（emoji label 開頭為英文字母，
# 「含」與 label 之間須補空格；surrogate label 開頭為中文字元則不需要）
# ---------------------------------------------------------------------------


def test_format_charset_violation_emoji_has_space_before_label():
    msg = _format_charset_violation("why", "\U0001F600", 0x1F600, "emoji")
    assert "含 emoji 字元" in msg
    assert "含emoji" not in msg


def test_format_charset_violation_surrogate_no_extra_space():
    msg = _format_charset_violation("why", chr(0xD83D), 0xD83D, "surrogate")
    assert "含孤立 UTF-16 代理碼位" in msg


# ---------------------------------------------------------------------------
# 化石豁免：既有含 emoji 的化石票，未觸碰該欄位的寫入不被阻擋
# ---------------------------------------------------------------------------


def test_fossil_emoji_field_untouched_not_blocked(capsys):
    path = _write_ticket_file("9.9.9-C1-004", why=f"化石 emoji {_EMOJI_CHAR}")
    ticket = load_ticket(_VERSION, "9.9.9-C1-004")
    assert ticket[CHARSET_SNAPSHOT_FIELD]["why"] == f"化石 emoji {_EMOJI_CHAR}"

    ticket["what"] = "只改 what，不碰 why（不相關欄位寫入，如 append-log 情境）"
    save_ticket(ticket, path)

    assert "[charset-gate" not in capsys.readouterr().err
    assert _EMOJI_CHAR in path.read_text(encoding="utf-8")


def test_fossil_emoji_field_touched_again_rejected(capsys):
    """化石欄位本身被本次操作再次觸碰（值改變）時仍須驗證，非永久豁免。"""
    path = _write_ticket_file("9.9.9-C1-005", why=f"化石 emoji {_EMOJI_CHAR}")
    ticket = load_ticket(_VERSION, "9.9.9-C1-005")

    ticket["why"] = f"仍帶 emoji 的新內容 {_EMOJI_CHAR}"
    with pytest.raises(CharsetGateViolation):
        save_ticket(ticket, path)


# ---------------------------------------------------------------------------
# 新建票（無載入快照）：全欄位驗證
# ---------------------------------------------------------------------------


def test_new_ticket_dict_emoji_rejected(tmp_path):
    ticket = {
        "id": "9.9.9-C1-006",
        "type": "IMP",
        "status": "pending",
        "priority": "P2",
        "what": f"新建票含 emoji {_EMOJI_CHAR}",
        "_body": "# Execution Log\n",
    }
    with pytest.raises(CharsetGateViolation):
        save_ticket(ticket, tmp_path / "9.9.9-C1-006.md")


def test_new_ticket_dict_all_clean_accepted(tmp_path, capsys):
    ticket = {
        "id": "9.9.9-C1-007",
        "type": "IMP",
        "status": "pending",
        "priority": "P2",
        "what": "新建票無違規字元",
        "_body": "# Execution Log\n",
    }
    save_ticket(ticket, tmp_path / "9.9.9-C1-007.md")
    assert "[charset-gate" not in capsys.readouterr().err


# ---------------------------------------------------------------------------
# deny 後 dict 完整性：finally 恢復 _body/_path/兩個快照欄位
# ---------------------------------------------------------------------------


def test_rejection_restores_dict_fields(capsys):
    path = _write_ticket_file("9.9.9-C1-008")
    ticket = load_ticket(_VERSION, "9.9.9-C1-008")

    ticket["why"] = f"含 emoji {_EMOJI_CHAR}"
    with pytest.raises(CharsetGateViolation):
        save_ticket(ticket, path)

    assert "_body" in ticket
    assert "_path" in ticket
    assert CHARSET_SNAPSHOT_FIELD in ticket
    assert ticket[CHARSET_SNAPSHOT_FIELD]["why"] == "原始描述"


# ---------------------------------------------------------------------------
# 嵌套欄位（如 how.strategy）同受字元閘保護
# ---------------------------------------------------------------------------


def test_nested_field_emoji_rejected(capsys):
    path = _write_ticket_file("9.9.9-C1-009")
    ticket = load_ticket(_VERSION, "9.9.9-C1-009")

    ticket["how"] = {"task_type": "Implementation", "strategy": f"含 emoji {_EMOJI_CHAR}"}
    with pytest.raises(CharsetGateViolation) as exc_info:
        save_ticket(ticket, path)

    field_paths = [v[0] for v in exc_info.value.violations]
    assert field_paths == ["how.strategy"]
