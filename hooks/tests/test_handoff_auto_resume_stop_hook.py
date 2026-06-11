"""
handoff-auto-resume-stop-hook tests.

W17-095.2：驗證 should_preserve_pending_json 引用 is_handoff_stale 後的行為。
W17-118：驗證 scan_pending_handoff_tasks 在剛建 handoff 與 stale 並存時的時序語意：
- 剛建 handoff (< RECENT_HANDOFF_WINDOW_SECONDS) → recent_tasks，不阻塞
- stale + 非剛建 → GC 刪除，不計入 pending_tasks
- 純 active（非 stale 非剛建） → pending_tasks
- 邊界值 299 / 300 / 301 秒驗證
"""

import importlib.util
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock


HOOK_PATH = Path(__file__).parent.parent.parent / "skills" / "ticket" / "hooks" / "handoff-auto-resume-stop-hook.py"


def load_hook_module():
    spec = importlib.util.spec_from_file_location(
        "handoff_auto_resume_stop_hook", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _patch_is_handoff_stale(monkeypatch, return_value):
    """以 monkeypatch 替換 module 的 is_handoff_stale，避開實際 ticket fs 依賴。"""
    hook = load_hook_module()
    monkeypatch.setattr(hook, "is_handoff_stale", lambda record, project_root=None: return_value)
    return hook


# ===== should_preserve_pending_json 行為驗證（W17-095.2）=====


def test_task_chain_target_in_progress_should_not_preserve(monkeypatch):
    """任務鏈方向 + 目標已 in_progress → stale → return False（GC）。"""
    hook = _patch_is_handoff_stale(
        monkeypatch, (True, "任務鏈目標 0.18.0-W17-002 已 in_progress")
    )
    record = {
        "ticket_id": "0.18.0-W17-001",
        "direction": "to-sibling:0.18.0-W17-002",
    }
    assert hook.should_preserve_pending_json(record, MagicMock()) is False


def test_task_chain_target_completed_should_not_preserve(monkeypatch):
    """任務鏈方向 + 目標已 completed → stale → return False（GC）。"""
    hook = _patch_is_handoff_stale(
        monkeypatch, (True, "任務鏈目標 0.18.0-W17-002 已 completed")
    )
    record = {
        "ticket_id": "0.18.0-W17-001",
        "direction": "to-sibling:0.18.0-W17-002",
    }
    assert hook.should_preserve_pending_json(record, MagicMock()) is False


def test_task_chain_target_pending_should_preserve(monkeypatch):
    """任務鏈方向 + 目標仍 pending → 非 stale → return True（保留）。"""
    hook = _patch_is_handoff_stale(monkeypatch, (False, ""))
    record = {
        "ticket_id": "0.18.0-W17-001",
        "direction": "to-sibling:0.18.0-W17-002",
    }
    assert hook.should_preserve_pending_json(record, MagicMock()) is True


def test_non_chain_with_completed_source_should_not_preserve(monkeypatch):
    """非任務鏈方向 + 來源 ticket 已 completed → stale → return False。"""
    hook = _patch_is_handoff_stale(
        monkeypatch, (True, "來源 ticket 0.18.0-W17-001 已 completed")
    )
    record = {
        "ticket_id": "0.18.0-W17-001",
        "direction": "context_refresh",
    }
    assert hook.should_preserve_pending_json(record, MagicMock()) is False


def test_non_chain_pending_should_preserve(monkeypatch):
    """非任務鏈方向 + 來源仍 pending → 非 stale → return True。"""
    hook = _patch_is_handoff_stale(monkeypatch, (False, ""))
    record = {
        "ticket_id": "0.18.0-W17-001",
        "direction": "context_refresh",
    }
    assert hook.should_preserve_pending_json(record, MagicMock()) is True


# ===== is_handoff_recently_created 邊界值（W17-118 Phase 2）=====


def test_recently_created_within_window():
    """timestamp 在 RECENT_HANDOFF_WINDOW_SECONDS 之內 → True。"""
    hook = load_hook_module()
    record = {"timestamp": (datetime.now() - timedelta(seconds=10)).isoformat()}
    assert hook.is_handoff_recently_created(record, MagicMock()) is True


def test_recently_created_boundary_299s():
    """邊界值 299 秒（窗口內）→ True。"""
    hook = load_hook_module()
    record = {"timestamp": (datetime.now() - timedelta(seconds=299)).isoformat()}
    assert hook.is_handoff_recently_created(record, MagicMock()) is True


def test_recently_created_boundary_301s():
    """邊界值 301 秒（窗口外）→ False。"""
    hook = load_hook_module()
    record = {"timestamp": (datetime.now() - timedelta(seconds=301)).isoformat()}
    assert hook.is_handoff_recently_created(record, MagicMock()) is False


def test_recently_created_missing_timestamp():
    """timestamp 缺失 → 保守 False（走原路徑）。"""
    hook = load_hook_module()
    assert hook.is_handoff_recently_created({}, MagicMock()) is False


def test_recently_created_invalid_format():
    """timestamp 格式錯誤 → 保守 False（走原路徑）。"""
    hook = load_hook_module()
    record = {"timestamp": "not-a-timestamp"}
    assert hook.is_handoff_recently_created(record, MagicMock()) is False


# ===== scan_pending_handoff_tasks 整合場景（W17-118 Phase 1+2）=====


def _write_handoff(pending_dir: Path, ticket_id: str, *,
                   direction: str = "context_refresh",
                   timestamp: datetime = None,
                   resumed_at=None,
                   title: str = "test"):
    """輔助：寫一筆 handoff json 到 pending dir。"""
    pending_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "ticket_id": ticket_id,
        "direction": direction,
        "timestamp": (timestamp or datetime.now()).isoformat(),
        "title": title,
        "resumed_at": resumed_at,
    }
    file_path = pending_dir / f"{ticket_id}.json"
    file_path.write_text(json.dumps(record), encoding="utf-8")
    return file_path


