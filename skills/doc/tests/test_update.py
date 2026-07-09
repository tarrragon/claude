"""update 子命令測試。"""

import argparse
from pathlib import Path
from unittest.mock import patch

import yaml

from doc_system.commands.update import execute
from doc_system.core.file_locator import FileLocator
from .tracking_fixtures import find_entry, make_test_tracking


def _setup_proposal(tmp_path, prop_id="PROP-001", status="draft", overrides=None):
    """建立 proposal md 檔 + list-based tracking.yaml（對齊
    docs/proposals-tracking.yaml 實際結構，經 make_test_tracking SSOT helper 生成，
    非手寫猜測欄位）。"""
    proposals_dir = tmp_path / "docs" / "proposals"
    proposals_dir.mkdir(parents=True)

    md = proposals_dir / f"{prop_id}-test.md"
    md.write_text(
        f'---\nid: {prop_id}\ntitle: "Test Proposal"\nstatus: {status}\n---\n# Content\n'
    )

    tracking = tmp_path / "docs" / "proposals-tracking.yaml"
    data = make_test_tracking(prop_id, status, overrides)
    tracking.write_text(
        yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)
    )

    return str(tmp_path)


# 向後相容別名：既有測試沿用 list-format 命名呼叫 target_version 情境。
def _setup_proposal_list_format(tmp_path, prop_id, status, target_version="__unset__"):
    overrides = None if target_version == "__unset__" else {"target_version": target_version}
    return _setup_proposal(tmp_path, prop_id, status, overrides)


def _setup_todolist(tmp_path, versions):
    """建立 todolist.yaml。versions 為 {version: status} 字典。"""
    todolist = tmp_path / "docs" / "todolist.yaml"
    data = {"versions": [{"version": v, "status": s} for v, s in versions.items()]}
    todolist.write_text(
        yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)
    )


class TestUpdateStatus:
    """update 子命令的測試案例。"""

    def test_update_status_success(self, tmp_path, capsys):
        """正常更新 proposal status 應修改檔案和 tracking.yaml。"""
        project_root = _setup_proposal(tmp_path, "PROP-001", "draft")
        args = argparse.Namespace(id="PROP-001", status="discussing")

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            execute(args)

        output = capsys.readouterr().out
        assert "已更新" in output
        assert "draft" in output
        assert "discussing" in output
        assert "已同步 tracking.yaml" in output

        # 檢查檔案 frontmatter 已更新
        md = tmp_path / "docs" / "proposals" / "PROP-001-test.md"
        content = md.read_text()
        assert "status: discussing" in content

        # 檢查 tracking.yaml 已同步
        tracking = tmp_path / "docs" / "proposals-tracking.yaml"
        data = yaml.safe_load(tracking.read_text())
        entry = find_entry(data["proposals"], "PROP-001")
        assert entry["status"] == "discussing"

    def test_update_nonexistent_id(self, tmp_path, capsys):
        """更新不存在的 ID 應顯示錯誤訊息。"""
        proposals_dir = tmp_path / "docs" / "proposals"
        proposals_dir.mkdir(parents=True)

        args = argparse.Namespace(id="PROP-999", status="confirmed")

        with patch.object(FileLocator, "get_project_root", return_value=str(tmp_path)):
            try:
                execute(args)
            except SystemExit:
                pass

        output = capsys.readouterr().out
        assert "找不到文件" in output

    def test_update_tracking_yaml_sync(self, tmp_path, capsys):
        """更新 proposal 為 confirmed 時應在 tracking.yaml 填入 confirmed_at 日期，
        且不產生 confirmed 欄位（真實 schema 為 confirmed_at，非 confirmed，
        IMP-APP-002 同族第四起）。"""
        project_root = _setup_proposal(tmp_path, "PROP-002", "discussing")
        args = argparse.Namespace(id="PROP-002", status="confirmed")

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            execute(args)

        output = capsys.readouterr().out
        assert "已更新" in output
        assert "已同步 tracking.yaml" in output

        # 檢查 tracking.yaml confirmed_at 日期已填入，且不產生 confirmed 欄位
        tracking = tmp_path / "docs" / "proposals-tracking.yaml"
        data = yaml.safe_load(tracking.read_text())
        entry = find_entry(data["proposals"], "PROP-002")
        assert entry["status"] == "confirmed"
        assert entry["confirmed_at"] is not None
        assert "confirmed" not in entry

        # 真實 schema 頂層僅 proposals/usecases/specs 三區塊，
        # 不應憑空新增 last_updated（IMP-APP-002 同族第五起）
        assert "last_updated" not in data

    def test_update_tracking_yaml_sync_list_format(self, tmp_path, capsys):
        """proposals-tracking.yaml 為 list-based 結構（實際 repo 格式）時，
        status 應同步成功（IMP-APP-002 同族：格式假設無真實資料驗證）。"""
        project_root = _setup_proposal_list_format(
            tmp_path, "PROP-030", status="discussing"
        )
        args = argparse.Namespace(id="PROP-030", status="confirmed")

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            execute(args)

        output = capsys.readouterr().out
        assert "已同步 tracking.yaml" in output
        assert "無對應 entry" not in output

        tracking = tmp_path / "docs" / "proposals-tracking.yaml"
        data = yaml.safe_load(tracking.read_text())
        entries = data["proposals"]
        assert isinstance(entries, list)
        entry = next(item for item in entries if item["id"] == "PROP-030")
        assert entry["status"] == "confirmed"
        assert entry["confirmed_at"] is not None
        assert "confirmed" not in entry

    def test_update_tracking_yaml_sync_list_format_not_found(self, tmp_path, capsys):
        """list-based 結構中找不到對應 prop_id 時應顯示無對應 entry（略過同步）。"""
        project_root = _setup_proposal_list_format(
            tmp_path, "PROP-031", status="discussing"
        )
        # 覆寫 tracking.yaml 使其僅含另一個不相關 id，模擬 doc 存在但 tracking 缺 entry
        tracking = tmp_path / "docs" / "proposals-tracking.yaml"
        tracking.write_text(
            yaml.dump(
                {"proposals": [{"id": "PROP-999", "status": "draft"}]},
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
            )
        )
        args = argparse.Namespace(id="PROP-031", status="confirmed")

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            execute(args)

        output = capsys.readouterr().out
        assert "無對應 entry" in output

    def test_update_registered_confirmed_target_version_no_guidance(self, tmp_path, capsys):
        """target_version 已在 todolist.yaml 註冊（不限 status）時不應觸發引導。"""
        project_root = _setup_proposal(
            tmp_path, "PROP-002", "discussing", overrides={"target_version": "v0.38.0"}
        )
        _setup_todolist(tmp_path, {"0.38.0": "planned"})
        args = argparse.Namespace(id="PROP-002", status="confirmed")

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            execute(args)

        output = capsys.readouterr().out
        assert "todolist" not in output

    def test_update_usecase_no_tracking_sync(self, tmp_path, capsys):
        """更新 usecase 不應嘗試同步 tracking.yaml。"""
        usecases_dir = tmp_path / "docs" / "usecases"
        usecases_dir.mkdir(parents=True)

        md = usecases_dir / "UC-01-test.md"
        md.write_text(
            '---\nid: UC-01\ntitle: "Test UC"\nstatus: draft\n---\n# UC-01\n'
        )

        args = argparse.Namespace(id="UC-01", status="confirmed")

        with patch.object(FileLocator, "get_project_root", return_value=str(tmp_path)):
            execute(args)

        output = capsys.readouterr().out
        assert "已更新" in output
        # UC 不會有 tracking 同步訊息
        assert "已同步 tracking.yaml" not in output


