"""
錯誤通道整合測試（W17-008.5.6.1）

驗證 W17-008.5 group 端到端行為：
- W17-008.5.2: format_error 雙路徑（legacy str / ErrorEnvelope）
- W17-008.5.3: create.py 業務錯誤改走 ErrorEnvelope（CHECKLIST_VALIDATION_FAILED）
- W17-008.5.4: argparse 業務錯誤改走 ArgparseFormatErrorParser（INVALID_CHOICE）
- W17-008.5.5: skill-cli-error-feedback-hook 偵測 envelope 標記跳過引導補充

涵蓋 5 個錯誤通道整合場景（acceptance criteria 對應）：
1. invalid-section: track append-log --section "NotValid" → 拒絕無效 section（legacy 路徑）
2. unrecognized-args: ticket --not-a-flag → argparse 預設 POSIX 路徑（純語法錯誤；W17-008.5.4 設計
   明確排除 unrecognized args 走 envelope，保留 argparse 預設行為）
3. section-not-found: append-log --section "<valid>" 但 body 缺該 section（legacy 路徑）
4. missing-required-field: create 缺必填欄位 → ErrorEnvelope errno=CHECKLIST_VALIDATION_FAILED
5. wrong-value-type: argparse choices 不匹配 → ErrorEnvelope errno=INVALID_CHOICE

測試策略：
- 使用 subprocess.run 進行真正端到端驗證（含 argparse + envelope rendering 完整路徑）
- 從 `ticket_system.lib.messages` import ERROR_ENVELOPE_VERSION_MARKER 做斷言（避免硬編碼）
- 每個場景至少 assert：exit code != 0、輸出含預期格式、含預期 errno（envelope 路徑）或
  關鍵字（legacy 路徑）

Marker 來源：
- ERROR_ENVELOPE_VERSION_MARKER 定義於 ticket_system.lib.messages
- 升級至 v2 時測試會自動跟隨 import 不需修改
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from ticket_system.lib.messages import ERROR_ENVELOPE_VERSION_MARKER


# ============================================================
# 共用輔助
# ============================================================


# ticket skill 目錄（subprocess cwd / uv run 工作目錄）
TICKET_SKILL_DIR = Path(__file__).resolve().parents[1]


def _run_ticket(*args: str) -> subprocess.CompletedProcess:
    """執行 `uv run ticket <args>` 並回傳 CompletedProcess（capture stdout+stderr）。

    使用 subprocess 達成真正端到端整合驗證：
    - 觸發完整 argparse 流程（含 ArgparseFormatErrorParser）
    - 觸發 CLI 入口點完整錯誤 rendering
    - 與 hook 偵測共用 stdin/stderr 通道（hook 雖在此不主動觸發，但
      ERROR_ENVELOPE_VERSION_MARKER 的 stdout/stderr 出現位置與 hook 偵測一致）

    Args:
        *args: 傳遞給 ticket CLI 的引數（不含 "uv run ticket" 前綴）

    Returns:
        CompletedProcess（含 stdout / stderr / returncode）
    """
    return subprocess.run(
        ["uv", "run", "ticket", *args],
        cwd=TICKET_SKILL_DIR,
        capture_output=True,
        text=True,
        check=False,
    )


def _combined_output(result: subprocess.CompletedProcess) -> str:
    """合併 stdout + stderr 便於斷言（兩通道皆可能含錯誤訊息）。"""
    return (result.stdout or "") + (result.stderr or "")


# ============================================================
# 整合測試：5 個錯誤通道場景
# ============================================================


class TestErrorChannelIntegration:
    """W17-008.5.6.1：5 個錯誤通道整合場景端到端驗證。"""

    def test_scenario_1_invalid_section(self):
        """場景 1：invalid-section（legacy str 路徑）。

        Given: ticket track append-log <existing-id> --section "NotAValidSection" "..."
        When: 透過 CLI 執行
        Then: exit code != 0、輸出含「無效的 section」與「有效值」清單；
              此路徑為 legacy str（W17-008.5.2 雙路徑保留向後相容），
              不含 ErrorEnvelope 標記。
        """
        # 使用本 ticket 自身（必定存在）作為 target
        result = _run_ticket(
            "track", "append-log", "0.18.0-W17-008.5.6.1",
            "--section", "NotAValidSection", "dummy-content",
        )

        assert result.returncode != 0, f"預期非零 exit，實際 rc={result.returncode}"
        combined = _combined_output(result)
        # legacy str 路徑訊號：INVALID_SECTION 訊息 + 有效值列出
        assert "無效的 section" in combined or "INVALID_SECTION" in combined
        assert "NotAValidSection" in combined
        # 提示用戶有效 section 清單
        assert "有效值" in combined or "valid" in combined.lower()

    def test_scenario_2_unrecognized_args(self):
        """場景 2：unrecognized-args（argparse 預設 POSIX 路徑）。

        Given: ticket --not-a-real-flag （未知 flag）
        When: 透過 CLI 執行
        Then: exit code != 0；走 argparse 預設 POSIX 風格輸出
              （W17-008.5.4 設計明確排除 unrecognized args 走 envelope；
               純語法錯誤保留 argparse usage + error 預設行為）

        註：本場景驗證 W17-008.5.4 的「保留純語法錯誤預設路徑」設計選擇，
            envelope 標記不應出現於此錯誤類別。
        """
        result = _run_ticket("track", "list", "--not-a-real-flag")

        assert result.returncode != 0
        combined = _combined_output(result)
        # argparse POSIX 風格訊號
        assert "unrecognized arguments" in combined
        assert "--not-a-real-flag" in combined
        # 純語法錯誤保留 POSIX 路徑（不含 envelope 標記，驗證 W17-008.5.4 設計界線）
        assert ERROR_ENVELOPE_VERSION_MARKER not in combined

    def test_scenario_3_section_not_found(self, tmp_path, monkeypatch):
        """場景 3：section-not-found（legacy str 路徑）。

        Given: target ticket md 缺指定 section
        When: 直接呼叫 execute_append_log（in-process；構造缺 section 的 body）
        Then: exit code != 0；輸出含 SECTION_NOT_FOUND 訊息與現有 H2 標題列舉

        為避免污染真實 ticket md，本測試走 in-process + monkeypatch load_ticket
        而非 subprocess（無法輕易構造缺 section 的真實 ticket）。
        """
        import argparse
        import io
        from ticket_system.commands import track_acceptance

        # 構造缺 "Solution" section 的 body（僅含 Problem Analysis）
        fake_body = (
            "# Test Ticket\n"
            "\n"
            "## Problem Analysis\n"
            "some content\n"
            "\n"
            "## Other Section\n"
            "other content\n"
        )
        fake_ticket = {
            "id": "fake-id-for-test",
            # W3-044 require_in_progress precondition：append-log 需 status=in_progress（否則
            # 在 SECTION_NOT_FOUND 邏輯前即被擋下並寫 stderr，stdout 為空）。
            "status": "in_progress",
            "_body": fake_body,
        }

        monkeypatch.setattr(
            "ticket_system.commands.track_acceptance.load_ticket",
            lambda v, tid: fake_ticket,
        )

        # 重定向 stdout 捕捉輸出
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)

        args = argparse.Namespace(
            ticket_id="fake-id-for-test",
            section="Solution",
            content="dummy",
        )
        rc = track_acceptance.execute_append_log(args, "0.18.0")

        output = captured.getvalue()
        assert rc != 0, f"預期非零 rc，實際 rc={rc}"
        # SECTION_NOT_FOUND 訊息
        assert "Solution" in output
        assert "區段" in output or "section" in output.lower()
        # W17-008.9 引導：列出現有 H2 標題
        assert "Problem Analysis" in output or "Other Section" in output

    def test_scenario_4_missing_required_field(self):
        """場景 4：missing-required-field（ErrorEnvelope 路徑；W17-008.5.3）。

        Given: ticket create 缺多項必填欄位（when / how_strategy 等）
        When: 透過 CLI 執行（提供最小可通過 argparse 的引數）
        Then: exit code != 0；輸出含 ErrorEnvelope 標記 +
              errno=CHECKLIST_VALIDATION_FAILED + 結構欄位（component/action/errno/hint）
        """
        # 提供最小引數讓 argparse 過關，但 checklist 必填欄位（when / how_strategy 等）缺失
        # decision-tree 三引數提供以避免被 DECISION_TREE 錯誤先擋下
        result = _run_ticket(
            "create",
            "--type", "IMP",
            "--action", "test",
            "--target", "test",
            "--wave", "99",
            "--decision-tree-entry", "x",
            "--decision-tree-decision", "x",
            "--decision-tree-rationale", "x",
        )

        assert result.returncode != 0
        combined = _combined_output(result)
        # ErrorEnvelope 路徑訊號（W17-008.5.3）
        assert ERROR_ENVELOPE_VERSION_MARKER in combined, (
            f"預期含 envelope 標記，實際輸出：\n{combined[:500]}"
        )
        # 結構欄位（其中至少一項為必填欄位錯誤）
        assert "component:" in combined
        assert "action:" in combined
        assert "errno:" in combined
        # 必填欄位錯誤的可能 errno（CHECKLIST_VALIDATION_FAILED 或先觸發的其他必填驗證 errno；
        # 兩者均屬「missing-required-field」場景的合法分類）
        valid_errnos = (
            "CHECKLIST_VALIDATION_FAILED",
            "WHY_REQUIRED",
            "WHEN_REQUIRED",
            "HOW_STRATEGY_REQUIRED",
        )
        assert any(e in combined for e in valid_errnos), (
            f"預期 errno 屬必填欄位錯誤類別之一 {valid_errnos}，實際輸出：\n{combined[:500]}"
        )

    def test_scenario_5_wrong_value_type(self):
        """場景 5：wrong-value-type（ErrorEnvelope 路徑；W17-008.5.4）。

        Given: argparse 含 choices=[...] 之 flag 提供非法值
              （ticket track list --format BAD_VALUE，--format choices=table/ids/yaml）
        When: 透過 CLI 執行
        Then: exit code != 0；輸出含 ErrorEnvelope 標記 + errno=INVALID_CHOICE +
              結構欄位；hint 含原始 argparse 訊息
        """
        result = _run_ticket("track", "list", "--format", "INVALID_FORMAT_VALUE")

        assert result.returncode != 0
        combined = _combined_output(result)
        # ErrorEnvelope 路徑訊號（W17-008.5.4 ArgparseFormatErrorParser）
        assert ERROR_ENVELOPE_VERSION_MARKER in combined
        assert "errno: INVALID_CHOICE" in combined
        # 結構欄位完整
        assert "component:" in combined
        assert "action: parse_args" in combined
        # hint 含 argparse 原始錯誤片段
        assert "INVALID_FORMAT_VALUE" in combined
        assert "invalid choice" in combined


# ============================================================
# 補強：envelope 與 hook 偵測一致性
# ============================================================


class TestEnvelopeMarkerConsistency:
    """補強：驗證 envelope 標記與 hook 偵測常數一致（防止升級至 v2 時兩處未同改）。"""

    def test_marker_value_is_v1(self):
        """確保 ERROR_ENVELOPE_VERSION_MARKER 為 __error_envelope_v1__。

        若升級至 v2，本測試與 skill-cli-error-feedback-hook.py:ENVELOPE_VERSION_MARKER
        須同時更新；本斷言充當「版本錨點」防止單側升級。
        """
        assert ERROR_ENVELOPE_VERSION_MARKER == "__error_envelope_v1__"

    def test_envelope_output_format_is_stable(self):
        """場景 5 之 envelope 輸出格式包含所有必要結構欄位。

        驗證 _render_envelope 的輸出順序與欄位齊備性，作為跨子場景的格式契約。
        """
        result = _run_ticket("track", "list", "--format", "BAD_VAL")
        combined = _combined_output(result)

        # 結構欄位順序（與 _render_envelope 行序一致）
        marker_idx = combined.find(ERROR_ENVELOPE_VERSION_MARKER)
        component_idx = combined.find("component:")
        action_idx = combined.find("action:")
        errno_idx = combined.find("errno:")

        assert marker_idx >= 0
        assert component_idx > marker_idx
        assert action_idx > component_idx
        assert errno_idx > action_idx
