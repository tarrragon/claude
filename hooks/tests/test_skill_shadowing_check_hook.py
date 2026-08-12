"""skill-shadowing-check-hook 測試（現涵蓋 personal 目錄非空政策檢查）

檔名採 `hooks-test-gate-hook.py` 的命名慣例（`test_<hook stem>.py`），使本 hook
納入該 gate 的保護範圍；後續針對同名碰撞比對的測試亦追加於本檔，不另開新檔。

驗證 9 情境：
1. personal 非空 → 輸出 WARNING 並列出全部 personal skill 名稱（含與 project 不同名者）
2. WARNING 內容含約束依據與正規替代路徑（canonical + sync-pull），非僅陳述現象
3. personal 為空 → 維持 suppressOutput，同名碰撞比對行為零回歸
4. personal 根目錄不存在（全新安裝）→ 同樣視為空，不輸出政策 WARNING
5. 政策 WARNING 與同名分歧 WARNING 可並存，且政策段落排在最前
6. personal 子目錄讀取失敗時仍計入名稱清單，且與 skipped 段並存（刻意雙列）
7. 不含入口檔的 personal 子目錄不列入（不會被載入為 skill，無遮蔽風險）
8. personal 路徑被檔案佔位 → 輸出警示，不與「目錄不存在」共用靜默路徑
9. personal 根目錄不可讀 → 降級為 skipped，不讓例外穿到 run_hook_safely

另驗證 main() 在 personal 非空時仍回傳 0（不阻擋 session 啟動）。

Ticket：0.2.1-W3-406
"""

import importlib.util
import json
import os
import stat
from pathlib import Path
from unittest.mock import MagicMock, patch


HOOK_PATH = Path(__file__).parent.parent / "skill-shadowing-check-hook.py"


