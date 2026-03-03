"""
bulk_create 模組測試

測試批次建立 Ticket 相關的所有功能。
"""

from typing import Dict, Any
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile

import pytest
import yaml

from ticket_system.commands.bulk_create import (
    BulkCreateResult,
    execute,
    register,
    _load_template,
    _parse_targets,
    _create_ticket_config,
    _create_batch_tickets,
    _print_batch_summary,
    _print_batch_result,
)


class TestParseTargets:
    """目標解析測試"""

    def test_parse_targets_normal(self):
        """
        Given: 逗號分隔的目標字串
        When: 呼叫 _parse_targets
        Then: 應回傳目標清單
        """
        targets_str = "目標1,目標2,目標3"
        result = _parse_targets(targets_str)
        assert result == ["目標1", "目標2", "目標3"]

    def test_parse_targets_with_whitespace(self):
        """
        Given: 包含空白的逗號分隔目標字串
        When: 呼叫 _parse_targets
        Then: 應正確移除空白
        """
        targets_str = " 目標1 , 目標2 , 目標3 "
        result = _parse_targets(targets_str)
        assert result == ["目標1", "目標2", "目標3"]

    def test_parse_targets_empty_string(self):
        """
        Given: 空字串
        When: 呼叫 _parse_targets
        Then: 應回傳空清單
        """
        targets_str = ""
        result = _parse_targets(targets_str)
        assert result == []

    def test_parse_targets_only_whitespace(self):
        """
        Given: 只包含逗號和空白的字串
        When: 呼叫 _parse_targets
        Then: 應回傳空清單
        """
        targets_str = " , , "
        result = _parse_targets(targets_str)
        assert result == []

    def test_parse_targets_single_target(self):
        """
        Given: 只有一個目標
        When: 呼叫 _parse_targets
        Then: 應回傳單元素清單
        """
        targets_str = "單一目標"
        result = _parse_targets(targets_str)
        assert result == ["單一目標"]


class TestBulkCreateResult:
    """BulkCreateResult 資料類別測試"""

    def test_bulk_create_result_defaults(self):
        """
        Given: 建立 BulkCreateResult 實例（使用預設值）
        When: 檢查預設值
        Then: 應有正確的預設值
        """
        result = BulkCreateResult()

        assert result.created == []
        assert result.warned == []
        assert result.failed == []
        assert result.skipped == []
        assert result.total == 0
        assert result.dry_run is False

    def test_bulk_create_result_with_values(self):
        """
        Given: 建立 BulkCreateResult 並設定值
        When: 設定各欄位
        Then: 應保存所有值
        """
        created_list = ["0.31.0-W1-001", "0.31.0-W1-002"]
        failed_list = [("目標3", "錯誤訊息")]
        warned_list = [("0.31.0-W1-001", "警告訊息")]

        result = BulkCreateResult(
            created=created_list,
            warned=warned_list,
            failed=failed_list,
            total=3,
            dry_run=True,
        )

        assert result.created == created_list
        assert result.warned == warned_list
        assert result.failed == failed_list
        assert result.total == 3
        assert result.dry_run is True


class TestLoadTemplate:
    """模板載入測試"""

    def test_load_template_success(self, tmp_path):
        """
        Given: 存在有效的 YAML 模板檔案
        When: 呼叫 _load_template
        Then: 應成功載入並回傳預設值
        """
        template_dir = tmp_path / "templates"
        template_dir.mkdir(parents=True)

        template_content = {
            "defaults": {
                "type": "IMP",
                "priority": "P1",
                "who": "parsley-flutter-developer",
                "when": "本版本內",
                "where_layer": "Domain",
            }
        }

        template_file = template_dir / "test_template.yaml"
        with open(template_file, "w", encoding="utf-8") as f:
            yaml.dump(template_content, f)

        with patch("ticket_system.commands.bulk_create.Path") as mock_path_class:
            mock_path_class.return_value.parent.parent = tmp_path
            result = _load_template("test_template")

            assert result == template_content["defaults"]

    def test_load_template_not_found(self, tmp_path):
        """
        Given: 模板檔案不存在
        When: 呼叫 _load_template
        Then: 應拋出 FileNotFoundError
        """
        template_dir = tmp_path / "templates"
        template_dir.mkdir(parents=True)

        with patch("ticket_system.commands.bulk_create.Path") as mock_path_class:
            mock_path_class.return_value.parent.parent = tmp_path
            with pytest.raises(FileNotFoundError):
                _load_template("nonexistent_template")

    def test_load_template_empty_defaults(self, tmp_path):
        """
        Given: 模板檔案不包含 defaults 鍵
        When: 呼叫 _load_template
        Then: 應回傳空字典
        """
        template_dir = tmp_path / "templates"
        template_dir.mkdir(parents=True)

        template_content = {"other_key": "value"}

        template_file = template_dir / "empty_defaults.yaml"
        with open(template_file, "w", encoding="utf-8") as f:
            yaml.dump(template_content, f)

        with patch("ticket_system.commands.bulk_create.Path") as mock_path_class:
            mock_path_class.return_value.parent.parent = tmp_path
            result = _load_template("empty_defaults")

            assert result == {}


