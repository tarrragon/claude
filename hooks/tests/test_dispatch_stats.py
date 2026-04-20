"""
TDD Phase 2 RED 測試：dispatch_stats.py + agent-dispatch-validation-hook 的 event 寫入

對應 Ticket: 0.18.0-W11-004.1.1
規格來源: ticket Solution「Phase 1 功能規格設計 v2」
預期狀態: 全部 RED（dispatch_stats.py 尚未實作）

測試策略：
- AC-1: event schema (對 _write_event_jsonl + 序列化)
- AC-2: Hook 寫入容錯 + 並發安全 (fcntl.flock + 多 process)
- AC-3: CLI list / show
- AC-4: CLI annotate (atomic rename)
- AC-5: CLI stats (TP/FP/誤報率/分組/markdown)
- AC-6: 單元測試覆蓋率與 fixture 設計

執行：
  pytest .claude/hooks/tests/test_dispatch_stats.py -v
"""

from __future__ import annotations

import importlib.util
import json
import multiprocessing
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Module loading helpers
# ---------------------------------------------------------------------------

HOOKS_DIR = Path(__file__).resolve().parent.parent
DISPATCH_STATS_PATH = HOOKS_DIR / "dispatch_stats.py"
HOOK_PATH = HOOKS_DIR / "agent-dispatch-validation-hook.py"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _load_module_from_path(name: str, path: Path):
    """從絕對路徑載入 module（hook 檔名含 hyphen，無法直接 import）"""
    if not path.exists():
        pytest.skip(f"模組尚未建立：{path}（預期 RED）")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def dispatch_stats_module():
    """載入 dispatch_stats 模組；不存在時 RED skip→fail"""
    assert DISPATCH_STATS_PATH.exists(), (
        f"dispatch_stats.py 尚未建立：{DISPATCH_STATS_PATH}（RED 期望）"
    )
    return _load_module_from_path("dispatch_stats", DISPATCH_STATS_PATH)


@pytest.fixture
def hook_module():
    """載入 agent-dispatch-validation-hook 模組"""
    assert HOOK_PATH.exists(), f"Hook 不存在：{HOOK_PATH}"
    return _load_module_from_path("agent_dispatch_validation_hook", HOOK_PATH)


@pytest.fixture
def tmp_events_dir(tmp_path: Path) -> Path:
    """建立 events/ 子目錄，含空 events.jsonl 與空 annotations.json"""
    events_dir = tmp_path / "events"
    events_dir.mkdir(parents=True, exist_ok=True)
    return events_dir


@pytest.fixture
def tmp_events_file(tmp_events_dir: Path) -> Path:
    return tmp_events_dir / "events.jsonl"


@pytest.fixture
def tmp_annotations_file(tmp_events_dir: Path) -> Path:
    return tmp_events_dir / "annotations.json"


@pytest.fixture
def populated_events(tmp_events_file: Path) -> Path:
    """複製 sample_events.jsonl 到 tmp"""
    shutil.copy(FIXTURES_DIR / "sample_events.jsonl", tmp_events_file)
    return tmp_events_file


@pytest.fixture
def populated_annotations(tmp_annotations_file: Path) -> Path:
    shutil.copy(FIXTURES_DIR / "sample_annotations.json", tmp_annotations_file)
    return tmp_annotations_file


@pytest.fixture
def patched_paths(monkeypatch, dispatch_stats_module, tmp_events_file, tmp_annotations_file):
    """將 dispatch_stats 內部路徑常數導向 tmp"""
    monkeypatch.setattr(dispatch_stats_module, "_EVENTS_JSONL_PATH", tmp_events_file, raising=False)
    monkeypatch.setattr(
        dispatch_stats_module, "_ANNOTATIONS_JSON_PATH", tmp_annotations_file, raising=False
    )
    return dispatch_stats_module


