"""Unit tests for lib.transcript_tail_reader (W11-004.11)。"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path

import pytest

# 加入 hooks/ 路徑以便 import lib.transcript_tail_reader
HOOKS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS_DIR))

from lib import transcript_tail_reader as ttr  # noqa: E402


@pytest.fixture
def logger():
    lg = logging.getLogger("test_transcript_tail_reader")
    lg.setLevel(logging.DEBUG)
    return lg


@pytest.fixture(autouse=True)
def _clear_cache():
    ttr.clear_cache()
    yield
    ttr.clear_cache()


def _write_jsonl(path: Path, records):
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _append_jsonl(path: Path, records):
    with path.open("a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


# --- 基礎讀取 ---

def test_returns_none_for_missing_path(logger):
    assert ttr.read_last_assistant_text(None, logger) is None
    assert ttr.read_last_assistant_text("", logger) is None


def test_returns_none_for_nonexistent_file(tmp_path, logger):
    p = tmp_path / "missing.jsonl"
    assert ttr.read_last_assistant_text(str(p), logger) is None


def test_reads_string_content(tmp_path, logger):
    p = tmp_path / "session.jsonl"
    _write_jsonl(p, [
        {"message": {"role": "user", "content": "hi"}},
        {"message": {"role": "assistant", "content": "hello world"}},
    ])
    assert ttr.read_last_assistant_text(str(p), logger) == "hello world"


def test_reads_block_content(tmp_path, logger):
    p = tmp_path / "session.jsonl"
    _write_jsonl(p, [
        {"message": {"role": "assistant", "content": [
            {"type": "text", "text": "part1"},
            {"type": "tool_use", "name": "x"},
            {"type": "text", "text": "part2"},
        ]}},
    ])
    assert ttr.read_last_assistant_text(str(p), logger) == "part1\npart2"


def test_returns_last_assistant_when_multiple(tmp_path, logger):
    p = tmp_path / "session.jsonl"
    _write_jsonl(p, [
        {"message": {"role": "assistant", "content": "first"}},
        {"message": {"role": "user", "content": "q"}},
        {"message": {"role": "assistant", "content": "second"}},
    ])
    assert ttr.read_last_assistant_text(str(p), logger) == "second"


def test_skips_malformed_lines(tmp_path, logger):
    p = tmp_path / "session.jsonl"
    p.write_text(
        '{"message": {"role": "assistant", "content": "ok"}}\n'
        "this-is-not-json\n"
        "\n",
        encoding="utf-8",
    )
    assert ttr.read_last_assistant_text(str(p), logger) == "ok"


def test_returns_none_when_no_assistant(tmp_path, logger):
    p = tmp_path / "session.jsonl"
    _write_jsonl(p, [
        {"message": {"role": "user", "content": "hi"}},
    ])
    assert ttr.read_last_assistant_text(str(p), logger) is None


# --- 快取機制 ---

def test_cache_hit_avoids_rescan(tmp_path, logger, monkeypatch):
    p = tmp_path / "session.jsonl"
    _write_jsonl(p, [
        {"message": {"role": "assistant", "content": "v1"}},
    ])
    assert ttr.read_last_assistant_text(str(p), logger) == "v1"

    # 第二次：檔案無變動 → 不應呼叫 _scan_forward_from
    sentinel = {"called": False}
    orig = ttr._scan_forward_from

    def spy(path, start):
        sentinel["called"] = True
        return orig(path, start)

    monkeypatch.setattr(ttr, "_scan_forward_from", spy)
    assert ttr.read_last_assistant_text(str(p), logger) == "v1"
    assert sentinel["called"] is False, "命中快取時不應重新掃描"


def test_cache_incremental_read_after_append(tmp_path, logger):
    p = tmp_path / "session.jsonl"
    _write_jsonl(p, [
        {"message": {"role": "assistant", "content": "old"}},
    ])
    assert ttr.read_last_assistant_text(str(p), logger) == "old"

    # mtime 解析度通常為 ns 級，但部分檔案系統較粗。確保有變動：
    time.sleep(0.01)
    _append_jsonl(p, [
        {"message": {"role": "user", "content": "q"}},
        {"message": {"role": "assistant", "content": "new"}},
    ])
    # 若 mtime 沒推進，手動調整以確保快取會被視為失效或增量
    os.utime(p, None)

    assert ttr.read_last_assistant_text(str(p), logger) == "new"


def test_cache_invalidates_on_truncation(tmp_path, logger):
    p = tmp_path / "session.jsonl"
    _write_jsonl(p, [
        {"message": {"role": "assistant", "content": "long-msg"}},
        {"message": {"role": "assistant", "content": "another-long-msg"}},
    ])
    assert ttr.read_last_assistant_text(str(p), logger) == "another-long-msg"

    # 截斷重寫（size 變小 → 快取必須失效，重新全檔掃描）
    time.sleep(0.01)
    _write_jsonl(p, [
        {"message": {"role": "assistant", "content": "fresh"}},
    ])
    os.utime(p, None)

    assert ttr.read_last_assistant_text(str(p), logger) == "fresh"


def test_clear_cache(tmp_path, logger):
    p = tmp_path / "session.jsonl"
    _write_jsonl(p, [
        {"message": {"role": "assistant", "content": "x"}},
    ])
    ttr.read_last_assistant_text(str(p), logger)
    assert len(ttr._OFFSET_CACHE) == 1
    ttr.clear_cache()
    assert len(ttr._OFFSET_CACHE) == 0
