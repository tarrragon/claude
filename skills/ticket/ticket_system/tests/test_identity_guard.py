"""identity_guard 分命令轉強制申報測試。

背景：identity_guard 對「未提供 --as」原為 warn-only（過渡期不阻擋）。
以 32 天 telemetry 實測 complete 呼叫端 96% 已帶 --as 且風險最高（終態轉換
不可逆）為依據，complete（含別名 finish）第一個轉為強制申報：未提供 --as
即 deny，其餘命令維持 warn-only。

本檔為 identity_guard 專屬測試（既有三份間接覆蓋檔——
test_complete_finish_alias.py / test_track_lease_wiring.py /
test_claim_as_sets_who.py——皆以 mock 完全取代 check_identity 的真實邏輯，
不驗證強制/警告分支，故本檔斷言不與其重疊）。

測試覆蓋：
1. complete 未帶 --as → deny，exit code 非零
2. complete 未帶 --as → deny 訊息含補救方式（--as 重試提示）
3. finish（complete 別名）未帶 --as → 同 complete 一併轉 deny
4. check-acceptance / set-acceptance 等未轉強制命令 → 未帶 --as 仍維持 warn-only（放行）
5. complete 帶 --as 且與 who.current 相符 → 放行（pass）
6. complete 帶 --as = PM_AGENT_NAME → PM 豁免路徑不受影響（exempt，放行）
"""
from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import patch

import pytest

from ticket_system.lib import identity_guard


def _fake_ticket(who_current: str):
    return {"who": {"current": who_current}}


