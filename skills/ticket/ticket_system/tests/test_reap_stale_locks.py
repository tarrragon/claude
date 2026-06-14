"""W8-017 — stale .md.lock reap 安全收割測試。

驗證：
- 操作結束後可安全收割 stale lock（無人持有的 *.md.lock）
- reap 不誤刪 active lock（仍被某 process 持鎖的 lock 不可刪）
- reap 為非阻塞（不會卡在 active lock 上）

設計約束（見 ticket 1.0.0-W8-017 Context Bundle）：
    禁止天真 inline unlink（會重新引入 W14-005 flock-unlink race）。
    reap 對每個 *.md.lock 試 flock(LOCK_EX | LOCK_NB)，搶到（=stale）
    才在持鎖狀態下 unlink，搶不到（=active）跳過。
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from ticket_system.lib.file_lock import file_lock, reap_stale_locks


def _make_lock_file(directory: Path, name: str) -> Path:
    """製造一個 0-byte stale lock file（無人持鎖），模擬殘留。"""
    lock_path = directory / f"{name}.md.lock"
    lock_path.write_text("", encoding="utf-8")
    return lock_path


class TestReapStaleLocks:
    """reap_stale_locks 的收割契約。"""

    def test_reaps_stale_lock_files(self, tmp_path):
        """無人持有的 *.md.lock 應被收割。"""
        stale_a = _make_lock_file(tmp_path, "ticket-a")
        stale_b = _make_lock_file(tmp_path, "ticket-b")
        assert stale_a.exists() and stale_b.exists()

        reaped = reap_stale_locks(tmp_path)

        assert not stale_a.exists()
        assert not stale_b.exists()
        assert reaped == 2

    def test_reaps_nested_lock_files(self, tmp_path):
        """巢狀目錄下的 *.md.lock 也應被遞迴收割。"""
        nested = tmp_path / "v1" / "v1.0" / "v1.0.0" / "tickets"
        nested.mkdir(parents=True)
        stale = _make_lock_file(nested, "ticket-nested")
        assert stale.exists()

        reaped = reap_stale_locks(tmp_path)

        assert not stale.exists()
        assert reaped == 1

    def test_does_not_reap_active_lock(self, tmp_path):
        """仍被持鎖的 active lock 不可被收割。"""
        target = tmp_path / "ticket-active.md"

        with file_lock(target):
            # 持鎖期間 reap：active lock 必須保留
            active_lock = tmp_path / "ticket-active.md.lock"
            assert active_lock.exists()

            reaped = reap_stale_locks(tmp_path)

            assert active_lock.exists()  # 未被誤刪
            assert reaped == 0

    def test_reaps_stale_but_skips_active(self, tmp_path):
        """混合場景：收割 stale，跳過 active。"""
        stale = _make_lock_file(tmp_path, "ticket-stale")
        target = tmp_path / "ticket-active.md"

        with file_lock(target):
            active_lock = tmp_path / "ticket-active.md.lock"
            reaped = reap_stale_locks(tmp_path)

            assert not stale.exists()  # stale 被收割
            assert active_lock.exists()  # active 保留
            assert reaped == 1

    def test_returns_zero_on_empty_dir(self, tmp_path):
        """無任何 lock file 時回傳 0，不丟例外。"""
        assert reap_stale_locks(tmp_path) == 0

    def test_graceful_on_missing_dir(self, tmp_path):
        """目錄不存在時 graceful 回傳 0（不丟例外）。"""
        missing = tmp_path / "does-not-exist"
        assert reap_stale_locks(missing) == 0

    def test_ignores_create_lock_sentinel(self, tmp_path):
        """只收割 *.md.lock，不動 .ticket-create.lock 等其他 lock。"""
        create_lock = tmp_path / ".ticket-create.lock"
        create_lock.write_text("", encoding="utf-8")

        reap_stale_locks(tmp_path)

        assert create_lock.exists()  # 非 *.md.lock，不收割
