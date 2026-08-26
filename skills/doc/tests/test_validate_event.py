"""validate 子命令對 EVT 型別的測試（0.2.1-W3-1060）。

EVT 是 B 層 proposed 型別：producers/consumers 建立模板時為選填，但
`doc validate` 對已存在的 EVT 文件強制檢查兩者皆非空——缺一端代表事件的
發送方或接收方未被記錄，這是本型別的核心價值（見票 why：BackupTracker
incrementSnapshotCount 有 consumer 無 producer 導致次數門檻永久失效）。
"""

import argparse
from pathlib import Path
from unittest.mock import patch

from doc_system.commands.validate import execute
from doc_system.core.file_locator import FileLocator


def _write_event(events_dir: Path, doc_id: str, extra_frontmatter: str, filename: str | None = None) -> Path:
    events_dir.mkdir(parents=True, exist_ok=True)
    md = events_dir / (filename or f"{doc_id}-x.md")
    frontmatter = f"---\nid: {doc_id}\n{extra_frontmatter}\n---\n# {doc_id}\n"
    md.write_text(frontmatter, encoding="utf-8")
    return md


class TestValidateEventSchema:
    """EVT 必填欄位（id/name/canonical_name/category）驗證。"""

    def test_valid_event_passes(self, tmp_path, capsys):
        """必填欄位齊全且 producer/consumer 皆非空應通過。"""
        events_dir = tmp_path / "docs" / "events" / "library"
        _write_event(
            events_dir,
            "EVT-LIBRARY-001",
            'name: "借閱完成"\ncanonical_name: "Library.Checkout.Completed"\n'
            "category: domain_event\nproducers: [CheckoutService]\nconsumers: [InventoryTracker]",
        )

        with patch.object(FileLocator, "get_project_root", return_value=str(tmp_path)):
            try:
                execute(argparse.Namespace(doc_id="EVT-LIBRARY-001"))
            except SystemExit as e:
                assert e.code == 0

        output = capsys.readouterr().out
        assert "通過" in output

    def test_missing_required_field_fails(self, tmp_path, capsys):
        """缺少 canonical_name 應驗證失敗。"""
        events_dir = tmp_path / "docs" / "events" / "library"
        _write_event(
            events_dir,
            "EVT-LIBRARY-002",
            'name: "借閱完成"\ncategory: domain_event\n'
            "producers: [CheckoutService]\nconsumers: [InventoryTracker]",
        )

        with patch.object(FileLocator, "get_project_root", return_value=str(tmp_path)):
            try:
                execute(argparse.Namespace(doc_id="EVT-LIBRARY-002"))
            except SystemExit as e:
                assert e.code == 1

        output = capsys.readouterr().out
        assert "canonical_name" in output

    def test_invalid_category_fails(self, tmp_path, capsys):
        """category 值不在合法清單內應驗證失敗。"""
        events_dir = tmp_path / "docs" / "events" / "library"
        _write_event(
            events_dir,
            "EVT-LIBRARY-003",
            'name: "借閱完成"\ncanonical_name: "Library.Checkout.Completed"\n'
            "category: not_a_real_category\nproducers: [X]\nconsumers: [Y]",
        )

        with patch.object(FileLocator, "get_project_root", return_value=str(tmp_path)):
            try:
                execute(argparse.Namespace(doc_id="EVT-LIBRARY-003"))
            except SystemExit as e:
                assert e.code == 1

        output = capsys.readouterr().out
        assert "category" in output


class TestValidateEventCrossReference:
    """producer/consumer 交叉驗證（本型別核心價值）。"""

    def test_missing_producer_fails(self, tmp_path, capsys):
        """缺 producer（空清單）應驗證失敗並指出缺口。"""
        events_dir = tmp_path / "docs" / "events" / "library"
        _write_event(
            events_dir,
            "EVT-LIBRARY-004",
            'name: "借閱完成"\ncanonical_name: "Library.Checkout.Completed"\n'
            "category: domain_event\nproducers: []\nconsumers: [InventoryTracker]",
        )

        with patch.object(FileLocator, "get_project_root", return_value=str(tmp_path)):
            try:
                execute(argparse.Namespace(doc_id="EVT-LIBRARY-004"))
            except SystemExit as e:
                assert e.code == 1

        output = capsys.readouterr().out
        assert "producer" in output.lower()

    def test_missing_consumer_fails(self, tmp_path, capsys):
        """缺 consumer（欄位缺失）應驗證失敗並指出缺口。

        對應票內查證事實：BackupTracker 的 incrementSnapshotCount 有
        consumer 無 producer 這類單邊缺口的鏡像案例（此處反向測缺 consumer）。
        """
        events_dir = tmp_path / "docs" / "events" / "library"
        _write_event(
            events_dir,
            "EVT-LIBRARY-005",
            'name: "借閱完成"\ncanonical_name: "Library.Checkout.Completed"\n'
            "category: domain_event\nproducers: [CheckoutService]",
        )

        with patch.object(FileLocator, "get_project_root", return_value=str(tmp_path)):
            try:
                execute(argparse.Namespace(doc_id="EVT-LIBRARY-005"))
            except SystemExit as e:
                assert e.code == 1

        output = capsys.readouterr().out
        assert "consumer" in output.lower()

    def test_missing_both_reports_both(self, tmp_path, capsys):
        """producer 與 consumer 皆缺時，兩項缺口都應被回報（非回報第一項即停）。"""
        events_dir = tmp_path / "docs" / "events" / "library"
        _write_event(
            events_dir,
            "EVT-LIBRARY-006",
            'name: "借閱完成"\ncanonical_name: "Library.Checkout.Completed"\ncategory: domain_event',
        )

        with patch.object(FileLocator, "get_project_root", return_value=str(tmp_path)):
            try:
                execute(argparse.Namespace(doc_id="EVT-LIBRARY-006"))
            except SystemExit as e:
                assert e.code == 1

        output = capsys.readouterr().out.lower()
        assert "producer" in output
        assert "consumer" in output


class TestValidateEventFileResolution:
    """EVT domain-scoped ID 不在 FileLocator.ID_PREFIX_FINDERS，需獨立解析路徑。"""

    def test_event_not_found_exits_2(self, tmp_path, capsys):
        """docs/events/ 下找不到對應檔案時應以 exit 2 報告（文件不存在，非驗證失敗）。"""
        (tmp_path / "docs").mkdir()

        with patch.object(FileLocator, "get_project_root", return_value=str(tmp_path)):
            try:
                execute(argparse.Namespace(doc_id="EVT-LIBRARY-999"))
            except SystemExit as e:
                assert e.code == 2

        output = capsys.readouterr().out
        assert "找不到文件" in output

    def test_event_resolved_via_domain_subdirectory(self, tmp_path, capsys):
        """EVT-LIBRARY-001 這類 domain-scoped ID（不匹配 FileLocator 既有前綴表）仍可被解析。"""
        events_dir = tmp_path / "docs" / "events" / "library"
        _write_event(
            events_dir,
            "EVT-LIBRARY-007",
            'name: "借閱完成"\ncanonical_name: "Library.Checkout.Completed"\n'
            "category: domain_event\nproducers: [A]\nconsumers: [B]",
            filename="EVT-LIBRARY-007-checkout.md",
        )

        with patch.object(FileLocator, "get_project_root", return_value=str(tmp_path)):
            try:
                execute(argparse.Namespace(doc_id="EVT-LIBRARY-007"))
            except SystemExit as e:
                assert e.code == 0

        output = capsys.readouterr().out
        assert "通過" in output