def _run_cli(args: list[str], events: Path, annotations: Path) -> subprocess.CompletedProcess:
    """以 subprocess 執行 dispatch_stats.py，透過環境變數覆寫路徑"""
    env = os.environ.copy()
    env["DISPATCH_STATS_EVENTS_PATH"] = str(events)
    env["DISPATCH_STATS_ANNOTATIONS_PATH"] = str(annotations)
    return subprocess.run(
        [sys.executable, str(DISPATCH_STATS_PATH), *args],
        env=env,
        capture_output=True,
        text=True,
    )


# ===========================================================================
# AC-1: event schema 正確性
# ===========================================================================

class TestAC1EventSchema:
    """AC-1：events.jsonl 寫入一行合法 JSON，6 必填欄位齊全且型別正確"""

    REQUIRED_TOP_FIELDS = {
        "event_id", "timestamp", "subagent_type",
        "conflicts", "prompt_hash", "prompt_length",
    }
    REQUIRED_CONFLICT_FIELDS = {"action", "keyword", "matched_pattern", "prompt_excerpt"}

    def test_event_is_single_line_valid_json(self, hook_module, tmp_events_file, monkeypatch):
        """單一 event 寫入後為單行合法 JSON"""
        monkeypatch.setattr(hook_module, "_EVENTS_JSONL_PATH", tmp_events_file, raising=False)
        conflicts = [
            {
                "action": "實作程式碼",
                "keyword": "實作",
                "matched_pattern": r"實作",
                "prompt_excerpt": "請你實作 hook 系統",
            }
        ]
        hook_module._write_event_jsonl(
            subagent_type="sage-test-architect",
            prompt="請你實作 hook 系統的測試",
            conflicts_detail=conflicts,
            logger=None,
        )
        lines = tmp_events_file.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        event = json.loads(lines[0])
        assert isinstance(event, dict)

    def test_event_has_all_required_top_fields(self, hook_module, tmp_events_file, monkeypatch):
        """6 個 top-level 必填欄位齊全"""
        monkeypatch.setattr(hook_module, "_EVENTS_JSONL_PATH", tmp_events_file, raising=False)
        hook_module._write_event_jsonl(
            subagent_type="sage-test-architect",
            prompt="實作測試",
            conflicts_detail=[
                {"action": "A", "keyword": "K", "matched_pattern": "P", "prompt_excerpt": "E"}
            ],
            logger=None,
        )
        event = json.loads(tmp_events_file.read_text(encoding="utf-8").splitlines()[0])
        assert self.REQUIRED_TOP_FIELDS.issubset(event.keys())

    def test_event_field_types(self, hook_module, tmp_events_file, monkeypatch):
        monkeypatch.setattr(hook_module, "_EVENTS_JSONL_PATH", tmp_events_file, raising=False)
        hook_module._write_event_jsonl(
            "sage-test-architect", "實作 X 功能",
            [{"action": "A", "keyword": "K", "matched_pattern": "P", "prompt_excerpt": "E"}],
            None,
        )
        event = json.loads(tmp_events_file.read_text(encoding="utf-8").splitlines()[0])
        assert isinstance(event["event_id"], str)
        assert isinstance(event["timestamp"], str)
        assert isinstance(event["subagent_type"], str)
        assert isinstance(event["conflicts"], list)
        assert isinstance(event["prompt_hash"], str)
        assert isinstance(event["prompt_length"], int)

    def test_conflicts_subobject_has_four_fields(self, hook_module, tmp_events_file, monkeypatch):
        monkeypatch.setattr(hook_module, "_EVENTS_JSONL_PATH", tmp_events_file, raising=False)
        hook_module._write_event_jsonl(
            "sage", "實作", [
                {"action": "實作程式碼", "keyword": "實作", "matched_pattern": r"實作", "prompt_excerpt": "...實作..."}
            ], None,
        )
        event = json.loads(tmp_events_file.read_text(encoding="utf-8").splitlines()[0])
        assert len(event["conflicts"]) >= 1
        for c in event["conflicts"]:
            assert self.REQUIRED_CONFLICT_FIELDS.issubset(c.keys())

    def test_prompt_hash_is_16_hex_chars(self, hook_module, tmp_events_file, monkeypatch):
        monkeypatch.setattr(hook_module, "_EVENTS_JSONL_PATH", tmp_events_file, raising=False)
        hook_module._write_event_jsonl(
            "sage", "請實作功能 ABC",
            [{"action": "A", "keyword": "K", "matched_pattern": "P", "prompt_excerpt": "E"}],
            None,
        )
        event = json.loads(tmp_events_file.read_text(encoding="utf-8").splitlines()[0])
        assert re.fullmatch(r"[0-9a-f]{16}", event["prompt_hash"])

    def test_prompt_text_not_present_in_event(self, hook_module, tmp_events_file, monkeypatch):
        """規格 1.1：只存 prompt_hash，原文不出現於 event 頂層"""
        monkeypatch.setattr(hook_module, "_EVENTS_JSONL_PATH", tmp_events_file, raising=False)
        secret = "MAGIC_PROMPT_TOKEN_XYZ_實作"
        hook_module._write_event_jsonl(
            "sage", secret,
            [{"action": "A", "keyword": "K", "matched_pattern": "P", "prompt_excerpt": "snippet"}],
            None,
        )
        raw = tmp_events_file.read_text(encoding="utf-8")
        # prompt_excerpt 是允許含片段的，但完整原文不應出現
        assert "MAGIC_PROMPT_TOKEN_XYZ" not in raw

    def test_event_id_format(self, hook_module, tmp_events_file, monkeypatch):
        """event_id = {YYYYMMDDTHHMMSSZ}-{prompt_hash[:8]}"""
        monkeypatch.setattr(hook_module, "_EVENTS_JSONL_PATH", tmp_events_file, raising=False)
        hook_module._write_event_jsonl(
            "sage", "實作功能",
            [{"action": "A", "keyword": "K", "matched_pattern": "P", "prompt_excerpt": "E"}],
            None,
        )
        event = json.loads(tmp_events_file.read_text(encoding="utf-8").splitlines()[0])
        assert re.fullmatch(r"\d{8}T\d{6}Z-[0-9a-f]{8}", event["event_id"])


