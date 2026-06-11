"""ticket create / bulk auto-seq 衝突防護（1.0.0-W1-042 + 1.0.0-W1-051）。

來源 Ticket
-----------
- 1.0.0-W1-042（IMP）：W1-039 執行期間 create 未帶 --seq 將新票誤配為已存在的
  1.0.0-W1-001（與既有 SKILL 上架票 ID 衝突），產生記錄平面幻影但世界平面無檔案落盤。
- 1.0.0-W1-051（IMP，重構）：W1-042 把 collision guard 寫在 create.py caller 層
  while-loop，違反「特例應在資料來源處消失」；bulk_create 沿用 get_next_seq 脆弱起點
  且無 guard，稀疏佔用 / 降級會連鎖覆寫多票。W1-051 將可用性保證內聚至
  get_next_seq 降級分支（共用 resolve_available_seq helper），create 與 bulk 共享。

三層缺陷鏈（W1-042）
--------------------
- 掃描層 get_next_seq：兩來源（本地 glob + main ref）同時掃空時回傳 1，
  降級靜默無警告（環境依賴：worktree stale base / git 逾時 / root 解析偏差）。
- 配號層 _resolve_ticket_id_and_wave：算出 ticket_id 後僅驗格式，無存在性檢查。
- 落盤層 save_ticket：無條件寫入，ID 撞號時靜默覆寫。

修復設計（指導本測試斷言）
--------------------------
1. collision guard 內聚（W1-051 核心）：可用性保證收斂至 get_next_seq 降級分支，
   透過共用 helper resolve_available_seq 推進至真正可用 seq。create.py caller 層
   while-loop 移除（只剩 seq = get_next_seq(...)）。
2. get_next_seq 正常路徑保持純掃描（max+1），不做逐一 .exists() 探測（linux caveat）。
3. 降級可觀測：兩來源皆空且 main ref 掃描降級（回 None）時，輸出 stderr warning
   並在訊息中標明 guard 推進後的可用序號（quality-baseline 規則 4 雙通道）。
4. bulk_create 每個配號都經 resolve_available_seq，覆蓋稀疏佔用撞號。
5. 顯式 --seq 模式：算出 ID 已存在則以 ErrorEnvelope 報錯退出（不覆寫、不跳號）。
6. 不改 save_ticket 本身語意。

測試策略
--------
Sociable Unit Test：真實 tmp 目錄重現既有 ticket 檔，不 mock 被測函式本身、
Path glob、seq 解析邏輯。get_next_seq 降級警告以 mock list_ticket_files_from_main
回 None + 空目錄重現「兩來源同時掃空且 main 降級」的環境態。

案例數：13 個（W1-051 修正——W1-042 commit 訊息誤稱 9，實為 8；W1-051 隨 guard
位置遷移調整既有案例並新增 resolve_available_seq 契約 4 + bulk 稀疏佔用 2 +
.yaml 缺口 1 等案例，合計 13）。
"""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import patch

import pytest

from ticket_system.lib import ticket_builder
from ticket_system.lib.ticket_builder import get_next_seq, resolve_available_seq
from ticket_system.commands import create as create_cmd
from ticket_system.commands import bulk_create as bulk_cmd


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tickets_dir(root: Path, version: str = "1.0.0") -> Path:
    """回傳三層階層 tickets 目錄路徑（對齊 get_tickets_dir 規則）。"""
    parts = version.split(".")
    major = f"v{parts[0]}"
    minor = f"v{parts[0]}.{parts[1]}"
    return root / "docs" / "work-logs" / major / minor / f"v{version}" / "tickets"


def _write_ticket(tickets_dir: Path, ticket_id: str, suffix: str = ".md") -> Path:
    """寫入最小化 ticket 檔（掃描只看檔名，內容僅需可解析）。

    suffix 預設 .md；傳 ".yaml" 重現 yaml 落盤格式的撞號（W1-051 .yaml 缺口）。
    """
    tickets_dir.mkdir(parents=True, exist_ok=True)
    path = tickets_dir / f"{ticket_id}{suffix}"
    path.write_text(
        f"---\nid: {ticket_id}\ntitle: Existing {ticket_id}\n"
        f"type: IMP\nstatus: pending\n---\n\n# Body\n",
        encoding="utf-8",
    )
    return path


def _patch_project_root(monkeypatch, root: Path) -> None:
    """將 ticket_builder / paths 的 get_project_root 指向 root。"""
    monkeypatch.setattr(
        ticket_builder, "get_project_root", lambda: root, raising=False
    )
    import ticket_system.lib.paths as paths_mod

    monkeypatch.setattr(
        paths_mod, "get_project_root", lambda: root, raising=False
    )


