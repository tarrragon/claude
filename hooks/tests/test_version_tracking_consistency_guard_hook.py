#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
version-tracking-consistency-guard-hook 測試套件

測試覆蓋（0.37.0-W9-004 誤報修復驗證）：
- todolist 解析：帶引號 status（`status: "completed"`）須正確解析為對應版本
- scan_ticket_versions：非 semver token（如 "0.22.x"、"可選"）須被過濾，不列入幽靈版本
- scan_worklog_versions：legacy/examples/archived 目錄不含 vX.Y.Z 子目錄，不誤判為版本

修復背景：原 VERSION_ENTRY_PATTERN 的 status group 用 `(\\w+)`，無法匹配帶引號
的 `"completed"`，導致正規表達式非貪婪擴張跨越多個版本條目，
把中間所有版本（含 todolist.yaml 已有條目的版本）誤判為「無條目」幽靈版本。
"""

import importlib.util
import tempfile
from pathlib import Path

import pytest

hooks_path = Path(__file__).parent.parent
hook_file = hooks_path / "version-tracking-consistency-guard-hook.py"
spec = importlib.util.spec_from_file_location(
    "version_tracking_consistency_guard_hook", hook_file
)
guard_hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard_hook)


class FakeLogger:
    """避免測試依賴真實日誌檔寫入"""

    def warning(self, *args, **kwargs):
        pass

    def info(self, *args, **kwargs):
        pass

    def debug(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


class TestParseTodolistQuotedStatus:
    """帶引號 status 解析修復（誤報根因 1）"""

    def test_quoted_status_parsed_correctly(self, tmp_path):
        todolist = tmp_path / "todolist.yaml"
        todolist.write_text(
            """
versions:
  - version: "0.32.1"
    codename: "QR-Offline-Sync"
    description: "desc"
    status: "completed"
    worklog: "docs/work-logs/v0/v0.32/v0.32.1/"
    notes: |
      多行說明文字。
      第二行。

  - version: "0.34.0"
    codename: "Test-Unify"
    description: "desc"
    status: "completed"
    worklog: "docs/work-logs/v0/v0.34/v0.34.0/"
    notes: |
      另一段說明。
""",
            encoding="utf-8",
        )
        versions = guard_hook.parse_todolist(todolist, FakeLogger())
        assert versions.get("0.32.1") == "completed"
        assert versions.get("0.34.0") == "completed"

    def test_unquoted_status_still_parsed(self, tmp_path):
        """向後相容：既有未加引號的 status 值仍須解析成功"""
        todolist = tmp_path / "todolist.yaml"
        todolist.write_text(
            """
versions:
  - version: "0.33.0"
    status: completed
""",
            encoding="utf-8",
        )
        versions = guard_hook.parse_todolist(todolist, FakeLogger())
        assert versions.get("0.33.0") == "completed"

    def test_multiple_quoted_entries_do_not_bleed_into_each_other(self, tmp_path):
        """迴歸測試：非貪婪擴張不得跨越多個版本條目吞噬中間版本"""
        todolist = tmp_path / "todolist.yaml"
        todolist.write_text(
            """
versions:
  - version: "0.31.0"
    status: "completed"
    notes: |
      長篇備註文字。

  - version: "0.32.1"
    status: "completed"

  - version: "0.37.0"
    status: "active"
""",
            encoding="utf-8",
        )
        versions = guard_hook.parse_todolist(todolist, FakeLogger())
        assert versions == {
            "0.31.0": "completed",
            "0.32.1": "completed",
            "0.37.0": "active",
        }


class TestScanTicketVersionsSemverFilter:
    """非 semver token 過濾修復（誤報根因 2）"""

    def _write_ticket(self, tickets_dir: Path, name: str, version: str) -> None:
        tickets_dir.mkdir(parents=True, exist_ok=True)
        (tickets_dir / name).write_text(
            f"""---
id: {name}
version: "{version}"
status: closed
---

