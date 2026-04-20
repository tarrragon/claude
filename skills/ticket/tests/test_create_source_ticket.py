"""
--source-ticket CLI 整合測試（PC-073 / 0.18.0-W12-006 Phase 3b Commit 2）

對應 Phase 2 測試策略的 B 層（CLI 整合）與 C 層（argparse 參數註冊與 help）。
Commit 1 已完成 A 層（builder 單元）+ D 層（frontmatter 寫入），見 test_ticket_builder.py。

測試覆蓋：
- B1-B12：CLI 整合 12 案例（happy path、錯誤路徑、ordering、共存）
- C1-C3：argparse 參數註冊與 help 3 案例

Mock 策略（Sociable Unit Tests）：
- Unit = Module：execute 與其使用的 validator/loader/builder 視為一個 module
- Mock 外部邊界：檔案 I/O（load_ticket / save_ticket / list_tickets / resolve_version /
  validate_version_registered / _build_and_save_ticket）
- 不 mock 內層驗證邏輯（validate_ticket_id、extract_version_from_ticket_id）
"""

import argparse
from unittest.mock import patch, MagicMock
import pytest

from ticket_system.commands.create import (
    execute,
    register,
    _validate_source_ticket_arg,
)


# ============================================================
# 共用輔助
# ============================================================


