"""
0.19.0-W1-127: config 化 version-release CLI 硬編碼假設測試

覆蓋三情境：
1. tag 命名（tag_format，預設 plain v{version}，可選 -final）
2. workflow 模式（release_workflow，trunk 跳過 merge / feature-branch 維持現行）
3. worklog 路徑（worklog_path_pattern，支援巢狀路徑）
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import version_release as vr  # noqa: E402


# ---------------------------------------------------------------------------
# 情境 1：tag 命名（tag_format）
# ---------------------------------------------------------------------------
class TestTagFormat:
    def test_default_config_plain_tag(self):
        """預設 config 的 tag_format 為 plain v{version}（無 -final）"""
        assert vr.DEFAULT_VERSION_RELEASE_CONFIG["tag_format"] == "v{version}"

    def test_tag_format_renders_plain(self):
        """tag_format 範本套用後產生 plain tag"""
        rendered = "v{version}".format(version="0.19.0", major_minor="0.19")
        assert rendered == "v0.19.0"
        assert "-final" not in rendered

    def test_tag_format_final_opt_in(self):
        """顯式設定 -final 後綴時可保留舊行為"""
        rendered = "v{version}-final".format(version="0.19.0", major_minor="0.19")
        assert rendered == "v0.19.0-final"

    def test_git_merge_uses_config_tag_format(self, tmp_path):
        """git_merge_and_push dry-run 使用 config tag_format（trunk + plain tag）"""
        config = dict(vr.DEFAULT_VERSION_RELEASE_CONFIG)
        config["tag_format"] = "v{version}"
        config["release_workflow"] = "trunk"

        with patch.object(vr, "get_project_root", return_value=tmp_path), \
                patch.object(vr, "load_version_release_config", return_value=config), \
                patch.object(vr, "commit_changes", return_value=True), \
                patch.object(vr, "subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=0, stderr="")
            ok = vr.git_merge_and_push("0.19.0", dry_run=True)

        assert ok is True


# ---------------------------------------------------------------------------
# 情境 2：workflow 模式（release_workflow）
# ---------------------------------------------------------------------------
class TestReleaseWorkflow:
    def test_default_workflow_is_trunk(self):
        """預設 release_workflow 為 trunk（all-on-main）"""
        assert vr.DEFAULT_VERSION_RELEASE_CONFIG["release_workflow"] == "trunk"

    def test_trunk_skips_merge_and_branch_cleanup(self, tmp_path):
        """trunk 模式 dry-run 不呼叫 git merge / branch -d（無分支不報錯）"""
        config = dict(vr.DEFAULT_VERSION_RELEASE_CONFIG)
        config["release_workflow"] = "trunk"

        with patch.object(vr, "get_project_root", return_value=tmp_path), \
                patch.object(vr, "load_version_release_config", return_value=config), \
                patch.object(vr, "commit_changes", return_value=True), \
                patch.object(vr, "subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=0, stderr="")
            ok = vr.git_merge_and_push("0.19.0", dry_run=True)

        assert ok is True
        # dry-run 不執行 subprocess.run（除 commit_changes 已 mock），
        # trunk 模式下 merge / branch 步驟整段跳過，無 feature-branch 副作用
        called_args = [c.args[0] for c in mock_sub.run.call_args_list if c.args]
        flat = [tok for cmd in called_args for tok in (cmd if isinstance(cmd, list) else [])]
        assert "merge" not in flat
        assert not any("feature/" in str(tok) for tok in flat)

    def test_feature_branch_workflow_preserved(self, tmp_path):
        """feature-branch 模式維持現行行為（非 dry-run 會嘗試 merge）"""
        config = dict(vr.DEFAULT_VERSION_RELEASE_CONFIG)
        config["release_workflow"] = "feature-branch"

        with patch.object(vr, "get_project_root", return_value=tmp_path), \
                patch.object(vr, "load_version_release_config", return_value=config), \
                patch.object(vr, "commit_changes", return_value=True), \
                patch.object(vr, "subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=0, stderr="")
            ok = vr.git_merge_and_push("0.19.0", dry_run=False)

        assert ok is True
        called_args = [c.args[0] for c in mock_sub.run.call_args_list if c.args]
        flat_cmds = [cmd for cmd in called_args if isinstance(cmd, list)]
        # feature-branch 模式應出現 merge feature/v0.19
        assert any("merge" in cmd and "feature/v0.19" in cmd for cmd in flat_cmds)


# ---------------------------------------------------------------------------
# 情境 3：worklog 路徑（worklog_path_pattern）
# ---------------------------------------------------------------------------
class TestWorklogPathPattern:
    def test_default_pattern_is_nested(self):
        """預設 worklog_path_pattern 為巢狀路徑"""
        assert (
            vr.DEFAULT_VERSION_RELEASE_CONFIG["worklog_path_pattern"]
            == "docs/work-logs/v{major}/v{major_minor}/v{version}"
        )

    def test_resolve_nested_path(self, tmp_path):
        """巢狀範本解析為 docs/work-logs/v0/v0.19/v0.19.0"""
        resolved = vr.resolve_worklog_dir(
            tmp_path, "0.19.0", "docs/work-logs/v{major}/v{major_minor}/v{version}"
        )
        assert resolved == tmp_path / "docs/work-logs/v0/v0.19/v0.19.0"

    def test_resolve_flat_path(self, tmp_path):
        """扁平範本（舊結構）解析為 docs/work-logs/v0.19.0"""
        resolved = vr.resolve_worklog_dir(
            tmp_path, "0.19.0", "docs/work-logs/v{version}"
        )
        assert resolved == tmp_path / "docs/work-logs/v0.19.0"

    def test_check_worklog_detects_nested(self, tmp_path):
        """check_worklog_completed 依 config 巢狀範本偵測到 worklog，不報找不到"""
        nested = tmp_path / "docs/work-logs/v0/v0.19/v0.19.0"
        nested.mkdir(parents=True)
        (nested / "v0.19.0-main.md").write_text("# v0.19.0 main worklog\n", encoding="utf-8")
        (nested / "v0.19.0-extra.md").write_text("# extra\n", encoding="utf-8")

        config = dict(vr.DEFAULT_VERSION_RELEASE_CONFIG)
        config["worklog_path_pattern"] = "docs/work-logs/v{major}/v{major_minor}/v{version}"

        with patch.object(vr, "get_project_root", return_value=tmp_path), \
                patch.object(vr, "load_version_release_config", return_value=config):
            ok, errors = vr.check_worklog_completed("0.19.0")

        # 無 tickets 子目錄 + 主 worklog 存在 -> 通過，無「找不到工作日誌」錯誤
        assert ok is True, f"unexpected errors: {errors}"
        assert not any("找不到" in e for e in errors)


# ---------------------------------------------------------------------------
# config 載入（.claude/ fallback）
# ---------------------------------------------------------------------------
class TestConfigClaudeFallback:
    def test_root_config_takes_precedence(self, tmp_path):
        (tmp_path / ".version-release.yaml").write_text(
            "release_workflow: feature-branch\n", encoding="utf-8"
        )
        claude = tmp_path / ".claude"
        claude.mkdir()
        (claude / ".version-release.yaml").write_text(
            "release_workflow: trunk\n", encoding="utf-8"
        )
        config = vr.load_version_release_config(tmp_path)
        assert config["release_workflow"] == "feature-branch"

    def test_claude_fallback_loaded(self, tmp_path):
        claude = tmp_path / ".claude"
        claude.mkdir()
        (claude / ".version-release.yaml").write_text(
            "release_workflow: trunk\ntag_format: \"v{version}\"\n", encoding="utf-8"
        )
        config = vr.load_version_release_config(tmp_path)
        assert config["release_workflow"] == "trunk"
        assert config["tag_format"] == "v{version}"

    def test_no_config_returns_default(self, tmp_path):
        config = vr.load_version_release_config(tmp_path)
        assert config["release_workflow"] == "trunk"
        assert config["tag_format"] == "v{version}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