def load_hook_module():
    spec = importlib.util.spec_from_file_location(
        "skill_shadowing_check_hook", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_skill(root: Path, name: str, body: str = "**Version**: 1.0.0\n") -> Path:
    """在 root 下建立一個含入口檔的 skill 目錄。"""
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(body, encoding="utf-8")
    return skill_dir


def _roots(tmp_path: Path):
    project_root = tmp_path / "project" / ".claude" / "skills"
    personal_root = tmp_path / "home" / ".claude" / "skills"
    project_root.mkdir(parents=True)
    personal_root.mkdir(parents=True)
    return project_root, personal_root


def _scan(hook, project_root: Path, personal_root: Path):
    return hook.scan_skills(project_root, personal_root, MagicMock())


def _context_text(output: dict) -> str:
    return output["hookSpecificOutput"]["additionalContext"]


# ---------------------------------------------------------------------------
# 1. personal 非空 → 列出全部 personal skill 名稱（不限同名交集）
# ---------------------------------------------------------------------------
def test_personal_non_empty_lists_all_skill_names(tmp_path):
    hook = load_hook_module()
    project_root, personal_root = _roots(tmp_path)
    _make_skill(project_root, "shared-skill")
    _make_skill(personal_root, "shared-skill")
    _make_skill(personal_root, "personal-only-skill")

    result = _scan(hook, project_root, personal_root)

    assert result.personal_skill_names == ["personal-only-skill", "shared-skill"]

    output = hook.build_hook_output(result, MagicMock())
    context = _context_text(output)
    # 整段逐行比對而非子字串存在性：一次鎖住計數、逐行格式與名稱排序。
    # 子字串斷言在「名稱只出現在其他區段而政策段消失」時仍會通過。
    assert (
        "[WARNING][SkillShadowCheck] personal skills 目錄非空（2 個）:\n"
        "  - personal-only-skill\n"
        "  - shared-skill\n"
    ) in context + "\n"


# ---------------------------------------------------------------------------
# 2. WARNING 內容指出約束依據與正規替代路徑
# ---------------------------------------------------------------------------
def test_warning_states_constraint_and_canonical_path(tmp_path):
    """走完整 scan -> build_hook_output 路徑，不直呼私有的文字組裝函式。

    直呼私有函式會把「文字由哪個函式組出」鎖成契約，內聯或改名時行為未變
    卻紅燈；經公開路徑取 additionalContext 驗證的則是使用者實際看到的輸出。
    """
    hook = load_hook_module()
    project_root, personal_root = _roots(tmp_path)
    _make_skill(personal_root, "some-skill")

    result = _scan(hook, project_root, personal_root)
    text = _context_text(hook.build_hook_output(result, MagicMock()))

    assert "全域 skills 目錄應維持空置" in text
    assert "canonical" in text
    assert "sync-pull" in text
    # 警告不阻擋，保留使用者覆蓋權
    assert "警告不阻擋" in text


# ---------------------------------------------------------------------------
# 3. personal 為空 → 維持現行靜默行為（零回歸）
# ---------------------------------------------------------------------------
def test_empty_personal_stays_silent(tmp_path):
    hook = load_hook_module()
    project_root, personal_root = _roots(tmp_path)
    _make_skill(project_root, "shared-skill")

    result = _scan(hook, project_root, personal_root)

    assert result.personal_skill_names == []
    assert result.divergences == []
    assert hook.build_hook_output(result, MagicMock()) == {"suppressOutput": True}


def test_missing_personal_root_stays_silent(tmp_path):
    """personal 根目錄不存在（全新安裝）同樣視為空，不輸出政策 WARNING。"""
    hook = load_hook_module()
    project_root, personal_root = _roots(tmp_path)
    _make_skill(project_root, "shared-skill")

    result = _scan(hook, project_root, tmp_path / "home" / "nonexistent")

    assert result.personal_skill_names == []
    assert hook.build_hook_output(result, MagicMock()) == {"suppressOutput": True}


# ---------------------------------------------------------------------------
# 4. 政策 WARNING 與同名分歧 WARNING 並存，政策段落在最前
# ---------------------------------------------------------------------------
def test_policy_and_divergence_coexist(tmp_path):
    hook = load_hook_module()
    project_root, personal_root = _roots(tmp_path)
    _make_skill(project_root, "shared-skill", "**Version**: 2.0.0\nproject\n")
    _make_skill(personal_root, "shared-skill", "**Version**: 1.0.0\npersonal\n")

    result = _scan(hook, project_root, personal_root)
    assert len(result.divergences) == 1

    context = _context_text(hook.build_hook_output(result, MagicMock()))
    policy_pos = context.index("personal skills 目錄非空")
    divergence_pos = context.index("個同名 skill 內容分歧")
    assert policy_pos < divergence_pos


# ---------------------------------------------------------------------------
# 6. personal 子目錄讀取失敗仍計入名稱清單，且與 skipped 段並存
# ---------------------------------------------------------------------------
def test_unreadable_personal_skill_still_counted(tmp_path):
    """以真實權限造成 OSError，不 patch 內部呼叫關係。

    patch `_find_entry_file` 會把「`_list_skills` 呼叫它且不吞其 OSError」
    這條內部佈線鎖成契約；改用 chmod 驗證的是真實的錯誤路徑。
    """
    hook = load_hook_module()
    project_root, personal_root = _roots(tmp_path)
    broken = _make_skill(personal_root, "broken-skill")

    os.chmod(broken, 0o000)
    try:
        result = _scan(hook, project_root, personal_root)
    finally:
        os.chmod(broken, stat.S_IRWXU)

    assert result.personal_skill_names == ["broken-skill"]
    context = _context_text(hook.build_hook_output(result, MagicMock()))
    assert "broken-skill" in context
    # 刻意雙列：政策段不因讀取失敗而漏列，skipped 段仍獨立揭露無法比對。
    # 此斷言把「同一名稱出現在兩個區段」寫成契約，避免被誤讀為重複輸出的 bug。
    assert "無法比對" in context


# ---------------------------------------------------------------------------
# 7. 不含入口檔的 personal 子目錄不列入
# ---------------------------------------------------------------------------
def test_directory_without_entry_file_excluded(tmp_path):
    hook = load_hook_module()
    project_root, personal_root = _roots(tmp_path)
    (personal_root / "not-a-skill").mkdir()
    (personal_root / "not-a-skill" / "notes.txt").write_text("x", encoding="utf-8")

    result = _scan(hook, project_root, personal_root)

    assert result.personal_skill_names == []
    assert hook.build_hook_output(result, MagicMock()) == {"suppressOutput": True}


# ---------------------------------------------------------------------------
# 8. personal 路徑被檔案佔位 → 輸出警示，不與「目錄不存在」共用靜默路徑
# ---------------------------------------------------------------------------
def test_personal_root_is_file_warns(tmp_path, capsys):
    hook = load_hook_module()
    project_root, personal_root = _roots(tmp_path)
    file_root = tmp_path / "home" / "skills-as-file"
    file_root.write_text("not a directory", encoding="utf-8")

    result = _scan(hook, project_root, file_root)

    assert result.personal_skill_names == []
    assert "存在但不是目錄" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# 9. personal 根目錄不可讀 → 降級為 skipped，不讓例外穿到 run_hook_safely
# ---------------------------------------------------------------------------
def test_unreadable_personal_root_degrades_to_skipped(tmp_path):
    hook = load_hook_module()
    project_root, personal_root = _roots(tmp_path)
    _make_skill(personal_root, "some-skill")

    os.chmod(personal_root, 0o000)
    try:
        result = _scan(hook, project_root, personal_root)
    finally:
        os.chmod(personal_root, stat.S_IRWXU)

    # 例外未穿出：拿得到 ScanResult 而非 OSError
    assert result.skipped, "根目錄讀取失敗必須計入 skipped，不可靜默視為空"
    assert "根目錄讀取失敗" in "".join(result.skipped)
    context = _context_text(hook.build_hook_output(result, MagicMock()))
    assert "無法比對" in context


# ---------------------------------------------------------------------------
# main()：personal 非空時仍 exit 0，輸出為合法 JSON
# ---------------------------------------------------------------------------
def test_main_returns_zero_with_non_empty_personal(tmp_path, capsys, monkeypatch):
    """以 HOME 環境變數導向假 home，不 patch `Path.home` 類別方法。

    `hook.Path` 就是 `pathlib.Path` 本身，`patch.object(hook.Path, "home", ...)`
    會把全域 `Path.home` 換成 mock，作用域涵蓋同 process 內所有模組——目前綠燈
    靠的是 main() 恰好沒有其他呼叫者，屬巧合而非隔離。`Path.home()` 走
    `expanduser("~")`，POSIX 上直接讀 HOME，改設環境變數即可精準導向。
    """
    hook = load_hook_module()
    project_root, personal_root = _roots(tmp_path)
    _make_skill(personal_root, "personal-only-skill")

    monkeypatch.setenv("HOME", str(personal_root.parent.parent))
    with patch.object(hook, "PROJECT_ROOT", project_root.parent.parent):
        exit_code = hook.main()

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert "personal-only-skill" in _context_text(output)
