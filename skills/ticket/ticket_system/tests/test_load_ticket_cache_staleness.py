"""3.2.0-W1-155 — 程序內快取不得讓 file_lock 內的讀改寫覆蓋他方寫入。

形狀：同一程序先 load_ticket（填快取）→ 外部改寫票檔 → 同程序在 file_lock 內
讀改寫。使用真實 parser.load_ticket（不 mock），兩方寫入都必須保留。
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

from ticket_system.lib import parser, ticket_builder

TID = "0.0.0-W0-CACHE"


@pytest.fixture
def ticket_file(tmp_path: Path, monkeypatch) -> Path:
    path = tmp_path / f"{TID}.md"
    path.write_text(
        f"---\nid: {TID}\ntitle: cache target\nstatus: pending\n"
        "children: []\nspawned_tickets: []\n---\n\nbody\n",
        encoding="utf-8",
    )
    fake = lambda version, ticket_id: path  # noqa: E731
    monkeypatch.setattr(parser, "get_ticket_path", fake)
    monkeypatch.setattr(ticket_builder, "get_ticket_path", fake)
    parser._ticket_cache.clear()
    getattr(parser, "_ticket_cache_stat", {}).clear()
    yield path
    parser._ticket_cache.clear()
    getattr(parser, "_ticket_cache_stat", {}).clear()


def _external_append(path: Path, line: str) -> None:
    """以另一個程序在票檔尾端追加內容（模擬他方 append-log）。"""
    code = (
        "import sys;p=sys.argv[1];"
        "open(p,'a',encoding='utf-8').write(sys.argv[2])"
    )
    subprocess.run([sys.executable, "-c", code, str(path), line], check=True)


def test_locked_rmw_keeps_external_write_after_cached_load(ticket_file: Path):
    assert parser.load_ticket("0.0.0", TID) is not None  # 填快取
    time.sleep(0.01)
    _external_append(ticket_file, "\nEXTERNAL-LOG-LINE\n")

    assert ticket_builder.update_source_spawned_tickets(TID, "0.0.0-W0-NEW") is True

    text = ticket_file.read_text(encoding="utf-8")
    assert "EXTERNAL-LOG-LINE" in text, "他方寫入被舊快取覆蓋"
    assert "0.0.0-W0-NEW" in text, "本方寫入遺失"


def test_cache_hit_still_works_when_file_unchanged(ticket_file: Path):
    first = parser.load_ticket("0.0.0", TID)
    assert parser.load_ticket("0.0.0", TID) is first
