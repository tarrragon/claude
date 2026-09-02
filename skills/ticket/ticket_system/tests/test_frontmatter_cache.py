"""frontmatter 磁碟快取（parser.py）與 ticket_state_root 行程快取（paths.py）
的專屬測試（0.2.1-W4-018 補測，來源 0.2.1-W4-020）。

背景：W4-018 為 list_tickets() 加入兩層快取——paths.get_ticket_state_root()
的行程內快取，與 parser 的 (mtime, size) 鍵磁碟快取
（.claude/hook-logs/ticket-frontmatter-cache.pkl，save_ticket 時失效，
TICKET_SYSTEM_TEST_ISOLATION 下停用）。分支合併時僅有實作與 conftest，
正確性只由既有回歸間接覆蓋，本檔補上專屬測試。

隔離策略：autouse fixture `_isolate_project_root`（skill-root conftest）預設
注入 TICKET_SYSTEM_TEST_ISOLATION=1，使磁碟快取停用（見 5.）。需要驗證磁碟
快取本身行為的測試改用 `_disk_cache_enabled` fixture：monkeypatch
`parser._frontmatter_disk_cache_enabled` 略過此旗標檢查、並將
`parser.get_ticket_state_root` 導向獨立 tmp 目錄（僅影響快取檔落點，不影響
ticket 檔案本身的路徑解析，後者仍走 `paths.get_ticket_state_root()`
原名，未被 monkeypatch），確保絕不寫入真實 repo 的
`.claude/hook-logs/ticket-frontmatter-cache.pkl`。
"""
from __future__ import annotations

import os
import pickle

import pytest

from ticket_system.lib import parser
from ticket_system.lib.paths import get_ticket_path
from ticket_system.lib.ticket_loader import list_tickets

VERSION = "9.9.9"


def _ticket_content(ticket_id: str, title: str) -> str:
    return (
        "---\n"
        f"id: {ticket_id}\n"
        f"title: {title}\n"
        "type: IMP\n"
        "priority: P2\n"
        "status: pending\n"
        "---\n\n"
        "# body\n"
    )


def _write_ticket(ticket_id: str, title: str) -> "os.PathLike[str]":
    path = get_ticket_path(VERSION, ticket_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_ticket_content(ticket_id, title), encoding="utf-8")
    return path


def _counting_parse_frontmatter(monkeypatch, module=parser):
    """包裝 module.parse_frontmatter 計數呼叫次數，回傳計數器（list 單元素）。"""
    original = module.parse_frontmatter
    counter = {"calls": 0}

    def _wrapped(content):
        counter["calls"] += 1
        return original(content)

    monkeypatch.setattr(module, "parse_frontmatter", _wrapped)
    return counter


@pytest.fixture
def disk_cache_enabled(monkeypatch, tmp_path):
    """啟用磁碟快取，快取檔落點導向獨立 tmp 目錄（不影響 ticket 檔案路徑解析）。"""
    cache_root = tmp_path / "cache-root"
    cache_root.mkdir()
    monkeypatch.setattr(parser, "_frontmatter_disk_cache_enabled", lambda: True)
    monkeypatch.setattr(parser, "get_ticket_state_root", lambda: cache_root)
    monkeypatch.setattr(parser, "_frontmatter_disk_cache", None)
    monkeypatch.setattr(parser, "_frontmatter_disk_cache_dirty", False)
    return cache_root


def _reset_process_caches(monkeypatch):
    """清空 process-scoped `_ticket_cache`，模擬「新的 CLI process」讀取。

    磁碟快取（`_frontmatter_disk_cache`）刻意不清，用以測試其跨呼叫存活的
    設計目的；只有測試需要驗證「磁碟快取本身失效」時才額外清除該變數。
    """
    monkeypatch.setattr(parser, "_ticket_cache", {})