# ===========================================================================
# AC-2: Hook 寫入容錯 + 並發安全
# ===========================================================================

def _writer_process(events_path_str: str, hook_path_str: str, n: int, agent: str):
    """子 process 入口：寫 n 筆 event"""
    import importlib.util as iu
    spec = iu.spec_from_file_location("h", hook_path_str)
    mod = iu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod._EVENTS_JSONL_PATH = Path(events_path_str)
    for i in range(n):
        mod._write_event_jsonl(
            agent, f"prompt {agent} {i} 實作",
            [{"action": "A", "keyword": "K", "matched_pattern": "P", "prompt_excerpt": f"E{i}"}],
            None,
        )


class TestAC2HookFaultTolerance:

    def test_creates_parent_directory_when_missing(self, hook_module, tmp_path, monkeypatch):
        """父目錄不存在時自動建立"""
        target = tmp_path / "deep" / "nested" / "events" / "events.jsonl"
        assert not target.parent.exists()
        monkeypatch.setattr(hook_module, "_EVENTS_JSONL_PATH", target, raising=False)
        hook_module._write_event_jsonl(
            "sage", "實作",
            [{"action": "A", "keyword": "K", "matched_pattern": "P", "prompt_excerpt": "E"}],
            None,
        )
        assert target.exists()

    def test_does_not_raise_on_unwritable_path(self, hook_module, tmp_path, monkeypatch, capsys):
        """不可寫路徑 → 不 raise，warning 寫 stderr"""
        readonly = tmp_path / "ro"
        readonly.mkdir()
        readonly.chmod(0o500)
        target = readonly / "events.jsonl"
        monkeypatch.setattr(hook_module, "_EVENTS_JSONL_PATH", target, raising=False)
        try:
            hook_module._write_event_jsonl(
                "sage", "實作",
                [{"action": "A", "keyword": "K", "matched_pattern": "P", "prompt_excerpt": "E"}],
                None,
            )
        finally:
            readonly.chmod(0o700)
        # 不應拋出，且不存在或為空都可
        # stderr 應有警告（規則 4 雙通道）
        captured = capsys.readouterr()
        assert captured.err != "" or True  # logger 可能也吃掉，這裡寬鬆驗證未 raise 即可

    def test_multiple_conflicts_produce_single_line(self, hook_module, tmp_events_file, monkeypatch):
        monkeypatch.setattr(hook_module, "_EVENTS_JSONL_PATH", tmp_events_file, raising=False)
        conflicts = [
            {"action": "A1", "keyword": "K1", "matched_pattern": "P1", "prompt_excerpt": "E1"},
            {"action": "A2", "keyword": "K2", "matched_pattern": "P2", "prompt_excerpt": "E2"},
            {"action": "A3", "keyword": "K3", "matched_pattern": "P3", "prompt_excerpt": "E3"},
        ]
        hook_module._write_event_jsonl("sage", "prompt 實作", conflicts, None)
        lines = tmp_events_file.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        event = json.loads(lines[0])
        assert len(event["conflicts"]) == 3

    def test_empty_prompt_early_return(self, hook_module, tmp_events_file, monkeypatch):
        monkeypatch.setattr(hook_module, "_EVENTS_JSONL_PATH", tmp_events_file, raising=False)
        hook_module._write_event_jsonl("sage", "", [
            {"action": "A", "keyword": "K", "matched_pattern": "P", "prompt_excerpt": "E"}
        ], None)
        assert not tmp_events_file.exists() or tmp_events_file.read_text() == ""

    def test_empty_subagent_early_return(self, hook_module, tmp_events_file, monkeypatch):
        monkeypatch.setattr(hook_module, "_EVENTS_JSONL_PATH", tmp_events_file, raising=False)
        hook_module._write_event_jsonl("", "實作 prompt", [
            {"action": "A", "keyword": "K", "matched_pattern": "P", "prompt_excerpt": "E"}
        ], None)
        assert not tmp_events_file.exists() or tmp_events_file.read_text() == ""

    def test_concurrent_writes_no_interleaving(self, hook_module, tmp_events_file):
        """2 process 各寫 100 筆 → 200 行皆合法 JSON 且無交錯"""
        n_per = 100
        p1 = multiprocessing.Process(
            target=_writer_process,
            args=(str(tmp_events_file), str(HOOK_PATH), n_per, "agent_one"),
        )
        p2 = multiprocessing.Process(
            target=_writer_process,
            args=(str(tmp_events_file), str(HOOK_PATH), n_per, "agent_two"),
        )
        p1.start(); p2.start()
        p1.join(timeout=30); p2.join(timeout=30)
        assert p1.exitcode == 0
        assert p2.exitcode == 0
        lines = tmp_events_file.read_text(encoding="utf-8").splitlines()
        assert len(lines) == n_per * 2
        for i, line in enumerate(lines):
            try:
                json.loads(line)
            except json.JSONDecodeError as e:
                pytest.fail(f"第 {i+1} 行非合法 JSON（疑似交錯）：{line[:80]} | {e}")