def _setup_scan(monkeypatch, tmp_path, *, stale_map=None,
                completed_map=None, recent_started=False):
    """
    建立 hook module 並 patch ticket fs 依賴：
    - is_handoff_stale: 依 stale_map[ticket_id] → (bool, str)
    - is_ticket_completed: 依 completed_map[ticket_id] → bool
    - is_ticket_recently_started: 統一回傳 recent_started
    """
    stale_map = stale_map or {}
    completed_map = completed_map or {}
    hook = load_hook_module()

    def fake_is_handoff_stale(record, project_root=None):
        tid = (record or {}).get("ticket_id", "")
        return stale_map.get(tid, (False, ""))

    monkeypatch.setattr(hook, "is_handoff_stale", fake_is_handoff_stale)
    monkeypatch.setattr(
        hook, "is_ticket_completed",
        lambda root, tid, log: completed_map.get(tid, False),
    )
    monkeypatch.setattr(
        hook, "is_ticket_recently_started",
        lambda root, tid, log, cache=None: recent_started,
    )
    # 將 PENDING_DIR_NAME 指向 tmp_path
    monkeypatch.setattr(hook, "PENDING_DIR_NAME", "pending")
    return hook


def test_scan_recently_created_with_stale_goes_to_recent(monkeypatch, tmp_path):
    """剛建 handoff（< 300s）+ stale → recent_tasks（不阻塞、不 GC）。"""
    pending_dir = tmp_path / "pending"
    _write_handoff(
        pending_dir, "W17-117",
        direction="to-sibling:W17-118",
        timestamp=datetime.now() - timedelta(seconds=30),
    )
    _write_handoff(
        pending_dir, "W17-115",
        direction="context_refresh",
        timestamp=datetime.now() - timedelta(seconds=3600),
    )
    hook = _setup_scan(
        monkeypatch, tmp_path,
        stale_map={
            "W17-117": (True, "任務鏈目標已啟動"),  # stale 但剛建 → recent
            "W17-115": (True, "來源 completed"),     # stale 且非剛建 → GC
        },
    )
    pending, recent = hook.scan_pending_handoff_tasks(tmp_path, MagicMock())
    assert [t["ticket_id"] for t in recent] == ["W17-117"]
    assert pending == []
    # W17-115 應被 GC 刪除
    assert not (pending_dir / "W17-115.json").exists()
    # W17-117 仍保留（剛建，不 GC）
    assert (pending_dir / "W17-117.json").exists()


def test_scan_pure_stale_gets_gced(monkeypatch, tmp_path):
    """純 stale（任務鏈目標已啟動，非剛建）→ GC 刪除，不計入 pending。"""
    pending_dir = tmp_path / "pending"
    _write_handoff(
        pending_dir, "W17-001",
        direction="to-sibling:W17-002",
        timestamp=datetime.now() - timedelta(hours=2),
    )
    hook = _setup_scan(
        monkeypatch, tmp_path,
        stale_map={"W17-001": (True, "任務鏈目標已 in_progress")},
    )
    pending, recent = hook.scan_pending_handoff_tasks(tmp_path, MagicMock())
    assert pending == []
    assert recent == []
    assert not (pending_dir / "W17-001.json").exists()


