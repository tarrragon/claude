"""
UC Reference Validation Hook 測試

驗證 PreToolUse UC 引用驗證 hook 的核心行為：
- 對程式碼檔新增內容偵測未定義 UC-XX token，輸出 WARNING（含合法清單提示），exit 0（WARNING-only）
- 五類路徑豁免規則生效（UC-Pattern / 歷史文件 / spec 自身 / fixtures / 規範文件；規範第 6 類「.claude 框架程式碼」
  僅 CLI 全量掃描以目錄排除方式豁免，本 hook 的 is_exempt_path 不涵蓋，見 uc-numbering-convention.md 第 5 節）
- 白名單動態解析 spec 標題行，無硬編碼清單
- 非程式碼檔跳過；uc_registry 不可用時 fail-open 並輸出可見日誌
"""

import importlib.util
import io
import json
import sys
from pathlib import Path

# 動態載入 hook module（檔名含連字號，無法直接 import）
_HOOKS_DIR = Path(__file__).parent.parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

_spec = importlib.util.spec_from_file_location(
    "uc_reference_validation_hook",
    _HOOKS_DIR / "uc-reference-validation-hook.py",
)
_hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hook)

main = _hook.main


# ----------------------------------------------------------------------------
# Fixture：建立一個含 2 個合法 UC 的假專案根目錄
# ----------------------------------------------------------------------------

def _make_fake_project(tmp_path: Path) -> Path:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True)
    spec_content = (
        "# 用例\n\n"
        "## UC-01: 匯入書庫資料\n\n說明。\n\n"
        "## UC-05: 雙模式書庫展示系統\n\n說明。\n"
    )
    (docs_dir / "app-use-cases.md").write_text(spec_content, encoding="utf-8")
    return tmp_path


def _run_hook(
    monkeypatch,
    tmp_path: Path,
    tool_input: dict,
    tool_name: str = "Edit",
) -> int:
    """以 monkeypatch 模擬 stdin 輸入 + CLAUDE_PROJECT_DIR 並執行 main()。"""
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    payload = {"tool_name": tool_name, "tool_input": tool_input}
    stdin_buffer = io.StringIO(json.dumps(payload))
    monkeypatch.setattr(sys, "stdin", stdin_buffer)
    return main()


# ----------------------------------------------------------------------------
# 案例 1：合法 token 靜默通過
# ----------------------------------------------------------------------------

