"""save_ticket 寫入失敗時原檔案內容必須完整保留（不可截斷為 0 byte）。

根因：`open(path, "w")` 在呼叫當下即截斷既有檔案；若隨後 `f.write()` 失敗
（如內容含孤立代理碼位觸發 UnicodeEncodeError），檔案停在截斷後的 0 byte
狀態，呼叫端捕獲例外也救不回已被截斷的原內容。修正為寫暫存檔成功後才
`os.replace` 原子取代目標檔案。
"""
from __future__ import annotations

import pytest

from ticket_system.lib.parser import save_ticket


def test_save_ticket_preserves_original_content_on_write_failure(tmp_path):
    """寫入拋 UnicodeEncodeError 時，原檔案內容完整保留，非 0 byte。"""
    path = tmp_path / "x-001.md"
    original = "---\nid: x-001\nstatus: pending\n---\n\n# Body\n原始內容\n"
    path.write_text(original, encoding="utf-8")

    # 直接以孤立代理碼位構造無法編碼的 _body，繞過 YAML 解析路徑，專注
    # 驗證 save_ticket 本身的寫入原子性（root cause 的第 1 環另有專屬測試：
    # test_parser_surrogate_sanitization.py）。
    ticket = {"id": "x-001", "status": "pending", "_body": "\ud83d broken"}

    with pytest.raises(UnicodeEncodeError):
        save_ticket(ticket, path)

    assert path.read_text(encoding="utf-8") == original
    assert path.stat().st_size > 0


def test_save_ticket_no_leftover_tmp_file_on_failure(tmp_path):
    """寫入失敗後，暫存檔必須被清除，不留下 .*.tmp 殘留檔案。"""
    path = tmp_path / "x-002.md"
    path.write_text("---\nid: x-002\nstatus: pending\n---\n\nbody\n", encoding="utf-8")

    ticket = {"id": "x-002", "status": "pending", "_body": "\ud83d broken"}
    with pytest.raises(UnicodeEncodeError):
        save_ticket(ticket, path)

    leftovers = list(tmp_path.glob(".*tmp*"))
    assert leftovers == [], f"暫存檔未清除: {leftovers}"


def test_save_ticket_still_succeeds_on_normal_content(tmp_path):
    """正常內容仍可成功寫入（回歸：原子化不破壞既有成功路徑）。"""
    path = tmp_path / "x-003.md"
    ticket = {"id": "x-003", "status": "pending", "_body": "# Body\n正常內容\n"}
    save_ticket(ticket, path)
    content = path.read_text(encoding="utf-8")
    assert "正常內容" in content
    assert "id: x-003" in content
