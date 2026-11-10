"""
pm-registry.json 共用模組單元測試

測試 .claude/lib/pm_registry.py 的公開 API。
"""

import json
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lib.pm_registry import (
    get_registry_dir,
    get_registry_paths,
    read_registry,
    write_registry,
    register_session,
    update_heartbeat,
    release_session,
    HEARTBEAT_DEBOUNCE_SECONDS,
    DEGRADED_READ_KEY,
)


@pytest.fixture
def registry_paths():
    """建立臨時目錄，回傳 (registry_file, lock_file) tuple。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        yield root / "pm-registry.json", root / "pm-registry.lock"


class TestGetRegistryDir:
    def test_non_git_cwd_returns_none(self):
        """非 git 環境回傳 None（契約 v2 D3：不再 fallback 寫入任何路徑）。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = get_registry_dir(cwd=tmpdir)
            assert result is None

    def test_get_registry_paths_returns_none_for_non_git_cwd(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = get_registry_paths(cwd=tmpdir)
            assert result is None

    def test_get_registry_paths_shape_for_git_repo(self):
        """真實 git repo（本專案自身）應解析出有效路徑 tuple。"""
        project_root = str(Path(__file__).resolve().parents[3])
        result = get_registry_paths(cwd=project_root)
        assert result is not None
        registry_file, lock_file = result
        assert registry_file.name == "pm-registry.json"
        assert lock_file.name == "pm-registry.lock"
        assert registry_file.parent == lock_file.parent


class TestReadRegistry:
    def test_missing_file_returns_empty_skeleton(self, registry_paths):
        registry_file, _ = registry_paths
        data = read_registry(registry_file)
        assert data == {"schema_version": 2, "sessions": {}, "_degraded": True}

    def test_corrupt_json_rebuilds_and_notifies_stderr(self, registry_paths, capsys):
        registry_file, _ = registry_paths
        registry_file.parent.mkdir(parents=True, exist_ok=True)
        registry_file.write_text("{not valid json", encoding="utf-8")
        data = read_registry(registry_file)
        assert data == {"schema_version": 2, "sessions": {}, "_degraded": True}
        captured = capsys.readouterr()
        assert "重建空 registry" in captured.err

    def test_missing_sessions_key_rebuilds(self, registry_paths):
        registry_file, _ = registry_paths
        registry_file.parent.mkdir(parents=True, exist_ok=True)
        registry_file.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")
        data = read_registry(registry_file)
        assert data == {"schema_version": 2, "sessions": {}, "_degraded": True}

    def test_v1_file_normalized_gracefully_not_rebuilt(self, registry_paths):
        """schema_version=1 檔案（含已廢棄的 parent_session_id 欄位）不視為
        損毀；graceful 正規化為 v2 形狀，既有 session 資料保留不遺失。"""
        registry_file, _ = registry_paths
        registry_file.parent.mkdir(parents=True, exist_ok=True)
        v1_payload = {
            "schema_version": 1,
            "sessions": {
                "legacy-sess": {
                    "name": "old-name",
                    "project": "/old/project",
                    "registered_at": "2026-01-01T00:00:00+00:00",
                    "heartbeat_ts": "2026-01-01T00:00:00+00:00",
                    "tickets": ["ticket-a"],
                    "files": ["a.py"],
                    "parent_session_id": "legacy-sess",
                }
            },
        }
        registry_file.write_text(json.dumps(v1_payload), encoding="utf-8")

        data = read_registry(registry_file)

        assert data["schema_version"] == 2
        entry = data["sessions"]["legacy-sess"]
        assert "parent_session_id" not in entry
        # 其餘欄位（含 lease：tickets/files）完整保留，非損毀重建
        assert entry["tickets"] == ["ticket-a"]
        assert entry["files"] == ["a.py"]
        assert entry["name"] == "old-name"


class TestWriteRegistry:
    def test_write_then_read_roundtrip(self, registry_paths):
        registry_file, _ = registry_paths
        payload = {"schema_version": 2, "sessions": {"s1": {"name": "x"}}}
        write_registry(registry_file, payload)
        assert read_registry(registry_file) == payload

    def test_write_overwrites_existing_content_fully(self, registry_paths):
        """seek(0)+truncate() 確保新內容較短時不殘留舊內容尾巴。"""
        registry_file, _ = registry_paths
        write_registry(
            registry_file,
            {"schema_version": 2, "sessions": {"a": {"name": "aaaaaaaaaa"}}},
        )
        write_registry(registry_file, {"schema_version": 2, "sessions": {}})
        raw = registry_file.read_text(encoding="utf-8")
        assert "aaaaaaaaaa" not in raw
        assert json.loads(raw) == {"schema_version": 2, "sessions": {}}

    def test_write_strips_degraded_flag_before_persisting(self, registry_paths):
        """DEGRADED_READ_KEY 是 read_registry 降級分支的顯示層旗標，非
        schema 正式欄位；write_registry 必須在序列化前剝除，不得讓其
        流向磁碟（否則首次啟動即固化旗標，此後每次讀取皆誤判降級）。"""
        registry_file, _ = registry_paths
        payload = {
            "schema_version": 2,
            "sessions": {"s1": {"name": "x"}},
            DEGRADED_READ_KEY: True,
        }
        write_registry(registry_file, payload)
        raw = json.loads(registry_file.read_text(encoding="utf-8"))
        assert DEGRADED_READ_KEY not in raw
        # 呼叫端傳入的 dict 不應被就地 mutate（同一鎖範圍內可能續用）
        assert payload[DEGRADED_READ_KEY] is True


class TestRegisterSession:
    def test_first_boot_does_not_persist_degraded_flag(self, registry_paths):
        """正常首次啟動（registry 檔尚不存在）不是邊界情況：read_registry
        對缺檔回傳帶 DEGRADED_READ_KEY 的空骨架，register_session 以此為
        基底寫入，write_registry 必須剝除該旗標，磁碟 top-level 不得殘留。
        """
        registry_file, lock_file = registry_paths
        assert not registry_file.exists()
        register_session(
            registry_file, lock_file, "sess-1", "flutter-balance-b6",
            "/repo/worktree-b6",
        )
        raw = json.loads(registry_file.read_text(encoding="utf-8"))
        assert DEGRADED_READ_KEY not in raw
        assert set(raw.keys()) == {"schema_version", "sessions"}
        # 再次讀取亦不應回報降級（檔案本身合法，非讀取失敗）
        data = read_registry(registry_file)
        assert DEGRADED_READ_KEY not in data
        assert "sess-1" in data["sessions"]

    def test_existing_poisoned_file_self_heals_on_read(self, registry_paths):
        """既有帶降級旗標的磁碟檔（本次修正前的舊碼誤寫入）不會被永久
        判為降級：檔案本身結構合法，read_registry 的成功讀取分支須原地
        剝除該殘留鍵，下次寫入自然不再帶出。"""
        registry_file, _ = registry_paths
        registry_file.parent.mkdir(parents=True, exist_ok=True)
        poisoned = {
            "schema_version": 2,
            "sessions": {"s1": {"name": "x", "heartbeat_ts": "2026-01-01T00:00:00+00:00"}},
            DEGRADED_READ_KEY: True,
        }
        registry_file.write_text(json.dumps(poisoned), encoding="utf-8")
        data = read_registry(registry_file)
        assert DEGRADED_READ_KEY not in data
        assert data["sessions"]["s1"]["name"] == "x"
    def test_register_creates_entry(self, registry_paths):
        registry_file, lock_file = registry_paths
        register_session(
            registry_file, lock_file, "sess-1", "flutter-balance-b6",
            "/repo/worktree-b6",
        )
        data = read_registry(registry_file)
        entry = data["sessions"]["sess-1"]
        assert entry["name"] == "flutter-balance-b6"
        assert entry["project"] == "/repo/worktree-b6"
        assert entry["registered_at"] == entry["heartbeat_ts"]
        assert entry["tickets"] == []
        assert entry["files"] == []
        assert "parent_session_id" not in entry

    def test_default_source_resets_existing_entry(self, registry_paths):
        """未指定 source（空字串，非 "resume"）一律 reset，維持原有行為
        （契約 v2 D4 增補 1：僅 resume 觸發 merge，其餘皆 reset）。"""
        registry_file, lock_file = registry_paths
        register_session(registry_file, lock_file, "sess-1", "old-name", "/old")
        register_session(registry_file, lock_file, "sess-1", "new-name", "/new")
        data = read_registry(registry_file)
        assert len(data["sessions"]) == 1
        assert data["sessions"]["sess-1"]["name"] == "new-name"

    def test_startup_source_resets_lease(self, registry_paths):
        """source="startup" 時重置 tickets/files/registered_at（新生 session
        不繼承舊 lease）。"""
        registry_file, lock_file = registry_paths
        register_session(registry_file, lock_file, "sess-1", "n", "/p", source="startup")
        data = read_registry(registry_file)
        data["sessions"]["sess-1"]["tickets"] = ["ticket-a"]
        write_registry(registry_file, data)
        old_registered_at = data["sessions"]["sess-1"]["registered_at"]

        register_session(registry_file, lock_file, "sess-1", "n", "/p", source="startup")

        after = read_registry(registry_file)["sessions"]["sess-1"]
        assert after["tickets"] == []
        assert after["registered_at"] != old_registered_at

    def test_clear_source_resets_lease(self, registry_paths):
        """source="clear" 與 startup 同視為新生 session，重置 lease。"""
        registry_file, lock_file = registry_paths
        register_session(registry_file, lock_file, "sess-1", "n", "/p")
        data = read_registry(registry_file)
        data["sessions"]["sess-1"]["tickets"] = ["ticket-a"]
        write_registry(registry_file, data)

        register_session(registry_file, lock_file, "sess-1", "n", "/p", source="clear")

        after = read_registry(registry_file)["sessions"]["sess-1"]
        assert after["tickets"] == []

    def test_resume_source_merges_and_preserves_lease(self, registry_paths):
        """source="resume" 且既有 entry 存在時 merge：保留 tickets/files/
        registered_at，僅更新 heartbeat_ts/name/project（契約 v2 D4 增補 1
        核心行為：繼承既有 lease）。"""
        registry_file, lock_file = registry_paths
        register_session(registry_file, lock_file, "sess-1", "old-name", "/old")
        data = read_registry(registry_file)
        data["sessions"]["sess-1"]["tickets"] = ["ticket-a"]
        data["sessions"]["sess-1"]["files"] = ["a.py"]
        write_registry(registry_file, data)
        old_registered_at = data["sessions"]["sess-1"]["registered_at"]

        register_session(
            registry_file, lock_file, "sess-1", "new-name", "/new", source="resume"
        )

        after = read_registry(registry_file)["sessions"]["sess-1"]
        assert after["tickets"] == ["ticket-a"]
        assert after["files"] == ["a.py"]
        assert after["registered_at"] == old_registered_at
        assert after["name"] == "new-name"
        assert after["project"] == "/new"

    def test_resume_source_without_existing_entry_creates_fresh(self, registry_paths):
        """source="resume" 但 entry 不存在（首次見過的 session_id）：無可
        merge 對象，退回建立全新 entry，非拋出例外或跳過。"""
        registry_file, lock_file = registry_paths
        register_session(
            registry_file, lock_file, "sess-orphan-resume", "n", "/p", source="resume"
        )
        data = read_registry(registry_file)
        assert "sess-orphan-resume" in data["sessions"]
        assert data["sessions"]["sess-orphan-resume"]["tickets"] == []


class TestUpdateHeartbeat:
    def test_missing_entry_self_heals(self, registry_paths):
        registry_file, lock_file = registry_paths
        wrote = update_heartbeat(registry_file, lock_file, "sess-2", "name-2", "/p")
        assert wrote is True
        data = read_registry(registry_file)
        assert "sess-2" in data["sessions"]

    def test_debounce_skips_write_within_window(self, registry_paths):
        registry_file, lock_file = registry_paths
        register_session(registry_file, lock_file, "sess-3", "name-3", "/p")
        before = read_registry(registry_file)["sessions"]["sess-3"]["heartbeat_ts"]

        wrote = update_heartbeat(registry_file, lock_file, "sess-3", "name-3", "/p")

        assert wrote is False
        after = read_registry(registry_file)["sessions"]["sess-3"]["heartbeat_ts"]
        assert before == after

    def test_stale_heartbeat_beyond_debounce_updates(self, registry_paths, monkeypatch):
        registry_file, lock_file = registry_paths
        register_session(registry_file, lock_file, "sess-4", "name-4", "/p")

        # 手動回撥 heartbeat_ts 到 debounce 視窗之外，模擬時間流逝
        data = read_registry(registry_file)
        from datetime import datetime, timedelta, timezone
        old_ts = (
            datetime.now(timezone.utc)
            - timedelta(seconds=HEARTBEAT_DEBOUNCE_SECONDS + 5)
        ).isoformat()
        data["sessions"]["sess-4"]["heartbeat_ts"] = old_ts
        write_registry(registry_file, data)

        wrote = update_heartbeat(registry_file, lock_file, "sess-4", "name-4", "/p")
        assert wrote is True
        new_ts = read_registry(registry_file)["sessions"]["sess-4"]["heartbeat_ts"]
        assert new_ts != old_ts

    def test_malformed_heartbeat_ts_treated_as_needs_update(self, registry_paths):
        registry_file, lock_file = registry_paths
        register_session(registry_file, lock_file, "sess-5", "name-5", "/p")
        data = read_registry(registry_file)
        data["sessions"]["sess-5"]["heartbeat_ts"] = "not-a-timestamp"
        write_registry(registry_file, data)

        wrote = update_heartbeat(registry_file, lock_file, "sess-5", "name-5", "/p")
        assert wrote is True

    def test_existing_entry_merge_preserves_tickets_and_files(
        self, registry_paths, monkeypatch
    ):
        """既有 entry 心跳更新一律 merge：保留 tickets/files/registered_at，
        僅更新 heartbeat_ts/name/project（契約 v2 D4：防心跳把 Phase 2
        lease 寫入覆蓋掉）。"""
        registry_file, lock_file = registry_paths
        register_session(registry_file, lock_file, "sess-7", "old-name", "/old")
        data = read_registry(registry_file)
        data["sessions"]["sess-7"]["tickets"] = ["ticket-a"]
        data["sessions"]["sess-7"]["files"] = ["a.py"]
        from datetime import datetime, timedelta, timezone
        old_ts = (
            datetime.now(timezone.utc)
            - timedelta(seconds=HEARTBEAT_DEBOUNCE_SECONDS + 5)
        ).isoformat()
        data["sessions"]["sess-7"]["heartbeat_ts"] = old_ts
        old_registered_at = data["sessions"]["sess-7"]["registered_at"]
        write_registry(registry_file, data)

        wrote = update_heartbeat(registry_file, lock_file, "sess-7", "new-name", "/new")

        assert wrote is True
        after = read_registry(registry_file)["sessions"]["sess-7"]
        assert after["tickets"] == ["ticket-a"]
        assert after["files"] == ["a.py"]
        assert after["registered_at"] == old_registered_at
        assert after["name"] == "new-name"
        assert after["project"] == "/new"
        assert after["heartbeat_ts"] != old_ts


class TestReleaseSession:
    def test_release_removes_entry(self, registry_paths):
        registry_file, lock_file = registry_paths
        register_session(registry_file, lock_file, "sess-6", "name-6", "/p")
        released = release_session(registry_file, lock_file, "sess-6")
        assert released is True
        data = read_registry(registry_file)
        assert "sess-6" not in data["sessions"]

    def test_release_missing_entry_returns_false(self, registry_paths):
        registry_file, lock_file = registry_paths
        released = release_session(registry_file, lock_file, "no-such-session")
        assert released is False

    def test_release_keeps_other_sessions(self, registry_paths):
        registry_file, lock_file = registry_paths
        register_session(registry_file, lock_file, "keep-me", "k", "/k")
        register_session(registry_file, lock_file, "remove-me", "r", "/r")
        release_session(registry_file, lock_file, "remove-me")
        data = read_registry(registry_file)
        assert set(data["sessions"].keys()) == {"keep-me"}


class TestConcurrentAccess:
    def test_multiple_sessions_accumulate(self, registry_paths):
        """依序（非併發，避免測試 flaky）註冊多個 session 均保留。"""
        registry_file, lock_file = registry_paths
        for i in range(5):
            register_session(registry_file, lock_file, f"sess-{i}", f"name-{i}", "/p")
        data = read_registry(registry_file)
        assert len(data["sessions"]) == 5


class TestAtomicWrite:
    """write_registry 的 tempfile + os.replace 原子替換（0.2.1-W3-556）。"""

    def test_no_temp_file_left_behind_after_success(self, registry_paths):
        registry_file, lock_file = registry_paths
        register_session(registry_file, lock_file, "sess-atomic", "n", "/p")
        siblings = [
            p for p in registry_file.parent.iterdir() if p.name != lock_file.name
        ]
        assert siblings == [registry_file]

    def test_replace_failure_cleans_up_temp_file_and_raises(self, registry_paths):
        registry_file, lock_file = registry_paths
        registry_file.parent.mkdir(parents=True, exist_ok=True)

        with patch("lib.pm_registry.os.replace", side_effect=OSError("disk full")):
            with pytest.raises(OSError):
                write_registry(registry_file, {"schema_version": 1, "sessions": {}})

        # 暫存檔已清理，且目標檔案未被建立（os.replace 從未真正發生）
        leftovers = list(registry_file.parent.glob("*.tmp.*"))
        assert leftovers == []
        assert not registry_file.exists()

    def test_write_failure_preserves_previous_content(self, registry_paths):
        """寫入失敗時，既有 registry 內容維持原封不動（原子替換未發生）。"""
        registry_file, lock_file = registry_paths
        register_session(registry_file, lock_file, "sess-keep", "n", "/p")
        before = registry_file.read_text(encoding="utf-8")

        with patch("lib.pm_registry.os.replace", side_effect=OSError("disk full")):
            with pytest.raises(OSError):
                write_registry(
                    registry_file, {"schema_version": 1, "sessions": {"x": {}}}
                )

        after = registry_file.read_text(encoding="utf-8")
        assert before == after

    def test_concurrent_read_during_write_never_sees_torn_content(self, registry_paths):
        """讀端在寫入密集進行時反覆讀取，永遠看到完整可解析的 JSON（不會 torn read）。

        直接讀原始檔案（非透過 read_registry，因其對解析失敗會靜默降級為
        「重建空 registry」，會遮蔽本測試要驗證的 torn-write 問題）。
        """
        registry_file, lock_file = registry_paths
        register_session(registry_file, lock_file, "seed", "n", "/p")

        stop_flag = threading.Event()
        errors = []

        def reader():
            while not stop_flag.is_set():
                if registry_file.exists():
                    try:
                        json.loads(registry_file.read_text(encoding="utf-8"))
                    except json.JSONDecodeError as e:
                        errors.append(e)

        reader_thread = threading.Thread(target=reader)
        reader_thread.start()
        try:
            for i in range(150):
                register_session(
                    registry_file, lock_file, f"writer-{i % 10}", f"name-{i}", f"/p{i}"
                )
        finally:
            stop_flag.set()
            reader_thread.join(timeout=5)

        assert errors == []
