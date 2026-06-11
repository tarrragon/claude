"""4 個 PostToolUse hook 的 subagent 偵測早期跳過回歸測試（W1-071）。

背景（PC-V1-004 入口污染）：
    commit-msg-layer2-marker-check / post-test / needs-context-listener /
    ticket-skill-sync-check 四個 PostToolUse:Bash hook 原缺 is_subagent_environment
    偵測，PM-only 動作性提示注入 subagent context，誘導唯讀委員越界
    （W1-060 實證 Explore 執行 git merge）。

驗證情境（每 hook 兩組）：
    1. subagent 環境（input 含 agent_id）→ 零注入（無 additionalContext）
    2. PM 主線程環境（無 agent_id）→ 行為不變（觸發條件成立時照常輸出）
"""

import importlib.util
import json
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


HOOKS_DIR = Path(__file__).resolve().parent.parent
TICKET_SKILL_HOOKS_DIR = HOOKS_DIR.parent / "skills" / "ticket" / "hooks"

HOOK_PATHS = {
    "layer2": HOOKS_DIR / "commit-msg-layer2-marker-check-hook.py",
    "post_test": HOOKS_DIR / "post-test-hook.py",
    "needs_context": TICKET_SKILL_HOOKS_DIR / "needs-context-listener-hook.py",
    "sync_check": TICKET_SKILL_HOOKS_DIR / "ticket-skill-sync-check-hook.py",
}


def _load_module(key: str):
    """動態載入含 hyphen 檔名的 hook；模組名加 w1071 前綴避免撞其他測試檔。"""
    spec = importlib.util.spec_from_file_location(f"w1071_{key}", HOOK_PATHS[key])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def layer2_hook():
    return _load_module("layer2")


@pytest.fixture(scope="module")
def post_test_hook():
    return _load_module("post_test")


@pytest.fixture(scope="module")
def needs_context_hook():
    return _load_module("needs_context")


@pytest.fixture(scope="module")
def sync_check_hook():
    return _load_module("sync_check")


@pytest.fixture
def test_logger():
    return logging.getLogger("test-w1071")


