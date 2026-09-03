"""topic_registry 模組的單元測試（主題中央清單 append-only 讀寫層）。

隔離依賴 `.claude/skills/ticket/conftest.py` 的 autouse fixture
`_isolate_project_root`：每個 test 前自動清 `get_project_root()` 快取並
注入獨立 tmp 目錄（含已建立的 `docs/work-logs/`），故本檔測試互不污染，
亦不觸及真實 repo 的 `docs/work-logs/topics-registry.txt`。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from ticket_system.lib import topic_registry
from ticket_system.lib.paths import (
    get_project_root,
    reset_project_root_cache,
    reset_ticket_state_root_cache,
)


def _registry_file():
    return get_project_root() / topic_registry.TOPICS_REGISTRY_RELATIVE_PATH


def _run_git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    )


def _init_git_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    _run_git(root, "init", "-q")
    _run_git(root, "checkout", "-q", "-b", "main")
    _run_git(root, "config", "user.email", "test@example.com")
    _run_git(root, "config", "user.name", "Test")
    (root / "README.md").write_text("init\n", encoding="utf-8")
    _run_git(root, "add", "README.md")
    _run_git(root, "commit", "-q", "-m", "init")


@pytest.fixture
def linked_worktree(tmp_path, monkeypatch):
    """建立真實 main repo + linked worktree，cwd 切至 worktree。

    關閉 autouse `_isolate_project_root` 注入的
    `TICKET_SYSTEM_TEST_ISOLATION` 逃生艙與 `CLAUDE_PROJECT_DIR`（手法同
    `conftest.py` 的 `real_repo_root` fixture：後設定的 monkeypatch 勝出），
    使 `get_project_root()` / `get_ticket_state_root()` 走真實 git 解析鏈，
    真實重現 worktree 場景下兩者的根目錄分歧（同 0.2.1-W4-025
    `test_topic_assignments.py::linked_worktree`，本檔另立一份避免跨測試
    檔共用 fixture 造成的隱性耦合）。
    """
    main_root = tmp_path / "main"
    wt_root = tmp_path / "wt"
    _init_git_repo(main_root)
    _run_git(main_root, "worktree", "add", "-q", "-b", "feat/test", str(wt_root), "HEAD")

    monkeypatch.delenv("TICKET_SYSTEM_TEST_ISOLATION", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    reset_project_root_cache()
    reset_ticket_state_root_cache()
    monkeypatch.chdir(wt_root)

    yield main_root, wt_root

    reset_project_root_cache()
    reset_ticket_state_root_cache()


class TestAppendTopicWorktreeRootUnification:
    """0.2.1-W4-029：linked worktree cwd 下寫入應落在主倉庫，非 worktree 副本。"""

    def test_append_topic_in_linked_worktree_writes_to_main_repo(
        self, linked_worktree
    ):
        main_root, wt_root = linked_worktree

        result = topic_registry.append_topic("主題 A")

        main_file = main_root / topic_registry.TOPICS_REGISTRY_RELATIVE_PATH
        wt_file = wt_root / topic_registry.TOPICS_REGISTRY_RELATIVE_PATH

        assert result is True
        assert main_file.exists()
        assert "主題 A" in main_file.read_text(encoding="utf-8")
        assert not wt_file.exists()


class TestListTopicsMissingFile:
    def test_returns_empty_list_when_file_absent(self):
        assert not _registry_file().exists()
        assert topic_registry.list_topics() == []

    def test_does_not_raise_when_file_absent(self):
        # 缺檔屬正常初始狀態，不應拋出例外（acceptance 第 2 條）。
        try:
            topic_registry.list_topics()
        except Exception as exc:  # noqa: BLE001 - 測試明確要求「不拋錯」
            raise AssertionError(f"list_topics() 在缺檔時不應拋出例外: {exc}")


class TestAppendTopicBasic:
    def test_append_creates_file_when_missing(self):
        assert topic_registry.append_topic("記帳流程重構") is True
        assert _registry_file().exists()
        assert topic_registry.list_topics() == ["記帳流程重構"]

    def test_append_multiple_distinct_topics(self):
        topic_registry.append_topic("主題 A")
        topic_registry.append_topic("主題 B")
        assert topic_registry.list_topics() == ["主題 A", "主題 B"]

    def test_append_returns_false_for_exact_duplicate(self):
        topic_registry.append_topic("主題 A")
        result = topic_registry.append_topic("主題 A")
        assert result is False
        assert topic_registry.list_topics() == ["主題 A"]

    def test_append_rejects_blank_name(self):
        try:
            topic_registry.append_topic("   ")
        except ValueError:
            pass
        else:
            raise AssertionError("append_topic('   ') 應拋出 ValueError")


class TestAppendOnlySemantics:
    """acceptance 第 3 條：既有條目在追加後逐字不變。"""

    def test_existing_content_byte_identical_after_append(self):
        topic_registry.append_topic("主題 A")
        topic_registry.append_topic("主題 B")
        original_content = _registry_file().read_text(encoding="utf-8")

        topic_registry.append_topic("主題 C")

        new_content = _registry_file().read_text(encoding="utf-8")
        assert new_content.startswith(original_content), (
            "追加新主題後，既有內容必須逐字保留於檔案前綴，"
            f"原內容={original_content!r}，新內容={new_content!r}"
        )
        assert new_content == original_content + "主題 C\n"

    def test_duplicate_append_leaves_file_byte_identical(self):
        topic_registry.append_topic("主題 A")
        original_content = _registry_file().read_text(encoding="utf-8")

        result = topic_registry.append_topic("主題 A")

        assert result is False
        assert _registry_file().read_text(encoding="utf-8") == original_content


class TestNormalization:
    """正規化規則：大小寫、空白差異視為同一主題；不同語意仍為不同主題。"""

    def test_case_insensitive_duplicate_ascii(self):
        topic_registry.append_topic("Refactor Auth")
        result = topic_registry.append_topic("refactor auth")
        assert result is False
        assert topic_registry.list_topics() == ["Refactor Auth"]

    def test_surrounding_whitespace_duplicate(self):
        topic_registry.append_topic("主題化排程")
        result = topic_registry.append_topic("  主題化排程  ")
        assert result is False
        assert topic_registry.list_topics() == ["主題化排程"]

    def test_internal_whitespace_collapse_duplicate(self):
        topic_registry.append_topic("Refactor Auth")
        result = topic_registry.append_topic("Refactor   Auth")
        assert result is False

    def test_distinct_topics_not_merged(self):
        topic_registry.append_topic("主題 A")
        result = topic_registry.append_topic("主題 B")
        assert result is True
        assert topic_registry.list_topics() == ["主題 A", "主題 B"]

    def test_normalize_topic_name_nfkc(self):
        # 全形英數與半形英數正規化後應視為相同 key。
        fullwidth = "Ａ"  # U+FF21 FULLWIDTH LATIN CAPITAL LETTER A
        halfwidth = "A"
        assert topic_registry.normalize_topic_name(
            fullwidth
        ) == topic_registry.normalize_topic_name(halfwidth)


class TestAppendTopicNoTrailingNewline:
    """0.2.1-W3-795.1.1：既有清單檔外部手動編輯致無尾換行時的黏合修復。"""

    def test_appends_without_gluing_existing_last_entry(self):
        registry_path = _registry_file()
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text("主題 A\n主題 B", encoding="utf-8")  # 無尾換行

        topic_registry.append_topic("主題 C")

        assert topic_registry.list_topics() == ["主題 A", "主題 B", "主題 C"]

    def test_new_entry_becomes_independent_item(self):
        registry_path = _registry_file()
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text("主題 A\n主題 B", encoding="utf-8")

        topic_registry.append_topic("主題 C")

        topics = topic_registry.list_topics()
        assert "主題 C" in topics
        assert "主題 B主題 C" not in topics

    def test_repair_is_still_pure_append_with_startswith_prefix(self):
        registry_path = _registry_file()
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        original_content = "主題 A\n主題 B"
        registry_path.write_text(original_content, encoding="utf-8")

        topic_registry.append_topic("主題 C")

        new_content = registry_path.read_text(encoding="utf-8")
        assert new_content.startswith(original_content), (
            "補行仍須是純 append：新內容須以原內容為前綴，"
            f"原內容={original_content!r}，新內容={new_content!r}"
        )
        assert new_content == original_content + "\n主題 C\n"

    def test_missing_file_not_misjudged_as_needing_newline_repair(self):
        # 缺檔情形：append_topic 應直接建檔並寫入，不因「補換行」邏輯
        # 誤判（缺檔沒有末位元組可讀）。
        assert not _registry_file().exists()
        topic_registry.append_topic("主題 A")
        assert _registry_file().read_text(encoding="utf-8") == "主題 A\n"

    def test_empty_file_not_misjudged_as_needing_newline_repair(self):
        # 0 bytes 空檔：不應被誤判為「需補換行」（空檔案沒有末位元組）。
        registry_path = _registry_file()
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text("", encoding="utf-8")

        topic_registry.append_topic("主題 A")

        assert registry_path.read_text(encoding="utf-8") == "主題 A\n"

    def test_existing_file_with_trailing_newline_unaffected(self):
        # 既有正常結尾（有尾換行）的檔案不應被多插入換行。
        registry_path = _registry_file()
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text("主題 A\n", encoding="utf-8")

        topic_registry.append_topic("主題 B")

        assert registry_path.read_text(encoding="utf-8") == "主題 A\n主題 B\n"


class TestListTopicsDedup:
    def test_list_topics_reads_manually_written_duplicate_lines(self):
        # 模擬清單檔被外部工具（如回填腳本）寫入含重複行的內容，
        # list_topics 仍須依正規化 key 去重且保留首次出現形式。
        registry_path = _registry_file()
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text(
            "主題 A\n主題 A\n  主題 A  \n主題 B\n\n", encoding="utf-8"
        )
        assert topic_registry.list_topics() == ["主題 A", "主題 B"]