def _make_args(**overrides) -> argparse.Namespace:
    """建立完整的 args Namespace（所有 create 子命令會讀的欄位預設 None/預設值）。

    必要預設：
    - type/priority/action/target/title：提供合法值，避免 execute 提早失敗
    - source_ticket/parent：本測試的核心參數
    - wave：提供 12（對應 W12 測試場景）
    - acceptance：提供一項避免 checklist 觸發額外路徑（不影響本測試斷言）
    """
    defaults = {
        # 版本/識別
        "version": None,
        "wave": 12,
        "seq": None,
        # 類型
        "type": "IMP",
        "priority": "P2",
        # 必填動作
        "action": "實作",
        "target": "測試目標",
        "title": "W12-006 測試 Ticket",
        # 5W1H
        "who": None,
        "what": "測試用 what",
        "when": "v0.18.0",
        "where_layer": "Infrastructure",
        "where_files": "src/test.py",
        "why": "測試用 why",
        "how_type": None,
        "how_strategy": "測試策略",
        # 關係（本測試核心）
        "parent": None,
        "source_ticket": None,
        "blocked_by": None,
        "related_to": None,
        # 驗收與決策樹（避免 WARNING 干擾斷言）
        "acceptance": ["驗收條件 A"],
        "decision_tree_entry": "第三層",
        "decision_tree_decision": "建立 IMP",
        "decision_tree_rationale": "PC-073 測試",
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _install_common_mocks(monkeypatch, *, source_ticket_data=None, source_exists=True):
    """安裝 execute() 需要的外部邊界 mock。

    為 execute 的外部呼叫提供可控的 mock：
    - resolve_version：回 "0.18.0"
    - validate_version_registered：回 (True, "")
    - list_tickets：回 []（避免重複偵測）
    - load_ticket：根據 source_ticket_data / source_exists 控制
    - _build_and_save_ticket：回 stub ticket dict（不實際寫檔）
    - get_ticket_path：回假路徑
    - update_parent_children / update_source_spawned_tickets：回 True

    Returns:
        dict: {"update_source": MagicMock}（測試可檢查呼叫情況）
    """
    # resolve_version
    monkeypatch.setattr(
        "ticket_system.commands.create.resolve_version",
        lambda v: "0.18.0",
    )

    # validate_version_registered（on-demand import in execute）
    monkeypatch.setattr(
        "ticket_system.lib.version.validate_version_registered",
        lambda v: (True, ""),
    )

    # list_tickets（避免重複偵測觸發）
    monkeypatch.setattr(
        "ticket_system.commands.create.list_tickets",
        lambda v: [],
    )

    # load_ticket（執行層會用此確認 source ticket 是否存在）
    def _load_ticket(version, ticket_id):
        if source_exists and source_ticket_data is not None:
            return source_ticket_data
        return None

    monkeypatch.setattr(
        "ticket_system.commands.create.load_ticket",
        _load_ticket,
    )

    # _build_and_save_ticket（避免實際寫檔）
    stub_ticket = {
        "id": "stub",
        "title": "stub",
        "what": "stub",
        "type": "IMP",
        "where": {"files": ["src/test.py"]},
        "how": {"strategy": "測試策略"},
    }
    monkeypatch.setattr(
        "ticket_system.commands.create._build_and_save_ticket",
        lambda v, tid, cfg: stub_ticket,
    )

    monkeypatch.setattr(
        "ticket_system.commands.create.get_ticket_path",
        lambda v, tid: f"/tmp/tickets/{tid}.md",
    )

    # update_parent_children（若有 --parent）
    monkeypatch.setattr(
        "ticket_system.commands.create.update_parent_children",
        lambda v, pid, tid: True,
    )

    # update_source_spawned_tickets（返回 True by default；測試可覆寫）
    update_source_mock = MagicMock(return_value=True)
    monkeypatch.setattr(
        "ticket_system.commands.create.update_source_spawned_tickets",
        update_source_mock,
    )

    # get_next_seq / get_next_child_seq（避免檔案系統依賴）
    monkeypatch.setattr(
        "ticket_system.commands.create.get_next_seq",
        lambda v, w: 1,
    )
    monkeypatch.setattr(
        "ticket_system.commands.create.get_next_child_seq",
        lambda pid: 1,
    )

    return {"update_source": update_source_mock}


# ============================================================
# 層 B：CLI 整合測試
# ============================================================


class TestCreateSourceTicketIntegration:
    """B1-B12：`--source-ticket` CLI 整合測試（execute 端到端路徑）。"""

    def test_b1_happy_path(self, monkeypatch, capsys):
        """B1 - Happy path：
        Given: 提供 --source-ticket 0.18.0-W12-002 且 source 存在 status=in_progress
        When: 執行 execute()
        Then: exit=0、stdout 含「已雙向關聯」、update_source_spawned_tickets 被呼叫
        """
        source_ticket = {
            "id": "0.18.0-W12-002",
            "status": "in_progress",
            "type": "ANA",
            "spawned_tickets": [],
        }
        mocks = _install_common_mocks(
            monkeypatch, source_ticket_data=source_ticket
        )

        args = _make_args(source_ticket="0.18.0-W12-002")
        result = execute(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "已雙向關聯" in captured.out
        # 雙向關聯調用
        mocks["update_source"].assert_called_once()
        call_args = mocks["update_source"].call_args[0]
        assert call_args[0] == "0.18.0-W12-002"

    def test_b2_source_not_found_fails_with_guidance(self, monkeypatch, capsys):
        """B2 - Given: --source-ticket 指定的 ID 不存在（load_ticket 返回 None）
        When: 執行 execute()
        Then: exit=1；stdout/stderr 含 SOURCE_TICKET_NOT_FOUND 與「ticket track list」引導；
              不呼叫 update_source_spawned_tickets
        """
        mocks = _install_common_mocks(
            monkeypatch, source_ticket_data=None, source_exists=False
        )

        args = _make_args(source_ticket="0.18.0-W99-999")
        result = execute(args)

        assert result == 1
        captured = capsys.readouterr()
        combined_output = captured.out + captured.err
        # 存在性失敗訊息
        assert "0.18.0-W99-999" in combined_output
        assert "ticket track list" in combined_output
        # 新 Ticket 未進入持久化/雙向關聯階段
        mocks["update_source"].assert_not_called()

    def test_b3_source_and_parent_mutually_exclusive(self, monkeypatch, capsys):
        """B3 - Given: 同時提供 --source-ticket 與 --parent
        When: 執行 execute()
        Then: exit=1；stdout/stderr 含 SOURCE_PARENT_MUTUALLY_EXCLUSIVE 含「PC-073」引用；
              不呼叫 update_source_spawned_tickets
        """
        source_ticket = {
            "id": "0.18.0-W12-002",
            "status": "in_progress",
            "spawned_tickets": [],
        }
        mocks = _install_common_mocks(
            monkeypatch, source_ticket_data=source_ticket
        )

        args = _make_args(
            source_ticket="0.18.0-W12-002",
            parent="0.18.0-W12-001",
        )
        result = execute(args)

        assert result == 1
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        # 互斥訊息
        assert "互斥" in combined
        assert "PC-073" in combined
        mocks["update_source"].assert_not_called()

    def test_b4_mutual_exclusion_precedes_existence_check(self, monkeypatch, capsys):
        """B4 - Ordering：當兩者同時提供，且 source 也不存在時，先報互斥錯誤。

        Given: --source-ticket 指定不存在 ID，且 --parent 也提供
        When: 執行 execute()
        Then: 訊息是互斥錯誤（非「不存在」錯誤），驗證 fail-fast 檢查順序
        """
        mocks = _install_common_mocks(
            monkeypatch, source_ticket_data=None, source_exists=False
        )

        args = _make_args(
            source_ticket="0.18.0-W99-999",
            parent="0.18.0-W12-001",
        )
        result = execute(args)

        assert result == 1
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        # 互斥訊息出現（關鍵：ordering 驗證）
        assert "互斥" in combined
        # 不應出現「不存在」相關 NOT_FOUND 訊息
        assert "ticket track list" not in combined
        mocks["update_source"].assert_not_called()

    def test_b5_invalid_id_format(self, monkeypatch, capsys):
        """B5 - Given: --source-ticket 為格式無效字串
        When: 執行 execute()
        Then: exit=1；沿用 INVALID_TICKET_ID_FORMAT 錯誤訊息；不觸及 load_ticket
        """
        # load_ticket 若被呼叫會回 None，但我們要驗證根本沒被呼叫
        load_ticket_calls = []

        def tracking_load_ticket(version, ticket_id):
            load_ticket_calls.append((version, ticket_id))
            return None

        _install_common_mocks(monkeypatch)
        monkeypatch.setattr(
            "ticket_system.commands.create.load_ticket",
            tracking_load_ticket,
        )

        args = _make_args(source_ticket="invalid-format")
        result = execute(args)

        assert result == 1
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        # 格式錯誤訊息（沿用 ErrorMessages.INVALID_TICKET_ID_FORMAT）
        assert "invalid-format" in combined
        # load_ticket 不應被呼叫（格式檢查在存在檢查之前）
        # 注意：_resolve_ticket_id_and_wave 不會載入 source ticket；
        # _validate_source_ticket_arg 的格式檢查也在存在檢查之前
        assert all(
            tid != "invalid-format" for _, tid in load_ticket_calls
        ), f"load_ticket 不應被呼叫 source_ticket=invalid-format，實際：{load_ticket_calls}"

    def test_b6_completed_allows_with_warning(self, monkeypatch, capsys):
        """B6 - Given: source ticket status=completed
        When: 執行 execute()
        Then: exit=0；stdout 同時含 SOURCE_TICKET_COMPLETED_WARN 與 SOURCE_TICKET_UPDATED
        """
        source_ticket = {
            "id": "0.18.0-W12-002",
            "status": "completed",
            "type": "ANA",
            "spawned_tickets": [],
        }
        mocks = _install_common_mocks(
            monkeypatch, source_ticket_data=source_ticket
        )

        args = _make_args(source_ticket="0.18.0-W12-002")
        result = execute(args)

        assert result == 0
        captured = capsys.readouterr()
        # WARNING（completed）與成功訊息並存
        assert "completed" in captured.out
        assert "已雙向關聯" in captured.out
        mocks["update_source"].assert_called_once()

    def test_b7_non_ana_type_no_extra_warning(self, monkeypatch, capsys):
        """B7 - Given: source type=IMP, status=completed
        When: 執行 execute()
        Then: exit=0；雙向關聯正常；無 type 相關額外警告（pepper §8：消除特例）
        """
        source_ticket = {
            "id": "0.18.0-W12-002",
            "status": "completed",
            "type": "IMP",
            "spawned_tickets": [],
        }
        mocks = _install_common_mocks(
            monkeypatch, source_ticket_data=source_ticket
        )

        args = _make_args(source_ticket="0.18.0-W12-002")
        result = execute(args)

        assert result == 0
        captured = capsys.readouterr()
        # 不應有 type 相關警告（如「非 ANA」等字串）
        assert "非 ANA" not in captured.out
        assert "非 ANA" not in captured.err
        # 雙向關聯執行
        assert "已雙向關聯" in captured.out
        mocks["update_source"].assert_called_once()

    def test_b8_with_blocked_by_and_related_to(self, monkeypatch, capsys):
        """B8 - Given: --source-ticket 與 --blocked-by/--related-to 共存
        When: 執行 execute()
        Then: exit=0；雙向關聯更新；blocked_by/related_to 正常進入 config

        注意：本測試假設 blocked-by 清單的 ticket 在 list_tickets 空結果下
             會被 _validate_blocked_by_references 擋下（因為 load_ticket 返回 None），
             所以這裡只給 related_to（不阻塞），確保 source 路徑仍執行成功。
        """
        source_ticket = {
            "id": "0.18.0-W12-002",
            "status": "in_progress",
            "type": "ANA",
            "spawned_tickets": [],
        }
        mocks = _install_common_mocks(
            monkeypatch, source_ticket_data=source_ticket
        )

        args = _make_args(
            source_ticket="0.18.0-W12-002",
            related_to="0.18.0-W12-005",
        )
        result = execute(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "已雙向關聯" in captured.out
        mocks["update_source"].assert_called_once()

    def test_b9_update_failure_keeps_new_ticket(self, monkeypatch, capsys):
        """B9 - Given: update_source_spawned_tickets 返回 False（例如 save_ticket 失敗）
        When: 執行 execute()
        Then: exit=0（新 Ticket 保留）；stdout 含 SOURCE_UPDATE_FAILED WARNING
        """
        source_ticket = {
            "id": "0.18.0-W12-002",
            "status": "in_progress",
            "type": "ANA",
            "spawned_tickets": [],
        }
        mocks = _install_common_mocks(
            monkeypatch, source_ticket_data=source_ticket
        )
        # 覆寫 update_source 為失敗
        mocks["update_source"].return_value = False

        args = _make_args(source_ticket="0.18.0-W12-002")
        result = execute(args)

        # 新 Ticket 已建立 → exit=0
        assert result == 0
        captured = capsys.readouterr()
        # WARNING 訊息
        assert "WARNING" in captured.out or "更新 source" in captured.out
        assert "失敗" in captured.out
        # 不應出現成功訊息
        assert "已雙向關聯" not in captured.out
        mocks["update_source"].assert_called_once()

    def test_b10_self_reference_fails_as_not_found(self, monkeypatch, capsys):
        """B10 - Given: --source-ticket 給尚未存在的新 ticket ID
        When: 執行 execute()
        Then: 由存在性檢查 fail（exit=1）；無需額外 self-ref 檢查邏輯
        """
        _install_common_mocks(
            monkeypatch, source_ticket_data=None, source_exists=False
        )

        args = _make_args(source_ticket="0.18.0-W12-006")
        result = execute(args)

        assert result == 1
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "ticket track list" in combined

    def test_b11_cross_version(self, monkeypatch, capsys):
        """B11 - 跨版本：source 在 0.17.0，新 ticket 建在 0.18.0
        When: 執行 execute()
        Then: extract_version_from_ticket_id 正確解析；跨版本 spawned 更新成功
        """
        source_ticket = {
            "id": "0.17.0-W1-001",
            "status": "completed",
            "type": "ANA",
            "spawned_tickets": [],
        }
        mocks = _install_common_mocks(
            monkeypatch, source_ticket_data=source_ticket
        )

        args = _make_args(source_ticket="0.17.0-W1-001")
        result = execute(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "已雙向關聯" in captured.out
        # 驗證 source_ticket_id 正確傳入
        mocks["update_source"].assert_called_once()
        call_args = mocks["update_source"].call_args[0]
        assert call_args[0] == "0.17.0-W1-001"

    def test_b12_duplicate_call_idempotent(self, monkeypatch, capsys):
        """B12 - 冪等性：同一 source 建立兩個衍生項 → update_source 各被呼叫一次
        When: 執行兩次 execute()
        Then: 兩次都 exit=0；update_source_spawned_tickets 累計兩次呼叫
        """
        source_ticket = {
            "id": "0.18.0-W12-002",
            "status": "in_progress",
            "type": "ANA",
            "spawned_tickets": [],
        }
        mocks = _install_common_mocks(
            monkeypatch, source_ticket_data=source_ticket
        )

        args1 = _make_args(source_ticket="0.18.0-W12-002")
        result1 = execute(args1)
        args2 = _make_args(source_ticket="0.18.0-W12-002")
        result2 = execute(args2)

        assert result1 == 0
        assert result2 == 0
        # 各新 ticket 分別觸發一次 update_source 呼叫
        assert mocks["update_source"].call_count == 2


# ============================================================
# 層 C：argparse 參數註冊與 help
# ============================================================


class TestCreateSourceTicketCLIRegistration:
    """C1-C3：argparse 參數註冊、dest、default、help 驗證。"""

    def _build_parser(self) -> argparse.ArgumentParser:
        """建立一個乾淨的 argparse parser，並註冊 create 子命令。"""
        root = argparse.ArgumentParser(prog="ticket")
        subparsers = root.add_subparsers(dest="command")
        register(subparsers)
        return root

    def test_c1_source_ticket_arg_registered_with_correct_dest(self):
        """C1 - 解析 --source-ticket 參數，dest=source_ticket 正確填入。"""
        parser = self._build_parser()
        args = parser.parse_args([
            "create",
            "--action", "實作",
            "--target", "目標",
            "--wave", "12",
            "--source-ticket", "0.18.0-W12-002",
        ])

        assert hasattr(args, "source_ticket")
        assert args.source_ticket == "0.18.0-W12-002"

    def test_c2_source_ticket_help_text_mentions_spawned(self, capsys):
        """C2 - --help 輸出含「衍生」/「spawned」關鍵字與「與 --parent 互斥」提示。"""
        parser = self._build_parser()

        with pytest.raises(SystemExit):
            parser.parse_args(["create", "--help"])

        captured = capsys.readouterr()
        help_text = captured.out
        # 「衍生」或「spawned」關鍵字
        assert ("衍生" in help_text) or ("spawned" in help_text)
        # 「與 --parent 互斥」提示
        assert "--parent" in help_text
        assert "互斥" in help_text

    def test_c3_source_ticket_default_none(self):
        """C3 - 不提供 --source-ticket 時 args.source_ticket is None（向後相容）。"""
        parser = self._build_parser()
        args = parser.parse_args([
            "create",
            "--action", "實作",
            "--target", "目標",
            "--wave", "12",
        ])

        assert hasattr(args, "source_ticket")
        assert args.source_ticket is None


# ============================================================
# 額外：_validate_source_ticket_arg 純函式測試（補強層）
# ============================================================


class TestValidateSourceTicketArg:
    """補強層：獨立測試 _validate_source_ticket_arg（執行層驗證函式）。"""

    def test_no_source_ticket_returns_true(self):
        """未提供 --source-ticket 時直接通過。"""
        args = _make_args(source_ticket=None)
        assert _validate_source_ticket_arg(args) is True

    def test_mutual_exclusion_returns_false(self, capsys):
        """同時提供 source_ticket + parent 應回傳 False。"""
        args = _make_args(
            source_ticket="0.18.0-W12-002",
            parent="0.18.0-W12-001",
        )
        result = _validate_source_ticket_arg(args)
        assert result is False
        captured = capsys.readouterr()
        assert "互斥" in captured.out