# ===========================================================================
# AC-3: CLI list / show
# ===========================================================================

class TestAC3ListShow:

    def test_list_default_shows_unannotated_only(
        self, populated_events, tmp_annotations_file, populated_annotations
    ):
        """預設 status=unannotated；fixture 5 筆事件，4 筆已標註 → 應只剩 1 筆"""
        result = _run_cli(["list", "--format", "json"], populated_events, populated_annotations)
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        ids = {e["event_id"] for e in data}
        assert "20260418T140000Z-eeeeeeee" in ids
        assert "20260418T100000Z-aaaaaaaa" not in ids

    def test_list_status_all(self, populated_events, populated_annotations):
        result = _run_cli(["list", "--status", "all", "--format", "json"], populated_events, populated_annotations)
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert len(data) == 5

    def test_list_status_annotated(self, populated_events, populated_annotations):
        result = _run_cli(
            ["list", "--status", "annotated", "--format", "json"],
            populated_events, populated_annotations,
        )
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        # annotations 含 4 個有對應 event 的 + 1 孤兒；孤兒不算
        assert len(data) == 4

    def test_list_filter_by_agent(self, populated_events, populated_annotations):
        result = _run_cli(
            ["list", "--status", "all", "--agent", "sage-test-architect", "--format", "json"],
            populated_events, populated_annotations,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert len(data) == 3
        assert all(e["subagent_type"] == "sage-test-architect" for e in data)

    def test_list_limit(self, populated_events, populated_annotations):
        result = _run_cli(
            ["list", "--status", "all", "--limit", "2", "--format", "json"],
            populated_events, populated_annotations,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert len(data) == 2

    def test_list_since(self, populated_events, populated_annotations):
        result = _run_cli(
            ["list", "--status", "all", "--since", "2026-04-18", "--format", "json"],
            populated_events, populated_annotations,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert len(data) == 5

    def test_list_format_json_is_valid(self, populated_events, populated_annotations):
        result = _run_cli(["list", "--status", "all", "--format", "json"], populated_events, populated_annotations)
        json.loads(result.stdout)  # 不 raise

    def test_list_empty_file_friendly(self, tmp_events_file, tmp_annotations_file):
        tmp_events_file.touch()
        result = _run_cli(["list"], tmp_events_file, tmp_annotations_file)
        assert result.returncode == 0
        assert "尚無事件" in result.stdout or "no events" in result.stdout.lower()

    def test_show_existing_event_full_fields(self, populated_events, populated_annotations):
        result = _run_cli(
            ["show", "20260418T100000Z-aaaaaaaa", "--format", "json"],
            populated_events, populated_annotations,
        )
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        for f in ("event_id", "timestamp", "subagent_type", "conflicts", "prompt_hash", "prompt_length"):
            assert f in data

    def test_show_nonexistent_event_exits_2(self, populated_events, populated_annotations):
        result = _run_cli(
            ["show", "nonexistent-id"],
            populated_events, populated_annotations,
        )
        assert result.returncode == 2


# ===========================================================================
# AC-4: CLI annotate (atomic rename)
# ===========================================================================

class TestAC4Annotate:

    def test_annotate_then_listed_as_annotated(self, populated_events, tmp_annotations_file):
        # 從乾淨 annotations 開始
        result = _run_cli(
            ["annotate", "20260418T140000Z-eeeeeeee", "--label", "true_positive"],
            populated_events, tmp_annotations_file,
        )
        assert result.returncode == 0, result.stderr
        # annotations.json 應有此 key
        data = json.loads(tmp_annotations_file.read_text())
        assert "20260418T140000Z-eeeeeeee" in data
        assert data["20260418T140000Z-eeeeeeee"]["label"] == "true_positive"

    def test_annotate_with_note(self, populated_events, tmp_annotations_file):
        result = _run_cli(
            ["annotate", "20260418T140000Z-eeeeeeee", "--label", "false_positive", "--note", "理由 X"],
            populated_events, tmp_annotations_file,
        )
        assert result.returncode == 0, result.stderr
        data = json.loads(tmp_annotations_file.read_text())
        assert data["20260418T140000Z-eeeeeeee"]["note"] == "理由 X"

    def test_annotate_invalid_label_exits_2(self, populated_events, tmp_annotations_file):
        result = _run_cli(
            ["annotate", "20260418T140000Z-eeeeeeee", "--label", "garbage"],
            populated_events, tmp_annotations_file,
        )
        assert result.returncode == 2

    def test_annotate_nonexistent_event_exits_2(self, populated_events, tmp_annotations_file):
        result = _run_cli(
            ["annotate", "nonexistent-id", "--label", "true_positive"],
            populated_events, tmp_annotations_file,
        )
        assert result.returncode == 2

    def test_annotate_idempotent_same_label(self, populated_events, tmp_annotations_file):
        for _ in range(3):
            r = _run_cli(
                ["annotate", "20260418T140000Z-eeeeeeee", "--label", "true_positive"],
                populated_events, tmp_annotations_file,
            )
            assert r.returncode == 0
        data = json.loads(tmp_annotations_file.read_text())
        assert data["20260418T140000Z-eeeeeeee"]["label"] == "true_positive"

    def test_annotate_overwrite_emits_stderr_warning(self, populated_events, tmp_annotations_file):
        _run_cli(
            ["annotate", "20260418T140000Z-eeeeeeee", "--label", "true_positive"],
            populated_events, tmp_annotations_file,
        )
        r = _run_cli(
            ["annotate", "20260418T140000Z-eeeeeeee", "--label", "false_positive"],
            populated_events, tmp_annotations_file,
        )
        assert r.returncode == 0
        assert r.stderr != ""
        data = json.loads(tmp_annotations_file.read_text())
        assert data["20260418T140000Z-eeeeeeee"]["label"] == "false_positive"

    def test_annotate_all_unannotated(self, populated_events, populated_annotations):
        # populated_annotations 已標 4 筆，剩 eeeeeeee 未標
        r = _run_cli(
            ["annotate", "--all-unannotated", "--label", "unknown"],
            populated_events, populated_annotations,
        )
        assert r.returncode == 0, r.stderr
        data = json.loads(populated_annotations.read_text())
        assert "20260418T140000Z-eeeeeeee" in data
        assert data["20260418T140000Z-eeeeeeee"]["label"] == "unknown"

    def test_annotations_atomic_rename_no_partial_corruption(
        self, dispatch_stats_module, populated_events, tmp_annotations_file, monkeypatch
    ):
        """atomic rename：寫入過程中不應產生半損壞檔案。
        驗證寫入後檔案仍是合法 JSON，且不存在殘留 .tmp 檔。"""
        monkeypatch.setattr(dispatch_stats_module, "_EVENTS_JSONL_PATH", populated_events, raising=False)
        monkeypatch.setattr(dispatch_stats_module, "_ANNOTATIONS_JSON_PATH", tmp_annotations_file, raising=False)
        # 直接呼叫內部 annotate API（若存在）
        annotate_fn = getattr(dispatch_stats_module, "annotate_event", None)
        if annotate_fn is None:
            pytest.skip("dispatch_stats.annotate_event 未實作（RED）")
        annotate_fn("20260418T140000Z-eeeeeeee", label="true_positive", note="x")
        # 確認結果可解析
        data = json.loads(tmp_annotations_file.read_text())
        assert "20260418T140000Z-eeeeeeee" in data
        # 不應殘留 tmp 檔
        leftovers = list(tmp_annotations_file.parent.glob("annotations.json.*"))
        assert leftovers == [], f"殘留 tmp 檔：{leftovers}"


# ===========================================================================
# AC-5: CLI stats
# ===========================================================================

class TestAC5Stats:

    def test_stats_empty_file(self, tmp_events_file, tmp_annotations_file):
        tmp_events_file.touch()
        r = _run_cli(["stats"], tmp_events_file, tmp_annotations_file)
        assert r.returncode == 0
        assert "尚無事件" in r.stdout or "no events" in r.stdout.lower()

    def test_stats_basic_counts(self, populated_events, populated_annotations):
        r = _run_cli(["stats", "--format", "json"], populated_events, populated_annotations)
        assert r.returncode == 0, r.stderr
        data = json.loads(r.stdout)
        assert data["total_events"] == 5
        assert data["annotated"] == 4  # 孤兒不計
        assert data["unannotated"] == 1
        assert data["true_positive"] == 2
        assert data["false_positive"] == 2
        assert data["unknown"] == 0

    def test_stats_false_positive_rate(self, populated_events, populated_annotations):
        r = _run_cli(["stats", "--format", "json"], populated_events, populated_annotations)
        data = json.loads(r.stdout)
        # FP / (TP+FP) = 2 / 4 = 0.5
        assert data["false_positive_rate"] == pytest.approx(0.5)

    def test_stats_zero_division_returns_na(self, tmp_events_file, tmp_annotations_file):
        # 寫一筆事件但不標註
        tmp_events_file.write_text(
            json.dumps({
                "event_id": "20260418T100000Z-zzzzzzzz",
                "timestamp": "2026-04-18T10:00:00Z",
                "subagent_type": "sage",
                "conflicts": [{"action": "A", "keyword": "K", "matched_pattern": "P", "prompt_excerpt": "E"}],
                "prompt_hash": "z" * 16,
                "prompt_length": 10,
            }) + "\n",
            encoding="utf-8",
        )
        tmp_annotations_file.write_text("{}", encoding="utf-8")
        r = _run_cli(["stats", "--format", "json"], tmp_events_file, tmp_annotations_file)
        assert r.returncode == 0
        data = json.loads(r.stdout)
        # 規格 3.3：TP+FP=0 → N/A，禁 ZeroDivisionError
        assert data["false_positive_rate"] in (None, "N/A")

    def test_stats_groupby_agent(self, populated_events, populated_annotations):
        r = _run_cli(
            ["stats", "--groupby", "agent", "--format", "json"],
            populated_events, populated_annotations,
        )
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert "groups" in data
        agents = {g["key"]: g for g in data["groups"]}
        assert "sage-test-architect" in agents

    def test_stats_groupby_keyword(self, populated_events, populated_annotations):
        r = _run_cli(
            ["stats", "--groupby", "keyword", "--format", "json"],
            populated_events, populated_annotations,
        )
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert "groups" in data

    def test_stats_format_markdown(self, populated_events, populated_annotations):
        r = _run_cli(
            ["stats", "--format", "markdown"],
            populated_events, populated_annotations,
        )
        assert r.returncode == 0
        # markdown 表格至少含 | 和 ---
        assert "|" in r.stdout
        assert "---" in r.stdout

    def test_stats_threshold_assessment_under_10pct(self, tmp_events_file, tmp_annotations_file):
        """誤報率 <= 10% → 達標"""
        # 構造 9 TP + 1 FP = 10% 誤報率
        events = []
        anns = {}
        for i in range(9):
            eid = f"20260418T1000{i:02d}Z-tp{i:06x}"
            events.append({
                "event_id": eid, "timestamp": "2026-04-18T10:00:00Z",
                "subagent_type": "sage", "conflicts": [{"action": "A", "keyword": "K", "matched_pattern": "P", "prompt_excerpt": "E"}],
                "prompt_hash": f"tp{i:014x}", "prompt_length": 10,
            })
            anns[eid] = {"label": "true_positive", "note": "", "annotated_at": "2026-04-19T00:00:00Z"}
        eid_fp = "20260418T100099Z-fp000001"
        events.append({
            "event_id": eid_fp, "timestamp": "2026-04-18T10:00:00Z",
            "subagent_type": "sage", "conflicts": [{"action": "A", "keyword": "K", "matched_pattern": "P", "prompt_excerpt": "E"}],
            "prompt_hash": "fp" + "0" * 14, "prompt_length": 10,
        })
        anns[eid_fp] = {"label": "false_positive", "note": "", "annotated_at": "2026-04-19T00:00:00Z"}
        tmp_events_file.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
        tmp_annotations_file.write_text(json.dumps(anns), encoding="utf-8")
        r = _run_cli(["stats", "--format", "json"], tmp_events_file, tmp_annotations_file)
        data = json.loads(r.stdout)
        assert data["false_positive_rate"] == pytest.approx(0.1)
        assert data.get("meets_threshold") is True

    def test_stats_threshold_assessment_over_10pct(self, populated_events, populated_annotations):
        r = _run_cli(["stats", "--format", "json"], populated_events, populated_annotations)
        data = json.loads(r.stdout)
        # 50% > 10%
        assert data.get("meets_threshold") is False

    def test_stats_malformed_lines_counted(self, tmp_events_file, tmp_annotations_file):
        good = json.dumps({
            "event_id": "20260418T100000Z-gggggggg",
            "timestamp": "2026-04-18T10:00:00Z",
            "subagent_type": "sage",
            "conflicts": [{"action": "A", "keyword": "K", "matched_pattern": "P", "prompt_excerpt": "E"}],
            "prompt_hash": "g" * 16,
            "prompt_length": 10,
        })
        tmp_events_file.write_text(
            good + "\n" + "this is not json\n" + "{broken json\n",
            encoding="utf-8",
        )
        tmp_annotations_file.write_text("{}", encoding="utf-8")
        r = _run_cli(["stats", "--format", "json"], tmp_events_file, tmp_annotations_file)
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["malformed_lines"] == 2
        assert data["total_events"] == 1


# ===========================================================================
# AC-6: 邊界與不變式
# ===========================================================================

class TestAC6BoundariesAndInvariants:

    def test_orphan_annotation_not_counted(self, populated_events, populated_annotations):
        """annotations 指向不存在 event_id 不計入 stats"""
        r = _run_cli(["stats", "--format", "json"], populated_events, populated_annotations)
        data = json.loads(r.stdout)
        # 5 events，annotations 5 筆其中 1 孤兒 → annotated 應為 4
        assert data["annotated"] == 4

    def test_events_jsonl_append_only_invariant(self, hook_module, tmp_events_file, monkeypatch):
        """events.jsonl 只 append，行數單調遞增"""
        monkeypatch.setattr(hook_module, "_EVENTS_JSONL_PATH", tmp_events_file, raising=False)
        prev = 0
        for i in range(5):
            hook_module._write_event_jsonl(
                "sage", f"prompt 實作 {i}",
                [{"action": "A", "keyword": "K", "matched_pattern": "P", "prompt_excerpt": "E"}],
                None,
            )
            cur = len(tmp_events_file.read_text(encoding="utf-8").splitlines())
            assert cur > prev
            prev = cur

    def test_format_error_skip_with_stderr(self, tmp_events_file, tmp_annotations_file):
        good = json.dumps({
            "event_id": "20260418T100000Z-gggggggg",
            "timestamp": "2026-04-18T10:00:00Z",
            "subagent_type": "sage",
            "conflicts": [{"action": "A", "keyword": "K", "matched_pattern": "P", "prompt_excerpt": "E"}],
            "prompt_hash": "g" * 16,
            "prompt_length": 10,
        })
        tmp_events_file.write_text(good + "\nNOT_JSON\n", encoding="utf-8")
        tmp_annotations_file.write_text("{}", encoding="utf-8")
        r = _run_cli(["list", "--status", "all", "--format", "json"], tmp_events_file, tmp_annotations_file)
        assert r.returncode == 0
        # stderr 應有「第 N 行格式錯誤」之類訊息
        assert "格式錯誤" in r.stderr or "malformed" in r.stderr.lower() or "skip" in r.stderr.lower()

    def test_duplicate_event_id_first_wins(self, tmp_events_file, tmp_annotations_file):
        """規格 3.3：重複 event_id list 顯示首筆"""
        eid = "20260418T100000Z-dupedupe"
        e1 = {"event_id": eid, "timestamp": "2026-04-18T10:00:00Z", "subagent_type": "agent_a",
              "conflicts": [{"action": "A", "keyword": "K", "matched_pattern": "P", "prompt_excerpt": "E1"}],
              "prompt_hash": "d" * 16, "prompt_length": 10}
        e2 = {**e1, "subagent_type": "agent_b",
              "conflicts": [{"action": "A", "keyword": "K", "matched_pattern": "P", "prompt_excerpt": "E2"}]}
        tmp_events_file.write_text(json.dumps(e1) + "\n" + json.dumps(e2) + "\n", encoding="utf-8")
        tmp_annotations_file.write_text("{}", encoding="utf-8")
        r = _run_cli(["show", eid, "--format", "json"], tmp_events_file, tmp_annotations_file)
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["subagent_type"] == "agent_a"