def _make_args(seq=None, wave=1, version="1.0.0", parent=None) -> argparse.Namespace:
    """建構 _resolve_ticket_id_and_wave 所需的最小 args。"""
    return argparse.Namespace(seq=seq, wave=wave, version=version, parent=parent)


# ---------------------------------------------------------------------------
# AC1：resolve_available_seq 共用 helper 契約（內聚 collision guard）
# ---------------------------------------------------------------------------


class TestResolveAvailableSeq:
    """從 start_seq 起遞增至第一個檔案系統不存在的序號。"""

    def test_returns_start_when_available(self, tmp_path, monkeypatch):
        """空目錄：start_seq 即可用，原樣回傳。"""
        root = tmp_path / "repo"
        _tickets_dir(root).mkdir(parents=True, exist_ok=True)
        _patch_project_root(monkeypatch, root)

        assert resolve_available_seq("1.0.0", 1, 1) == 1

    def test_skips_single_existing(self, tmp_path, monkeypatch):
        """W1-001 存在：start=1 推進至 2。"""
        root = tmp_path / "repo"
        _write_ticket(_tickets_dir(root), "1.0.0-W1-001")
        _patch_project_root(monkeypatch, root)

        assert resolve_available_seq("1.0.0", 1, 1) == 2

    def test_skips_multiple_existing(self, tmp_path, monkeypatch):
        """W1-001/002/003 存在：start=1 推進至 4。"""
        root = tmp_path / "repo"
        td = _tickets_dir(root)
        for sid in ("1.0.0-W1-001", "1.0.0-W1-002", "1.0.0-W1-003"):
            _write_ticket(td, sid)
        _patch_project_root(monkeypatch, root)

        assert resolve_available_seq("1.0.0", 1, 1) == 4

    def test_skips_yaml_format_collision(self, tmp_path, monkeypatch):
        """W1-001.yaml（非 .md）存在：guard 仍應跳過（get_ticket_path 探測雙格式）。

        W1-051 .yaml 缺口補測：collision 判定用 get_ticket_path(...).exists()，
        該函式對 .md / .yaml 皆探測，故 yaml 落盤的 ticket 也不會被覆寫。
        """
        root = tmp_path / "repo"
        _write_ticket(_tickets_dir(root), "1.0.0-W1-001", suffix=".yaml")
        _patch_project_root(monkeypatch, root)

        assert resolve_available_seq("1.0.0", 1, 1) == 2


# ---------------------------------------------------------------------------
# AC2：create auto-seq 路徑信任 get_next_seq 內聚保證（caller while-loop 已移除）
# ---------------------------------------------------------------------------


class TestAutoSeqCallerTrustsGuard:
    """create caller 層不再兜底——get_next_seq 回傳值即視為可用。"""

    def test_auto_seq_uses_get_next_seq_value(self, tmp_path, monkeypatch):
        """
        Given: 真實掃描——W1-001/002 存在，get_next_seq 走純掃描回 3
        When: _resolve_ticket_id_and_wave(args(seq=None), "1.0.0")
        Then: 回傳 1.0.0-W1-003（不再有 caller while-loop，直接信任掃描結果）
        """
        root = tmp_path / "repo"
        td = _tickets_dir(root)
        _write_ticket(td, "1.0.0-W1-001")
        _write_ticket(td, "1.0.0-W1-002")
        _patch_project_root(monkeypatch, root)

        # main ref 降級回 None，使 get_next_seq 走「本地有效（local_stems 非空）」
        # 正常路徑——max+1=3，且不觸發降級 guard（local_stems 非空）。
        with patch.object(
            ticket_builder, "list_ticket_files_from_main", return_value=None
        ):
            result = create_cmd._resolve_ticket_id_and_wave(
                _make_args(seq=None, wave=1), "1.0.0"
            )

        assert result is not None
        _version, ticket_id, _wave = result
        assert ticket_id == "1.0.0-W1-003"

    def test_auto_seq_downgrade_guard_skips_existing(self, tmp_path, monkeypatch):
        """
        Given: W1-001/002/003 存在，但兩來源同時掃空且 main 降級（誤回 candidate=1）
               重現方式：mock glob 結果為空 + main ref 回 None
        When: _resolve_ticket_id_and_wave(args(seq=None), "1.0.0")
        Then: get_next_seq 降級分支內 resolve_available_seq 推進至 1.0.0-W1-004
        """
        root = tmp_path / "repo"
        td = _tickets_dir(root)
        for sid in ("1.0.0-W1-001", "1.0.0-W1-002", "1.0.0-W1-003"):
            _write_ticket(td, sid)
        _patch_project_root(monkeypatch, root)

        # 重現「兩來源同時掃空」：本地 glob 回空（即使檔案存在）+ main ref 降級。
        # 這是 W1-039 撞號的真實環境態（stale base worktree / glob 偏差）。
        import ticket_system.lib.paths as paths_mod

        original_glob = Path.glob

        def empty_glob(self, pattern):
            if "-W1-" in pattern:
                return iter([])
            return original_glob(self, pattern)

        with patch.object(
            ticket_builder, "list_ticket_files_from_main", return_value=None
        ), patch.object(Path, "glob", empty_glob):
            result = create_cmd._resolve_ticket_id_and_wave(
                _make_args(seq=None, wave=1), "1.0.0"
            )

        assert result is not None
        _version, ticket_id, _wave = result
        assert ticket_id == "1.0.0-W1-004", (
            f"降級分支 guard 應推進至可用 seq，實際 {ticket_id}"
        )


