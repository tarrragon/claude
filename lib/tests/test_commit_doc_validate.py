"""commit 守衛的 doc validate 檢查（3.3.0-W1-018）。

缺陷：線直接提交規格到共用 main 時，commit 守衛不跑 doc validate，格式錯誤的規格直接進 main。
修復：觸及的 docs 節點跑 doc validate，只擋本次新增的錯誤；工作區與提交內容不一致時降為 warn；
doc CLI 失敗 fail-open（stderr 與日誌）。以真實 doc CLI 跑，不 mock 驗證結果。
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib import commit_doc_validate as dv  # noqa: E402
from lib.commit_content_guards import Finding, StagedFile, _check_doc_validate  # noqa: E402

EVT_PATH = "docs/events/EVT-DEMO-001-demo.md"
_HEAD = "---\nid: EVT-DEMO-001\nname: demo\ncanonical_name: Demo\ncategory: domain_event\n"
EVT_OK = _HEAD + "producers: [a]\nconsumers: [b]\n---\n# demo\n"
EVT_NO_CONSUMER = _HEAD + "producers: [a]\n---\n# demo\n"
EVT_NO_BOTH = _HEAD + "---\n# demo\n"


class _Logger:
    def __init__(self):
        self.warnings = []
        self.infos = []

    def info(self, msg, *args):
        self.infos.append(msg % args if args else msg)

    def warning(self, msg, *args):
        self.warnings.append(msg % args if args else msg)

    def debug(self, *a, **k):
        pass


def _project(tmp_path, text):
    """建立工作區（含 EVT 檔現況），回傳專案根。"""
    root = tmp_path / "proj"
    target = root / EVT_PATH
    target.parent.mkdir(parents=True)
    target.write_text(text, encoding="utf-8")
    return root


def _check(root, pre, post, logger=None):
    sf = StagedFile(EVT_PATH, pre, post, "")
    return dv.check_doc_validate([sf], root, logger or _Logger(), Finding)


class TestParseValidateOutput:
    def test_pass(self):
        result = dv.parse_validate_output(0, "通過: x\n")
        assert result.ok and result.errors == frozenset()

    def test_fail_items_paired_with_header(self):
        out = "驗證失敗: EVT-1 缺少以下項目\n  - a\n  - b\n"
        result = dv.parse_validate_output(1, out)
        assert result.ok
        assert ("驗證失敗: EVT-1 缺少以下項目", "a") in result.errors
        assert ("驗證失敗: EVT-1 缺少以下項目", "b") in result.errors

    def test_info_items_not_counted(self):
        out = "INFO: 已豁免 1 項\n  - x.md\n驗證失敗: EVT-1 缺少以下項目\n  - a\n"
        result = dv.parse_validate_output(1, out)
        assert all(item != "x.md" for _, item in result.errors)

    def test_rc1_without_header_is_cli_failure(self):
        """rc=1 但非驗證輸出（例如 import 失敗的 traceback）不當成驗證錯誤。"""
        result = dv.parse_validate_output(1, "Traceback ...\nModuleNotFoundError: yaml\n")
        assert not result.ok

    def test_unknown_rc_is_cli_failure(self):
        assert not dv.parse_validate_output(3, "").ok

    def test_rc2_counts_as_error(self):
        result = dv.parse_validate_output(2, "無法解析 frontmatter: x.md\n")
        assert result.ok and result.errors


class TestNodeSelection:
    def test_node_paths(self):
        assert dv.is_doc_node_path(EVT_PATH)
        assert dv.is_doc_node_path("docs/spec/a/SPEC-001.md")
        assert dv.is_doc_node_path("docs/domain-map.md")
        assert not dv.is_doc_node_path("docs/proposals/PROP-001.md")  # proposal-evaluation 負責
        assert not dv.is_doc_node_path("docs/work-logs/x.md")
        assert not dv.is_doc_node_path("docs/spec/a/notes.txt")

    def test_frontmatter_id(self):
        assert dv.frontmatter_id(EVT_OK) == "EVT-DEMO-001"
        assert dv.frontmatter_id("# 無 frontmatter\n") is None
        assert dv.frontmatter_id("---\ntitle: x\n---\nid: 不在 frontmatter\n") is None


class TestCheckDocValidate:
    def test_clean_node_passes(self, tmp_path):
        root = _project(tmp_path, EVT_OK)
        assert _check(root, "", EVT_OK) == []

    def test_new_node_with_error_denied(self, tmp_path):
        """正向對照：新檔帶錯誤，全部算新增，應擋。"""
        root = _project(tmp_path, EVT_NO_CONSUMER)
        findings = _check(root, "", EVT_NO_CONSUMER)
        assert [f.severity for f in findings] == ["deny"]
        assert "缺少 consumer" in findings[0].message

    def test_existing_error_not_blocked(self, tmp_path):
        """存量：提交前已有同一錯誤，只改內文，不擋。"""
        post = EVT_NO_CONSUMER + "補一段說明。\n"
        root = _project(tmp_path, post)
        assert _check(root, EVT_NO_CONSUMER, post) == []

    def test_only_new_errors_reported(self, tmp_path):
        """提交前缺 consumer、本次又刪掉 producer：只報新增的 producer。"""
        root = _project(tmp_path, EVT_NO_BOTH)
        findings = _check(root, EVT_NO_CONSUMER, EVT_NO_BOTH)
        assert [f.severity for f in findings] == ["deny"]
        assert "缺少 producer" in findings[0].message
        assert "缺少 consumer" not in findings[0].message

    def test_post_text_without_trailing_newline_still_consistent(self, tmp_path):
        """呼叫端重建的 post_text 去掉尾端換行（git 輸出 rstrip），不可誤判為不一致。"""
        root = _project(tmp_path, EVT_NO_CONSUMER)
        findings = _check(root, "", EVT_NO_CONSUMER.rstrip("\n"))
        assert [f.severity for f in findings] == ["deny"]

    def test_workspace_mismatch_downgrades_to_warn(self, tmp_path):
        """工作區（doc validate 讀的內容）與提交內容不一致：降為 warn。"""
        root = _project(tmp_path, EVT_NO_CONSUMER)
        findings = _check(root, "", EVT_NO_CONSUMER + "工作區另有未暫存的修改。\n")
        assert [f.severity for f in findings] == ["warn"]
        assert "不一致" in findings[0].message

    def test_deleted_node_skipped(self, tmp_path):
        root = tmp_path / "proj"
        root.mkdir()
        assert _check(root, EVT_NO_CONSUMER, "") == []

    def test_cli_timeout_fail_open_visible(self, tmp_path, monkeypatch, capsys):
        root = _project(tmp_path, EVT_NO_CONSUMER)

        def _timeout(*a, **k):
            raise subprocess.TimeoutExpired(cmd="doc", timeout=1)

        monkeypatch.setattr(dv.subprocess, "run", _timeout)
        logger = _Logger()
        assert _check(root, "", EVT_NO_CONSUMER, logger) == []
        assert "doc validate 執行失敗" in capsys.readouterr().err
        assert any("逾時" in w for w in logger.warnings)

    def test_pre_tree_reverts_other_staged_docs(self, tmp_path):
        """提交前的樹把同批其他 docs 檔還原為 pre_text、新檔移除。"""
        root = _project(tmp_path, EVT_OK)
        other_new = root / "docs/events/EVT-DEMO-002-new.md"
        other_new.write_text("new\n", encoding="utf-8")
        dest = tmp_path / "pre"
        dv._build_pre_commit_tree(  # noqa: SLF001
            root,
            [StagedFile(EVT_PATH, EVT_NO_CONSUMER, EVT_OK, ""),
             StagedFile("docs/events/EVT-DEMO-002-new.md", "", "new\n", "")],
            dest,
        )
        assert (dest / EVT_PATH).read_text(encoding="utf-8") == EVT_NO_CONSUMER
        assert not (dest / "docs/events/EVT-DEMO-002-new.md").exists()


class TestMergeCommitNotApplied:
    def test_merge_commit_skipped_with_positive_control(self, tmp_path):
        root = _project(tmp_path, EVT_NO_CONSUMER)
        sf = StagedFile(EVT_PATH, "", EVT_NO_CONSUMER, "")
        assert _check_doc_validate([sf], root, _Logger(), is_merge_commit=False)  # 正向對照
        assert _check_doc_validate([sf], root, _Logger(), is_merge_commit=True) == []
