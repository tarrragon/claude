"""worklog-format-check 抽樣計數器路徑隔離測試（3.3.0-W1-097）。

計數器須於每次呼叫時由 lib 的 get_hook_log_dir("_sampling") 解析，
CLAUDE_PROJECT_DIR 指向 tmp_path 時只落在 tmp_path 下，不得寫入
skills/doc-flow/hook-logs。
"""

import importlib.util
import logging
from pathlib import Path

HOOK_PATH = (
    Path(__file__).resolve().parents[2]
    / "skills" / "doc-flow" / "hooks" / "worklog-format-check.py"
)


def _load_hook():
    spec = importlib.util.spec_from_file_location("worklog_format_check_under_test", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_counter_lands_under_project_dir_not_skill_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.setenv("HOOK_TEST_ISOLATION", "1")
    hook = _load_hook()

    hook.should_sample_run(logging.getLogger("test"))

    expected = tmp_path / ".claude" / "hook-logs" / "_sampling" / "worklog-format-check.count"
    assert expected.read_text() == "1"


def test_counter_path_is_not_import_time_fixed(tmp_path, monkeypatch):
    """舊寫法（import 時固定 Path(__file__).parent.parent / hook-logs）的對照。

    舊碼在同一輸入下落在 skills/doc-flow/hook-logs/_sampling/，與 tmp_path 無關。
    新碼不得保留該固定常數。
    """
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.setenv("HOOK_TEST_ISOLATION", "1")
    hook = _load_hook()

    old_location = HOOK_PATH.parent.parent / "hook-logs" / "_sampling" / "worklog-format-check.count"
    assert tmp_path not in old_location.parents
    assert not hasattr(hook, "SAMPLING_COUNTER_FILE")