class TestCreateTicketConfig:
    """TicketConfig 建立測試"""

    def test_create_ticket_config_basic(self):
        """
        Given: 基本模板預設值和目標
        When: 呼叫 _create_ticket_config
        Then: 應建立正確的 TicketConfig
        """
        template_defaults = {
            "type": "IMP",
            "priority": "P1",
            "when": "本版本內",
            "where_layer": "Domain",
        }

        config = _create_ticket_config(
            template_defaults=template_defaults,
            target="實作使用者認證",
            ticket_id="0.31.0-W1-001",
            version="0.31.0",
            wave=1,
        )

        assert config["ticket_id"] == "0.31.0-W1-001"
        assert config["version"] == "0.31.0"
        assert config["wave"] == 1
        assert config["title"] == "實作使用者認證"
        assert config["ticket_type"] == "IMP"
        assert config["priority"] == "P1"
        assert config["when"] == "本版本內"
        assert config["where_layer"] == "Domain"
        assert "parent_id" not in config

    def test_create_ticket_config_with_parent(self):
        """
        Given: 指定了 parent_id
        When: 呼叫 _create_ticket_config
        Then: 應在 config 中包含 parent_id
        """
        template_defaults = {"type": "IMP"}

        config = _create_ticket_config(
            template_defaults=template_defaults,
            target="子任務",
            ticket_id="0.31.0-W1-001.1",
            version="0.31.0",
            wave=1,
            parent_id="0.31.0-W1-001",
        )

        assert config["parent_id"] == "0.31.0-W1-001"

    def test_create_ticket_config_uses_template_defaults(self):
        """
        Given: 模板包含各種預設值
        When: 呼叫 _create_ticket_config
        Then: 應使用模板中的預設值
        """
        template_defaults = {
            "type": "TST",
            "priority": "P0",
            "who": "sage-test-architect",
            "when": "Phase 2",
            "where_layer": "Presentation",
            "why": "需求 BR-001",
            "how_task_type": "Testing",
            "how_strategy": "邊界值測試",
        }

        config = _create_ticket_config(
            template_defaults=template_defaults,
            target="編寫測試案例",
            ticket_id="0.31.0-W1-001",
            version="0.31.0",
            wave=1,
        )

        assert config["ticket_type"] == "TST"
        assert config["priority"] == "P0"
        assert config["who"] == "sage-test-architect"
        assert config["when"] == "Phase 2"
        assert config["where_layer"] == "Presentation"
        assert config["why"] == "需求 BR-001"
        assert config["how_task_type"] == "Testing"
        assert config["how_strategy"] == "邊界值測試"