class TestCompleteEnforced:
    """情境 1a：complete/finish 未提供 --as → deny。"""

    def test_complete_missing_as_denies_with_nonzero_exit(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOOK_LOGS_DIR", str(tmp_path))
        result = identity_guard.check_identity(
            "0.0.0", "0.0.0-W0-001", None, command="complete"
        )
        assert result is not None
        assert result != 0
        assert result == identity_guard.IDENTITY_DENY_EXIT

    def test_complete_missing_as_deny_message_includes_remedy(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("HOOK_LOGS_DIR", str(tmp_path))
        identity_guard.check_identity(
            "0.0.0", "0.0.0-W0-001", None, command="complete"
        )
        stderr = capsys.readouterr().err
        assert "deny" in stderr
        assert "--as" in stderr
        # 訊息須含具體補救動作（重試指令），非僅陳述拒絕
        assert "重試" in stderr or "retry" in stderr.lower()

    def test_complete_missing_as_empty_string_also_denies(self, tmp_path, monkeypatch):
        """空字串視同未提供（與既有防禦性檢查一致）。"""
        monkeypatch.setenv("HOOK_LOGS_DIR", str(tmp_path))
        result = identity_guard.check_identity(
            "0.0.0", "0.0.0-W0-001", "  ", command="complete"
        )
        assert result == identity_guard.IDENTITY_DENY_EXIT

    def test_finish_alias_missing_as_denies_same_as_complete(self, tmp_path, monkeypatch):
        """finish 為 complete 別名，telemetry command 欄位取實際操作名，兩者皆須強制。"""
        monkeypatch.setenv("HOOK_LOGS_DIR", str(tmp_path))
        result = identity_guard.check_identity(
            "0.0.0", "0.0.0-W0-001", None, command="finish"
        )
        assert result == identity_guard.IDENTITY_DENY_EXIT


class TestOtherCommandsUnaffected:
    """情境 1b：其餘命令未轉強制，維持 warn-only（回歸防護）。"""

    def test_check_acceptance_missing_as_still_warns_and_passes(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOOK_LOGS_DIR", str(tmp_path))
        result = identity_guard.check_identity(
            "0.0.0", "0.0.0-W0-001", None, command="check-acceptance"
        )
        assert result is None

    def test_set_acceptance_missing_as_still_warns_and_passes(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOOK_LOGS_DIR", str(tmp_path))
        result = identity_guard.check_identity(
            "0.0.0", "0.0.0-W0-001", None, command="set-acceptance"
        )
        assert result is None

    def test_claim_missing_as_still_warns_and_passes(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOOK_LOGS_DIR", str(tmp_path))
        result = identity_guard.check_identity(
            "0.0.0", "0.0.0-W0-001", None, command="claim"
        )
        assert result is None


class TestPmExemptionUnaffected:
    """PM 身份豁免路徑不受本次變更影響（情境 2）。"""

    def test_pm_agent_bypasses_even_for_enforced_command(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOOK_LOGS_DIR", str(tmp_path))
        result = identity_guard.check_identity(
            "0.0.0",
            "0.0.0-W0-001",
            identity_guard.PM_AGENT_NAME,
            command="complete",
        )
        assert result is None


class TestMatchingIdentityUnaffected:
    """--as 與 who.current 相符時放行（情境 3），不受強制清單影響。"""

    def test_complete_with_matching_as_passes(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOOK_LOGS_DIR", str(tmp_path))
        with patch.object(
            identity_guard, "load_ticket", return_value=_fake_ticket("thyme-python-developer")
        ):
            result = identity_guard.check_identity(
                "0.0.0",
                "0.0.0-W0-001",
                "thyme-python-developer",
                command="complete",
            )
        assert result is None

    def test_complete_with_mismatched_as_still_denies(self, tmp_path, monkeypatch):
        """情境 4（既有行為）：--as 與 who.current 不符仍 deny，不因本次變更改變。"""
        monkeypatch.setenv("HOOK_LOGS_DIR", str(tmp_path))
        with patch.object(
            identity_guard, "load_ticket", return_value=_fake_ticket("other-agent")
        ):
            result = identity_guard.check_identity(
                "0.0.0",
                "0.0.0-W0-001",
                "thyme-python-developer",
                command="complete",
            )
        assert result == identity_guard.IDENTITY_DENY_EXIT


# ============================================================
# 過渡期監測腳本測試（identity_guard_adoption.py）
# ============================================================
#
# tools/ 非套件目錄（無 __init__.py），以 importlib 依檔案路徑載入，
# 避免污染 sys.path 或改動既有目錄結構。

import importlib.util as _importlib_util
from datetime import datetime as _datetime
from pathlib import Path as _Path


def _load_adoption_module():
    module_path = (
        _Path(__file__).parent.parent / "tools" / "identity_guard_adoption.py"
    )
    spec = _importlib_util.spec_from_file_location(
        "identity_guard_adoption", module_path
    )
    module = _importlib_util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


adoption = _load_adoption_module()


def _write_log(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


class TestAdoptionRollingStats:
    """per-command 7 日滾動 warn 率與樣本數計算。"""

    def test_computes_warn_rate_within_window(self, tmp_path):
        log_path = tmp_path / "usage.log"
        now = _datetime(2026, 8, 21, 12, 0, 0)
        records = []
        # 30 筆 pass + 5 筆 warn，皆在 7 日窗口內 → warn 率 5/35
        for i in range(30):
            records.append(
                {
                    "timestamp": (now - timedelta(days=1)).isoformat(),
                    "command": "check-acceptance",
                    "result": "pass",
                }
            )
        for i in range(5):
            records.append(
                {
                    "timestamp": (now - timedelta(days=2)).isoformat(),
                    "command": "check-acceptance",
                    "result": "warn",
                }
            )
        _write_log(log_path, records)

        stats = adoption.compute_rolling_stats(log_path, now=now)
        s = stats["check-acceptance"]
        assert s.total == 35
        assert s.warn == 5
        assert abs(s.warn_rate - (5 / 35)) < 1e-9

    def test_excludes_records_outside_window(self, tmp_path):
        log_path = tmp_path / "usage.log"
        now = _datetime(2026, 8, 21, 12, 0, 0)
        records = [
            {
                "timestamp": (now - timedelta(days=1)).isoformat(),
                "command": "complete",
                "result": "warn",
            },
            {
                # 超出 7 日窗口，不應計入
                "timestamp": (now - timedelta(days=10)).isoformat(),
                "command": "complete",
                "result": "warn",
            },
        ]
        _write_log(log_path, records)

        stats = adoption.compute_rolling_stats(log_path, now=now)
        assert stats["complete"].total == 1


class TestAdoptionMinSampleSize:
    """acceptance 第 2 項：樣本數不足時不作判定。"""

    def test_sample_below_threshold_is_insufficient(self, tmp_path):
        log_path = tmp_path / "usage.log"
        now = _datetime(2026, 8, 21, 12, 0, 0)
        # 3 筆呼叫，遠低於 MIN_SAMPLE_SIZE（30）
        records = [
            {
                "timestamp": (now - timedelta(days=1)).isoformat(),
                "command": "set-acceptance",
                "result": "warn",
            }
        ] * 3
        _write_log(log_path, records)

        stats = adoption.compute_rolling_stats(log_path, now=now)
        s = stats["set-acceptance"]
        assert s.sample_sufficient is False
        assert s.meets_end_condition is False

        report = adoption.format_report(stats)
        assert "樣本不足，不作判定" in report
        # 樣本不足時報表不得印出誤導性比例數字
        assert "%" not in report.split("set-acceptance")[1].split("\n")[0]

    def test_sample_at_threshold_is_sufficient(self, tmp_path):
        log_path = tmp_path / "usage.log"
        now = _datetime(2026, 8, 21, 12, 0, 0)
        records = [
            {
                "timestamp": (now - timedelta(days=1)).isoformat(),
                "command": "set-acceptance",
                "result": "pass",
            }
        ] * adoption.MIN_SAMPLE_SIZE
        _write_log(log_path, records)

        stats = adoption.compute_rolling_stats(log_path, now=now)
        assert stats["set-acceptance"].sample_sufficient is True


class TestAdoptionEndCondition:
    """結束條件：7 日滾動 warn 率 < 5% 且樣本數足夠。"""

    def test_meets_end_condition_when_warn_rate_below_threshold(self, tmp_path):
        log_path = tmp_path / "usage.log"
        now = _datetime(2026, 8, 21, 12, 0, 0)
        records = [
            {
                "timestamp": (now - timedelta(days=1)).isoformat(),
                "command": "check-acceptance",
                "result": "pass",
            }
        ] * 99 + [
            {
                "timestamp": (now - timedelta(days=1)).isoformat(),
                "command": "check-acceptance",
                "result": "warn",
            }
        ] * 1
        _write_log(log_path, records)

        stats = adoption.compute_rolling_stats(log_path, now=now)
        s = stats["check-acceptance"]
        assert s.warn_rate == 0.01
        assert s.meets_end_condition is True

    def test_does_not_meet_end_condition_when_warn_rate_at_threshold(self, tmp_path):
        log_path = tmp_path / "usage.log"
        now = _datetime(2026, 8, 21, 12, 0, 0)
        records = [
            {
                "timestamp": (now - timedelta(days=1)).isoformat(),
                "command": "check-acceptance",
                "result": "pass",
            }
        ] * 95 + [
            {
                "timestamp": (now - timedelta(days=1)).isoformat(),
                "command": "check-acceptance",
                "result": "warn",
            }
        ] * 5
        _write_log(log_path, records)

        stats = adoption.compute_rolling_stats(log_path, now=now)
        s = stats["check-acceptance"]
        # warn_rate = 5/100 = 0.05，門檻為 < 5%（不含等於），故不符合
        assert s.warn_rate == 0.05
        assert s.meets_end_condition is False


class TestAdoptionMissingLog:
    """log 檔不存在須明確報錯，不得與『窗口內確實無記錄』混淆（本票核心修復）。"""

    def test_missing_log_file_raises_not_found(self, tmp_path):
        log_path = tmp_path / "does-not-exist.log"
        now = _datetime(2026, 8, 21, 12, 0, 0)
        with pytest.raises(adoption.LogFileNotFoundError):
            adoption.compute_rolling_stats(log_path, now=now)

    def test_main_missing_log_file_exits_nonzero_with_message(self, tmp_path, capsys):
        log_path = tmp_path / "does-not-exist.log"
        exit_code = adoption.main(["--log-path", str(log_path), "--now", "2026-08-21T12:00:00"])
        assert exit_code != 0
        stderr = capsys.readouterr().err
        assert "不存在" in stderr

    def test_existing_log_empty_window_returns_empty_report(self, tmp_path):
        """log 檔存在但窗口內無記錄：正常路徑，不報錯，與檔案不存在明確區分。"""
        log_path = tmp_path / "usage.log"
        _write_log(log_path, [])
        now = _datetime(2026, 8, 21, 12, 0, 0)
        stats = adoption.compute_rolling_stats(log_path, now=now)
        assert stats == {}
        assert "無" in adoption.format_report(stats)


class TestAdoptionDefaultLogPathResolution:
    """DEFAULT_LOG_RELATIVE_PATH 解析須與 cwd 無關（本票核心修復）。"""

    def test_default_log_path_is_absolute_and_cwd_independent(self, monkeypatch, tmp_path):
        fake_root = tmp_path / "fake-project"
        (fake_root / "docs" / "work-logs").mkdir(parents=True, exist_ok=True)
        (fake_root / "CLAUDE.md").write_text("# CLAUDE.md\n", encoding="utf-8")
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(fake_root))
        monkeypatch.setenv("TICKET_SYSTEM_TEST_ISOLATION", "1")
        from ticket_system.lib.paths import reset_project_root_cache

        reset_project_root_cache()

        resolved = adoption._resolve_log_path(None)

        assert resolved.is_absolute()
        assert resolved == fake_root / adoption.DEFAULT_LOG_RELATIVE_PATH