def test_scan_pure_active_goes_to_pending(monkeypatch, tmp_path):
    """純 active（非 stale 非剛建 非 recent_started）→ pending_tasks。"""
    pending_dir = tmp_path / "pending"
    _write_handoff(
        pending_dir, "W17-200",
        direction="context_refresh",
        timestamp=datetime.now() - timedelta(hours=1),
    )
    hook = _setup_scan(monkeypatch, tmp_path, recent_started=False)
    pending, recent = hook.scan_pending_handoff_tasks(tmp_path, MagicMock())
    assert [t["ticket_id"] for t in pending] == ["W17-200"]
    assert recent == []


def test_scan_stale_plus_active_mixed(monkeypatch, tmp_path):
    """stale + active 混合 → stale 被 GC，active 進 pending。"""
    pending_dir = tmp_path / "pending"
    _write_handoff(
        pending_dir, "W17-stale",
        direction="to-sibling:W17-target",
        timestamp=datetime.now() - timedelta(hours=2),
    )
    _write_handoff(
        pending_dir, "W17-active",
        direction="context_refresh",
        timestamp=datetime.now() - timedelta(hours=1),
    )
    hook = _setup_scan(
        monkeypatch, tmp_path,
        stale_map={"W17-stale": (True, "任務鏈目標已啟動")},
    )
    pending, recent = hook.scan_pending_handoff_tasks(tmp_path, MagicMock())
    assert [t["ticket_id"] for t in pending] == ["W17-active"]
    assert recent == []
    assert not (pending_dir / "W17-stale.json").exists()
    assert (pending_dir / "W17-active.json").exists()


def test_scan_multiple_active_all_blocking(monkeypatch, tmp_path):
    """多 active（皆非 stale 非剛建）→ 全進 pending（多任務 blocking 行為保留）。"""
    pending_dir = tmp_path / "pending"
    for tid in ("W17-A", "W17-B"):
        _write_handoff(
            pending_dir, tid,
            direction="context_refresh",
            timestamp=datetime.now() - timedelta(hours=1),
        )
    hook = _setup_scan(monkeypatch, tmp_path)
    pending, recent = hook.scan_pending_handoff_tasks(tmp_path, MagicMock())
    assert sorted(t["ticket_id"] for t in pending) == ["W17-A", "W17-B"]
    assert recent == []


def test_scan_recently_created_pure_no_block(monkeypatch, tmp_path):
    """純剛建 handoff（非 stale）→ recent_tasks，不阻塞。"""
    pending_dir = tmp_path / "pending"
    _write_handoff(
        pending_dir, "W17-117",
        direction="context_refresh",
        timestamp=datetime.now() - timedelta(seconds=10),
    )
    hook = _setup_scan(monkeypatch, tmp_path)
    pending, recent = hook.scan_pending_handoff_tasks(tmp_path, MagicMock())
    assert pending == []
    assert [t["ticket_id"] for t in recent] == ["W17-117"]
    # 不應被 GC
    assert (pending_dir / "W17-117.json").exists()


# ===== W17-165 L2-C：terminal status 過濾（closed 也視為 terminal）=====


def test_terminal_statuses_includes_closed():
    """W17-165 L2-C：TERMINAL_STATUSES 集合包含 completed 與 closed。

    W17-197 修法：hook 不直接 re-export TERMINAL_STATUSES（W17-181.2 起 SSOT 移至
    ticket_system.constants），改為驗證 lib 端 constants 的 TERMINAL_STATUSES。
    """
    # 透過 hook 的 sys.path 設定取得 lib 端 TERMINAL_STATUSES
    load_hook_module()  # 確保 sys.path 已設定（hook 模組加 skills/ticket 父路徑）
    from ticket_system.constants import TERMINAL_STATUSES
    assert set(TERMINAL_STATUSES) == {"completed", "closed"}


def test_is_ticket_completed_returns_true_for_closed(monkeypatch, tmp_path):
    """W17-165 L2-C：closed 狀態應走 terminal 路徑（is_ticket_completed=True）。

    W17-197 修法：hook.is_ticket_completed delegate 至 lib `is_ticket_terminal`
    （W17-181.2 SSOT），原測試 monkeypatch hook 層級 find_ticket_file /
    parse_ticket_frontmatter 已不適用。改為 monkeypatch hook 內 `_lib_is_ticket_terminal`。
    """
    hook = load_hook_module()
    monkeypatch.setattr(
        hook, "_lib_is_ticket_terminal",
        lambda tid, project_root=None: True,
    )
    assert hook.is_ticket_completed(tmp_path, "W17-X", MagicMock()) is True


def test_is_ticket_completed_returns_true_for_completed(monkeypatch, tmp_path):
    """向後相容：completed 仍視為 terminal。

    W17-197 修法：同 closed 測試，改 monkeypatch lib delegate。
    """
    hook = load_hook_module()
    monkeypatch.setattr(
        hook, "_lib_is_ticket_terminal",
        lambda tid, project_root=None: True,
    )
    assert hook.is_ticket_completed(tmp_path, "W17-X", MagicMock()) is True


