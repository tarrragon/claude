"""
test_messages_error_envelope
=============================

驗證錯誤信封尾部摘要行（頭尾皆帶 [Error] 前綴，防 `tail -N` 截斷）：

- `_render_envelope` / `format_error(ErrorEnvelope)` 最後一行固定含
  `[Error]` 前綴與簡短原因（component/action/errno）
- 既有第 1 行內容與欄位順序不變（component/action/errno/hint）
- 3 行最小重現：`tail -2` 截斷後仍可見 `[Error]` 判別依據
- 端對端：以 `ticket create` 缺必填欄位（既有走 ErrorEnvelope 的代表性
  寫入類命令）驗證真實 CLI 輸出含尾部摘要

範圍說明：append-log／claim／complete／set-acceptance 目前的 status
precondition 拒絕訊息（`ticket_system.lib.precondition._build_error_msg`）
繞過本模組的 format_error/ErrorEnvelope，直接由呼叫端
`sys.stderr.write(error_msg + "\\n")` 輸出，不在本次尾部摘要機制的涵蓋範圍
內；此發現已記錄於 ticket Problem Analysis 並登記後續遷移 spawn-request，
故本檔改以 `ticket create` 作為端對端驗證的代表性命令。

Source: ticket 0.2.1-W3-1225
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from ticket_system.lib.messages import (
    ERROR_ENVELOPE_VERSION_MARKER,
    ErrorEnvelope,
    format_error,
)


# ---------------------------------------------------------------------------
# 共用輔助（與 test_error_channel_integration.py 同模式：subprocess 端對端）
# ---------------------------------------------------------------------------

TICKET_SKILL_DIR = Path(__file__).resolve().parents[1]


def _run_ticket(*args: str) -> subprocess.CompletedProcess:
    """執行 `uv run ticket <args>` 並回傳 CompletedProcess（capture stdout+stderr）。"""
    return subprocess.run(
        ["uv", "run", "ticket", *args],
        cwd=TICKET_SKILL_DIR,
        capture_output=True,
        text=True,
        check=False,
    )


def _combined_output(result: subprocess.CompletedProcess) -> str:
    return (result.stdout or "") + (result.stderr or "")


# ---------------------------------------------------------------------------
# 尾部摘要行格式驗證
# ---------------------------------------------------------------------------


class TestTailSummaryFormat:
    """驗證尾部摘要行固定含 [Error] 前綴與簡短原因，且不影響既有欄位。"""

    def test_last_line_has_error_prefix(self):
        env = ErrorEnvelope(component="track", action="append-log", errno="STATUS_PENDING")
        rendered = format_error(env)
        last_line = rendered.split("\n")[-1]
        assert last_line.startswith("[Error]")

    def test_last_line_contains_short_reason(self):
        """簡短原因：至少含 component/action/errno 三者，供 tail 截斷後仍可判別。"""
        env = ErrorEnvelope(component="track", action="claim", errno="ALREADY_CLAIMED")
        rendered = format_error(env)
        last_line = rendered.split("\n")[-1]
        assert "track" in last_line
        assert "claim" in last_line
        assert "ALREADY_CLAIMED" in last_line

    def test_first_line_unchanged(self):
        """acceptance #4：不改變既有第 1 行內容。"""
        env = ErrorEnvelope(component="track", action="append-log", errno="STATUS_PENDING")
        rendered = format_error(env)
        assert rendered.split("\n")[0] == f"[Error] {ERROR_ENVELOPE_VERSION_MARKER}"

    def test_existing_field_order_unchanged(self):
        """既有 component/action/errno/hint 順序不變，尾部摘要只附加在最後。"""
        env = ErrorEnvelope(
            component="track", action="claim", errno="TICKET_NOT_FOUND", hint="檢查 ID"
        )
        rendered = format_error(env)
        lines = rendered.split("\n")
        assert lines[0] == f"[Error] {ERROR_ENVELOPE_VERSION_MARKER}"
        assert lines[1] == "  component: track"
        assert lines[2] == "  action: claim"
        assert lines[3] == "  errno: TICKET_NOT_FOUND"
        assert lines[4] == "  hint: 檢查 ID"
        assert lines[5].startswith("[Error]")
        assert len(lines) == 6

    def test_no_hint_still_has_tail_summary(self):
        """hint 為 None 時，尾部摘要仍附加在既有欄位之後（緊接 errno 行）。"""
        env = ErrorEnvelope(component="lifecycle", action="complete", errno="NOT_IN_PROGRESS")
        rendered = format_error(env)
        lines = rendered.split("\n")
        assert lines[3] == "  errno: NOT_IN_PROGRESS"
        assert lines[4].startswith("[Error]")
        assert len(lines) == 5


