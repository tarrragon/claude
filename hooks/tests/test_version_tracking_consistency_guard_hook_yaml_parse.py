"""
Version Tracking Consistency Guard Hook - todolist.yaml 解析失敗偵測測試

涵蓋範圍（0.2.1-W3-008 + 0.2.1-W3-013）：
1. 以本次實際錯位樣態（0.2.1 版本條目誤插到 references mapping 之後）
   重現 yaml.safe_load ParserError，驗證 hook 輸出 ERROR 級警告
   （含行號與 ParserError 訊息），不靜默 fallback。
2. versions 結構驗證：versions 鍵非 list、條目缺 version/status 欄位時
   輸出結構錯誤。
3. 正常可解析的 todolist.yaml 不觸發解析失敗警告。
4. 0.2.1-W3-013：確認 subprocess 探測系統 python3 路徑候選已移除，
   改用 PEP 723 宣告的 PyYAML 直接解析；在無 homebrew python3 的環境
   假設下（mock PATH / shutil.which）解析前提驗證仍執行。

背景：`.claude/error-patterns/implementation/IMP-BAL-003-guard-lenient-parser-blind-to-structural-error.md`
"""

import importlib.util
import logging
import sys
from pathlib import Path

import pytest


_HOOKS_DIR = Path(__file__).parent.parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

_spec = importlib.util.spec_from_file_location(
    "version_tracking_consistency_guard_hook",
    _HOOKS_DIR / "version-tracking-consistency-guard-hook.py",
)
_hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hook)


# 本次實際錯位樣態（commit 955a018 修復前）：0.2.1 版本條目誤插到
# references.design mapping 底下的 list 之後，破壞 block mapping 結構。
MALFORMED_TODOLIST_YAML = """\
versions:
  - version: "0.2.0"
    status: completed

# ============================================================
# 參考文件
# ============================================================
references:
  development:
    - path: "CLAUDE.md"
      description: "專案開發指導規範"
  design:
    - path: "flutter_handoff/README.md"
      description: "設計交付說明"
    - path: "flutter_handoff/models.dart"
      description: "資料模型與 SQLite schema"

  - version: "0.2.1"
    status: active
    description: "資料契約框架工具鏈改進"
"""

VALID_TODOLIST_YAML = """\
versions:
  - version: "0.2.0"
    status: completed
  - version: "0.2.1"
    status: active

references:
  development:
    - path: "CLAUDE.md"
      description: "專案開發指導規範"
"""

VERSIONS_NOT_LIST_YAML = """\
versions:
  "0.2.0": completed
"""

VERSIONS_ENTRY_MISSING_FIELD_YAML = """\
versions:
  - version: "0.2.0"
    status: completed
  - version: "0.2.1"
"""


@pytest.fixture()
def logger():
    logger_ = logging.getLogger("test-version-tracking-yaml-parse")
    logger_.addHandler(logging.NullHandler())
    return logger_


def test_load_todolist_via_yaml_detects_parse_error(tmp_path, logger, capsys):
    """重現實際錯位樣態：yaml.safe_load 失敗須回傳 None，且 stderr 含
    ERROR 級警告、行號與 ParserError 訊息，不可靜默 fallback。"""
    todolist_path = tmp_path / "todolist.yaml"
    todolist_path.write_text(MALFORMED_TODOLIST_YAML, encoding="utf-8")

    result = _hook.load_todolist_via_yaml(todolist_path, logger)

    assert result is None
    captured = capsys.readouterr()
    assert "ERROR" in captured.err
    assert "todolist.yaml" in captured.err
    # ParserError 訊息含行號資訊（"line N"）
    assert "line" in captured.err.lower()


def test_load_todolist_via_yaml_parses_valid_yaml(tmp_path, logger):
    """正常可解析的 todolist.yaml 應成功回傳解析後結構。"""
    todolist_path = tmp_path / "todolist.yaml"
    todolist_path.write_text(VALID_TODOLIST_YAML, encoding="utf-8")

    result = _hook.load_todolist_via_yaml(todolist_path, logger)

    assert result is not None
    assert isinstance(result["versions"], list)
    assert len(result["versions"]) == 2


def test_no_subprocess_python3_probing_remains():
    """0.2.1-W3-013：確認 subprocess 探測系統 python3 的路徑已完全移除，
    不留作 fallback（保留即保留靜默降級路徑，問題未除）。"""
    assert not hasattr(_hook, "_find_python3_with_yaml")
    assert not hasattr(_hook, "_PYTHON3_WITH_YAML_CANDIDATES")
    assert not hasattr(_hook, "load_todolist_via_subprocess")


def test_load_todolist_via_yaml_works_without_homebrew_python3(tmp_path, logger, monkeypatch):
    """驗證前提解析不依賴系統 python3 路徑探測：模擬「無 homebrew python3」
    環境（PATH 清空、shutil.which 找不到任何 python3 候選），解析仍應
    成功——因為依賴已由 PEP 723 header 於 uv 隔離環境內保證，parsing
    直接呼叫 `import yaml`，不透過 subprocess 尋找系統直譯器。"""
    monkeypatch.setenv("PATH", str(tmp_path / "empty-bin"))
    monkeypatch.setattr("shutil.which", lambda *_args, **_kwargs: None)

    todolist_path = tmp_path / "todolist.yaml"
    todolist_path.write_text(VALID_TODOLIST_YAML, encoding="utf-8")

    result = _hook.load_todolist_via_yaml(todolist_path, logger)

    assert result is not None
    assert isinstance(result["versions"], list)
    assert len(result["versions"]) == 2


def test_validate_versions_schema_rejects_non_list():
    data = {"versions": {"0.2.0": "completed"}}
    errors = _hook.validate_versions_schema(data)
    assert errors
    assert any("非 list" in e or "缺席" in e for e in errors)


def test_validate_versions_schema_rejects_entry_missing_fields():
    data = {
        "versions": [
            {"version": "0.2.0", "status": "completed"},
            {"version": "0.2.1"},  # 缺 status
        ]
    }
    errors = _hook.validate_versions_schema(data)
    assert errors
    assert any("0.2.1" in e for e in errors)


def test_validate_versions_schema_accepts_well_formed_versions():
    data = {
        "versions": [
            {"version": "0.2.0", "status": "completed"},
            {"version": "0.2.1", "status": "active"},
        ]
    }
    errors = _hook.validate_versions_schema(data)
    assert errors == []


def test_main_reports_parse_failure_and_does_not_fallback_silently(tmp_path, monkeypatch, capsys):
    """整合驗證：main() 遇到本次錯位樣態時輸出 ERROR 警告，且不繼續執行
    後續依賴 versions dict 的漂移掃描（判定順序：前提失敗，後續結論不具意義）。
    """
    project_root = tmp_path / "project"
    (project_root / "docs").mkdir(parents=True)
    (project_root / "docs" / "todolist.yaml").write_text(MALFORMED_TODOLIST_YAML, encoding="utf-8")

    monkeypatch.setattr(_hook, "get_project_root", lambda: str(project_root))

    exit_code = _hook.main()

    assert exit_code == 0  # session-start hook 不阻擋
    captured = capsys.readouterr()
    assert "ERROR" in captured.err
    assert "todolist.yaml" in captured.err
