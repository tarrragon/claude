"""create 以所附 --dedup-keywords 實際執行 dedup 並把結果寫入〈查重紀錄〉。

分層：
- A：dedup_runner（解析報告、失敗降級），runner 可注入，不打 gh／網路
- B：_build_and_save_ticket 接線（dedup_runner.run_dedup 以 mock 取代）
E1 對照：同一 config 在有／無關鍵字下產物不同；E2 正向：失敗輸入確實產生『查重未完成』。
"""
from __future__ import annotations

import subprocess
from types import SimpleNamespace

from ticket_system.commands import create as create_mod
from ticket_system.lib import dedup_runner
from ticket_system.lib.dedup_runner import DedupOutcome

# 模組載入時先取真實函式：conftest 的 autouse 會把 run_dedup 換成 mock
_REAL_RUN_DEDUP = dedup_runner.run_dedup

REPORT = """[framework-issue] 查重關鍵字集合（1 組）：['閘門 dedup']

## 關鍵字「閘門 dedup」（2 則命中）
  - #102 [open] 查重閘門缺口
    https://example/102
    命中詞：閘門｜命中位置：title
  - #105 [closed] dedup 範本
    https://example/105
    命中詞：dedup｜命中位置：body

命中不等於重複
查詢失敗略過的 token 數：0
"""


def _fake_runner(stdout="", returncode=0, stderr="", exc=None):
    def runner(cmd, **kwargs):
        if exc:
            raise exc
        return SimpleNamespace(stdout=stdout, returncode=returncode, stderr=stderr)

    return runner


class TestRunDedup:
    def test_parses_hits_number_and_title(self):
        out = _REAL_RUN_DEDUP(["閘門 dedup"], runner=_fake_runner(REPORT))
        assert out.hits == [(102, "查重閘門缺口"), (105, "dedup 範本")]
        assert out.error is None

    def test_cmd_uses_dedup_subcommand_with_keywords(self):
        seen = {}

        def runner(cmd, **kwargs):
            seen["cmd"] = cmd
            return SimpleNamespace(stdout="", returncode=0, stderr="")

        _REAL_RUN_DEDUP(["a", "b c"], runner=runner)
        assert seen["cmd"][-4:] == ["dedup", "--keywords", "a", "b c"]

    def test_timeout_becomes_error_and_warns(self, capsys):
        exc = subprocess.TimeoutExpired(cmd="x", timeout=1)
        out = _REAL_RUN_DEDUP(["k"], runner=_fake_runner(exc=exc))
        assert out.hits == [] and "TimeoutExpired" in out.error
        assert "查重未完成" in capsys.readouterr().err

    def test_nonzero_exit_becomes_error(self, capsys):
        out = _REAL_RUN_DEDUP(
            ["k"], runner=_fake_runner(returncode=1, stderr="gh: offline")
        )
        assert "exit 1" in out.error and "gh: offline" in out.error
        assert "查重未完成" in capsys.readouterr().err

    def test_skipped_tokens_reported_as_error_with_hits_kept(self, capsys):
        report = REPORT.replace("略過的 token 數：0", "略過的 token 數：2")
        out = _REAL_RUN_DEDUP(["k"], runner=_fake_runner(report))
        assert len(out.hits) == 2 and "2 個" in out.error
        assert out.partial is True
        assert "查重部分未完成" in capsys.readouterr().err

    def test_failure_also_logged(self, caplog):
        exc = subprocess.TimeoutExpired(cmd="x", timeout=1)
        with caplog.at_level("WARNING"):
            _REAL_RUN_DEDUP(["k"], runner=_fake_runner(exc=exc))
        assert any("查重未完成" in r.getMessage() for r in caplog.records)

    def test_partial_label_differs_from_full_failure(self, monkeypatch, tmp_path):
        partial = DedupOutcome(hits=[(1, "x")], error="2 個", partial=True)
        full = DedupOutcome(error="boom")
        body_p, _ = _build(monkeypatch, tmp_path, ["k"], partial)
        (tmp_path / "f").mkdir()
        body_f, _ = _build(monkeypatch, tmp_path / "f", ["k"], full)
        assert "查重部分未完成：2 個" in body_p
        assert "查重部分未完成" not in body_f and "查重未完成：boom" in body_f


def _config():
    return {
        "type": "IMP",
        "title": "t",
        "what": "t",
        "who": "thyme-python-developer",
        "ticket_type": "IMP",
        "priority": "P2",
        "when": "w",
        "where_layer": "x",
        "where_files": [".claude/hooks/a.py"],
        "why": "w",
        "how_task_type": "Implementation",
        "how_strategy": "s",
        "acceptance": ["a"],
        "version": "0.1.0",
        "wave": 1,
        "ticket_id": "0.1.0-W1-001",
    }


def _build(monkeypatch, tmp_path, dedup_keywords, outcome):
    path = tmp_path / "0.1.0-W1-001.md"
    saved = {}
    monkeypatch.setattr(create_mod, "get_tickets_dir", lambda v: tmp_path)
    monkeypatch.setattr(create_mod, "get_ticket_path", lambda v, t: path)

    def save(ticket, p):
        saved["body"] = ticket["_body"]
        p.write_text("x", encoding="utf-8")

    monkeypatch.setattr(create_mod, "save_ticket", save)
    calls = []

    def fake_run(keywords, **_kw):
        calls.append(keywords)
        return outcome

    monkeypatch.setattr(dedup_runner, "run_dedup", fake_run)
    cfg = _config()
    cfg["dedup_keywords"] = dedup_keywords
    create_mod._build_and_save_ticket("0.1.0", "0.1.0-W1-001", cfg)
    return saved["body"], calls


class TestCreateWiring:
    def test_hits_written_to_record(self, monkeypatch, tmp_path):
        outcome = DedupOutcome(hits=[(102, "查重閘門缺口")])
        body, calls = _build(monkeypatch, tmp_path, ["閘門"], outcome)
        assert calls == [["閘門"]]
        assert "### 查重紀錄" in body
        assert "- #102 查重閘門缺口" in body

    def test_failure_does_not_block_and_records_incomplete(self, monkeypatch, tmp_path):
        outcome = DedupOutcome(error="TimeoutExpired: 90s")
        body, _ = _build(monkeypatch, tmp_path, ["閘門"], outcome)
        assert "查重未完成：TimeoutExpired: 90s" in body

    def test_no_keywords_skips_dedup_and_record(self, monkeypatch, tmp_path):
        body, calls = _build(monkeypatch, tmp_path, None, DedupOutcome())
        assert calls == []
        assert "### 查重紀錄" not in body
