"""迴歸測試：sync-claude-push.py 的 skill 庫版本 drift 檢查已移除（0.2.1-W3-134）。

背景：0.3.5-W1-001 建立 check_skill_repo_version_drift，以版本字串比對本地
skill 與 skill 庫 versions.json。0.2.1-W3-131 將 versions.json 改為巢狀
{name: {hash, version}} 後，該函式仍以字串比對 dict，永遠不相等，會將全部
skill 誤判為漂移，且外層 except Exception 攔不下（比較本身不拋例外）。

決策：不修補比對邏輯，改為移除。正確的內容雜湊比對已存在於
skill_sync/cli.py::_classify_sync_status，涵蓋新格式（hash 比對）與舊格式
（無 hash 欄位時 skipped_no_hash）兩案例（見
.claude/skills/skill-sync/tests/test_cli.py::
test_classify_sync_status_up_to_date_when_hash_matches 與
test_classify_sync_status_skips_remote_without_hash_field）。push.py 不再
重複維護第二套比對邏輯，避免兩個獨立實作再次隨 schema 變更各自漂移。

本檔鎖定移除決策本身：函式、死常數、未用 import 皆已清除；保留功能
（本地 skill 版本 before/after diff）不受影響；且移除後仍給予使用者
可執行的下一步指引。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-push.py"
_spec = importlib.util.spec_from_file_location("sync_claude_push", _SCRIPT)
assert _spec and _spec.loader
sync_mod = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_push"] = sync_mod
_spec.loader.exec_module(sync_mod)  # type: ignore[union-attr]


def test_check_skill_repo_version_drift_removed():
    """比對 remote versions.json 的舊函式已不存在，不再有字串 vs dict 誤判路徑。"""
    assert not hasattr(sync_mod, "check_skill_repo_version_drift")


def test_skill_repo_url_dead_constant_removed():
    """SKILL_REPO_URL 僅供已移除函式使用，隨函式一併清除，避免死程式碼殘留。"""
    assert not hasattr(sync_mod, "SKILL_REPO_URL")


def test_source_no_longer_imports_urllib_for_removed_check():
    """urllib.request 僅供已移除的 HTTP GET 使用，一併移除避免未用 import。"""
    source = _SCRIPT.read_text(encoding="utf-8")
    assert "import urllib" not in source


def test_extract_skill_versions_unaffected_by_removal(tmp_path):
    """保留功能：本地 SKILL.md 版本擷取（供 before/after diff 摘要）不受移除影響。

    此函式讀本地檔案，從未讀取 remote versions.json，與被移除的漂移檢查
    是獨立路徑，schema 變更不影響它。
    """
    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: demo-skill\n---\n\n**Version**: 1.2.3\n",
        encoding="utf-8",
    )

    versions = sync_mod.extract_skill_versions(skills_dir)

    assert versions == {"demo-skill": "1.2.3"}


def test_format_skill_version_diff_unaffected_by_removal():
    """保留功能：before/after 版本摘要邏輯不受移除影響（純本地字串比對，非漂移判定）。"""
    before = {"demo-skill": "1.0.0"}
    after = {"demo-skill": "1.1.0", "new-skill": "0.1.0"}

    diff = sync_mod.format_skill_version_diff(before, after)

    assert diff is not None
    assert "demo-skill 1.0.0 -> 1.1.0" in diff
    assert "new-skill (0.1.0)" in diff