def test_is_ticket_completed_returns_false_for_in_progress(monkeypatch, tmp_path):
    """非 terminal 狀態（in_progress/pending）回 False。"""
    hook = load_hook_module()
    fake_path = tmp_path / "fake.md"
    fake_path.write_text("---\nstatus: in_progress\n---\n")
    monkeypatch.setattr(
        hook, "find_ticket_file",
        lambda tid, root, log: fake_path,
    )
    monkeypatch.setattr(
        hook, "parse_ticket_frontmatter",
        lambda path, log: {"status": "in_progress"},
    )
    assert hook.is_ticket_completed(tmp_path, "W17-X", MagicMock()) is False


# ===== PC-097 / single-source-io-collection-rules：mock call count assertion =====
#
# 驗證單次請求（單次 is_ticket_recently_started 連續呼叫 / 單次 scan）內，
# parse_ticket_frontmatter 對同一 ticket_id 的呼叫次數 ≤ 1（符合單一採集點規範）。


def test_is_ticket_recently_started_cache_hit_avoids_reparse(monkeypatch, tmp_path):
    """PC-097：傳入 frontmatter_cache 時，同一 ticket 的第二次呼叫不重複解析。

    驗證 call count assertion：第二次呼叫的 parse_ticket_frontmatter call count 不增加。
    """
    hook = load_hook_module()
    fake_path = tmp_path / "fake.md"
    fake_path.write_text("---\nstarted_at: 2026-05-18T00:00:00\n---\n")

    parse_calls = {"count": 0}

    def counting_parse(path, log):
        parse_calls["count"] += 1
        return {"started_at": datetime.now().isoformat()}

    monkeypatch.setattr(hook, "find_ticket_file", lambda tid, root, log: fake_path)
    monkeypatch.setattr(hook, "parse_ticket_frontmatter", counting_parse)

    cache: dict = {}
    # 第一次呼叫：應解析一次 frontmatter
    hook.is_ticket_recently_started(tmp_path, "W17-PC097-A", MagicMock(), cache)
    assert parse_calls["count"] == 1, "第一次呼叫應解析 frontmatter 一次"

    # 第二次呼叫（同 ticket_id）：應走快取，不再解析
    hook.is_ticket_recently_started(tmp_path, "W17-PC097-A", MagicMock(), cache)
    assert parse_calls["count"] == 1, (
        "PC-097 違規：同一 ticket 第二次呼叫不應重複解析 frontmatter"
    )


def test_is_ticket_recently_started_no_cache_reparses(monkeypatch, tmp_path):
    """向後相容：未傳 cache（None）時維持每次解析行為（單一查詢場景合法）。

    此測試確保 cache=None 不破壞既有單次呼叫語意（hook 內仍有其他位置以 None 呼叫）。
    """
    hook = load_hook_module()
    fake_path = tmp_path / "fake.md"
    fake_path.write_text("---\nstarted_at: 2026-05-18T00:00:00\n---\n")

    parse_calls = {"count": 0}

    def counting_parse(path, log):
        parse_calls["count"] += 1
        return {"started_at": datetime.now().isoformat()}

    monkeypatch.setattr(hook, "find_ticket_file", lambda tid, root, log: fake_path)
    monkeypatch.setattr(hook, "parse_ticket_frontmatter", counting_parse)

    # 不傳 cache：每次都解析（單一查詢場景允許）
    hook.is_ticket_recently_started(tmp_path, "W17-PC097-B", MagicMock())
    hook.is_ticket_recently_started(tmp_path, "W17-PC097-B", MagicMock())
    assert parse_calls["count"] == 2, "未傳 cache 時維持每次解析"