# ---------------------------------------------------------------------------
# AC3：顯式 --seq 撞號報錯（尊重用戶意圖，不覆寫、不自動跳號）
# ---------------------------------------------------------------------------


class TestExplicitSeqCollisionErrors:
    """顯式 --seq 指定已存在 ID 時報錯退出。"""

    def test_explicit_seq_collision_returns_none(self, tmp_path, monkeypatch, capsys):
        """
        Given: 1.0.0-W1-001.md 已存在，用戶顯式 --seq 1
        When: _resolve_ticket_id_and_wave(args(seq=1), "1.0.0")
        Then: 回傳 None（報錯退出），stdout 含 ErrorEnvelope 撞號訊息
        """
        root = tmp_path / "repo"
        existing = _write_ticket(_tickets_dir(root), "1.0.0-W1-001")
        assert existing.exists()
        _patch_project_root(monkeypatch, root)

        result = create_cmd._resolve_ticket_id_and_wave(
            _make_args(seq=1, wave=1), "1.0.0"
        )

        assert result is None, "顯式 --seq 撞號應報錯退出（回 None）"
        captured = capsys.readouterr()
        assert "1.0.0-W1-001" in captured.out
        assert (
            "存在" in captured.out
            or "EXISTS" in captured.out
            or "COLLISION" in captured.out.upper()
        ), f"應含撞號錯誤語意，實際輸出: {captured.out}"

    def test_explicit_seq_no_collision_passes(self, tmp_path, monkeypatch):
        """
        Given: tickets 目錄無 W1-042，用戶顯式 --seq 42
        When: _resolve_ticket_id_and_wave(args(seq=42), "1.0.0")
        Then: 回傳 1.0.0-W1-042（無碰撞時尊重顯式 seq）
        """
        root = tmp_path / "repo"
        _tickets_dir(root).mkdir(parents=True, exist_ok=True)
        _patch_project_root(monkeypatch, root)

        result = create_cmd._resolve_ticket_id_and_wave(
            _make_args(seq=42, wave=1), "1.0.0"
        )

        assert result is not None
        _version, ticket_id, _wave = result
        assert ticket_id == "1.0.0-W1-042"


# ---------------------------------------------------------------------------
# AC4：get_next_seq 降級可觀測（兩來源掃空且 main ref 降級 → stderr warning）
# ---------------------------------------------------------------------------


