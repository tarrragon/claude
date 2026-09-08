"""0.2.1-W3-1333 — track_audit.py 呈現層接線 artifact_who / artifact_updated。

0.2.1-W3-1330 已在 AuditReport 補齊 artifact_who / artifact_updated 兩欄位
（資料層），但 track_audit.py 的 _format_audit_report 尚未讀取這兩欄位輸出，
使 CLI 使用者看不到「這份被稽核的 artifact 是誰、何時寫的」。本測試直接針對
_format_audit_report（純函式）驗證輸出內容，不經 run_audit（資料層已有
test_acceptance_auditor_artifact_writer.py 覆蓋）。

覆蓋 cases：
1. artifact_who 與 artifact_updated 皆非空 → 輸出含兩者的值
2. 皆為空字串 → 輸出不含該行（不製造誤導性的「未知/未知」雜訊）
3. 僅 artifact_who 非空 → 輸出行對缺失的 artifact_updated 標註「未知」
"""

from __future__ import annotations

from ticket_system.commands.track_audit import _format_audit_report
from ticket_system.lib.acceptance_auditor import AuditReport


def _make_report(*, artifact_who: str, artifact_updated: str) -> AuditReport:
    return AuditReport(
        ticket_id="0.0.0-W1-001",
        title="test",
        timestamp="2026-09-08T00:00:00",
        steps=[],
        overall_passed=True,
        artifact_who=artifact_who,
        artifact_updated=artifact_updated,
    )


def test_format_audit_report_shows_artifact_who_and_updated_when_present():
    report = _make_report(artifact_who="thyme-python-developer", artifact_updated="2026-09-08")

    output = _format_audit_report(report)

    assert "thyme-python-developer" in output
    assert "2026-09-08" in output


def test_format_audit_report_omits_artifact_line_when_both_missing():
    report = _make_report(artifact_who="", artifact_updated="")

    output = _format_audit_report(report)

    assert "執行者:" not in output
    assert "最後更新:" not in output


def test_format_audit_report_marks_unknown_for_missing_updated():
    report = _make_report(artifact_who="thyme-python-developer", artifact_updated="")

    output = _format_audit_report(report)

    assert "thyme-python-developer" in output
    assert "未知" in output