def test_scan_pending_uses_frontmatter_cache_for_recent_started(monkeypatch, tmp_path):
    """PC-097：scan_pending_handoff_tasks 在多筆 handoff 指向同一 ticket 時，
    傳遞同一 frontmatter_cache 給 is_ticket_recently_started，避免重複解析。

    場景：兩個 handoff 檔指向同一 ticket_id（context_refresh direction，超過剛建窗口），
    scan 內應對 is_ticket_recently_started 各呼叫一次，但底層 parse_ticket_frontmatter
    僅應被呼叫一次（單一採集點）。
    """
    pending_dir = tmp_path / "pending"
    # 兩筆 handoff 指向不同 ticket，但測試走 recent_started 分支驗證 cache 機制
    _write_handoff(
        pending_dir, "W17-shared-A",
        direction="context_refresh",
        timestamp=datetime.now() - timedelta(hours=1),
    )
    _write_handoff(
        pending_dir, "W17-shared-B",
        direction="context_refresh",
        timestamp=datetime.now() - timedelta(hours=1),
    )

    hook = load_hook_module()
    monkeypatch.setattr(hook, "is_handoff_stale",
                        lambda record, project_root=None: (False, ""))
    monkeypatch.setattr(hook, "is_ticket_completed",
                        lambda root, tid, log: False)
    monkeypatch.setattr(hook, "PENDING_DIR_NAME", "pending")

    # 計數 parse_ticket_frontmatter 被呼叫次數；同一 ticket 重複呼叫應走快取
    fake_path = tmp_path / "fake.md"
    fake_path.write_text("---\n---\n")
    parse_calls: dict = {"by_ticket": {}}

    def counting_parse(path, log):
        # 由 _load_frontmatter_cached 呼叫；以路徑模擬資料
        return {"started_at": datetime.now().isoformat()}

    def counting_find(tid, root, log):
        parse_calls["by_ticket"][tid] = parse_calls["by_ticket"].get(tid, 0) + 1
        return fake_path

    monkeypatch.setattr(hook, "find_ticket_file", counting_find)
    monkeypatch.setattr(hook, "parse_ticket_frontmatter", counting_parse)

    pending, recent = hook.scan_pending_handoff_tasks(tmp_path, MagicMock())
    # 兩個不同 ticket 各被 find_ticket_file 呼叫一次（recent_started 走 cache 首採集）
    assert parse_calls["by_ticket"].get("W17-shared-A", 0) <= 1, (
        "PC-097 違規：W17-shared-A 不應被 find_ticket_file 呼叫超過 1 次"
    )
    assert parse_calls["by_ticket"].get("W17-shared-B", 0) <= 1, (
        "PC-097 違規：W17-shared-B 不應被 find_ticket_file 呼叫超過 1 次"
    )
    # 兩個 ticket 都走 is_ticket_recently_started → recent_tasks（started_at = 現在）
    assert sorted(t["ticket_id"] for t in recent) == ["W17-shared-A", "W17-shared-B"]


# ===== W3-026.1: has_background_agents 弱依賴策略驗證 =====


def test_has_background_agents_with_non_empty_list_returns_true():
    """background_tasks 非空 list → 視為有背景代理人。"""
    hook = load_hook_module()
    input_data = {"background_tasks": [{"id": "agent-1"}]}
    assert hook.has_background_agents(input_data, MagicMock()) is True


def test_has_background_agents_with_empty_list_returns_false():
    """background_tasks 為空 list → 無背景代理人，caller 應 fallback。"""
    hook = load_hook_module()
    input_data = {"background_tasks": []}
    assert hook.has_background_agents(input_data, MagicMock()) is False


def test_has_background_agents_missing_field_returns_false():
    """欄位不存在（舊版 CC）→ 回 False 觸發 fallback。"""
    hook = load_hook_module()
    assert hook.has_background_agents({}, MagicMock()) is False


def test_has_background_agents_non_list_type_returns_false():
    """background_tasks 為非 list 型別（schema 異常）→ 安全回 False。"""
    hook = load_hook_module()
    assert hook.has_background_agents(
        {"background_tasks": "not-a-list"}, MagicMock()
    ) is False
    assert hook.has_background_agents(
        {"background_tasks": {"key": "value"}}, MagicMock()
    ) is False
    assert hook.has_background_agents(
        {"background_tasks": None}, MagicMock()
    ) is False


def test_has_background_agents_input_not_dict_returns_false():
    """input_data 非 dict（極端防禦）→ 回 False。"""
    hook = load_hook_module()
    assert hook.has_background_agents(None, MagicMock()) is False
    assert hook.has_background_agents([], MagicMock()) is False
    assert hook.has_background_agents("string", MagicMock()) is False


def test_has_background_agents_weak_dependency_ignores_task_internal_schema():
    """弱依賴策略：只判斷 list 非空，不依賴 task object 內部欄位。

    無論 task 內部結構為何（dict / str / 空 dict），只要 list 非空都回 True。
    """
    hook = load_hook_module()
    # task 為任意型別都可
    assert hook.has_background_agents(
        {"background_tasks": [{}]}, MagicMock()
    ) is True
    assert hook.has_background_agents(
        {"background_tasks": ["any-string"]}, MagicMock()
    ) is True
    assert hook.has_background_agents(
        {"background_tasks": [None, None]}, MagicMock()
    ) is True


# ===== W3-026.1: scan_pending_handoff_tasks 整合 background_tasks 驗證 =====