class TestGetNextSeqDowngradeWarning:
    """兩來源皆空且 main ref 掃描降級（None）時輸出 stderr warning。"""

    def test_warns_when_both_sources_empty_and_main_downgraded(
        self, tmp_path, monkeypatch, capsys
    ):
        """
        Given: 空 tickets 目錄（本地 glob 空）+ main ref 掃描降級（mock 回 None）
        When: get_next_seq("1.0.0", 1)
        Then: 回傳 1（無既有檔，guard 推進後仍為 1）且 stderr 含降級 warning
        """
        root = tmp_path / "repo"
        _tickets_dir(root).mkdir(parents=True, exist_ok=True)
        _patch_project_root(monkeypatch, root)

        with patch.object(
            ticket_builder, "list_ticket_files_from_main", return_value=None
        ):
            result = get_next_seq("1.0.0", 1)

        assert result == 1
        captured = capsys.readouterr()
        assert "WARNING" in captured.err, (
            f"降級時應輸出 stderr warning，實際 stderr: {captured.err!r}"
        )
        assert "get_next_seq" in captured.err

    def test_no_warning_when_local_has_tickets(self, tmp_path, monkeypatch, capsys):
        """
        Given: 本地有 W1-003（非空），main ref 降級（None）
        When: get_next_seq("1.0.0", 1)
        Then: 回傳 4，不輸出降級 warning（本地來源有效，非兩來源皆空）
        """
        root = tmp_path / "repo"
        _write_ticket(_tickets_dir(root), "1.0.0-W1-003")
        _patch_project_root(monkeypatch, root)

        with patch.object(
            ticket_builder, "list_ticket_files_from_main", return_value=None
        ):
            result = get_next_seq("1.0.0", 1)

        assert result == 4
        captured = capsys.readouterr()
        assert "get_next_seq" not in captured.err, (
            f"本地來源有效時不應輸出降級 warning，實際 stderr: {captured.err!r}"
        )

    def test_no_warning_when_main_ref_available(self, tmp_path, monkeypatch, capsys):
        """
        Given: 空本地目錄，main ref 掃描成功回空清單（非降級，是 main 確實無此 wave）
        When: get_next_seq("1.0.0", 1)
        Then: 回傳 1，不輸出降級 warning（main ref 有效解析，只是無檔）
        """
        root = tmp_path / "repo"
        _tickets_dir(root).mkdir(parents=True, exist_ok=True)
        _patch_project_root(monkeypatch, root)

        with patch.object(
            ticket_builder, "list_ticket_files_from_main", return_value=[]
        ):
            result = get_next_seq("1.0.0", 1)

        assert result == 1
        captured = capsys.readouterr()
        assert "get_next_seq" not in captured.err, (
            f"main ref 有效解析時不應誤報降級 warning，實際 stderr: {captured.err!r}"
        )


# ---------------------------------------------------------------------------
# AC5：bulk_create 批次配號可用性保證（稀疏佔用 / 連鎖覆寫防護）
# ---------------------------------------------------------------------------


class TestBulkCreateSparseOccupancy:
    """bulk 每個配號經 resolve_available_seq，稀疏佔用下不撞號覆寫。"""

    def _make_bulk_args(self, targets, wave=1, version="1.0.0", dry_run=False):
        return argparse.Namespace(
            template="default",
            targets=targets,
            version=version,
            wave=wave,
            parent=None,
            dry_run=dry_run,
        )

    def test_bulk_skips_sparse_existing_seq(self, tmp_path, monkeypatch):
        """
        Given: 起始可用 seq=1，但 W1-002 已被既有票佔用（稀疏佔用）
        When: batch-create 三個 targets
        Then: 配得 001 / 003 / 004（跳過已佔用的 002，不覆寫）
        """
        root = tmp_path / "repo"
        _write_ticket(_tickets_dir(root), "1.0.0-W1-002")  # 稀疏佔用點
        _patch_project_root(monkeypatch, root)

        # main ref 降級回 None，使 get_next_seq 走本地掃描（W1-002 → max+1=3?）
        # 但 W1-002 是唯一檔，max=2 → candidate=3，且 local_stems 非空不觸發降級。
        # 為測「起始 1 但 002 佔用」的稀疏情境，mock get_next_seq 回 1。
        with patch.object(
            bulk_cmd, "get_next_seq", return_value=1
        ):
            result = bulk_cmd._create_batch_tickets(
                {"type": "IMP", "priority": "P2"},
                ["target-a", "target-b", "target-c"],
                "1.0.0",
                1,
                dry_run=False,
            )

        assert result.failed == [], f"不應有失敗：{result.failed}"
        assert result.created == [
            "1.0.0-W1-001",
            "1.0.0-W1-003",
            "1.0.0-W1-004",
        ], f"應跳過稀疏佔用的 002，實際 {result.created}"

        # 既有 W1-002 未被覆寫（title 仍為 Existing）
        existing = _tickets_dir(root) / "1.0.0-W1-002.md"
        assert "Existing 1.0.0-W1-002" in existing.read_text(encoding="utf-8")

    def test_bulk_no_collision_sequential(self, tmp_path, monkeypatch):
        """
        Given: 空目錄，無稀疏佔用
        When: batch-create 三個 targets
        Then: 配得連續 001 / 002 / 003（無碰撞時行為不變）
        """
        root = tmp_path / "repo"
        _tickets_dir(root).mkdir(parents=True, exist_ok=True)
        _patch_project_root(monkeypatch, root)

        with patch.object(bulk_cmd, "get_next_seq", return_value=1):
            result = bulk_cmd._create_batch_tickets(
                {"type": "IMP", "priority": "P2"},
                ["t1", "t2", "t3"],
                "1.0.0",
                1,
                dry_run=False,
            )

        assert result.created == [
            "1.0.0-W1-001",
            "1.0.0-W1-002",
            "1.0.0-W1-003",
        ]