# body
""",
            encoding="utf-8",
        )

    def test_non_semver_token_filtered_out(self, tmp_path):
        tickets_dir = tmp_path / "docs" / "work-logs" / "v0" / "v0.21" / "v0.21.1" / "tickets"
        self._write_ticket(tickets_dir, "0.21.1-TD-001.md", "0.22.x")
        self._write_ticket(tickets_dir, "0.21.1-TD-002.md", "可選")

        versions = guard_hook.scan_ticket_versions(tmp_path)
        assert "0.22.x" not in versions
        assert "可選" not in versions

    def test_semver_token_still_included(self, tmp_path):
        tickets_dir = tmp_path / "docs" / "work-logs" / "v0" / "v0.34" / "v0.34.0" / "tickets"
        self._write_ticket(tickets_dir, "0.34.0-W1-001.md", "0.34.0")

        versions = guard_hook.scan_ticket_versions(tmp_path)
        assert "0.34.0" in versions


class TestScanWorklogVersionsExcludesLegacyDirs:
    """legacy/examples/archived 目錄不被誤判為版本（acceptance 第 3 項）"""

    def test_legacy_examples_archived_have_no_version_subdirs(self, tmp_path):
        work_logs = tmp_path / "docs" / "work-logs"
        for special_dir in ("legacy", "examples", "archived"):
            (work_logs / special_dir).mkdir(parents=True)
            (work_logs / special_dir / "some-report.md").write_text("x", encoding="utf-8")

        # 正常版本目錄仍須被正確掃到
        (work_logs / "v0" / "v0.37" / "v0.37.0").mkdir(parents=True)

        versions = guard_hook.scan_worklog_versions(tmp_path)
        assert versions == {"0.37.0"}


class TestGhostVersionsIntegration:
    """幽靈版本偵測整合測試：三案例合併驗證"""

    def test_no_false_positive_for_known_versions(self, tmp_path):
        (tmp_path / "docs" / "work-logs" / "v0" / "v0.32" / "v0.32.1").mkdir(parents=True)
        versions = {"0.32.1": "completed"}

        ghosts = guard_hook.detect_ghost_versions(versions, tmp_path)
        assert "0.32.1" not in ghosts


class TestGetLatestGitTagVersionMergedFilter:
    """get_latest_git_tag_version 只認 HEAD 可達 tags（0.37.0-W9-005）

    背景：sync-pull 若未加 --no-tags，框架 repo（tarrragon/claude.git）的
    v2.x 系列版本 tags 會混入本地，其指向的 commit 不在本 APP repo 的 HEAD
    歷史內。--merged HEAD 過濾天然排除這類 tag，不需維護版本範圍白名單。
    """

    def _init_repo_with_commit(self, repo_dir: Path) -> None:
        import subprocess

        subprocess.run(["git", "init", "-q", str(repo_dir)], check=True)
        subprocess.run(
            ["git", "-C", str(repo_dir), "config", "user.email", "test@test.com"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_dir), "config", "user.name", "test"], check=True
        )
        (repo_dir / "README.md").write_text("x", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo_dir), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(repo_dir), "commit", "-q", "-m", "init"], check=True
        )

    def test_recognizes_head_reachable_project_tag(self, tmp_path):
        """本專案 tag（HEAD 可達）應被認得"""
        import subprocess

        self._init_repo_with_commit(tmp_path)
        subprocess.run(["git", "-C", str(tmp_path), "tag", "v0.37.0"], check=True)

        version = guard_hook.get_latest_git_tag_version(tmp_path, FakeLogger())
        assert version == "0.37.0"

    def test_ignores_unreachable_framework_tag(self, tmp_path):
        """框架 tag（指向 HEAD 歷史外的 commit）應被忽略，不視為最新"""
        import subprocess

        self._init_repo_with_commit(tmp_path)
        subprocess.run(["git", "-C", str(tmp_path), "tag", "v0.37.0"], check=True)

        # 建立一個不可達的 commit 物件（不接在目前分支歷史上），模擬混入的框架 tag
        tree_sha = subprocess.run(
            ["git", "-C", str(tmp_path), "rev-parse", "HEAD^{tree}"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        orphan_sha = subprocess.run(
            ["git", "-C", str(tmp_path), "commit-tree", tree_sha, "-m", "orphan"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        subprocess.run(
            ["git", "-C", str(tmp_path), "tag", "v2.12.0", orphan_sha], check=True
        )

        version = guard_hook.get_latest_git_tag_version(tmp_path, FakeLogger())
        assert version == "0.37.0"
        assert version != "2.12.0"

    def test_no_tags_returns_none(self, tmp_path):
        """無任何 tag 時回傳 None"""
        self._init_repo_with_commit(tmp_path)

        version = guard_hook.get_latest_git_tag_version(tmp_path, FakeLogger())
        assert version is None


class TestParseProposalsRealFormat:
    """parse_proposals 對真實 docs/proposals-tracking.yaml 的 `- id: PROP-XXX`
    清單格式須正確解析（0.38.0-W1-002 修復：舊 PROPOSAL_ID_PATTERN 只認
    `  PROP-001:` 這種鍵值格式，與實際檔案結構不符，parse_proposals 對真實
    檔案一律回傳空字典）。
    """

    def _write_proposals(self, path: Path, body: str) -> None:
        path.write_text(body, encoding="utf-8")

    def test_confirmed_proposal_with_target_version_parsed(self, tmp_path):
        proposals_path = tmp_path / "proposals-tracking.yaml"
        self._write_proposals(
            proposals_path,
            """proposals:
  - id: PROP-016
    title: "元件庫統一化"
    status: confirmed
    priority: P1
    confirmed_at: "2026-07-08"
    target_version: v0.38.0

  - id: PROP-017
    title: "回饋類元件統一化"
    status: draft
    priority: P2

