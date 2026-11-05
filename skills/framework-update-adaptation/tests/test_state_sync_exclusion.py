"""framework-update-adaptation 狀態檔的 sync 排除測試。

狀態檔記錄「本專案上次適應到哪一版」，每個 consumer 各一份。push 與 pull 兩端的
三方合併、full overlay、content hash 都經 should_exclude 過濾，所以這裡驗
should_exclude 的判定即可涵蓋兩個方向（兩端呼叫點的一致性由 scripts/tests 的
project-integration 保護測試負責）。
"""
import sys
from pathlib import Path

CLAUDE_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CLAUDE_DIR))

from lib.sync_exclude_manifest import should_exclude  # noqa: E402

SKILL_DIR = Path(__file__).resolve().parents[1]
STATE_REL = Path("project-integration/framework-update-adaptation/last-adapted.md")


def state_path_from_skill() -> Path:
    """從 SKILL.md 正文取狀態檔路徑，避免測試與文件各寫一份而漂移。"""
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    marker = "`.claude/project-integration/framework-update-adaptation/"
    start = text.index(marker) + len("`.claude/")
    end = text.index("`", start)
    return Path(text[start:end])


def test_skill_documents_the_tested_state_path():
    assert state_path_from_skill() == STATE_REL


def test_state_file_is_excluded_from_sync():
    assert should_exclude(STATE_REL)


def test_skill_files_are_not_excluded():
    # 對照輸入：skill 本體要隨 sync 擴散，排除規則不得連它一起排掉
    assert not should_exclude(Path("skills/framework-update-adaptation/SKILL.md"))
    assert not should_exclude(Path("skills/framework-update-adaptation/CHANGELOG.md"))


def test_state_inside_skill_dir_would_not_be_excluded():
    # 對照輸入：狀態檔若放進 skill 目錄就會隨 sync 擴散，這正是 SKILL.md 禁止的放法
    assert not should_exclude(Path("skills/framework-update-adaptation/state/last-adapted.md"))
