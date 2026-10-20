"""建票時執行 framework-issue 的 dedup 並解析命中清單。

呼叫方式定案：以子程序呼叫 `section_comment.py dedup`，不匯入其函式。
理由：ticket 與 framework-issue 為兩個獨立 skill，匯入會讓 ticket 在載入期依賴
另一 skill 的內部符號與其 gh 依賴；子程序只依賴 CLI 契約（stdout 報告格式）。

查重不阻擋建票：任何失敗以 DedupOutcome.error 回傳，由呼叫端寫入〈查重紀錄〉。
"""
from __future__ import annotations

import logging
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Tuple

logger = logging.getLogger(__name__)

DEDUP_TIMEOUT_SECONDS = 90
_SCRIPT = (
    Path(__file__).resolve().parents[3]
    / "framework-issue" / "scripts" / "section_comment.py"
)
_HIT_LINE = re.compile(r"^\s+- #(\d+) \[[^\]]*\] (.*)$")
_SKIPPED_LINE = re.compile(r"查詢失敗略過的 token 數：(\d+)")


@dataclass
class DedupOutcome:
    """hits 為 (issue 號碼, 標題)；error 非 None 表示查重未完成。"""

    hits: List[Tuple[int, str]] = field(default_factory=list)
    error: Optional[str] = None
    partial: bool = False  # True：部分 token 失敗，hits 仍有效


def parse_dedup_report(stdout: str) -> DedupOutcome:
    """從 dedup 報告取命中清單（依號碼去重）與查詢失敗略過數。"""
    seen = {}
    for line in stdout.splitlines():
        m = _HIT_LINE.match(line)
        if m:
            seen.setdefault(int(m.group(1)), m.group(2).strip())
    outcome = DedupOutcome(hits=sorted(seen.items()))
    skipped = _SKIPPED_LINE.search(stdout)
    if skipped and int(skipped.group(1)) > 0:
        outcome.error = f"{skipped.group(1)} 個關鍵字 token 查詢失敗被略過"
    return outcome


def run_dedup(
    keywords: List[str],
    runner: Callable = subprocess.run,
    timeout: int = DEDUP_TIMEOUT_SECONDS,
) -> DedupOutcome:
    """執行 dedup；離線、逾時、例外、非零退出皆轉為 error，不拋出。"""
    cmd = [sys.executable, str(_SCRIPT), "dedup", "--keywords", *keywords]
    try:
        proc = runner(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        return _failed(f"{type(exc).__name__}: {exc}")
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip().splitlines()[-1:] or ["（無 stderr）"]
        return _failed(f"exit {proc.returncode}: {tail[0]}")
    outcome = parse_dedup_report(proc.stdout or "")
    if outcome.error:
        outcome.partial = True
        _warn(f"建票查重部分未完成（不阻擋建票）：{outcome.error}")
    return outcome


def _warn(message: str) -> None:
    """同一訊息寫 stderr 與日誌（業務邏輯失敗須有日誌）。"""
    sys.stderr.write(f"[WARNING] {message}\n")
    logger.warning(message)


def _failed(summary: str) -> DedupOutcome:
    _warn(f"建票查重未完成（不阻擋建票）：{summary}")
    return DedupOutcome(error=summary)