# ---------------------------------------------------------------------------
# 3 行最小重現：tail -2 截斷後仍可見 [Error]
# ---------------------------------------------------------------------------


class TestTailTruncationMinimalRepro:
    """重現 0.2.1-W3-1219 記錄的原始事件形狀：短輸出（3 行級）被 `tail -2`
    截斷時，[Error] 前綴曾完全消失。驗證加入尾部摘要後不再發生。
    """

    def test_tail_2_still_shows_error_prefix(self):
        # 最小信封（無 hint）：4 行本體 + 1 行尾部摘要 = 5 行，與原始 3 行
        # 事件同屬「短輸出、常用 tail -2/-3 會切到頭部」的量級。
        env = ErrorEnvelope(component="track", action="append-log", errno="STATUS_PENDING")
        rendered = format_error(env)
        lines = rendered.split("\n")

        # 模擬 `| tail -2`
        tail_2 = lines[-2:]
        assert any(line.startswith("[Error]") for line in tail_2), (
            f"tail -2 應仍可見 [Error] 判別依據，實際最後兩行：{tail_2}"
        )

    def test_tail_1_still_shows_error_prefix(self):
        """更嚴格情形：`tail -1` 只取最後一行，仍須看到 [Error]（尾部摘要
        必須是最後一行而非倒數第二行，否則 tail -1 仍看不到）。
        """
        env = ErrorEnvelope(component="track", action="append-log", errno="STATUS_PENDING")
        rendered = format_error(env)
        last_line = rendered.split("\n")[-1]
        assert last_line.startswith("[Error]")


# ---------------------------------------------------------------------------
# 端對端：以 ticket track list --format <invalid> 驗證真實 CLI 輸出含尾部
# 摘要（既有走 ErrorEnvelope 的代表性命令）
# ---------------------------------------------------------------------------


class TestEndToEndRepresentativeCommand:
    """端對端驗證：透過真實 CLI 呼叫，確認尾部摘要出現在實際輸出中（非僅
    單元測試 `_render_envelope` 回傳值）。

    未直接以 append-log 端對端驗證：append-log 的 pending 拒絕訊息現行由
    `ticket_system.lib.precondition._build_error_msg` 組字串後經
    `sys.stderr.write()` 直接輸出，繞過本模組的 format_error/ErrorEnvelope，
    不受本次尾部摘要機制涵蓋（範圍說明見模組 docstring；已於 ticket
    Problem Analysis 記錄並登記後續遷移 spawn-request）。

    改以 `ticket track list --format <invalid>` 作為代表性命令：其業務錯誤
    經 `ArgparseFormatErrorParser` 走 ErrorEnvelope（見
    tests/test_error_channel_integration.py 場景 5），且輸出在
    envelope 後即 `sys.exit(2)`，不像 `create` 缺必填欄位路徑會在 envelope
    後續印每個缺漏欄位的建議值（trailing 內容會使尾部摘要不再是輸出最後一
    行，無法乾淨驗證「輸出尾端可見 [Error]」這件事）。
    """

    def test_invalid_format_choice_shows_tail_summary(self):
        result = _run_ticket("track", "list", "--format", "INVALID_FORMAT_VALUE")

        assert result.returncode != 0
        combined = _combined_output(result)
        assert ERROR_ENVELOPE_VERSION_MARKER in combined

        # 尾部摘要行：真實 CLI 輸出的最後一個非空行仍以 [Error] 開頭
        non_empty_lines = [line for line in combined.rstrip("\n").split("\n") if line.strip()]
        assert non_empty_lines, f"CLI 輸出為空，實際輸出：{combined[:500]}"
        assert non_empty_lines[-1].startswith("[Error]"), (
            f"預期最後一行以 [Error] 開頭，實際：{non_empty_lines[-1]!r}"
        )

        # tail -2 情境：即使只取最後兩行，仍可見 [Error] 判別依據
        tail_2 = non_empty_lines[-2:]
        assert any(line.startswith("[Error]") for line in tail_2)