class TestCreateBatchTickets:
    """批次建立 Tickets 測試"""

    def test_create_batch_tickets_dry_run(self):
        """
        Given: 啟用 dry-run 模式
        When: 呼叫 _create_batch_tickets
        Then: 應不建立任何檔案，但返回成功的結果
        """
        template_defaults = {"type": "IMP", "priority": "P1"}
        targets = ["目標1", "目標2"]

        with patch("ticket_system.commands.bulk_create.get_next_seq") as mock_seq:
            mock_seq.return_value = 1

            with patch("ticket_system.commands.bulk_create.format_ticket_id") as mock_format:
                mock_format.side_effect = [
                    "0.31.0-W1-001",
                    "0.31.0-W1-002",
                ]

                with patch("ticket_system.commands.bulk_create.create_ticket_frontmatter"):
                    with patch("ticket_system.commands.bulk_create.create_ticket_body"):
                        with patch("ticket_system.commands.bulk_create.save_ticket") as mock_save:
                            result = _create_batch_tickets(
                                template_defaults,
                                targets,
                                "0.31.0",
                                1,
                                dry_run=True,
                            )

                            assert result.total == 2
                            assert len(result.created) == 2
                            assert result.dry_run is True
                            # dry-run 不應該呼叫 save_ticket
                            mock_save.assert_not_called()

    def test_create_batch_tickets_success(self):
        """
        Given: 有效的模板和目標清單
        When: 呼叫 _create_batch_tickets
        Then: 應成功建立所有 Tickets
        """
        template_defaults = {"type": "IMP"}
        targets = ["目標1", "目標2", "目標3"]

        with patch("ticket_system.commands.bulk_create.get_tickets_dir") as mock_dir:
            mock_dir.return_value = Path("/tmp/tickets")

            with patch("ticket_system.commands.bulk_create.get_next_seq") as mock_seq:
                mock_seq.return_value = 1

                with patch("ticket_system.commands.bulk_create.format_ticket_id") as mock_format:
                    mock_format.side_effect = [
                        "0.31.0-W1-001",
                        "0.31.0-W1-002",
                        "0.31.0-W1-003",
                    ]

                    with patch("ticket_system.commands.bulk_create.create_ticket_frontmatter"):
                        with patch("ticket_system.commands.bulk_create.create_ticket_body"):
                            with patch("ticket_system.commands.bulk_create.get_ticket_path"):
                                with patch("ticket_system.commands.bulk_create.save_ticket"):
                                    result = _create_batch_tickets(
                                        template_defaults,
                                        targets,
                                        "0.31.0",
                                        1,
                                    )

                                    assert result.total == 3
                                    assert len(result.created) == 3
                                    assert result.failed == []

    def test_create_batch_tickets_with_parent(self):
        """
        Given: 指定了 parent_id
        When: 呼叫 _create_batch_tickets
        Then: 應在所有 Ticket 中包含 parent_id
        """
        template_defaults = {"type": "IMP"}
        targets = ["子任務1", "子任務2"]
        parent_id = "0.31.0-W1-001"

        with patch("ticket_system.commands.bulk_create.get_tickets_dir") as mock_dir:
            mock_dir.return_value = Path("/tmp/tickets")

            with patch("ticket_system.commands.bulk_create.get_next_seq") as mock_seq:
                mock_seq.return_value = 1

                with patch("ticket_system.commands.bulk_create.format_ticket_id") as mock_format:
                    mock_format.side_effect = [
                        "0.31.0-W1-001.1",
                        "0.31.0-W1-001.2",
                    ]

                    with patch("ticket_system.commands.bulk_create._create_ticket_config") as mock_config:
                        mock_config.return_value = {"parent_id": parent_id}

                        with patch("ticket_system.commands.bulk_create.create_ticket_frontmatter"):
                            with patch("ticket_system.commands.bulk_create.create_ticket_body"):
                                with patch("ticket_system.commands.bulk_create.get_ticket_path"):
                                    with patch("ticket_system.commands.bulk_create.save_ticket"):
                                        result = _create_batch_tickets(
                                            template_defaults,
                                            targets,
                                            "0.31.0",
                                            1,
                                            parent_id=parent_id,
                                        )

                                        assert result.total == 2
                                        assert len(result.created) == 2

    def test_create_batch_tickets_wave_seq_allocation(self):
        """
        Given: 同一 Wave 內多個 Targets
        When: 呼叫 _create_batch_tickets
        Then: 應正確分配遞增的序號
        """
        template_defaults = {"type": "IMP"}
        targets = ["目標1", "目標2", "目標3"]

        with patch("ticket_system.commands.bulk_create.get_tickets_dir") as mock_dir:
            mock_dir.return_value = Path("/tmp/tickets")

            with patch("ticket_system.commands.bulk_create.get_next_seq") as mock_seq:
                mock_seq.return_value = 5

                seq_counter = [5]

                def format_ticket_id_side_effect(version, wave, seq):
                    return f"{version}-W{wave}-{seq:03d}"

                with patch("ticket_system.commands.bulk_create.format_ticket_id") as mock_format:
                    mock_format.side_effect = format_ticket_id_side_effect

                    with patch("ticket_system.commands.bulk_create.create_ticket_frontmatter"):
                        with patch("ticket_system.commands.bulk_create.create_ticket_body"):
                            with patch("ticket_system.commands.bulk_create.get_ticket_path"):
                                with patch("ticket_system.commands.bulk_create.save_ticket"):
                                    result = _create_batch_tickets(
                                        template_defaults,
                                        targets,
                                        "0.31.0",
                                        1,
                                    )

                                    assert len(result.created) == 3
                                    # 驗證 ID 格式正確
                                    for ticket_id in result.created:
                                        assert "0.31.0-W1-" in ticket_id

    def test_create_batch_tickets_partial_failure(self):
        """
        Given: 部分 Targets 產生例外
        When: 呼叫 _create_batch_tickets
        Then: 應記錄失敗但繼續處理其他 Targets
        """
        template_defaults = {"type": "IMP"}
        targets = ["目標1", "目標2", "目標3"]

        with patch("ticket_system.commands.bulk_create.get_tickets_dir") as mock_dir:
            mock_dir.return_value = Path("/tmp/tickets")

            with patch("ticket_system.commands.bulk_create.get_next_seq") as mock_seq:
                mock_seq.return_value = 1

                with patch("ticket_system.commands.bulk_create.format_ticket_id") as mock_format:
                    mock_format.side_effect = [
                        "0.31.0-W1-001",
                        ValueError("序號分配失敗"),  # 模擬第二個失敗
                        "0.31.0-W1-003",
                    ]

                    with patch("ticket_system.commands.bulk_create.create_ticket_frontmatter"):
                        with patch("ticket_system.commands.bulk_create.create_ticket_body"):
                            with patch("ticket_system.commands.bulk_create.get_ticket_path"):
                                with patch("ticket_system.commands.bulk_create.save_ticket"):
                                    result = _create_batch_tickets(
                                        template_defaults,
                                        targets,
                                        "0.31.0",
                                        1,
                                    )

                                    assert result.total == 3
                                    assert len(result.created) == 2
                                    assert len(result.failed) == 1