def test_scan_with_background_tasks_treats_as_recent(monkeypatch, tmp_path):
    """background_tasks 非空 + pending task → recent_tasks（取代 started_at 推斷）。"""
    pending_dir = tmp_path / "pending"
    _write_handoff(
        pending_dir, "W3-026-A",
        direction="context_refresh",
        timestamp=datetime.now() - timedelta(hours=1),
    )
    hook = _setup_scan(
        monkeypatch, tmp_path,
        # 即使 is_ticket_recently_started 回 False（超過 30 分鐘）
        recent_started=False,
    )
    pending, recent = hook.scan_pending_handoff_tasks(
        tmp_path, MagicMock(),
        input_data={"background_tasks": [{"id": "agent-1"}]},
    )
    # background_tasks 非空 → 視為 recent，不阻塞退出
    assert [t["ticket_id"] for t in recent] == ["W3-026-A"]
    assert pending == []


def test_scan_with_empty_background_tasks_falls_back_to_started_at(
    monkeypatch, tmp_path
):
    """background_tasks 為空 list + recent_started=True → fallback 視為 recent。"""
    pending_dir = tmp_path / "pending"
    _write_handoff(
        pending_dir, "W3-026-B",
        direction="context_refresh",
        timestamp=datetime.now() - timedelta(hours=1),
    )
    hook = _setup_scan(
        monkeypatch, tmp_path,
        recent_started=True,  # started_at 在 30 分鐘內
    )
    pending, recent = hook.scan_pending_handoff_tasks(
        tmp_path, MagicMock(),
        input_data={"background_tasks": []},
    )
    # background_tasks 空 → 走 is_ticket_recently_started fallback → recent
    assert [t["ticket_id"] for t in recent] == ["W3-026-B"]
    assert pending == []


def test_scan_missing_background_tasks_falls_back_to_started_at(
    monkeypatch, tmp_path
):
    """背景欄位不存在（舊版 CC）+ recent_started=False → fallback → pending（阻擋）。"""
    pending_dir = tmp_path / "pending"
    _write_handoff(
        pending_dir, "W3-026-C",
        direction="context_refresh",
        timestamp=datetime.now() - timedelta(hours=1),
    )
    hook = _setup_scan(
        monkeypatch, tmp_path,
        recent_started=False,  # 超過 30 分鐘
    )
    pending, recent = hook.scan_pending_handoff_tasks(
        tmp_path, MagicMock(),
        input_data={},  # 欄位不存在
    )
    # 兩種推斷都判否 → pending（阻擋退出）
    assert [t["ticket_id"] for t in pending] == ["W3-026-C"]
    assert recent == []


def test_scan_with_none_input_data_falls_back_safely(monkeypatch, tmp_path):
    """input_data=None（呼叫端未傳）→ 視同空 dict，fallback 到 started_at。"""
    pending_dir = tmp_path / "pending"
    _write_handoff(
        pending_dir, "W3-026-D",
        direction="context_refresh",
        timestamp=datetime.now() - timedelta(hours=1),
    )
    hook = _setup_scan(
        monkeypatch, tmp_path,
        recent_started=True,
    )
    pending, recent = hook.scan_pending_handoff_tasks(tmp_path, MagicMock())
    # 未傳 input_data → has_background_agents 回 False → fallback → recent
    assert [t["ticket_id"] for t in recent] == ["W3-026-D"]
    assert pending == []


def test_scan_non_blocking_direction_priority_over_background_tasks(
    monkeypatch, tmp_path
):
    """non_blocking direction（auto / next-wave）優先級高於 background_tasks。

    既有行為不破壞：建議性 handoff 不論 background_tasks 狀態都進 recent_tasks。
    """
    pending_dir = tmp_path / "pending"
    _write_handoff(
        pending_dir, "W3-026-E",
        direction="auto",
        timestamp=datetime.now() - timedelta(hours=1),
    )
    hook = _setup_scan(
        monkeypatch, tmp_path,
        recent_started=False,
    )
    # 即使 background_tasks 空也應該因 direction=auto 進 recent
    pending, recent = hook.scan_pending_handoff_tasks(
        tmp_path, MagicMock(),
        input_data={"background_tasks": []},
    )
    assert [t["ticket_id"] for t in recent] == ["W3-026-E"]
    assert pending == []