class TestTargetVersionRegistrationGuidance:
    """提案 confirmed 時 target_version 註冊 todolist 的源頭引導測試。

    判定標準與 version-tracking-consistency-guard-hook 漂移 7 一致：
    target_version 出現於 todolist.yaml 任一版本條目（不論 status）即視為已註冊。
    """

    def test_confirmed_unregistered_target_version_prints_guidance(self, tmp_path, capsys):
        """confirmed 且 target_version 未在 todolist.yaml 註冊時應輸出引導。"""
        project_root = _setup_proposal_list_format(
            tmp_path, "PROP-020", status="discussing", target_version="v0.39.0"
        )
        _setup_todolist(tmp_path, {"0.37.0": "completed"})
        args = argparse.Namespace(id="PROP-020", status="confirmed")

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            execute(args)

        output = capsys.readouterr().out
        assert "PROP-020" in output
        assert "0.39.0" in output
        assert "todolist" in output

    def test_confirmed_registered_target_version_no_guidance(self, tmp_path, capsys):
        """target_version 已在 todolist.yaml 註冊（不限 status）時不應提示。"""
        project_root = _setup_proposal_list_format(
            tmp_path, "PROP-021", status="discussing", target_version="v0.39.0"
        )
        _setup_todolist(tmp_path, {"0.39.0": "planned"})
        args = argparse.Namespace(id="PROP-021", status="confirmed")

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            execute(args)

        output = capsys.readouterr().out
        assert "todolist" not in output

    def test_confirmed_null_target_version_no_guidance(self, tmp_path, capsys):
        """target_version 為 null（或未設定）時不提示（與 guard 漂移 7 判定標準一致，
        該情境屬「提案未指定目標版本」的不同關注點，非本引導職責）。"""
        project_root = _setup_proposal_list_format(
            tmp_path, "PROP-022", status="discussing", target_version=None
        )
        _setup_todolist(tmp_path, {"0.37.0": "completed"})
        args = argparse.Namespace(id="PROP-022", status="confirmed")

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            execute(args)

        output = capsys.readouterr().out
        assert "todolist" not in output

    def test_non_confirmed_transition_no_guidance(self, tmp_path, capsys):
        """非 confirmed 的狀態轉換不應觸發 target_version 檢查。"""
        project_root = _setup_proposal_list_format(
            tmp_path, "PROP-023", status="draft", target_version="v0.39.0"
        )
        _setup_todolist(tmp_path, {"0.37.0": "completed"})
        args = argparse.Namespace(id="PROP-023", status="discussing")

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            execute(args)

        output = capsys.readouterr().out
        assert "todolist" not in output

    def test_prop_016_regression_scenario(self, tmp_path, capsys):
        """PROP-016 情境回歸測試：confirmed + target_version=v0.38.0 未註冊 todolist，
        重現 2026-07-08 誤推進事件的流程層根因（0.38.0 缺席 planned 候選，
        activate 誤選 1.0.0）。"""
        project_root = _setup_proposal_list_format(
            tmp_path, "PROP-016", status="discussing", target_version="v0.38.0"
        )
        # 對應事件現場：todolist 僅有 0.37.0（completed）與 1.0.0（planned），無 0.38.0 條目
        _setup_todolist(tmp_path, {"0.37.0": "completed", "1.0.0": "planned"})
        args = argparse.Namespace(id="PROP-016", status="confirmed")

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            execute(args)

        output = capsys.readouterr().out
        assert "PROP-016" in output
        assert "0.38.0" in output
        assert "todolist" in output