class TestExecuteCommand:
    """execute 命令整合測試"""

    def test_execute_missing_version(self):
        """
        Given: 無法偵測版本
        When: 執行 execute 命令
        Then: 應返回錯誤代碼 1
        """
        args = Mock()
        args.version = None
        args.template = "test"
        args.targets = "目標1"
        args.wave = 1

        result = execute(args)

        assert result == 1

    def test_execute_invalid_wave(self):
        """
        Given: Wave 編號無效（0 或負數）
        When: 執行 execute 命令
        Then: 應返回錯誤代碼 1
        """
        args = Mock()
        args.version = "0.31.0"
        args.template = "test"
        args.targets = "目標1"
        args.wave = 0

        result = execute(args)

        assert result == 1

    def test_execute_template_not_found(self):
        """
        Given: 指定的模板不存在
        When: 執行 execute 命令
        Then: 應返回錯誤代碼 1
        """
        args = Mock()
        args.version = "0.31.0"
        args.template = "nonexistent_template"
        args.targets = "目標1"
        args.wave = 1

        with patch("ticket_system.commands.bulk_create._load_template") as mock_load:
            mock_load.side_effect = FileNotFoundError("模板不存在")

            with patch("ticket_system.commands.bulk_create.format_error") as mock_format_error:
                mock_format_error.return_value = "[Error] 模板不存在"

                result = execute(args)

                assert result == 1

    def test_execute_empty_targets(self):
        """
        Given: 目標清單為空
        When: 執行 execute 命令
        Then: 應返回錯誤代碼 1
        """
        args = Mock()
        args.version = "0.31.0"
        args.template = "test"
        args.targets = ""
        args.wave = 1

        with patch("ticket_system.commands.bulk_create._load_template") as mock_load:
            mock_load.return_value = {}

            result = execute(args)

            assert result == 1

    def test_execute_dry_run_success(self):
        """
        Given: 使用 --dry-run 參數
        When: 執行 execute 命令
        Then: 應成功執行但不建立檔案
        """
        args = Mock()
        args.version = "0.31.0"
        args.template = "test"
        args.targets = "目標1,目標2"
        args.wave = 1
        args.dry_run = True

        with patch("ticket_system.commands.bulk_create._load_template") as mock_load:
            mock_load.return_value = {"type": "IMP"}

            with patch("ticket_system.commands.bulk_create._create_batch_tickets") as mock_create:
                result_obj = BulkCreateResult(
                    created=["0.31.0-W1-001", "0.31.0-W1-002"],
                    total=2,
                    dry_run=True,
                )
                mock_create.return_value = result_obj

                with patch("ticket_system.commands.bulk_create._print_batch_summary"):
                    with patch("ticket_system.commands.bulk_create._print_batch_result"):
                        result = execute(args)

                        assert result == 0
                        mock_create.assert_called_once()

    def test_execute_with_parent_id(self):
        """
        Given: 指定了 parent 參數
        When: 執行 execute 命令
        Then: 應將 parent_id 傳遞給 _create_batch_tickets
        """
        args = Mock()
        args.version = "0.31.0"
        args.template = "test"
        args.targets = "子任務1"
        args.wave = 1
        args.dry_run = False
        args.parent = "0.31.0-W1-001"

        with patch("ticket_system.commands.bulk_create._load_template") as mock_load:
            mock_load.return_value = {"type": "IMP"}

            with patch("ticket_system.commands.bulk_create._create_batch_tickets") as mock_create:
                result_obj = BulkCreateResult(
                    created=["0.31.0-W1-001.1"],
                    total=1,
                )
                mock_create.return_value = result_obj

                with patch("ticket_system.commands.bulk_create._print_batch_summary"):
                    with patch("ticket_system.commands.bulk_create._print_batch_result"):
                        result = execute(args)

                        assert result == 0
                        # 驗證 parent_id 被正確傳遞
                        call_kwargs = mock_create.call_args[1]
                        assert call_kwargs["parent_id"] == "0.31.0-W1-001"

    def test_execute_failure_returns_1(self):
        """
        Given: 建立過程中有失敗項目
        When: 執行 execute 命令
        Then: 應返回錯誤代碼 1
        """
        args = Mock()
        args.version = "0.31.0"
        args.template = "test"
        args.targets = "目標1,目標2"
        args.wave = 1
        args.dry_run = False

        with patch("ticket_system.commands.bulk_create._load_template") as mock_load:
            mock_load.return_value = {"type": "IMP"}

            with patch("ticket_system.commands.bulk_create._create_batch_tickets") as mock_create:
                result_obj = BulkCreateResult(
                    created=["0.31.0-W1-001"],
                    failed=[("目標2", "序號分配失敗")],
                    total=2,
                )
                mock_create.return_value = result_obj

                with patch("ticket_system.commands.bulk_create._print_batch_summary"):
                    with patch("ticket_system.commands.bulk_create._print_batch_result"):
                        result = execute(args)

                        assert result == 1


