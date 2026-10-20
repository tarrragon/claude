#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""context-depth-warning-hook.py 測試（0.20.0-W2-013）

涵蓋方案 A 實作規格：
  - transcript 解析：取最後一則 assistant entry 的 usage.cache_read_input_tokens
  - 閾值判定：cache_read >= THRESHOLD 才考慮觸發
  - 去重邏輯：state file 記 {session_id: last_warned_tier}，同 tier 不重複
  - 跨 tier 再提示：cache_read 跨入下一 tier（TIER_STEP）再觸發一次
  - graceful exit 0：payload 缺欄位 / transcript 讀不到 / state IO 失敗皆 exit 0
  - --self-test 分支與內嵌 _self_test() 全通過

永遠 exit 0（提示性 hook，禁 exit 2 阻擋 Stop）。
"""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK_PATH = REPO_ROOT / ".claude" / "hooks" / "context-depth-warning-hook.py"


def _load_hook_module():
    """動態載入 Hook 模組（檔名含 `-` 不能用一般 import）。"""
    spec = importlib.util.spec_from_file_location("context_depth_warning_hook", HOOK_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def hook_mod():
    return _load_hook_module()


def _write_transcript(tmp_path: Path, entries: list) -> Path:
    """寫 transcript JSONL，回傳路徑。"""
    p = tmp_path / "transcript.jsonl"
    with p.open("w", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(json.dumps(entry) + "\n")
    return p


def _assistant_entry(cache_read: int, input_tokens: int = 0, cache_creation: int = 0) -> dict:
    """構造一則含 usage 三欄位的 assistant entry。"""
    return {
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": "ok"}],
            "usage": {
                "input_tokens": input_tokens,
                "cache_creation_input_tokens": cache_creation,
                "cache_read_input_tokens": cache_read,
            },
        }
    }


# ---------------------------------------------------------------------------
# transcript 解析
# ---------------------------------------------------------------------------


def test_read_last_cache_read_basic(hook_mod, tmp_path):
    """取最後一則 assistant entry 的 cache_read。"""
    p = _write_transcript(
        tmp_path,
        [_assistant_entry(10_000), _assistant_entry(200_000)],
    )
    assert hook_mod.read_last_total_context(str(p)) == 200_000


def test_read_last_cache_read_skips_non_assistant(hook_mod, tmp_path):
    """非 assistant entry 不影響取值；取最後一則 assistant。"""
    entries = [
        _assistant_entry(50_000),
        {"message": {"role": "user", "content": "hi"}},
    ]
    p = _write_transcript(tmp_path, entries)
    assert hook_mod.read_last_total_context(str(p)) == 50_000


def test_read_last_cache_read_missing_file(hook_mod):
    """transcript 檔不存在 → None。"""
    assert hook_mod.read_last_total_context("/nonexistent/transcript.jsonl") is None


def test_read_last_cache_read_no_usage(hook_mod, tmp_path):
    """assistant entry 無 usage → None。"""
    p = _write_transcript(
        tmp_path,
        [{"message": {"role": "assistant", "content": "ok"}}],
    )
    assert hook_mod.read_last_total_context(str(p)) is None


# ---------------------------------------------------------------------------
# 閾值與 tier 判定
# ---------------------------------------------------------------------------


def test_tier_of(hook_mod):
    assert hook_mod.tier_of(0) == 0
    assert hook_mod.tier_of(hook_mod.TIER_STEP - 1) == 0
    assert hook_mod.tier_of(hook_mod.TIER_STEP) == 1
    assert hook_mod.tier_of(hook_mod.TIER_STEP * 3 + 5) == 3


def test_should_warn_below_threshold(hook_mod):
    """低於閾值不觸發。"""
    assert hook_mod.should_warn(hook_mod.THRESHOLD - 1, last_warned_tier=-1) is False


def test_should_warn_at_threshold_first_time(hook_mod):
    """到閾值且該 tier 未提示 → 觸發。"""
    cache_read = hook_mod.THRESHOLD
    assert hook_mod.should_warn(cache_read, last_warned_tier=-1) is True


def test_should_warn_same_tier_deduped(hook_mod):
    """同 tier 已提示 → 不重複。"""
    cache_read = hook_mod.THRESHOLD
    tier = hook_mod.tier_of(cache_read)
    assert hook_mod.should_warn(cache_read, last_warned_tier=tier) is False


def test_should_warn_next_tier_triggers_again(hook_mod):
    """跨下一 tier → 再次觸發。"""
    base = hook_mod.THRESHOLD
    base_tier = hook_mod.tier_of(base)
    deeper = base + hook_mod.TIER_STEP
    assert hook_mod.tier_of(deeper) > base_tier
    assert hook_mod.should_warn(deeper, last_warned_tier=base_tier) is True


# ---------------------------------------------------------------------------
# state 讀寫去重
# ---------------------------------------------------------------------------


def test_state_roundtrip(hook_mod, tmp_path):
    state_file = tmp_path / "state.json"
    assert hook_mod.load_state(state_file) == {}
    hook_mod.save_state(state_file, {"sess-1": 6})
    assert hook_mod.load_state(state_file) == {"sess-1": 6}


def test_load_state_corrupt_returns_empty(hook_mod, tmp_path):
    """state 檔損壞 → 回空 dict（graceful）。"""
    state_file = tmp_path / "state.json"
    state_file.write_text("not json", encoding="utf-8")
    assert hook_mod.load_state(state_file) == {}


# ---------------------------------------------------------------------------
# main graceful exit 0
# ---------------------------------------------------------------------------


def _run_hook(stdin_str: str, env=None):
    """以 subprocess 跑 hook，回傳 (returncode, stderr)。"""
    return _run_hook_full(stdin_str, env)[:2]


def _run_hook_full(stdin_str: str, env=None):
    """回傳 (returncode, stderr, stdout)。env 為額外環境變數。"""
    proc = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=stdin_str,
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )
    return proc.returncode, proc.stderr, proc.stdout


def test_main_empty_stdin_exits_0(hook_mod):
    rc, _ = _run_hook("")
    assert rc == 0


def test_main_invalid_json_exits_0(hook_mod):
    rc, _ = _run_hook("not json")
    assert rc == 0


def test_main_missing_transcript_path_exits_0(hook_mod):
    rc, _ = _run_hook(json.dumps({"session_id": "s1"}))
    assert rc == 0


def test_main_below_threshold_no_warning(hook_mod, tmp_path):
    p = _write_transcript(tmp_path, [_assistant_entry(10_000)])
    rc, stderr = _run_hook(
        json.dumps({"session_id": "s1", "transcript_path": str(p)})
    )
    assert rc == 0
    assert "context-depth-warning" not in stderr


def _payload(p, sid="sess-x"):
    return json.dumps({"session_id": sid, "transcript_path": str(p)})


def test_sum_of_three_usage_fields(hook_mod, tmp_path):
    """口徑為 input + cache_creation + cache_read 合計。"""
    p = _write_transcript(tmp_path, [_assistant_entry(300_000, 50_000, 60_000)])
    assert hook_mod.read_last_total_context(str(p)) == 410_000


def test_log_line_uses_total_field_name(hook_mod, tmp_path, monkeypatch):
    """日誌欄位名稱表達合計口徑：total=，不得沿用 cache_read=。"""
    import io

    p = _write_transcript(tmp_path, [_assistant_entry(300_000, 50_000, 60_000)])
    log_dir = tmp_path / "logs"
    monkeypatch.setattr(hook_mod, "LOG_DIR", log_dir)
    monkeypatch.setattr(hook_mod, "LOG_FILE", log_dir / "x.log")
    monkeypatch.setenv("CONTEXT_DEPTH_WARNING_STATE", str(tmp_path / "state.json"))
    monkeypatch.setattr(sys, "stdin", io.StringIO(_payload(p)))
    assert hook_mod.main() == 0
    text = (log_dir / "x.log").read_text(encoding="utf-8")
    assert "total=410000" in text
    assert "cache_read=" not in text


def test_above_threshold_emits_additional_context(hook_mod, tmp_path):
    """400K 以上輸出 additionalContext JSON，含 K 數、/compact、claude -n。"""
    p = _write_transcript(tmp_path, [_assistant_entry(410_000)])
    state_file = tmp_path / "state.json"
    rc, _, out = _run_hook_full(
        _payload(p), {"CONTEXT_DEPTH_WARNING_STATE": str(state_file)}
    )
    assert rc == 0
    ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "410K" in ctx and "/compact" in ctx and "claude -n" in ctx
    assert hook_mod.load_state(state_file).get("sess-x") is not None


def test_below_threshold_no_output(hook_mod, tmp_path):
    p = _write_transcript(tmp_path, [_assistant_entry(399_000)])
    rc, _, out = _run_hook_full(
        _payload(p), {"CONTEXT_DEPTH_WARNING_STATE": str(tmp_path / "s.json")}
    )
    assert rc == 0
    assert out.strip() == ""


def test_same_tier_not_repeated(hook_mod, tmp_path):
    p = _write_transcript(tmp_path, [_assistant_entry(410_000)])
    env = {"CONTEXT_DEPTH_WARNING_STATE": str(tmp_path / "s.json")}
    _, _, first = _run_hook_full(_payload(p), env)
    _, _, second = _run_hook_full(_payload(p), env)
    assert first.strip() != ""
    assert second.strip() == ""


def test_drop_below_threshold_resets_dedup(hook_mod, tmp_path):
    env = {"CONTEXT_DEPTH_WARNING_STATE": str(tmp_path / "s.json")}
    high = _write_transcript(tmp_path, [_assistant_entry(410_000)])
    _run_hook_full(_payload(high), env)
    low = _write_transcript(tmp_path, [_assistant_entry(50_000)])
    _run_hook_full(_payload(low), env)
    assert hook_mod.load_state(tmp_path / "s.json").get("sess-x") is None
    high = _write_transcript(tmp_path, [_assistant_entry(410_000)])
    _, _, again = _run_hook_full(_payload(high), env)
    assert again.strip() != ""


def test_env_override_threshold(hook_mod, tmp_path):
    p = _write_transcript(tmp_path, [_assistant_entry(120_000)])
    env = {
        "CONTEXT_DEPTH_WARNING_STATE": str(tmp_path / "s.json"),
        "CONTEXT_DEPTH_WARNING_THRESHOLD": "100000",
    }
    _, _, out = _run_hook_full(_payload(p), env)
    assert "120K" in json.loads(out)["hookSpecificOutput"]["additionalContext"]


# ---------------------------------------------------------------------------
# 內嵌 self-test
# ---------------------------------------------------------------------------


def test_embedded_self_test_passes(hook_mod):
    assert hook_mod._self_test() == []


def test_self_test_cli_exit_0():
    proc = subprocess.run(
        [sys.executable, str(HOOK_PATH), "--self-test"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