def _stdin(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _run_main(module, payload: dict, test_logger, capsys, main_attr: str = "main"):
    """以 mock stdin 執行 hook main()，回傳 (exit_code, stdout)。"""
    with patch("sys.stdin.read", return_value=_stdin(payload)), \
         patch.object(module, "setup_hook_logging", return_value=test_logger):
        rc = getattr(module, main_attr)()
    captured = capsys.readouterr()
    return rc, captured.out


# ---------------------------------------------------------------------------
# 1. commit-msg-layer2-marker-check-hook
# ---------------------------------------------------------------------------

LAYER2_COMMIT_PAYLOAD = {
    "tool_name": "Bash",
    "tool_input": {"command": 'git commit -m "feat: framework rule update"'},
    "tool_response": {"stdout": "1 file changed, 1 insertion(+)", "stderr": ""},
}


def test_layer2_subagent_env_zero_injection(layer2_hook, test_logger, capsys):
    """subagent 環境：早期跳過，零輸出（不執行 git 偵測邏輯）"""
    payload = dict(LAYER2_COMMIT_PAYLOAD, agent_id="thyme-python-developer")
    sentinel = MagicMock()
    with patch.object(layer2_hook, "check_layer2_marker", sentinel):
        rc, out = _run_main(layer2_hook, payload, test_logger, capsys)
    assert rc == 0
    assert out == "", "subagent 環境不應有任何 stdout 注入"
    sentinel.assert_not_called()


def test_layer2_pm_env_behavior_unchanged(layer2_hook, test_logger, capsys):
    """PM 環境：framework commit 缺標記照常輸出警告（行為不變）"""
    with patch.object(layer2_hook, "is_framework_path", lambda f: True), \
         patch.object(layer2_hook, "_get_changed_files", lambda *a, **kw: [".claude/rules/core/foo.md"]), \
         patch.object(layer2_hook, "_get_commit_msg", lambda *a, **kw: "feat: framework rule update"), \
         patch.object(layer2_hook, "_is_merge_or_revert", lambda *a, **kw: False), \
         patch.object(layer2_hook, "get_project_root", return_value=Path(".")):
        rc, out = _run_main(layer2_hook, LAYER2_COMMIT_PAYLOAD, test_logger, capsys)
    assert rc == 0
    output = json.loads(out)
    assert "additionalContext" in output["hookSpecificOutput"], \
        "PM 環境觸發條件成立時應照常輸出 Layer 2 警告"


# ---------------------------------------------------------------------------
# 2. post-test-hook
# ---------------------------------------------------------------------------

POST_TEST_PAYLOAD = {
    "tool_name": "Bash",
    "tool_input": {"command": "npm test"},
    "tool_response": {"stdout": "Tests: 1 failed, 10 passed"},
}


def test_post_test_subagent_env_zero_injection(post_test_hook, test_logger, capsys):
    """subagent 環境：早期跳過，子邏輯不執行、零輸出"""
    payload = dict(POST_TEST_PAYLOAD, agent_id="thyme-python-developer")
    timeout_sentinel = MagicMock()
    eval_sentinel = MagicMock()
    with patch.object(post_test_hook, "check_test_timeout", timeout_sentinel), \
         patch.object(post_test_hook, "evaluate_test_failure", eval_sentinel):
        rc, out = _run_main(post_test_hook, payload, test_logger, capsys)
    assert rc == 0
    assert out == "", "subagent 環境不應有任何 stdout 注入"
    timeout_sentinel.assert_not_called()
    eval_sentinel.assert_not_called()


def test_post_test_pm_env_behavior_unchanged(post_test_hook, test_logger, capsys):
    """PM 環境：測試命令照常進入子邏輯並輸出 additionalContext（行為不變）"""
    with patch.object(post_test_hook, "check_test_timeout", lambda *a, **kw: None), \
         patch.object(post_test_hook, "evaluate_test_failure", lambda *a, **kw: "失敗評估訊息"):
        rc, out = _run_main(post_test_hook, POST_TEST_PAYLOAD, test_logger, capsys)
    assert rc == 0
    output = json.loads(out)
    assert output["hookSpecificOutput"]["additionalContext"] == "失敗評估訊息", \
        "PM 環境子邏輯訊息應照常輸出"


# ---------------------------------------------------------------------------
# 3. needs-context-listener-hook
# ---------------------------------------------------------------------------

NEEDS_CONTEXT_PAYLOAD = {
    "tool_name": "Bash",
    "tool_input": {
        "command": 'ticket track append-log 1.0.0-W1-071 --section "NeedsContext" "缺料說明"'
    },
    "tool_response": {"success": True, "stdout": "appended"},
}


def test_needs_context_subagent_env_zero_injection(needs_context_hook, test_logger, capsys):
    """subagent 環境：早期跳過，零輸出"""
    payload = dict(NEEDS_CONTEXT_PAYLOAD, agent_id="saffron-system-analyst")
    rc, out = _run_main(needs_context_hook, payload, test_logger, capsys, main_attr="main_logic")
    assert rc == 0
    assert out == "", "subagent 環境不應有任何 stdout 注入"


def test_needs_context_pm_env_behavior_unchanged(needs_context_hook, test_logger, capsys):
    """PM 環境：NeedsContext append-log 照常輸出提醒（行為不變）"""
    rc, out = _run_main(needs_context_hook, NEEDS_CONTEXT_PAYLOAD, test_logger, capsys, main_attr="main_logic")
    assert rc == 0
    output = json.loads(out)
    context = output["hookSpecificOutput"]["additionalContext"]
    assert "[NeedsContext]" in context and "1.0.0-W1-071" in context, \
        "PM 環境應照常輸出 NeedsContext 提醒"


# ---------------------------------------------------------------------------
# 4. ticket-skill-sync-check-hook
# ---------------------------------------------------------------------------

SYNC_CHECK_PAYLOAD = {
    "tool_name": "Bash",
    "tool_input": {"command": 'git commit -m "feat(ticket): add lifecycle command"'},
    "tool_response": {"stdout": "2 files changed, 50 insertions(+)"},
}

SYNC_CHECK_SKILL_FILES = [".claude/skills/ticket/ticket_system/lifecycle.py"]


def test_sync_check_subagent_env_zero_injection(sync_check_hook, test_logger, capsys):
    """subagent 環境：早期跳過，輸出預設 JSON（無 additionalContext）且不查 git"""
    payload = dict(SYNC_CHECK_PAYLOAD, agent_id="thyme-python-developer")
    sentinel = MagicMock()
    with patch.object(sync_check_hook, "get_commit_files", sentinel):
        rc, out = _run_main(sync_check_hook, payload, test_logger, capsys)
    assert rc == 0
    output = json.loads(out)
    assert "additionalContext" not in output["hookSpecificOutput"], \
        "subagent 環境不應注入同步檢查提醒"
    sentinel.assert_not_called()


def test_sync_check_pm_env_behavior_unchanged(sync_check_hook, test_logger, capsys):
    """PM 環境：feat commit 含 skill src 改動照常輸出提醒（行為不變）"""
    with patch.object(sync_check_hook, "get_commit_files", return_value=SYNC_CHECK_SKILL_FILES):
        rc, out = _run_main(sync_check_hook, SYNC_CHECK_PAYLOAD, test_logger, capsys)
    assert rc == 0
    output = json.loads(out)
    assert "additionalContext" in output["hookSpecificOutput"], \
        "PM 環境觸發條件成立時應照常輸出同步檢查提醒"