class TestDiskCacheHitAvoidsReparse:
    """失效鍵：(mtime, size) 相符時第二次讀取跳過重新解析。"""

    def test_second_load_ticket_skips_parse_when_stat_unchanged(
        self, disk_cache_enabled, monkeypatch
    ):
        _write_ticket("9.9.9-W1-001", "first")
        counter = _counting_parse_frontmatter(monkeypatch)

        first = parser.load_ticket(VERSION, "9.9.9-W1-001")
        assert counter["calls"] == 1
        assert first["title"] == "first"

        _reset_process_caches(monkeypatch)  # 模擬新 process：process cache 已清空
        second = parser.load_ticket(VERSION, "9.9.9-W1-001")

        assert counter["calls"] == 1  # 磁碟快取命中，未重新解析
        assert second["title"] == "first"

    def test_list_tickets_second_call_zero_parse_invocations(
        self, disk_cache_enabled, monkeypatch
    ):
        """acceptance 要求的計數斷言：第二次 list_tickets 解析呼叫計數為 0。"""
        _write_ticket("9.9.9-W1-001", "alpha")
        _write_ticket("9.9.9-W1-002", "beta")

        first_batch = list_tickets(VERSION)
        assert {t["title"] for t in first_batch} == {"alpha", "beta"}

        # 模擬新 process：process-scoped 快取與磁碟快取記憶體副本皆重置，
        # 強迫第二次讀取真的走 Guard Clause 1.7（讀取磁碟檔案），而非只是
        # 沿用同一 process 尚未落盤的記憶體 dict。
        monkeypatch.setattr(parser, "_ticket_cache", {})
        monkeypatch.setattr(parser, "_frontmatter_disk_cache", None)

        counter = _counting_parse_frontmatter(monkeypatch)
        second_batch = list_tickets(VERSION)

        assert counter["calls"] == 0
        assert {t["title"] for t in second_batch} == {"alpha", "beta"}


class TestSameSecondSameLengthRewriteRisk:
    """已知風險：mtime 與 size 皆相同的同秒等長改寫會誤判快取命中。

    來源票 how 要求：若判定為可接受風險，於測試檔頭與 Solution 明示理由。
    結論（見本票 Solution）：mtime+size 鍵在此極端情境下確實會 false-hit，
    但 save_ticket 每次寫入必然更新 mtime 且顯式呼叫
    `_invalidate_frontmatter_disk_cache_entry`（見 parser.py 模組註解），
    唯有繞過 save_ticket 直接以外部工具改寫檔案且維持位元組長度完全相同、
    並以 os.utime 精確對齊到原 mtime，才會重現此路徑——非 ticket CLI 的
    正常寫入路徑會觸發。以下測試用 os.utime 顯式構造此邊界情境（非仰賴同秒
    時鐘巧合，確定性可重現），驗證行為與模組註解描述一致。
    """

    def test_identical_mtime_and_size_causes_stale_read(
        self, disk_cache_enabled, monkeypatch
    ):
        path = _write_ticket("9.9.9-W1-003", "before")
        parser.load_ticket(VERSION, "9.9.9-W1-003")  # 建立快取條目
        original_stat = path.stat()

        # 等長改寫（"before" 與 "after " 皆 6 字元），避免 size 產生差異
        rewritten = _ticket_content("9.9.9-W1-003", "after ")
        assert len(rewritten) == len(_ticket_content("9.9.9-W1-003", "before"))
        path.write_text(rewritten, encoding="utf-8")
        os.utime(path, (original_stat.st_atime, original_stat.st_mtime))
        assert path.stat().st_size == original_stat.st_size
        assert path.stat().st_mtime == original_stat.st_mtime

        _reset_process_caches(monkeypatch)
        stale = parser.load_ticket(VERSION, "9.9.9-W1-003")

        # 已知風險重現：(mtime, size) 鍵無法區分內容差異，回傳的仍是舊值
        assert stale["title"] == "before"


class TestInvalidationOnSave:
    """save_ticket 寫入後同步失效磁碟快取，下次讀取重新解析。"""

    def test_reload_after_save_reparse_gets_fresh_value(
        self, disk_cache_enabled, monkeypatch
    ):
        path = _write_ticket("9.9.9-W1-004", "original")
        counter = _counting_parse_frontmatter(monkeypatch)

        loaded = parser.load_ticket(VERSION, "9.9.9-W1-004")
        assert counter["calls"] == 1
        loaded["title"] = "updated"
        parser.save_ticket(loaded, path)

        _reset_process_caches(monkeypatch)
        reloaded = parser.load_ticket(VERSION, "9.9.9-W1-004")

        assert counter["calls"] == 2  # save 後失效，第二次讀取重新解析
        assert reloaded["title"] == "updated"


