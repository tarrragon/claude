"""Unit tests for framework-rule-edit-skill-trigger-hook (W17-127.2)

涵蓋 4 情境（acceptance #5）：
1. framework path + 已讀 SKILL → 放行（無警告、無 cache）
2. framework path + 未讀 SKILL → 警告（exit 0、寫 stderr、寫 cache）
3. 非 framework path → 跳過（無警告）
4. cache 命中 → 跳過（已警告路徑同 session 不再警告）

額外驗證：
- strict 模式：未讀 SKILL → exit 2 阻擋
- 訊息文字機會成本語氣（acceptance #4）：無「禁止 / 必須 / 不可」
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import textwrap
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from lib import framework_paths  # noqa: E402


HOOK_PATH = HOOKS_DIR / "framework-rule-edit-skill-trigger-hook.py"


def _import_hook_module():
    """以 file path 匯入 hook 模組（檔名含 hyphen 無法直接 import）。"""
    spec = importlib.util.spec_from_file_location(
        "framework_rule_edit_skill_trigger_hook", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hook = _import_hook_module()


@pytest.fixture(autouse=True)
def _reset_framework_cache():
    framework_paths.reset_cache()
    yield
    framework_paths.reset_cache()


@pytest.fixture
def project_dir(tmp_path, monkeypatch):
    """建立臨時專案根目錄並設 CLAUDE_PROJECT_DIR。"""
    # 建立必要目錄
    (tmp_path / ".claude" / "config").mkdir(parents=True)
    (tmp_path / ".claude" / "hook-logs").mkdir(parents=True)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    return tmp_path


def _write_strict_config(project_dir: Path, strict: bool) -> None:
    config = project_dir / ".claude" / "config" / "skill-trigger-strict.yaml"
    config.write_text(f"strict: {'true' if strict else 'false'}\n", encoding="utf-8")


def _write_transcript(project_dir: Path, with_skill_call: bool) -> Path:
    """建立 transcript JSONL；with_skill_call=True 時含 Skill compositional-writing 呼叫。"""
    path = project_dir / "transcript.jsonl"
    lines = []
    # 一般 user message
    lines.append(json.dumps({
        "type": "user",
        "message": {"role": "user", "content": "hello"},
    }))
    if with_skill_call:
        lines.append(json.dumps({
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "讀 skill"},
                    {
                        "type": "tool_use",
                        "name": "Skill",
                        "input": {"skill": "compositional-writing", "args": "ctx"},
                    },
                ],
            },
        }))
    else:
        # 其他無關的 tool_use（Bash），不應被誤判
        lines.append(json.dumps({
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Bash",
                        "input": {"command": "ls"},
                    },
                ],
            },
        }))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _make_input(project_dir: Path, file_path: str, transcript: Path,
                tool_name: str = "Edit", session_id: str = "test-session-001") -> dict:
    return {
        "session_id": session_id,
        "transcript_path": str(transcript),
        "tool_name": tool_name,
        "tool_input": {"file_path": str(project_dir / file_path)
                       if not file_path.startswith("/") else file_path},
    }


def _run_main_with_input(monkeypatch, capsys, input_data: dict) -> tuple[int, str]:
    """以 stdin 餵 input_data 呼叫 hook.main()，回傳 (exit_code, stderr)。"""
    payload = json.dumps(input_data)

    import io
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
    capsys.readouterr()  # 清空之前的 capture
    code = hook.main()
    captured = capsys.readouterr()
    return code, captured.err


# ---- 情境 1：framework + 已讀 SKILL → 放行 ----

def test_framework_path_with_skill_read_passes(project_dir, monkeypatch, capsys):
    _write_strict_config(project_dir, False)
    transcript = _write_transcript(project_dir, with_skill_call=True)
    input_data = _make_input(project_dir, ".claude/rules/core/example.md", transcript)

    code, stderr = _run_main_with_input(monkeypatch, capsys, input_data)

    assert code == 0
    assert stderr == ""  # 無警告

    # cache 應未寫入該路徑（已讀 SKILL 屬合規路徑）
    cache_files = list((project_dir / ".claude" / "hook-logs").glob("skill-trigger-cache-*.json"))
    if cache_files:
        # 即使有 cache 檔，warned_paths 不該含本路徑
        data = json.loads(cache_files[0].read_text())
        assert ".claude/rules/core/example.md" not in data.get("warned_paths", [])


# ---- 情境 2：framework + 未讀 SKILL → 警告 ----

def test_framework_path_without_skill_warns(project_dir, monkeypatch, capsys):
    _write_strict_config(project_dir, False)
    transcript = _write_transcript(project_dir, with_skill_call=False)
    input_data = _make_input(project_dir, ".claude/rules/core/example.md", transcript)

    code, stderr = _run_main_with_input(monkeypatch, capsys, input_data)

    assert code == 0  # 預設 exit 0 警告
    assert "skill-trigger" in stderr
    assert "compositional-writing" in stderr
    assert ".claude/rules/core/example.md" in stderr

    # cache 應寫入該路徑
    cache_files = list((project_dir / ".claude" / "hook-logs").glob("skill-trigger-cache-test-session-001.json"))
    assert len(cache_files) == 1
    data = json.loads(cache_files[0].read_text())
    assert ".claude/rules/core/example.md" in data["warned_paths"]


# ---- 情境 3：非 framework → 跳過 ----

def test_non_framework_path_skips(project_dir, monkeypatch, capsys):
    _write_strict_config(project_dir, False)
    transcript = _write_transcript(project_dir, with_skill_call=False)
    input_data = _make_input(project_dir, "src/foo/bar.py", transcript)

    code, stderr = _run_main_with_input(monkeypatch, capsys, input_data)

    assert code == 0
    assert stderr == ""

    cache_files = list((project_dir / ".claude" / "hook-logs").glob("skill-trigger-cache-*.json"))
    assert cache_files == []  # 完全沒寫 cache


# ---- 情境 4：cache 命中 → 跳過 ----

def test_cache_hit_skips_warning(project_dir, monkeypatch, capsys):
    _write_strict_config(project_dir, False)
    transcript = _write_transcript(project_dir, with_skill_call=False)

    session_id = "test-session-cache"
    # 預先寫入 cache（模擬第一次警告已發生）
    cache_path = project_dir / ".claude" / "hook-logs" / f"skill-trigger-cache-{session_id}.json"
    rel_target = ".claude/rules/core/example.md"
    cache_path.write_text(json.dumps({
        "session_id": session_id,
        "warned_paths": [rel_target],
    }), encoding="utf-8")

    input_data = _make_input(project_dir, rel_target, transcript, session_id=session_id)
    code, stderr = _run_main_with_input(monkeypatch, capsys, input_data)

    assert code == 0
    assert stderr == ""  # cache 命中，不再警告


# ---- 額外：strict 模式 ----

def test_strict_mode_blocks_unread_skill(project_dir, monkeypatch, capsys):
    _write_strict_config(project_dir, True)
    transcript = _write_transcript(project_dir, with_skill_call=False)
    input_data = _make_input(
        project_dir, ".claude/pm-rules/decision-tree.md", transcript,
        session_id="strict-session",
    )

    code, stderr = _run_main_with_input(monkeypatch, capsys, input_data)

    assert code == 2
    assert "strict" in stderr
    assert "skill-trigger" in stderr


# ---- 額外：訊息文字機會成本語氣（acceptance #4） ----

def test_warn_message_uses_opportunity_cost_language():
    """WARN_MESSAGE 不應含絕對主義詞「禁止 / 必須 / 不可」。"""
    msg = hook.WARN_MESSAGE
    forbidden_words = ["禁止", "必須", "不可"]
    for word in forbidden_words:
        assert word not in msg, f"WARN_MESSAGE 含絕對主義詞「{word}」，違反原則 3"
    # 應含機會成本語氣關鍵字
    assert "建議" in msg
    assert "成本較高" in msg
    assert "豁免條件" in msg


def test_strict_message_uses_opportunity_cost_language():
    """STRICT_MESSAGE 雖屬阻擋場景，仍以機會成本語氣描述豁免路徑。"""
    msg = hook.STRICT_MESSAGE
    forbidden_words = ["禁止", "必須", "不可"]
    for word in forbidden_words:
        assert word not in msg, f"STRICT_MESSAGE 含絕對主義詞「{word}」，違反原則 3"
    assert "建議" in msg
    assert "豁免條件" in msg


# ---- 額外：非 Edit/Write 工具 / 缺 file_path 等防護 ----

def test_non_edit_tool_skips(project_dir, monkeypatch, capsys):
    _write_strict_config(project_dir, False)
    transcript = _write_transcript(project_dir, with_skill_call=False)
    input_data = _make_input(project_dir, ".claude/rules/core/x.md", transcript, tool_name="Bash")
    code, stderr = _run_main_with_input(monkeypatch, capsys, input_data)
    assert code == 0
    assert stderr == ""


def test_missing_file_path_skips(project_dir, monkeypatch, capsys):
    _write_strict_config(project_dir, False)
    transcript = _write_transcript(project_dir, with_skill_call=False)
    input_data = {
        "session_id": "x",
        "transcript_path": str(transcript),
        "tool_name": "Edit",
        "tool_input": {},  # 無 file_path
    }
    code, stderr = _run_main_with_input(monkeypatch, capsys, input_data)
    assert code == 0
    assert stderr == ""