def test_valid_uc_token_passes_silently(monkeypatch, capsys, tmp_path):
    project_root = _make_fake_project(tmp_path)
    exit_code = _run_hook(
        monkeypatch,
        project_root,
        {
            "file_path": str(project_root / "lib" / "book_service.dart"),
            "old_string": "x",
            "new_string": "// 實作 UC-01 匯入邏輯",
        },
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    assert captured.err == ""


# ----------------------------------------------------------------------------
# 案例 2：未定義 token 觸發 WARNING（exit 0，不阻擋）
# ----------------------------------------------------------------------------

def test_undefined_uc_token_emits_warning_but_passes(monkeypatch, capsys, tmp_path):
    project_root = _make_fake_project(tmp_path)
    exit_code = _run_hook(
        monkeypatch,
        project_root,
        {
            "file_path": str(project_root / "lib" / "book_service.dart"),
            "old_string": "x",
            "new_string": "// 對應 UC-99 尚未定義的用例",
        },
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "UC-99" in captured.err
    assert "uc-reference-validation" in captured.err
    # 合法清單提示必須出現
    assert "UC-01" in captured.err
    assert "UC-05" in captured.err


# ----------------------------------------------------------------------------
# 案例 3：五類豁免規則
# ----------------------------------------------------------------------------

def test_exempt_uc_pattern_token_no_warning(monkeypatch, capsys, tmp_path):
    """UC-Pattern 設計模式標註（大寫字母開頭）豁免。"""
    project_root = _make_fake_project(tmp_path)
    exit_code = _run_hook(
        monkeypatch,
        project_root,
        {
            "file_path": str(project_root / "lib" / "widget.dart"),
            "content": "// 採用 UC-Singleton 模式",
        },
        tool_name="Write",
    )
    assert exit_code == 0
    assert capsys.readouterr().err == ""


def test_exempt_worklog_path_no_warning(monkeypatch, capsys, tmp_path):
    """歷史 ticket / 工作日誌文件路徑豁免（不受 SCANNABLE_EXTENSIONS 限制時仍先過 exempt path 檢查）。

    此案例路徑本身非程式碼副檔名，驗證真正的路徑豁免用 .py 檔案模擬工作日誌內嵌腳本情境。
    """
    project_root = _make_fake_project(tmp_path)
    worklog_dir = project_root / "docs" / "work-logs" / "v0" / "v0.1" / "v0.1.0"
    worklog_dir.mkdir(parents=True)
    exit_code = _run_hook(
        monkeypatch,
        project_root,
        {
            "file_path": str(worklog_dir / "notes.py"),
            "content": "# 引用 UC-99 但屬歷史工作日誌\n",
        },
        tool_name="Write",
    )
    assert exit_code == 0
    assert capsys.readouterr().err == ""


def test_exempt_spec_self_path_no_warning(monkeypatch, capsys, tmp_path):
    """SSOT 自身（docs/app-use-cases.md）豁免。"""
    project_root = _make_fake_project(tmp_path)
    exit_code = _run_hook(
        monkeypatch,
        project_root,
        {
            "file_path": str(project_root / "docs" / "app-use-cases.md"),
            "content": "## UC-42: 新用例（尚未加入其他 SSOT 引用）\n",
        },
        tool_name="Write",
    )
    assert exit_code == 0
    assert capsys.readouterr().err == ""
    # docs/app-use-cases.md 非 SCANNABLE_EXTENSIONS（.md），本案例同時驗證副檔名跳過路徑


def test_exempt_test_fixtures_path_no_warning(monkeypatch, capsys, tmp_path):
    """測試 fixture 路徑豁免。"""
    project_root = _make_fake_project(tmp_path)
    fixtures_dir = project_root / "test" / "fixtures"
    fixtures_dir.mkdir(parents=True)
    exit_code = _run_hook(
        monkeypatch,
        project_root,
        {
            "file_path": str(fixtures_dir / "sample.dart"),
            "content": "// UC-99 測試假資料",
        },
        tool_name="Write",
    )
    assert exit_code == 0
    assert capsys.readouterr().err == ""


def test_exempt_docs_spec_path_no_warning(monkeypatch, capsys, tmp_path):
    """規範文件（docs/spec/）路徑豁免。"""
    project_root = _make_fake_project(tmp_path)
    spec_dir = project_root / "docs" / "spec"
    spec_dir.mkdir(parents=True)
    exit_code = _run_hook(
        monkeypatch,
        project_root,
        {
            "file_path": str(spec_dir / "example.py"),
            "content": "# 範例引用 UC-99（規範說明用，不代表宣告新用例）\n",
        },
        tool_name="Write",
    )
    assert exit_code == 0
    assert capsys.readouterr().err == ""


# ----------------------------------------------------------------------------
# 案例 4：非程式碼檔跳過
# ----------------------------------------------------------------------------

def test_non_code_file_skipped(monkeypatch, capsys, tmp_path):
    project_root = _make_fake_project(tmp_path)
    exit_code = _run_hook(
        monkeypatch,
        project_root,
        {
            "file_path": str(project_root / "README.md"),
            "content": "# 引用 UC-99\n",
        },
        tool_name="Write",
    )
    assert exit_code == 0
    assert capsys.readouterr().err == ""


def test_non_write_edit_tool_skipped(monkeypatch, capsys, tmp_path):
    project_root = _make_fake_project(tmp_path)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project_root))
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "echo UC-99"},
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    assert main() == 0
    assert capsys.readouterr().err == ""


# ----------------------------------------------------------------------------
# 案例 4b：MultiEdit 提取分支（聚合 edits[] 補強驗證）
# ----------------------------------------------------------------------------