class TestDiskCacheCorruptionFailsOpen:
    """pickle 損毀或版本不符時 fail-open 重建，而非崩潰。"""

    def test_truncated_pickle_file_returns_empty_dict_without_raising(
        self, disk_cache_enabled, capsys
    ):
        cache_path = parser._frontmatter_cache_path()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(b"\x80\x04not-a-valid-pickle-stream")

        result = parser._load_frontmatter_disk_cache()

        assert result == {}
        captured = capsys.readouterr()
        assert "frontmatter 磁碟快取載入失敗" in captured.err

    def test_load_ticket_still_succeeds_when_cache_file_corrupted(
        self, disk_cache_enabled
    ):
        cache_path = parser._frontmatter_cache_path()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(b"garbage-not-pickle")
        _write_ticket("9.9.9-W1-005", "resilient")

        ticket = parser.load_ticket(VERSION, "9.9.9-W1-005")

        assert ticket is not None
        assert ticket["title"] == "resilient"

    def test_non_dict_pickle_payload_treated_as_empty(self, disk_cache_enabled):
        """pickle 內容合法但型別非 dict（版本不符的可能樣態之一）：視為空快取。"""
        cache_path = parser._frontmatter_cache_path()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "wb") as f:
            pickle.dump(["unexpected", "list", "payload"], f)

        result = parser._load_frontmatter_disk_cache()

        assert result == {}


class TestAtomicWrite:
    """flush_frontmatter_disk_cache 原子寫入：暫存檔 + os.replace，不留殘檔。"""

    def test_flush_writes_readable_pickle_without_leftover_tmp_files(
        self, disk_cache_enabled
    ):
        parser._frontmatter_disk_cache = {
            "k": {"mtime": 1.0, "size": 10, "frontmatter": {"id": "k"}, "body": ""}
        }
        parser._frontmatter_disk_cache_dirty = True

        parser.flush_frontmatter_disk_cache()

        cache_path = parser._frontmatter_cache_path()
        assert cache_path.exists()
        with open(cache_path, "rb") as f:
            loaded = pickle.load(f)
        assert loaded["k"]["frontmatter"]["id"] == "k"

        leftover_tmp = list(cache_path.parent.glob(f".{cache_path.name}.*.tmp"))
        assert leftover_tmp == []
        assert parser._frontmatter_disk_cache_dirty is False

    def test_flush_failure_leaves_prior_cache_file_untouched(
        self, disk_cache_enabled, monkeypatch, capsys
    ):
        """寫入失敗（模擬 pickle.dump 拋錯）時，暫存檔清除且既有快取檔不受影響。"""
        parser._frontmatter_disk_cache = {
            "k1": {"mtime": 1.0, "size": 1, "frontmatter": {"id": "k1"}, "body": ""}
        }
        parser._frontmatter_disk_cache_dirty = True
        parser.flush_frontmatter_disk_cache()
        cache_path = parser._frontmatter_cache_path()
        original_bytes = cache_path.read_bytes()

        parser._frontmatter_disk_cache = {
            "k2": {"mtime": 2.0, "size": 2, "frontmatter": {"id": "k2"}, "body": ""}
        }
        parser._frontmatter_disk_cache_dirty = True

        def _raise_oserror(*_args, **_kwargs):
            raise OSError("simulated disk full")

        monkeypatch.setattr(parser.pickle, "dump", _raise_oserror)
        parser.flush_frontmatter_disk_cache()  # 不應拋出（quality-baseline 規則 4）

        assert cache_path.read_bytes() == original_bytes  # 舊內容完整保留
        leftover_tmp = list(cache_path.parent.glob(f".{cache_path.name}.*.tmp"))
        assert leftover_tmp == []
        captured = capsys.readouterr()
        assert "frontmatter 磁碟快取寫回失敗" in captured.err


class TestTestIsolationDisablesDiskCache:
    """測試隔離開關（TICKET_SYSTEM_TEST_ISOLATION=1，autouse fixture 預設值）
    確實停用磁碟快取——本 class 刻意不使用 disk_cache_enabled fixture。
    """

    def test_enabled_check_is_false_under_default_isolation(self):
        assert os.environ.get("TICKET_SYSTEM_TEST_ISOLATION") == "1"
        assert parser._frontmatter_disk_cache_enabled() is False

    def test_second_load_ticket_still_reparses_without_disk_cache(self, monkeypatch):
        _write_ticket("9.9.9-W1-006", "iso-first")
        counter = _counting_parse_frontmatter(monkeypatch)

        parser.load_ticket(VERSION, "9.9.9-W1-006")
        assert counter["calls"] == 1

        monkeypatch.setattr(parser, "_ticket_cache", {})  # 模擬新 process
        parser.load_ticket(VERSION, "9.9.9-W1-006")

        assert counter["calls"] == 2  # 磁碟快取停用，process cache 清空後必重新解析

    def test_cache_file_never_created_under_default_isolation(self, monkeypatch):
        _write_ticket("9.9.9-W1-007", "iso-file-check")
        list_tickets(VERSION)

        cache_path = parser._frontmatter_cache_path()
        assert not cache_path.exists()
