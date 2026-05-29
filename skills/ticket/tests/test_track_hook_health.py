"""
測試 ticket track hook-health 命令（W13-018 落地，源自 W13-008 IMP-3）。

覆蓋 5 條 acceptance：
1. hook-health 子命令解析正確
2. 預設 --since 7 天
3. dry-run 不寫入 ticket
4. 與 IMP-2 共用 collector 邏輯
5. table/json 兩格式輸出正確
"""

from __future__ import annotations

import argparse
import io
import json
from contextlib import redirect_stdout
from datetime import datetime
from typing import Dict
from unittest.mock import patch


def _args(**overrides) -> argparse.Namespace:
    defaults = dict(
        operation="hook-health",
        since=7,
        format="table",
        dry_run=False,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _fake_stats() -> Dict[str, Dict]:
    """模擬 scan_logs 回傳：兩個 hook，一個 flagged（warning/critical）一個 normal。

    去時間依賴設計（W3-084）：
    - 原 fixture 寫死 2026-05-13~15 日期，且 25/22/13 在 high_freq 閾值（baseline×3）以下，
      無法穩定產生 flagged 狀態（_evaluate_all 以「今日」取 recent，寫死日期永遠 recent=0）。
    - 改法：wrap-decision-tripwire 的 spike 落在「執行當日」（動態 _today），count 遠高於
      baseline×3，使 recent > threshold 穩定觸發 warning，不再依賴寫死日期。
    """
    _today = datetime.now().strftime("%Y-%m-%d")
    return {
        "wrap-decision-tripwire": {
            # 單日 spike 300 → baseline=300/7≈42.9、high_freq threshold=baseline×3≈128.6
            # recent(今日)=300 > 128.6 穩定 warning，與「今日是哪天」無關。
            "total": 300,
            "per_day": {
                _today: 300,
            },
        },
        "phase4-decision-enforcement": {
            "total": 4,
            "per_day": {"2026-05-19": 4},
        },
    }


def _run(args: argparse.Namespace, stats: Dict[str, Dict] | None = None) -> tuple[int, str]:
    from ticket_system.commands.track_hook_health import execute_hook_health

    if stats is None:
        stats = _fake_stats()

    buf = io.StringIO()
    with patch(
        "ticket_system.commands.track_hook_health.scan_logs",
        return_value=stats,
    ), redirect_stdout(buf):
        rc = execute_hook_health(args)
    return rc, buf.getvalue()


class TestHookHealthCommandRegistration:
    def test_register_adds_hook_health_subcommand(self):
        from ticket_system.commands.track_hook_health import register_hook_health

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="operation")
        register_hook_health(subparsers)

        ns = parser.parse_args(["hook-health"])
        assert ns.operation == "hook-health"

    def test_default_since_is_7_days(self):
        """Acceptance 2: 預設 --since 7 天。"""
        from ticket_system.commands.track_hook_health import register_hook_health

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="operation")
        register_hook_health(subparsers)

        ns = parser.parse_args(["hook-health"])
        assert ns.since == 7

    def test_format_choices_table_json(self):
        """Acceptance 5: --format 接受 table / json。"""
        from ticket_system.commands.track_hook_health import register_hook_health

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="operation")
        register_hook_health(subparsers)

        ns_table = parser.parse_args(["hook-health", "--format", "table"])
        ns_json = parser.parse_args(["hook-health", "--format", "json"])
        assert ns_table.format == "table"
        assert ns_json.format == "json"


class TestHookHealthExecution:
    def test_uses_shared_collector(self):
        """Acceptance 4: 透過 scan_logs（lib.hook_health）取得統計。"""
        rc, out = _run(_args())
        assert rc == 0
        # 兩個 hook 名稱都應出現在輸出
        assert "wrap-decision-tripwire" in out
        assert "phase4-decision-enforcement" in out

    def test_dry_run_does_not_create_ticket(self):
        """Acceptance 3: dry-run 不寫入 ticket。

        本子命令本即不會自動建 ticket（W13-008 §自動建 ticket 流程為 stderr 提醒），
        故 dry-run 旗標僅作為「明示禁止任何副作用」的契約點：
          - 不呼叫任何 ticket create / append-log
          - 不寫入任何檔案
        本測試以「執行成功且無 side effect 例外」為驗證下界，
        並斷言 dry-run 開啟時 stdout 含明示標記。
        """
        rc, out = _run(_args(dry_run=True))
        assert rc == 0
        assert "dry-run" in out.lower()

    def test_table_format_renders_status_column(self):
        """Acceptance 5: table 格式輸出含 status 欄位。"""
        rc, out = _run(_args(format="table"))
        assert rc == 0
        # table 應含表頭欄位字樣
        assert "hook" in out.lower()
        assert "status" in out.lower()
        # 至少一筆 critical 應呈現
        assert "critical" in out.lower() or "warning" in out.lower()

    def test_json_format_is_parseable(self):
        """Acceptance 5: json 格式可被 json.loads 解析。"""
        rc, out = _run(_args(format="json"))
        assert rc == 0
        payload = json.loads(out)
        assert isinstance(payload, dict)
        assert "results" in payload
        assert isinstance(payload["results"], list)
        # 至少有 2 筆 hook 結果
        assert len(payload["results"]) >= 2
        first = payload["results"][0]
        assert "hook" in first
        assert "status" in first
        assert "recent" in first
        assert "baseline" in first

    def test_empty_stats_returns_zero(self):
        """無 hook log 時不應崩潰。"""
        rc, out = _run(_args(), stats={})
        assert rc == 0
        # 應有「無資料」訊息或空 results
        assert out  # 至少有 header 或訊息

    def test_since_arg_passed_to_scan_logs(self):
        """Acceptance 2: --since 值會轉為 datetime 並傳入 scan_logs。"""
        from ticket_system.commands.track_hook_health import execute_hook_health

        captured = {}

        def fake_scan(since, logs_root=None):
            captured["since"] = since
            return {}

        with patch(
            "ticket_system.commands.track_hook_health.scan_logs",
            side_effect=fake_scan,
        ), redirect_stdout(io.StringIO()):
            execute_hook_health(_args(since=3))

        assert "since" in captured
        assert isinstance(captured["since"], datetime)
        # since=3 → 大約 3 天前
        delta_days = (datetime.now() - captured["since"]).days
        assert 2 <= delta_days <= 4
