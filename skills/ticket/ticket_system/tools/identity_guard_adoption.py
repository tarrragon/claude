#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
identity-guard 採用率監測腳本。

用途：
  讀取 identity-guard telemetry（.claude/hook-logs/identity-guard/usage.log），
  輸出 per-command 的 7 日滾動 warn 率與樣本數，作為過渡期結束條件的判定
  依據：某命令 7 日滾動 warn 率降至 5% 以下（且樣本數足夠）即可將該命令
  加入 identity_guard.ENFORCED_COMMANDS 轉為強制申報。

樣本數不足時的處理：
  最小樣本數定為 MIN_SAMPLE_SIZE = 30。依據：常態近似下二項比例的可靠區間
  經驗法則要求 n*p >= 10 且 n*(1-p) >= 10；本情境 warn 率最低可能趨近 0，
  以保守上界 p = 0.5 代入需 n >= 20，取業界慣用的「大樣本」門檻 30 作為
  安全邊際。7 日窗口內樣本數 < 30 時，本腳本不輸出 warn 率數字，改標示
  「樣本不足，不作判定」，避免如 3 筆呼叫算出 33%/67% 這類無統計意義的
  比例被誤讀為趨勢。

使用：
  uv run .claude/skills/ticket/ticket_system/tools/identity_guard_adoption.py
  可加 --log-path 覆蓋預設 log 路徑（測試隔離用）、
  --window-days 覆蓋預設 7 日滾動窗口、--now ISO8601 覆蓋「現在」基準時間
  （測試用，預設 datetime.now()）。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Optional

# tools/ 非套件目錄，以 importlib 依檔案路徑載入時無法用套件相對匯入；
# 直接匯入 lib.paths 需將 skill root 加入 sys.path（與既有 CLI 進入點作法
# 一致，見 ticket_system/scripts/ticket.py 的執行環境假設：本腳本以
# `uv run .claude/skills/ticket/ticket_system/tools/identity_guard_adoption.py`
# 或經由上述 tests 的 importlib loader 執行，兩者 sys.path[0] 皆可能不含
# skill root，故顯式補上）。
_SKILL_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

from ticket_system.lib.paths import get_project_root  # noqa: E402

DEFAULT_LOG_RELATIVE_PATH = ".claude/hook-logs/identity-guard/usage.log"
DEFAULT_WINDOW_DAYS = 7

# 過渡期結束條件（identity_guard.py 模組註解引用同一數值，維持單一事實來源
# 的意圖；因跨檔案常數同步屬既知限制，兩處各自以註解交叉引用對方，
# 變更其一時人工同步）。
WARN_RATE_THRESHOLD = 0.05

# 樣本數不足判準：見上方 docstring「樣本數不足時的處理」。
MIN_SAMPLE_SIZE = 30


class CommandStats:
    """單一命令在滾動窗口內的統計。"""

    __slots__ = ("command", "total", "warn")

    def __init__(self, command: str) -> None:
        self.command = command
        self.total = 0
        self.warn = 0

    @property
    def warn_rate(self) -> Optional[float]:
        if self.total == 0:
            return None
        return self.warn / self.total

    @property
    def sample_sufficient(self) -> bool:
        return self.total >= MIN_SAMPLE_SIZE

    @property
    def meets_end_condition(self) -> bool:
        """7 日滾動 warn 率 < 5% 且樣本數足夠 → 符合轉強制條件。"""
        if not self.sample_sufficient:
            return False
        rate = self.warn_rate
        return rate is not None and rate < WARN_RATE_THRESHOLD


class LogFileNotFoundError(FileNotFoundError):
    """usage.log 不存在。

    與「log 存在但窗口內確實無記錄」明確區分：前者是環境/路徑問題，
    後者是正常的觀測結果。呼叫端（main）需分別處理，不可讓兩者輸出同一
    段人類可讀文字（此為本票修復的核心缺陷）。
    """


def _iter_log_records(log_path: Path) -> Iterable[dict]:
    """逐行讀取 usage.log JSONL；壞行跳過（telemetry 為旁路觀測，不因單行壞資料中斷統計）。

    Raises:
        LogFileNotFoundError: log 檔不存在。
    """
    if not log_path.exists():
        raise LogFileNotFoundError(f"telemetry log 不存在：{log_path}")
    with open(log_path, mode="r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def compute_rolling_stats(
    log_path: Path,
    *,
    window_days: int = DEFAULT_WINDOW_DAYS,
    now: Optional[datetime] = None,
) -> dict:
    """計算 per-command 的滾動窗口統計。

    Returns:
        {command: CommandStats} 的 dict，僅含窗口內出現過的命令。
    """
    now = now or datetime.now()
    window_start = now - timedelta(days=window_days)

    result: dict = {}

    for record in _iter_log_records(log_path):
        timestamp_str = record.get("timestamp")
        command = record.get("command")
        result_value = record.get("result")
        if not isinstance(timestamp_str, str) or not isinstance(command, str):
            continue
        try:
            ts = datetime.fromisoformat(timestamp_str)
        except ValueError:
            continue
        if ts < window_start or ts > now:
            continue

        if command not in result:
            result[command] = CommandStats(command)
        cmd_stats = result[command]
        cmd_stats.total += 1
        if result_value == "warn":
            cmd_stats.warn += 1

    return result


def format_report(stats: dict) -> str:
    """輸出人類可讀報表；樣本不足的命令明示不判定，不印比例數字。"""
    if not stats:
        return "（窗口內無 telemetry 記錄）"

    lines = [
        f"{'command':<20}{'樣本數':>8}{'warn 率':>12}{'判定':>20}",
        "-" * 60,
    ]
    for command in sorted(stats.keys()):
        s = stats[command]
        if not s.sample_sufficient:
            lines.append(
                f"{command:<20}{s.total:>8}{'--':>12}{'樣本不足，不作判定':>20}"
            )
            continue
        rate_pct = f"{s.warn_rate * 100:.1f}%"
        verdict = "符合結束條件" if s.meets_end_condition else "未達結束條件"
        lines.append(f"{command:<20}{s.total:>8}{rate_pct:>12}{verdict:>20}")
    return "\n".join(lines)


def _resolve_log_path(cli_value: Optional[str]) -> Path:
    """解析 usage.log 路徑。

    預設路徑由 get_project_root() 推導為絕對路徑，與呼叫時的 cwd 無關
    （修復：原相對路徑字串經 Path() 解析相對於 cwd，自非專案根目錄執行時
    指向不存在的路徑）。--log-path 覆蓋值原樣使用，供測試隔離。
    """
    if cli_value:
        return Path(cli_value)
    return get_project_root() / DEFAULT_LOG_RELATIVE_PATH


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log-path", default=None, help="覆蓋預設 usage.log 路徑")
    parser.add_argument(
        "--window-days", type=int, default=DEFAULT_WINDOW_DAYS, help="滾動窗口天數"
    )
    parser.add_argument(
        "--now", default=None, help="覆蓋「現在」基準時間（ISO8601，測試用）"
    )
    args = parser.parse_args(argv)

    log_path = _resolve_log_path(args.log_path)
    now = datetime.fromisoformat(args.now) if args.now else None

    try:
        stats = compute_rolling_stats(log_path, window_days=args.window_days, now=now)
    except LogFileNotFoundError as exc:
        print(f"[錯誤] {exc}", file=sys.stderr)
        return 1
    print(format_report(stats))
    return 0


if __name__ == "__main__":
    sys.exit(main())