def test_scan_background_tasks_priority_over_started_at(monkeypatch, tmp_path):
    """background_tasks 非空時優先判定，不再呼叫 is_ticket_recently_started。

    驗證新邏輯取代 started_at 推斷的優先序：bg_tasks 非空 → 直接判為 recent。
    """
    pending_dir = tmp_path / "pending"
    _write_handoff(
        pending_dir, "W3-026-F",
        direction="context_refresh",
        timestamp=datetime.now() - timedelta(hours=1),
    )

    # 故意讓 is_ticket_recently_started 若被呼叫即 raise，驗證未被呼叫
    hook = load_hook_module()
    monkeypatch.setattr(
        hook, "is_handoff_stale", lambda record, project_root=None: (False, "")
    )
    monkeypatch.setattr(hook, "is_ticket_completed", lambda root, tid, log: False)
    monkeypatch.setattr(hook, "PENDING_DIR_NAME", "pending")

    call_counter = {"started_at": 0}

    def fake_recently_started(root, tid, log, cache=None):
        call_counter["started_at"] += 1
        return False

    monkeypatch.setattr(hook, "is_ticket_recently_started", fake_recently_started)

    pending, recent = hook.scan_pending_handoff_tasks(
        tmp_path, MagicMock(),
        input_data={"background_tasks": [{"id": "x"}]},
    )
    assert [t["ticket_id"] for t in recent] == ["W3-026-F"]
    # bg_tasks 非空命中後不再 fallback
    assert call_counter["started_at"] == 0, (
        "background_tasks 非空時不應再呼叫 is_ticket_recently_started fallback"
    )


# ===== W3-036: has_background_agents 迴圈外提（loop-invariant code motion）=====


def test_scan_calls_has_background_agents_once_per_scan(monkeypatch, tmp_path):
    """has_background_agents 屬 loop-invariant，每次 scan 只應呼叫一次。

    輸入 >= 2 筆 pending JSON（皆為非建議性方向、未完成），驗證外提後
    has_background_agents 不再隨迴圈每筆重複呼叫，call_count == 1。
    """
    pending_dir = tmp_path / "pending"
    for ticket_id in ("W3-036-A", "W3-036-B", "W3-036-C"):
        _write_handoff(
            pending_dir, ticket_id,
            direction="context_refresh",
            timestamp=datetime.now() - timedelta(hours=1),
        )
    hook = _setup_scan(monkeypatch, tmp_path, recent_started=False)

    mock_has_bg = MagicMock(return_value=False)
    monkeypatch.setattr(hook, "has_background_agents", mock_has_bg)

    hook.scan_pending_handoff_tasks(
        tmp_path, MagicMock(),
        input_data={"background_tasks": []},
    )

    assert mock_has_bg.call_count == 1, (
        f"has_background_agents 屬 loop-invariant，每次 scan 只應呼叫一次，"
        f"實際呼叫 {mock_has_bg.call_count} 次（3 筆 pending JSON）"
    )


# ===== main() stdin 整合測試（W3-037，承接 W3-026.1 commit 7f2ec9e6）=====
# 驗證 main() 的 stdin 讀取四路徑：
#   1. tty 互動模式 → input_data={}，fallback
#   2. JSONDecodeError → input_data={}，fallback + warning log
#   3. JSON 但非 dict → input_data={}，fallback + warning log
#   4. JSON 含 background_tasks → 完整傳遞給 generate_hook_output


import io


class _FakeStdin(io.StringIO):
    """StringIO 包裝，提供 isatty() 介面以模擬 sys.stdin。"""

    def __init__(self, content: str = "", tty: bool = False):
        super().__init__(content)
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


def _patch_main_dependencies(monkeypatch, hook, captured: dict):
    """mock generate_hook_output 攔截 input_data，避開真實 fs 依賴。"""

    def fake_generate_hook_output(logger, input_data=None):
        captured["input_data"] = input_data
        return {"suppressOutput": True}

    monkeypatch.setattr(hook, "generate_hook_output", fake_generate_hook_output)


def test_main_stdin_tty_fallback(monkeypatch, capsys):
    """路徑 1：tty 互動模式時不讀取 stdin，input_data 維持空 dict。"""
    hook = load_hook_module()
    captured: dict = {}
    _patch_main_dependencies(monkeypatch, hook, captured)
    monkeypatch.setattr(hook.sys, "stdin", _FakeStdin("", tty=True))

    exit_code = hook.main()

    assert exit_code == hook.EXIT_SUCCESS
    assert captured["input_data"] == {}, "tty 模式不應讀取 stdin，input_data 應為空 dict"


def test_main_stdin_json_decode_error_fallback(monkeypatch, capsys):
    """路徑 2：stdin 為非法 JSON 時 fallback 到空 dict。"""
    hook = load_hook_module()
    captured: dict = {}
    _patch_main_dependencies(monkeypatch, hook, captured)
    monkeypatch.setattr(
        hook.sys, "stdin", _FakeStdin("not a valid json {{{", tty=False)
    )

    exit_code = hook.main()

    assert exit_code == hook.EXIT_SUCCESS
    assert captured["input_data"] == {}, "JSONDecodeError 應 fallback 至空 dict"


