"""
1.2.0-W1-002: version-release 統一版本 monorepo 模式 + #4 monorepo/trunk fixes

覆蓋：
- unified-monorepo：project_type:monorepo + 頂層 version_source（無 subprojects）
  → 以 version_source 為 SoT 偵測子目錄版本檔
- Gap 1：非 chrome-ext 不印 Chrome Extension 雙版本 dual report
- Gap 2：resolve_sync_version_files 優先採 version_source.primary（含子目錄）
- Gap 3：trunk 工作流跳過 feature 分支慣例警告
- Gap 5：主日誌偵測 fallback 至版本子目錄內任一 v{version}*.md
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import version_release as vr  # noqa: E402


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# unified-monorepo 模式 + Gap 2：resolve_sync_version_files
# ---------------------------------------------------------------------------
class TestUnifiedMonorepoResolve:
    def test_version_source_primary_in_subdir(self, tmp_path):
        """monorepo + version_source.primary 指向子目錄版本檔 → 偵測該檔"""
        _write(tmp_path / "app" / "pubspec.yaml", "version: 1.2.0\n")
        config = dict(vr.DEFAULT_VERSION_RELEASE_CONFIG)
        config["project_type"] = "monorepo"
        config["version_source"] = {"primary": "app/pubspec.yaml", "parser": "yaml"}
        config["subprojects"] = None

        files = vr.resolve_sync_version_files(tmp_path, config)

        assert len(files) == 1
        path, parser = files[0]
        assert path == tmp_path / "app" / "pubspec.yaml"
        assert parser == "yaml"

    def test_parser_inferred_from_suffix(self, tmp_path):
        """version_source 未指定 parser 時由副檔名推斷"""
        _write(tmp_path / "server" / "package.json", '{"version": "2.0.0"}\n')
        config = dict(vr.DEFAULT_VERSION_RELEASE_CONFIG)
        config["project_type"] = "monorepo"
        config["version_source"] = {"primary": "server/package.json"}
        config["subprojects"] = None

        files = vr.resolve_sync_version_files(tmp_path, config)

        assert files[0][1] == "json"

    def test_fallback_to_root_scan_when_no_version_source(self, tmp_path):
        """無 version_source 時 fallback 至 root 掃描（向後相容）"""
        _write(tmp_path / "package.json", '{"version": "3.0.0"}\n')
        config = dict(vr.DEFAULT_VERSION_RELEASE_CONFIG)
        config["version_source"] = None

        files = vr.resolve_sync_version_files(tmp_path, config)

        assert any(p.name == "package.json" for p, _ in files)

    def test_git_tag_strategy_returns_empty(self, tmp_path):
        """version_source.parser=git-tag 且無 root 版本檔 → 空 list（走 git-tag）"""
        config = dict(vr.DEFAULT_VERSION_RELEASE_CONFIG)
        config["version_source"] = {"parser": "git-tag"}

        files = vr.resolve_sync_version_files(tmp_path, config)

        assert files == []

    def test_unified_monorepo_version_detected(self, tmp_path):
        """end-to-end：unified-monorepo 模式下 detect_version 取子目錄版本"""
        _write(tmp_path / "app" / "pubspec.yaml", "version: 1.2.0\n")
        config = dict(vr.DEFAULT_VERSION_RELEASE_CONFIG)
        config["project_type"] = "monorepo"
        config["version_source"] = {"primary": "app/pubspec.yaml", "parser": "yaml"}
        config["subprojects"] = None

        with patch.object(vr, "get_project_root", return_value=tmp_path), \
                patch.object(vr, "load_version_release_config", return_value=config), \
                patch.object(vr, "subprocess") as mock_sub:
            # git 分支 / tag 偵測都回傳無結果，強制走版本檔路徑
            mock_sub.run.return_value = MagicMock(returncode=1, stdout="")
            detected = vr.detect_version()

        assert detected == "1.2.0"


# ---------------------------------------------------------------------------
# Gap 1：非 chrome-ext 不印雙版本 dual report
# ---------------------------------------------------------------------------
class TestGap1DualReportGate:
    def test_non_chrome_ext_skips_dual_report(self, tmp_path):
        """project_type=monorepo → 不呼叫 print_version_sync_report"""
        _write(tmp_path / "app" / "pubspec.yaml", "version: 1.2.0\n")
        config = dict(vr.DEFAULT_VERSION_RELEASE_CONFIG)
        config["project_type"] = "monorepo"
        config["version_source"] = {"primary": "app/pubspec.yaml", "parser": "yaml"}
        config["release_workflow"] = "trunk"

        with patch.object(vr, "get_project_root", return_value=tmp_path), \
                patch.object(vr, "load_version_release_config", return_value=config), \
                patch.object(vr, "print_version_sync_report") as mock_report, \
                patch.object(vr, "check_version_sync_dual") as mock_dual:
            vr.check_version_sync("1.2.0")

        mock_report.assert_not_called()
        mock_dual.assert_not_called()

    def test_chrome_ext_prints_dual_report(self, tmp_path):
        """project_type=chrome-ext → 仍印 dual report（向後相容）"""
        _write(tmp_path / "package.json", '{"version": "1.2.0"}\n')
        config = dict(vr.DEFAULT_VERSION_RELEASE_CONFIG)
        config["project_type"] = "chrome-ext"
        config["release_workflow"] = "trunk"

        with patch.object(vr, "get_project_root", return_value=tmp_path), \
                patch.object(vr, "load_version_release_config", return_value=config), \
                patch.object(vr, "print_version_sync_report") as mock_report, \
                patch.object(vr, "check_version_sync_dual",
                             return_value={"messages": []}) as mock_dual:
            vr.check_version_sync("1.2.0")

        mock_report.assert_called_once()
        mock_dual.assert_called_once()


# ---------------------------------------------------------------------------
# Gap 3：trunk 工作流跳過 feature 分支慣例警告
# ---------------------------------------------------------------------------
class TestGap3TrunkSkipsBranchWarning:
    def test_trunk_does_not_query_branch(self, tmp_path):
        """release_workflow=trunk → 不執行 git branch 查詢（無分支慣例警告）"""
        _write(tmp_path / "app" / "pubspec.yaml", "version: 1.2.0\n")
        config = dict(vr.DEFAULT_VERSION_RELEASE_CONFIG)
        config["project_type"] = "monorepo"
        config["version_source"] = {"primary": "app/pubspec.yaml", "parser": "yaml"}
        config["release_workflow"] = "trunk"

        with patch.object(vr, "get_project_root", return_value=tmp_path), \
                patch.object(vr, "load_version_release_config", return_value=config), \
                patch.object(vr, "subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=0, stdout="main")
            vr.check_version_sync("1.2.0")

        branch_calls = [
            c for c in mock_sub.run.call_args_list
            if "branch" in c.args[0]
        ]
        assert branch_calls == []

    def test_feature_branch_queries_branch(self, tmp_path):
        """release_workflow=feature-branch → 仍執行 git branch 查詢"""
        _write(tmp_path / "package.json", '{"version": "1.2.0"}\n')
        config = dict(vr.DEFAULT_VERSION_RELEASE_CONFIG)
        config["project_type"] = "npm"
        config["release_workflow"] = "feature-branch"

        with patch.object(vr, "get_project_root", return_value=tmp_path), \
                patch.object(vr, "load_version_release_config", return_value=config), \
                patch.object(vr, "subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=0, stdout="main")
            vr.check_version_sync("1.2.0")

        branch_calls = [
            c for c in mock_sub.run.call_args_list
            if "branch" in c.args[0]
        ]
        assert len(branch_calls) >= 1


# ---------------------------------------------------------------------------
# Gap 5：主日誌偵測 fallback
# ---------------------------------------------------------------------------
class TestGap5WorklogMainFallback:
    def _setup_worklog(self, tmp_path, main_filename):
        """建立巢狀 worklog 結構，主日誌使用指定檔名。"""
        subdir = (
            tmp_path / "docs" / "work-logs" / "v1" / "v1.2" / "v1.2.0"
        )
        _write(subdir / main_filename, "# worklog\n")
        (subdir / "tickets").mkdir(parents=True, exist_ok=True)
        return subdir

    def test_fallback_to_non_main_named_worklog(self, tmp_path):
        """無 v{version}-main.md 時 fallback 取版本子目錄內任一 v{version}*.md"""
        self._setup_worklog(tmp_path, "v1.2.0-overview.md")
        config = dict(vr.DEFAULT_VERSION_RELEASE_CONFIG)

        with patch.object(vr, "get_project_root", return_value=tmp_path), \
                patch.object(vr, "load_version_release_config", return_value=config):
            ok, errors = vr.check_worklog_completed("1.2.0")

        # 主日誌 fallback 命中 → 無「找不到主工作日誌」錯誤
        assert not any("找不到主工作日誌" in e for e in errors)
        assert ok

    def test_main_md_still_preferred(self, tmp_path):
        """v{version}-main.md 存在時優先使用（不受 fallback 影響）"""
        self._setup_worklog(tmp_path, "v1.2.0-main.md")
        config = dict(vr.DEFAULT_VERSION_RELEASE_CONFIG)

        with patch.object(vr, "get_project_root", return_value=tmp_path), \
                patch.object(vr, "load_version_release_config", return_value=config):
            ok, errors = vr.check_worklog_completed("1.2.0")

        assert not any("找不到主工作日誌" in e for e in errors)
        assert ok
