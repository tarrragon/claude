"""error-pattern flat 號 negative gate hook 測試（1.0.0-W1-021 / W1-036）。

hook 自包含於 .claude/skills/error-pattern/hooks/error-pattern-flat-gate-hook.py；
測試暫借 hooks pytest env 執行（與 test_error_pattern_allocator.py 同慣例，
skill 完整 package 化屬 W1-001 上架範圍）。

驗證 decide() 純函式四分支 + 輔助判定：
- deny: 新建 flat 號（<CAT>-NNN）error-pattern 檔
- allow: 前綴號（<CAT>-<PROJ>-NNN）新建 / 既有 flat 檔編輯 / 非 error-patterns / 非 Write|Edit

W1-036 補強：
- 數字開頭描述段（PC-099-3-layer-defense.md）不得被誤判為前綴號而繞過 gate。
- subprocess 層 main()/stdin/emit 接線測試（exit code + hookSpecificOutput shape）。
"""

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

_HOOK_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "skills"
    / "error-pattern"
    / "hooks"
    / "error-pattern-flat-gate-hook.py"
)


def _load_hook():
    """以 importlib 載入含 '-' 的 hook 檔（無法直接 import）。

    載入時 hook 頂層自設 sys.path 指向 .claude/hooks/ 取得 hook_utils 與 lib.pattern_id。
    """
    spec = importlib.util.spec_from_file_location(
        "error_pattern_flat_gate_hook", _HOOK_PATH
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hook = _load_hook()


# --- is_flat_id：flat（2 段）vs 前綴（3+ 段） ---
@pytest.mark.parametrize(
    "pattern_id,expected",
    [
        ("PC-099", True),
        ("IMP-049", True),
        ("ARCH-020", True),
        ("PC-V1-001", False),
        ("PC-C2C-001", False),
        ("IMP-APP-012", False),
        (None, False),
        # W1-036：數字開頭描述段被 extract_pattern_id 過度匹配為 3 段
        # （PC-099-3-layer-defense.md → PC-099-3）。中段純數字 = flat 號的描述
        # 段被誤吸，真實 ID 為 flat（PC-099），必須判 flat 才不繞過凍結 gate。
        ("PC-099-3", True),
        ("IMP-049-2", True),
        ("ARCH-020-5", True),
    ],
)
def test_is_flat_id(pattern_id, expected):
    assert hook.is_flat_id(pattern_id) is expected


# --- is_error_pattern_file：路徑 + 副檔名 filter ---
def test_is_error_pattern_file_md_in_dir():
    assert hook.is_error_pattern_file(
        ".claude/error-patterns/process-compliance/PC-099-x.md"
    )


def test_is_error_pattern_file_rejects_non_md():
    assert not hook.is_error_pattern_file(
        ".claude/error-patterns/_project-registry.yaml"
    )


def test_is_error_pattern_file_rejects_outside_dir():
    assert not hook.is_error_pattern_file("src/foo.md")


def test_is_error_pattern_file_rejects_empty():
    assert not hook.is_error_pattern_file("")


# --- decide：deny 分支（acceptance 0）---
def test_decide_deny_new_flat_pc(tmp_path):
    target = tmp_path / "error-patterns" / "process-compliance" / "PC-179-new.md"
    decision, reason, code = hook.decide("Write", {"file_path": str(target)})
    assert decision == "deny"
    assert code == hook.EXIT_BLOCK
    assert "PC-179" in reason
    assert "/error-pattern add" in reason  # 規則 4：引導正確路徑


def test_decide_deny_new_flat_imp(tmp_path):
    target = tmp_path / "error-patterns" / "implementation" / "IMP-099-x.md"
    decision, _, code = hook.decide("Write", {"file_path": str(target)})
    assert decision == "deny"
    assert code == hook.EXIT_BLOCK


def test_decide_deny_numeric_description_segment(tmp_path):
    """W1-036：數字開頭描述段（PC-099-3-layer-defense）不得繞過凍結 gate。

    extract_pattern_id 將 PC-099-3-layer-defense.md 過度匹配為 PC-099-3（3 段），
    舊 is_flat_id 誤判為前綴號放行。真實 ID 為 flat（PC-099），須 deny。
    """
    target = (
        tmp_path
        / "error-patterns"
        / "process-compliance"
        / "PC-099-3-layer-defense.md"
    )
    decision, reason, code = hook.decide("Write", {"file_path": str(target)})
    assert decision == "deny"
    assert code == hook.EXIT_BLOCK


# --- decide：allow 分支（acceptance 1）---
def test_decide_allow_new_prefix(tmp_path):
    target = tmp_path / "error-patterns" / "process-compliance" / "PC-V1-001-x.md"
    decision, _, code = hook.decide("Write", {"file_path": str(target)})
    assert decision == "allow"
    assert code == hook.EXIT_ALLOW


def test_decide_allow_edit_existing_flat(tmp_path):
    target_dir = tmp_path / "error-patterns" / "process-compliance"
    target_dir.mkdir(parents=True)
    target = target_dir / "PC-099-existing.md"
    target.write_text("x", encoding="utf-8")
    decision, _, code = hook.decide("Edit", {"file_path": str(target)})
    assert decision == "allow"
    assert code == hook.EXIT_ALLOW


def test_decide_allow_overwrite_existing_flat(tmp_path):
    # Write 覆蓋既有 flat 檔（非新建）→ allow
    target_dir = tmp_path / "error-patterns" / "process-compliance"
    target_dir.mkdir(parents=True)
    target = target_dir / "PC-001-existing.md"
    target.write_text("x", encoding="utf-8")
    decision, _, _ = hook.decide("Write", {"file_path": str(target)})
    assert decision == "allow"


def test_decide_allow_non_error_pattern_dir(tmp_path):
    target = tmp_path / "src" / "foo.md"
    decision, _, _ = hook.decide("Write", {"file_path": str(target)})
    assert decision == "allow"


def test_decide_allow_readme_no_id(tmp_path):
    target = tmp_path / "error-patterns" / "README.md"
    decision, _, _ = hook.decide("Write", {"file_path": str(target)})
    assert decision == "allow"


def test_decide_allow_non_write_tool():
    decision, _, code = hook.decide(
        "Read",
        {"file_path": ".claude/error-patterns/process-compliance/PC-179-x.md"},
    )
    assert decision == "allow"
    assert code == hook.EXIT_ALLOW


def test_decide_allow_empty_tool_input():
    decision, _, _ = hook.decide("Write", {})
    assert decision == "allow"


# --- subprocess 層：main()/stdin/emit 接線測試（W1-036，acceptance 1）---
def _run_hook_subprocess(stdin_obj):
    """以 uv shebang 真實啟動 hook，餵 JSON stdin，回傳 CompletedProcess。

    驗證 main() → read_json_from_stdin → decide → emit_hook_output → exit code
    的完整接線（純函式測試無法覆蓋的 IO 層）。
    """
    return subprocess.run(
        [str(_HOOK_PATH)],
        input=json.dumps(stdin_obj),
        capture_output=True,
        text=True,
    )


def _parse_hook_output(stdout):
    """解析 hook stdout JSON 並回傳 hookSpecificOutput（IMP-055 shape 驗證）。"""
    payload = json.loads(stdout)
    assert "hookSpecificOutput" in payload
    hso = payload["hookSpecificOutput"]
    assert hso["hookEventName"] == "PreToolUse"
    return hso


def test_subprocess_deny_new_flat(tmp_path):
    target = tmp_path / "error-patterns" / "process-compliance" / "PC-179-new.md"
    result = _run_hook_subprocess(
        {"tool_name": "Write", "tool_input": {"file_path": str(target)}}
    )
    assert result.returncode == hook.EXIT_BLOCK
    hso = _parse_hook_output(result.stdout)
    assert hso["permissionDecision"] == "deny"
    assert "PC-179" in result.stderr  # 規則 4：deny 雙通道（stderr 可見）


def test_subprocess_deny_numeric_description_segment(tmp_path):
    """W1-036：subprocess 層也須擋住數字開頭描述段檔名。"""
    target = (
        tmp_path
        / "error-patterns"
        / "process-compliance"
        / "PC-099-3-layer-defense.md"
    )
    result = _run_hook_subprocess(
        {"tool_name": "Write", "tool_input": {"file_path": str(target)}}
    )
    assert result.returncode == hook.EXIT_BLOCK
    hso = _parse_hook_output(result.stdout)
    assert hso["permissionDecision"] == "deny"


def test_subprocess_allow_prefix(tmp_path):
    target = tmp_path / "error-patterns" / "process-compliance" / "PC-V1-001-x.md"
    result = _run_hook_subprocess(
        {"tool_name": "Write", "tool_input": {"file_path": str(target)}}
    )
    assert result.returncode == hook.EXIT_ALLOW
    hso = _parse_hook_output(result.stdout)
    assert hso["permissionDecision"] == "allow"


def test_subprocess_allow_empty_stdin():
    """空 stdin 走 fallback allow 分支（仍須完整 hookSpecificOutput）。"""
    result = subprocess.run(
        [str(_HOOK_PATH)],
        input="",
        capture_output=True,
        text=True,
    )
    assert result.returncode == hook.EXIT_ALLOW
    hso = _parse_hook_output(result.stdout)
    assert hso["permissionDecision"] == "allow"
