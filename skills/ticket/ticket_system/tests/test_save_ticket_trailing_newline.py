"""W9-005 / issue #1 問題5：save_ticket 保留檔尾單一換行。

claim/release roundtrip 後 ticket .md 檔尾換行被吃掉，git diff 出現
「No newline at end of file」雜訊。save_ticket 寫回時應確保檔尾有換行，
且不重複既有換行。
"""
from __future__ import annotations

from ticket_system.lib.parser import save_ticket


def _save(tmp_path, body: str):
    ticket = {"id": "x-001", "status": "pending", "_body": body}
    path = tmp_path / "x-001.md"
    save_ticket(ticket, path)
    return path.read_text(encoding="utf-8")


def test_md_without_trailing_newline_gets_one(tmp_path):
    """body 無檔尾換行 → 寫回補上單一換行（避免 No newline at end of file）。"""
    content = _save(tmp_path, "# Body\n無結尾換行")
    assert content.endswith("無結尾換行\n")
    assert not content.endswith("\n\n")


def test_md_with_trailing_newline_preserved(tmp_path):
    """body 已帶檔尾換行 → 不重複加（保留單一換行）。"""
    content = _save(tmp_path, "# Body\n")
    assert content.endswith("# Body\n")
    assert not content.endswith("# Body\n\n")


def test_empty_body_still_ends_with_newline(tmp_path):
    """空 body → 檔尾仍有換行（frontmatter 後 ---\\n\\n 已含換行）。"""
    content = _save(tmp_path, "")
    assert content.endswith("\n")