usecases:
  - id: UC-01
    title: "匯入書庫資料"
    status: approved
""",
        )
        proposals = guard_hook.parse_proposals(proposals_path, FakeLogger())
        assert proposals["PROP-016"] == {"status": "confirmed", "target_version": "0.38.0"}
        assert proposals["PROP-017"] == {"status": "draft", "target_version": None}
        assert "UC-01" not in proposals

    def test_last_entry_bounded_by_usecases_section_not_bleeding(self, tmp_path):
        """迴歸測試：最後一個提案（無 target_version）不得吞噬 usecases 區塊內容"""
        proposals_path = tmp_path / "proposals-tracking.yaml"
        self._write_proposals(
            proposals_path,
            """proposals:
  - id: PROP-007
    title: "跨專案 Spec 對齊"
    status: confirmed
    priority: P1
    confirmed_at: "2026-06-02"

usecases:
  - id: UC-01
    title: "匯入書庫資料"
    status: approved
    implementation_status: implemented
""",
        )
        proposals = guard_hook.parse_proposals(proposals_path, FakeLogger())
        assert proposals["PROP-007"] == {"status": "confirmed", "target_version": None}


class TestDetectUnregisteredConfirmedProposals:
    """漂移 7：confirmed 提案 target_version 未在 todolist.yaml 註冊（0.38.0-W1-002）"""

    def test_confirmed_unregistered_target_warns(self):
        proposals = {
            "PROP-016": {"status": "confirmed", "target_version": "0.38.0"},
        }
        versions: dict[str, str] = {}

        result = guard_hook.detect_unregistered_confirmed_proposals(proposals, versions)
        assert len(result) == 1
        assert "PROP-016" in result[0]
        assert "0.38.0" in result[0]

    def test_confirmed_registered_target_no_warning(self):
        """PROP-016 回歸案例：confirmed + target 已在 todolist 註冊（任何 status）→ 不警告"""
        proposals = {
            "PROP-016": {"status": "confirmed", "target_version": "0.38.0"},
        }
        versions = {"0.38.0": "active"}

        result = guard_hook.detect_unregistered_confirmed_proposals(proposals, versions)
        assert result == []

    def test_registered_regardless_of_status_counts(self):
        """已註冊即不誤報，不論 todolist 該版本 status 為何（planned/active/completed）"""
        proposals = {
            "PROP-A": {"status": "confirmed", "target_version": "0.40.0"},
        }
        versions = {"0.40.0": "planned"}

        result = guard_hook.detect_unregistered_confirmed_proposals(proposals, versions)
        assert result == []

    def test_non_confirmed_status_not_checked(self):
        """非 confirmed（draft）提案即使 target_version 未註冊也不誤報"""
        proposals = {
            "PROP-017": {"status": "draft", "target_version": "0.39.0"},
        }
        versions: dict[str, str] = {}

        result = guard_hook.detect_unregistered_confirmed_proposals(proposals, versions)
        assert result == []

    def test_null_target_version_not_checked(self):
        """target_version 為 None（未設定）不誤報"""
        proposals = {
            "PROP-007": {"status": "confirmed", "target_version": None},
        }
        versions: dict[str, str] = {}

        result = guard_hook.detect_unregistered_confirmed_proposals(proposals, versions)
        assert result == []


class TestDetectMissingMainWorklog:
    """漂移 8：版本目錄存在但缺 main worklog（0.38.0-W1-005）

    僅查 status 為 active/planned 的版本，避免歷史存量（completed）版本
    目錄大量缺 main.md 造成每 session 重複噪音（W9-003 教訓）。v0.37.0 為
    本 ticket 動機案例，下列前兩測試即回歸驗證（補 main 前警告、補後不警告）。
    """

    def test_active_version_dir_missing_main_warns(self, tmp_path):
        """v0.37.0 回歸案例（補前）：目錄存在但缺 main.md → 警告"""
        version_dir = tmp_path / "docs" / "work-logs" / "v0" / "v0.37" / "v0.37.0"
        (version_dir / "tickets").mkdir(parents=True)
        versions = {"0.37.0": "active"}

        result = guard_hook.detect_missing_main_worklog(versions, tmp_path)
        assert result == ["0.37.0"]

    def test_active_version_dir_with_main_no_warning(self, tmp_path):
        """v0.37.0 回歸案例（補後）：main.md 存在 → 不警告"""
        version_dir = tmp_path / "docs" / "work-logs" / "v0" / "v0.37" / "v0.37.0"
        version_dir.mkdir(parents=True)
        (version_dir / "v0.37.0-main.md").write_text("x", encoding="utf-8")
        versions = {"0.37.0": "active"}

        result = guard_hook.detect_missing_main_worklog(versions, tmp_path)
        assert result == []

    def test_completed_version_missing_main_not_checked(self, tmp_path):
        """歷史存量豁免：completed 版本缺 main.md 不警告（避免噪音）"""
        version_dir = tmp_path / "docs" / "work-logs" / "v0" / "v0.21" / "v0.21.0"
        version_dir.mkdir(parents=True)
        versions = {"0.21.0": "completed"}

        result = guard_hook.detect_missing_main_worklog(versions, tmp_path)
        assert result == []

    def test_version_dir_not_exist_not_checked(self, tmp_path):
        """版本目錄尚未建立（尚未開工）不誤報缺 main worklog"""
        versions = {"0.99.0": "planned"}

        result = guard_hook.detect_missing_main_worklog(versions, tmp_path)
        assert result == []

    def test_planned_version_dir_missing_main_warns(self, tmp_path):
        version_dir = tmp_path / "docs" / "work-logs" / "v1" / "v1.0" / "v1.0.0"
        version_dir.mkdir(parents=True)
        versions = {"1.0.0": "planned"}

        result = guard_hook.detect_missing_main_worklog(versions, tmp_path)
        assert result == ["1.0.0"]

    def test_tickets_subdir_does_not_satisfy_main_worklog(self, tmp_path):
        """tickets/ 子目錄存在不誤判為已有 main worklog"""
        version_dir = tmp_path / "docs" / "work-logs" / "v0" / "v0.38" / "v0.38.0"
        (version_dir / "tickets").mkdir(parents=True)
        (version_dir / "tickets" / "0.38.0-W1-001.md").write_text("x", encoding="utf-8")
        versions = {"0.38.0": "active"}

        result = guard_hook.detect_missing_main_worklog(versions, tmp_path)
        assert result == ["0.38.0"]