def test_main_stdin_non_dict_fallback(monkeypatch, capsys):
    """路徑 3：stdin 為合法 JSON 但非 dict（list/null/str）時 fallback 到空 dict。"""
    hook = load_hook_module()
    captured: dict = {}
    _patch_main_dependencies(monkeypatch, hook, captured)
    monkeypatch.setattr(hook.sys, "stdin", _FakeStdin('["a", "b"]', tty=False))

    exit_code = hook.main()

    assert exit_code == hook.EXIT_SUCCESS
    assert captured["input_data"] == {}, "non-dict JSON 應 fallback 至空 dict"


def test_main_stdin_with_background_tasks(monkeypatch, capsys):
    """路徑 4：stdin 含 background_tasks 時完整傳遞給 generate_hook_output。"""
    hook = load_hook_module()
    captured: dict = {}
    _patch_main_dependencies(monkeypatch, hook, captured)

    payload = {
        "background_tasks": [{"id": "bg-1", "status": "running"}],
        "session_id": "s-test",
    }
    monkeypatch.setattr(
        hook.sys, "stdin", _FakeStdin(json.dumps(payload), tty=False)
    )

    exit_code = hook.main()

    assert exit_code == hook.EXIT_SUCCESS
    assert captured["input_data"] == payload, (
        "background_tasks 完整 payload 應傳遞給 generate_hook_output"
    )
    assert captured["input_data"]["background_tasks"] == [
        {"id": "bg-1", "status": "running"}
    ]


# ===== W1-044: subagent context 偵測 + suppressOutput =====


def test_is_subagent_context_detects_agent_id():
    """stdin 含非空 agent_id → 視為 subagent context。"""
    hook = load_hook_module()
    assert hook.is_subagent_context({"agent_id": "agt-123"}, MagicMock()) is True


def test_is_subagent_context_detects_agent_type():
    """stdin 含非空 agent_type → 視為 subagent context。"""
    hook = load_hook_module()
    assert hook.is_subagent_context({"agent_type": "thyme"}, MagicMock()) is True


def test_is_subagent_context_false_for_pm_stop():
    """PM Stop event stdin（無 agent_id/agent_type）→ 非 subagent context。"""
    hook = load_hook_module()
    pm_stdin = {
        "session_id": "s-1",
        "transcript_path": "/tmp/t.jsonl",
        "stop_hook_active": False,
        "background_tasks": [],
    }
    assert hook.is_subagent_context(pm_stdin, MagicMock()) is False


def test_is_subagent_context_false_for_empty_marker():
    """agent_id 為空字串 → 不視為 subagent（避免空值誤判）。"""
    hook = load_hook_module()
    assert hook.is_subagent_context({"agent_id": "", "agent_type": ""}, MagicMock()) is False


def test_is_subagent_context_false_for_non_dict():
    """非 dict 輸入 → False（防禦）。"""
    hook = load_hook_module()
    assert hook.is_subagent_context(None, MagicMock()) is False
    assert hook.is_subagent_context([], MagicMock()) is False


def test_generate_hook_output_suppresses_in_subagent_context(monkeypatch):
    """subagent context 下 generate_hook_output 直接回 suppressOutput，
    不觸發 pending 掃描（不注入 decision:block）。"""
    hook = load_hook_module()

    # 若誤入掃描路徑，scan_pending_handoff_tasks 被呼叫即視為失敗
    def _should_not_be_called(*args, **kwargs):
        raise AssertionError("subagent context 不應掃描 pending（不應注入恢復指令）")

    monkeypatch.setattr(hook, "scan_pending_handoff_tasks", _should_not_be_called)
    monkeypatch.setattr(hook, "read_session_state", lambda logger: None)

    output = hook.generate_hook_output(MagicMock(), input_data={"agent_id": "agt-1"})

    assert output == {"suppressOutput": True}, (
        "subagent stop 應 suppressOutput，消除最終訊息劫持"
    )


def test_generate_hook_output_pm_session_behavior_unchanged(monkeypatch):
    """PM session（無 subagent 標記）行為不變：仍走原掃描路徑。
    無任何 pending/recent 任務時回 suppressOutput（4c 分支）。"""
    hook = load_hook_module()

    monkeypatch.setattr(hook, "has_been_triggered_this_session", lambda logger: False)
    monkeypatch.setattr(hook, "read_session_state", lambda logger: None)
    scan_called = {"count": 0}

    def _scan(project_root, logger, input_data=None):
        scan_called["count"] += 1
        return ([], [])  # 無待恢復、無最近任務

    monkeypatch.setattr(hook, "scan_pending_handoff_tasks", _scan)

    pm_stdin = {"session_id": "s-1", "background_tasks": []}
    output = hook.generate_hook_output(MagicMock(), input_data=pm_stdin)

    assert scan_called["count"] == 1, "PM session 應正常走 pending 掃描路徑"
    assert output == {"suppressOutput": True}