class TestPrintBatchSummary:
    """批次摘要列印測試"""

    def test_print_batch_summary_normal_mode(self, capsys):
        """
        Given: 正常模式的 BulkCreateResult
        When: 呼叫 _print_batch_summary
        Then: 應列印正確的摘要資訊
        """
        result = BulkCreateResult(
            created=["0.31.0-W1-001", "0.31.0-W1-002"],
            total=2,
            dry_run=False,
        )

        with patch("ticket_system.commands.bulk_create.format_info") as mock_format:
            mock_format.return_value = "批次建立摘要"
            _print_batch_summary(result, "test_template", "0.31.0", 1)

            captured = capsys.readouterr()
            assert "0.31.0" in captured.out
            assert "test_template" in captured.out
            assert "2" in captured.out

    def test_print_batch_summary_dry_run_mode(self, capsys):
        """
        Given: dry-run 模式的 BulkCreateResult
        When: 呼叫 _print_batch_summary
        Then: 應顯示「預演」標籤
        """
        result = BulkCreateResult(
            created=["0.31.0-W1-001"],
            total=1,
            dry_run=True,
        )

        with patch("ticket_system.commands.bulk_create.format_info") as mock_format:
            mock_format.return_value = "摘要"
            _print_batch_summary(result, "test", "0.31.0", 1)

            captured = capsys.readouterr()
            # 應該包含表示 dry-run 的資訊
            assert "0.31.0" in captured.out