def test_multiedit_with_violation_in_any_edit_emits_warning(monkeypatch, capsys, tmp_path):
    """MultiEdit 多段 edits 中，任一段 new_string 含未定義 UC token 即觸發 WARNING。"""
    project_root = _make_fake_project(tmp_path)
    exit_code = _run_hook(
        monkeypatch,
        project_root,
        {
            "file_path": str(project_root / "lib" / "book_service.dart"),
            "edits": [
                {"old_string": "a", "new_string": "// 對應 UC-01 匯入流程"},
                {"old_string": "b", "new_string": "// 對應 UC-99 尚未定義的用例"},
            ],
        },
        tool_name="MultiEdit",
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "UC-99" in captured.err
    assert "uc-reference-validation" in captured.err


def test_multiedit_all_valid_tokens_passes_silently(monkeypatch, capsys, tmp_path):
    """MultiEdit 所有 edits 皆為合法 UC token，靜默通過。"""
    project_root = _make_fake_project(tmp_path)
    exit_code = _run_hook(
        monkeypatch,
        project_root,
        {
            "file_path": str(project_root / "lib" / "book_service.dart"),
            "edits": [
                {"old_string": "a", "new_string": "// 對應 UC-01"},
                {"old_string": "b", "new_string": "// 對應 UC-05"},
            ],
        },
        tool_name="MultiEdit",
    )
    assert exit_code == 0
    assert capsys.readouterr().err == ""


def test_multiedit_empty_edits_no_error(monkeypatch, capsys, tmp_path):
    """MultiEdit edits 為空陣列時不誤報、不拋例外。"""
    project_root = _make_fake_project(tmp_path)
    exit_code = _run_hook(
        monkeypatch,
        project_root,
        {
            "file_path": str(project_root / "lib" / "book_service.dart"),
            "edits": [],
        },
        tool_name="MultiEdit",
    )
    assert exit_code == 0
    assert capsys.readouterr().err == ""


# ----------------------------------------------------------------------------
# 案例 5：uc_registry 不可用時 fail-open（附日誌）
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
# 案例 6：token 變體（小寫/全形）與豁免路徑/負向案例
# ----------------------------------------------------------------------------

def test_lowercase_uc_token_variant_emits_warning(monkeypatch, capsys, tmp_path):
    """小寫 uc-99 變體須被偵測並以正規形式 UC-99 顯示於 WARNING。"""
    project_root = _make_fake_project(tmp_path)
    exit_code = _run_hook(
        monkeypatch,
        project_root,
        {
            "file_path": str(project_root / "lib" / "book_service.dart"),
            "old_string": "x",
            "new_string": "// 對應 uc-99 尚未定義的用例",
        },
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "UC-99" in captured.err


def test_fullwidth_uc_token_variant_emits_warning(monkeypatch, capsys, tmp_path):
    """全形 ＵＣ－９９ 變體須被偵測並以正規形式 UC-99 顯示於 WARNING。"""
    project_root = _make_fake_project(tmp_path)
    exit_code = _run_hook(
        monkeypatch,
        project_root,
        {
            "file_path": str(project_root / "lib" / "book_service.dart"),
            "old_string": "x",
            "new_string": "// 對應 ＵＣ－９９ 尚未定義的用例",
        },
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "UC-99" in captured.err


def test_plain_text_mentioning_uc_command_not_misdetected(monkeypatch, capsys, tmp_path):
    """負向案例：合法描述文字「uc verify 命令」不應被誤判為 token 觸發 WARNING。"""
    project_root = _make_fake_project(tmp_path)
    exit_code = _run_hook(
        monkeypatch,
        project_root,
        {
            "file_path": str(project_root / "lib" / "book_service.dart"),
            "old_string": "x",
            "new_string": "// 執行 uc verify 命令確認",
        },
    )
    assert exit_code == 0
    assert capsys.readouterr().err == ""


def test_worktree_style_path_outside_project_root_still_exempted(monkeypatch, capsys, tmp_path):
    """worktree 情境：project_root（CLAUDE_PROJECT_DIR）指向主 repo，但實際檔案位於
    另一個鏡射目錄（worktree）下的豁免路徑，仍應正確判定為豁免（不誤報 WARNING）。
    """
    main_root = _make_fake_project(tmp_path / "main-repo")
    worktree_worklog_dir = tmp_path / "worktree-a" / "docs" / "work-logs" / "v1"
    worktree_worklog_dir.mkdir(parents=True)

    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(main_root))
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": str(worktree_worklog_dir / "notes.py"),
            "content": "# 引用 UC-99 但屬歷史工作日誌\n",
        },
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))

    assert main() == 0
    assert capsys.readouterr().err == ""


def test_uc_registry_import_failure_fails_open(monkeypatch, capsys, tmp_path):
    project_root = _make_fake_project(tmp_path)

    import builtins

    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "doc_system.core.uc_registry" or name.startswith("doc_system"):
            raise ImportError("模擬 doc_system 不可用")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)

    exit_code = _run_hook(
        monkeypatch,
        project_root,
        {
            "file_path": str(project_root / "lib" / "book_service.dart"),
            "content": "// UC-99",
        },
        tool_name="Write",
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "uc_registry" in captured.err
    assert "跳過驗證" in captured.err
