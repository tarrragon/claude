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


# ---- 3.5.0-W1-167：未觸及但工作區有未提交修改的 docs 檔，取提交內容（HEAD）參與判定 ----

# 跨檔檢查：觸及的 SPEC 以 depends_on_domains 引用 domain，須被某 DomainBundle 宣告
# （語料完全沒有 DomainBundle 時 doc validate 不檢查）
SPEC_PATH = "docs/spec/ui/SPEC-001-sample.md"
SPEC_REF = (
    "---\nid: SPEC-001\ntitle: sample\nstatus: draft\ndomain: ui\nsubdomain: null\n"
    "depends_on_domains: [alpha]\n---\n# spec\n"
)
MAP_ALPHA_PATH = "docs/spec/alpha/domain-map.md"
MAP_BETA_PATH = "docs/spec/beta/domain-map.md"
MAP_ALPHA = "---\nid: DOMAIN-MAP-alpha\ndomain: alpha\n---\n# map\n"
MAP_BETA = "---\nid: DOMAIN-MAP-beta\ndomain: beta\n---\n# map\n"


def _git(root, *args):
    subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@t", *args],
                   check=True, capture_output=True)


def _repo(tmp_path, head_files, workspace_files):
    """建 git repo：head_files 提交進 HEAD，workspace_files 再覆寫工作區。"""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    for rel, text in head_files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "--allow-empty", "-m", "base")
    for rel, text in workspace_files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    return root


def _touched_check(root):
    sf = StagedFile(SPEC_PATH, "", SPEC_REF, "")
    return [f.severity for f in dv.check_doc_validate([sf], root, _Logger(), Finding)]


class TestUntouchedDirtyFilesUseHead:
    def test_baseline_declared_in_head_passes(self, tmp_path):
        root = _repo(tmp_path, {MAP_ALPHA_PATH: MAP_ALPHA}, {SPEC_PATH: SPEC_REF})
        assert _touched_check(root) == []

    def test_other_uncommitted_removes_declaration_not_blocking(self, tmp_path):
        """他檔未提交修改把宣告改成 beta：修改前誤擋，修改後以 HEAD 放行。"""
        root = _repo(tmp_path, {MAP_ALPHA_PATH: MAP_ALPHA}, {SPEC_PATH: SPEC_REF})
        (root / MAP_ALPHA_PATH).write_text(MAP_BETA, encoding="utf-8")
        assert _touched_check(root) == []

    def test_other_uncommitted_blank_not_blocking(self, tmp_path):
        """設定為空：HEAD 有宣告、工作區清成空檔，以 HEAD 判定放行。"""
        root = _repo(tmp_path, {MAP_ALPHA_PATH: MAP_ALPHA}, {SPEC_PATH: SPEC_REF})
        (root / MAP_ALPHA_PATH).write_text("", encoding="utf-8")
        assert _touched_check(root) == []

    def test_other_uncommitted_adds_declaration_denied(self, tmp_path):
        """HEAD 只宣告 beta，他檔未提交修改改成宣告 alpha：修改前誤放，修改後 deny。"""
        root = _repo(tmp_path, {MAP_ALPHA_PATH: MAP_BETA}, {SPEC_PATH: SPEC_REF})
        (root / MAP_ALPHA_PATH).write_text(MAP_ALPHA, encoding="utf-8")
        assert _touched_check(root) == ["deny"]

    def test_other_untracked_only_in_workspace_denied(self, tmp_path):
        """整段缺席：宣告 alpha 的檔 HEAD 不存在、只在工作區 untracked，改判 deny。"""
        root = _repo(tmp_path, {MAP_BETA_PATH: MAP_BETA}, {SPEC_PATH: SPEC_REF, MAP_ALPHA_PATH: MAP_ALPHA})
        assert _touched_check(root) == ["deny"]

    def test_untracked_declaration_with_empty_head_corpus_passes(self, tmp_path):
        """HEAD 無任何 DomainBundle：doc validate 不檢查，untracked 宣告不影響（不變）。"""
        root = _repo(tmp_path, {}, {SPEC_PATH: SPEC_REF, MAP_ALPHA_PATH: MAP_ALPHA})
        assert _touched_check(root) == []

    def test_touched_file_mismatch_still_warn(self, tmp_path):
        root = _repo(tmp_path, {}, {EVT_PATH: EVT_NO_CONSUMER + "工作區另有修改\n"})
        sf = StagedFile(EVT_PATH, "", EVT_NO_CONSUMER, "")
        findings = dv.check_doc_validate([sf], root, _Logger(), Finding)
        assert [f.severity for f in findings] == ["warn"]

    def test_git_failure_falls_back_to_workspace_judgement_with_stderr(self, tmp_path, monkeypatch, capsys):
        root = _repo(tmp_path, {}, {EVT_PATH: EVT_NO_CONSUMER})
        real_run = subprocess.run

        def _fail_git(cmd, *a, **k):
            if cmd and cmd[0] == "git":
                raise OSError("injected")
            return real_run(cmd, *a, **k)

        monkeypatch.setattr(dv.subprocess, "run", _fail_git)
        logger = _Logger()
        sf = StagedFile(EVT_PATH, "", EVT_NO_CONSUMER, "")
        findings = dv.check_doc_validate([sf], root, logger, Finding)
        # E1 對照：改動前同輸入為 deny，git 失敗時退回原判定，仍 deny
        assert [f.severity for f in findings] == ["deny"]
        assert "injected" in capsys.readouterr().err
        assert any("injected" in w for w in logger.warnings)
