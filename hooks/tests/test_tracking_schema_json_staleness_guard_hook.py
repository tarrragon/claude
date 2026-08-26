"""
tracking-schema-json-staleness-guard-hook 測試

涵蓋範圍：
1. 純函式單元測試（is_commit_command / get_staged_files / compute_expected_schema /
   load_disk_schema，皆以 mock subprocess.run 隔離真實 git/uv 呼叫）
2. main() in-process 端到端測試（三種輸入情境：改 .py 未重產 JSON / 同時改
   兩者 / 未改 .py 的 commit 不受影響）
3. 生產啟動方式整合測試（subprocess 呼叫 `uv run <hook>`，覆蓋
   TEST-BAL-010：不可只用 in-process import 驗證隔離 venv 下的真實行為）。
   本組測試會暫時修改真實 tracking_schema.py 並在 finally 還原，驗證
   純註解改動不觸發（方式 B 選擇的理由）與語意改動觸發兩種真實情境。
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


_HOOKS_DIR = Path(__file__).parent.parent
_PROJECT_ROOT = _HOOKS_DIR.parent.parent  # .claude/hooks/tests -> repo root
_HOOK_PATH = _HOOKS_DIR / "tracking-schema-json-staleness-guard-hook.py"

if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

_spec = importlib.util.spec_from_file_location(
    "tracking_schema_json_staleness_guard_hook",
    _HOOK_PATH,
)
_hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hook)


# ============================================================================
# 純函式單元測試
# ============================================================================


def test_is_commit_command_true():
    assert _hook.is_commit_command('git commit -m "feat: x"') is True


def test_is_commit_command_excludes_amend_and_readonly():
    assert _hook.is_commit_command("git commit --amend") is False
    assert _hook.is_commit_command("git log") is False
    assert _hook.is_commit_command("git diff --cached") is False


def test_is_commit_command_false_for_unrelated():
    assert _hook.is_commit_command("git status") is False


def test_get_staged_files_parses_output():
    logger = MagicMock()
    fake_result = MagicMock(returncode=0, stdout="a.py\nb.json\n", stderr="")
    with patch.object(_hook.subprocess, "run", return_value=fake_result):
        files = _hook.get_staged_files(Path("/tmp"), logger)
    assert files == ["a.py", "b.json"]


def test_get_staged_files_returns_empty_on_failure():
    logger = MagicMock()
    fake_result = MagicMock(returncode=1, stdout="", stderr="boom")
    with patch.object(_hook.subprocess, "run", return_value=fake_result):
        files = _hook.get_staged_files(Path("/tmp"), logger)
    assert files == []
    logger.warning.assert_called()


def test_compute_expected_schema_parses_json():
    logger = MagicMock()
    fake_result = MagicMock(returncode=0, stdout='{"a": 1}', stderr="")
    with patch.object(_hook.subprocess, "run", return_value=fake_result):
        result = _hook.compute_expected_schema(Path("/tmp"), logger)
    assert result == {"a": 1}


def test_compute_expected_schema_fail_open_on_nonzero_exit():
    logger = MagicMock()
    fake_result = MagicMock(returncode=1, stdout="", stderr="uv error")
    with patch.object(_hook.subprocess, "run", return_value=fake_result):
        result = _hook.compute_expected_schema(Path("/tmp"), logger)
    assert result is None
    logger.warning.assert_called()


def test_compute_expected_schema_fail_open_on_invalid_json():
    logger = MagicMock()
    fake_result = MagicMock(returncode=0, stdout="not json", stderr="")
    with patch.object(_hook.subprocess, "run", return_value=fake_result):
        result = _hook.compute_expected_schema(Path("/tmp"), logger)
    assert result is None
    logger.warning.assert_called()


def test_compute_expected_schema_fail_open_on_exception():
    logger = MagicMock()
    with patch.object(_hook.subprocess, "run", side_effect=OSError("no uv")):
        result = _hook.compute_expected_schema(Path("/tmp"), logger)
    assert result is None
    logger.warning.assert_called()


def test_load_disk_schema_missing_file(tmp_path):
    logger = MagicMock()
    project_root = tmp_path
    result = _hook.load_disk_schema(project_root, logger)
    assert result is None
    logger.info.assert_called()


def test_load_disk_schema_valid(tmp_path):
    logger = MagicMock()
    json_path = tmp_path / _hook.SCHEMA_JSON_REL_PATH
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps({"x": 1}), encoding="utf-8")
    result = _hook.load_disk_schema(tmp_path, logger)
    assert result == {"x": 1}


def test_load_disk_schema_invalid_json(tmp_path):
    logger = MagicMock()
    json_path = tmp_path / _hook.SCHEMA_JSON_REL_PATH
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text("not json", encoding="utf-8")
    result = _hook.load_disk_schema(tmp_path, logger)
    assert result is None
    logger.warning.assert_called()


# ============================================================================
# main() in-process 端到端測試（三種輸入情境）
# ============================================================================


def _run_main_with(monkeypatch, command, staged_files, expected_schema, disk_schema):
    """組裝 stdin 並呼叫 main()，mock 掉 git/uv 呼叫與磁碟讀取。"""
    stdin_payload = json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": command}}
    )
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO(stdin_payload))
    monkeypatch.setattr(_hook, "get_staged_files", lambda root, logger: staged_files)
    monkeypatch.setattr(
        _hook, "compute_expected_schema", lambda root, logger: expected_schema
    )
    monkeypatch.setattr(_hook, "load_disk_schema", lambda root, logger: disk_schema)
    return _hook.main()


def test_scenario_py_changed_json_stale_blocks(monkeypatch, capsys):
    """情境 1：改 tracking_schema.py 未重產 JSON → 產生可見訊號（exit 2）。"""
    exit_code = _run_main_with(
        monkeypatch,
        command='git commit -m "feat: x"',
        staged_files=[_hook.SCHEMA_PY_REL_PATH],
        expected_schema={"node_types": {"a": 1}},
        disk_schema={"node_types": {}},
    )
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "tracking_schema.json 過期" in captured.err


def test_scenario_both_changed_in_sync_passes(monkeypatch):
    """情境 2：同時改動 .py 與重產的 JSON（內容一致）→ 不觸發（exit 0）。"""
    exit_code = _run_main_with(
        monkeypatch,
        command='git commit -m "feat: x"',
        staged_files=[_hook.SCHEMA_PY_REL_PATH, _hook.SCHEMA_JSON_REL_PATH],
        expected_schema={"node_types": {"a": 1}},
        disk_schema={"node_types": {"a": 1}},
    )
    assert exit_code == 0


def test_scenario_py_not_changed_skips(monkeypatch):
    """情境 3：未改動 tracking_schema.py 的 commit 不受影響（exit 0，未呼叫比對）。"""
    called = {"compute": False}

    def _should_not_be_called(root, logger):
        called["compute"] = True
        return {}

    stdin_payload = json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": 'git commit -m "feat: unrelated"'}}
    )
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO(stdin_payload))
    monkeypatch.setattr(_hook, "get_staged_files", lambda root, logger: ["some/other/file.py"])
    monkeypatch.setattr(_hook, "compute_expected_schema", _should_not_be_called)
    monkeypatch.setattr(_hook, "load_disk_schema", lambda root, logger: None)

    exit_code = _hook.main()

    assert exit_code == 0
    assert called["compute"] is False


def test_scenario_compute_fails_fail_open(monkeypatch):
    """compute_expected_schema 失敗（環境問題）→ fail-open 放行，非靜默阻擋。"""
    exit_code = _run_main_with(
        monkeypatch,
        command='git commit -m "feat: x"',
        staged_files=[_hook.SCHEMA_PY_REL_PATH],
        expected_schema=None,
        disk_schema={"node_types": {}},
    )
    assert exit_code == 0


def test_non_commit_command_skips(monkeypatch):
    exit_code = _run_main_with(
        monkeypatch,
        command="git status",
        staged_files=[_hook.SCHEMA_PY_REL_PATH],
        expected_schema=None,
        disk_schema=None,
    )
    assert exit_code == 0


# ============================================================================
# 生產啟動方式整合測試（TEST-BAL-010 防護：不可只用 in-process import 驗證）
# ============================================================================


SCHEMA_PY_ABS = _PROJECT_ROOT / _hook.SCHEMA_PY_REL_PATH


def _run_hook_as_subprocess(command: str) -> subprocess.CompletedProcess:
    """以生產啟動方式（uv run --quiet <hook>）呼叫 hook，不經 in-process import。"""
    stdin_payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    return subprocess.run(
        ["uv", "run", "--quiet", str(_HOOK_PATH)],
        input=stdin_payload,
        capture_output=True,
        text=True,
        cwd=str(_PROJECT_ROOT),
        timeout=60,
    )


def _git(*args) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(_PROJECT_ROOT), *args],
        capture_output=True,
        text=True,
        timeout=15,
    )


@pytest.fixture
def restore_schema_py():
    """暫時修改真實 tracking_schema.py，測試結束後強制還原（unstage + checkout）。"""
    original = SCHEMA_PY_ABS.read_text(encoding="utf-8")
    yield
    SCHEMA_PY_ABS.write_text(original, encoding="utf-8")
    _git("restore", "--staged", "--", str(_hook.SCHEMA_PY_REL_PATH))
    _git("checkout", "--", str(_hook.SCHEMA_PY_REL_PATH))


@pytest.mark.integration
def test_production_launch_comment_only_change_does_not_block(restore_schema_py):
    """方式 B 選擇的理由的實測證成：純註解改動（不影響 schema 值）→ 不觸發。

    若改用方式 A（檔案存在性），此情境會誤報（0.2.1-W3-1108 曾發生過的
    存在性檢查誤報型態）；方式 B 因比對的是 build_schema_dict() 輸出內容，
    純註解改動不改變輸出，故不觸發。
    """
    original = SCHEMA_PY_ABS.read_text(encoding="utf-8")
    SCHEMA_PY_ABS.write_text(
        original + "\n# tracking-schema-json-staleness-guard-hook 測試用純註解改動\n",
        encoding="utf-8",
    )
    add_result = _git("add", "--", str(_hook.SCHEMA_PY_REL_PATH))
    assert add_result.returncode == 0, add_result.stderr

    result = _run_hook_as_subprocess('git commit -m "test: comment only"')

    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"


@pytest.mark.integration
def test_production_launch_semantic_change_without_regen_blocks(restore_schema_py):
    """語意改動（新增 GRAPH_NODE_TYPES 條目）但未重產 JSON → 生產路徑下阻擋（exit 2）。

    以生產啟動方式驗證：hook 呼叫 `uv run --project .claude/skills/doc doc
    schema export --json` 取得的內容與磁碟 JSON 比對，語意不一致時真實阻擋。
    """
    original = SCHEMA_PY_ABS.read_text(encoding="utf-8")
    assert "GRAPH_NODE_TYPES" in original, "測試前提：tracking_schema.py 應含 GRAPH_NODE_TYPES"

    # 在 GRAPH_NODE_TYPES 字典後緊接插入一個臨時測試節點，製造語意層面差異。
    marker = "GRAPH_NODE_TYPES"
    insert_at = original.index(marker)
    # 找到該行後緊接的 "= {" 開頭處，插入一個明顯可辨識、易還原的臨時條目
    brace_at = original.index("{", insert_at)
    mutated = (
        original[: brace_at + 1]
        + '\n    "TRACKING_SCHEMA_STALENESS_GUARD_TEST_TEMP_NODE": {},'
        + original[brace_at + 1:]
    )
    SCHEMA_PY_ABS.write_text(mutated, encoding="utf-8")

    add_result = _git("add", "--", str(_hook.SCHEMA_PY_REL_PATH))
    assert add_result.returncode == 0, add_result.stderr

    result = _run_hook_as_subprocess('git commit -m "test: semantic change no regen"')

    assert result.returncode == 2, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "tracking_schema.json 過期" in result.stderr


@pytest.mark.integration
def test_production_launch_unrelated_commit_not_affected():
    """未改動 tracking_schema.py 的 commit 不受影響（生產啟動方式驗證）。"""
    # 確保目前無任何 staged 的 tracking_schema.py 改動（測試環境不應殘留）
    staged = _git("diff", "--cached", "--name-only").stdout.splitlines()
    assert _hook.SCHEMA_PY_REL_PATH not in staged

    result = _run_hook_as_subprocess('git commit -m "test: unrelated"')

    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