class TestPrintBatchResult:
    """批次結果列印測試"""

    def test_print_batch_result_all_success(self, capsys):
        """
        Given: 所有 Tickets 建立成功
        When: 呼叫 _print_batch_result
        Then: 應顯示成功數目
        """
        result = BulkCreateResult(
            created=["0.31.0-W1-001", "0.31.0-W1-002", "0.31.0-W1-003"],
            total=3,
        )

        with patch("ticket_system.commands.bulk_create.format_info") as mock_format:
            mock_format.return_value = "批次建立完成"
            _print_batch_result(result)

            captured = capsys.readouterr()
            assert "0.31.0-W1-001" not in captured.out  # 預設不列出成功清單
            assert "3" in captured.out  # 成功數目應該出現

    def test_print_batch_result_with_failures(self, capsys):
        """
        Given: 有失敗項目
        When: 呼叫 _print_batch_result
        Then: 應列出失敗項目的描述和錯誤訊息
        """
        result = BulkCreateResult(
            created=["0.31.0-W1-001"],
            failed=[("目標2", "序號分配失敗")],
            total=2,
        )

        with patch("ticket_system.commands.bulk_create.format_info") as mock_format:
            mock_format.return_value = "完成"
            _print_batch_result(result)

            captured = capsys.readouterr()
            assert "目標2" in captured.out
            assert "序號分配失敗" in captured.out

    def test_print_batch_result_with_warnings(self, capsys):
        """
        Given: 有警告項目
        When: 呼叫 _print_batch_result
        Then: 應列出警告項目的 ID 和警告訊息
        """
        result = BulkCreateResult(
            created=["0.31.0-W1-001", "0.31.0-W1-002"],
            warned=[("0.31.0-W1-001", "檔案已存在")],
            total=2,
        )

        with patch("ticket_system.commands.bulk_create.format_info") as mock_format:
            mock_format.return_value = "完成"
            _print_batch_result(result)

            captured = capsys.readouterr()
            assert "0.31.0-W1-001" in captured.out
            assert "檔案已存在" in captured.out


class TestRegisterCommand:
    """命令註冊測試"""

    def test_register_adds_subparser(self):
        """
        Given: argparse 的 subparsers 物件
        When: 呼叫 register 函式
        Then: 應新增 batch-create 子命令
        """
        subparsers = Mock(spec=["add_parser"])
        parser = Mock()
        subparsers.add_parser.return_value = parser

        register(subparsers)

        # 驗證 add_parser 被呼叫
        subparsers.add_parser.assert_called_once()
        call_args = subparsers.add_parser.call_args
        assert call_args[0][0] == "batch-create"

    def test_register_sets_defaults(self):
        """
        Given: argparse 的 subparsers 物件
        When: 呼叫 register 函式
        Then: 應設定 func 預設為 execute
        """
        subparsers = Mock(spec=["add_parser"])
        parser = Mock()
        subparsers.add_parser.return_value = parser

        register(subparsers)

        # 驗證 set_defaults 被呼叫並設定了 func
        parser.set_defaults.assert_called_once()
        call_kwargs = parser.set_defaults.call_args[1]
        assert call_kwargs["func"] == execute

    def test_register_adds_required_arguments(self):
        """
        Given: argparse 的 subparsers 物件
        When: 呼叫 register 函式
        Then: 應新增必要的命令行引數
        """
        subparsers = Mock(spec=["add_parser"])
        parser = Mock()
        subparsers.add_parser.return_value = parser

        register(subparsers)

        # 驗證 add_argument 被呼叫多次
        assert parser.add_argument.call_count >= 6

        # 檢查呼叫的引數名稱
        arg_names = []
        for call in parser.add_argument.call_args_list:
            # call[0] 是 positional args, call[1] 是 kwargs
            if call[0]:
                # 有位置參數時，第一個就是引數名稱
                arg_names.append(call[0][0])

        assert "--template" in arg_names
        assert "--targets" in arg_names
        assert "--version" in arg_names
        assert "--wave" in arg_names
        assert "--parent" in arg_names
        assert "--dry-run" in arg_names
