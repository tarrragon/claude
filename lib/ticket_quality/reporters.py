"""
Ticket Quality Gate - 報告生成器

提供 Markdown 和 JSON 格式的檢測報告生成功能
"""

import json
from typing import Dict, Any
from datetime import datetime


def generate_markdown_report(check_results: Dict[str, Any], file_path: str) -> str:
    """
    生成 Markdown 格式的檢測報告

    Args:
        check_results: 完整檢測結果
        file_path: Ticket 檔案路徑

    Returns:
        str - Markdown 格式報告
    """
    sections = []
    sections.append(_build_report_header(check_results, file_path))
    sections.append(_build_report_summary(check_results))
    sections.append(_build_c1_section(check_results))
    sections.append(_build_c2_section(check_results))
    sections.append(_build_c3_section(check_results))
    sections.append(_build_human_review_section(check_results))
    sections.append(_build_report_footer())
    return "\n".join(sections)


def _build_report_header(results: Dict[str, Any], path: str) -> str:
    """
    建立報告標題

    Returns:
        str: Markdown 標題章節
    """
    return f"""# [WARNING] Ticket 品質檢測報告

**檔案**: `{path}`
**檢測時間**: {results.get('check_time', '')}
**整體狀態**: {results.get('overall_status', 'unknown')}
**整體信心度**: {results.get('overall_confidence', 0):.2f}

---
"""


def _build_report_summary(results: Dict[str, Any]) -> str:
    """
    建立檢測摘要

    Returns:
        str: Markdown 摘要章節
    """
    summary = results.get("summary", {})
    return f"""## 檢測摘要

- **總檢測數**: {summary.get('total_checks', 0)}
- **通過**: {summary.get('passed', 0)} [PASS]
- **失敗**: {summary.get('failed', 0)} [FAIL]
- **警告**: {summary.get('warnings', 0)} [WARNING]
- **錯誤**: {summary.get('errors', 0)} [ERROR]

---
"""


def _build_c1_section(results: Dict[str, Any]) -> str:
    """
    建立 C1 God Ticket 檢測章節

    Returns:
        str: Markdown C1 章節
    """
    checks = results.get("checks", {})
    if "c1_god_ticket" not in checks:
        return ""

    c1 = checks["c1_god_ticket"]
    emoji = "[FAIL]" if c1["status"] == "failed" else "[PASS]"
    lines = [
        f"## {emoji} C1. God Ticket 檢測",
        "",
        f"**狀態**: {c1['status']}",
        f"**信心度**: {c1['confidence']:.2f}",
        ""
    ]

    details = c1.get("details", {})
    if details:
        lines.extend([
            "### 檢測詳情",
            "",
            f"- **檔案數量**: {details.get('file_count', 0)} / {details.get('file_count_threshold', 10)} ({details.get('file_count_status', 'unknown')})",
            f"- **層級跨度**: {details.get('layer_span', 0)} / {details.get('layer_span_threshold', 1)} ({details.get('layer_span_status', 'unknown')})",
            f"- **預估工時**: {details.get('estimated_hours', 0)}h / {details.get('estimated_hours_threshold', 16)}h ({details.get('estimated_hours_status', 'unknown')})",
            f"- **涉及層級**: {details.get('layers_involved', [])}",
            ""
        ])

    lines.extend(_build_recommendations_section(c1))
    return "\n".join(lines)


def _build_c2_section(results: Dict[str, Any]) -> str:
    """
    建立 C2 Incomplete Ticket 檢測章節

    Returns:
        str: Markdown C2 章節
    """
    checks = results.get("checks", {})
    if "c2_incomplete_ticket" not in checks:
        return ""

    c2 = checks["c2_incomplete_ticket"]
    emoji = "[FAIL]" if c2["status"] == "failed" else "[PASS]"
    lines = [
        f"## {emoji} C2. Incomplete Ticket 檢測",
        "",
        f"**狀態**: {c2['status']}",
        f"**信心度**: {c2['confidence']:.2f}",
        ""
    ]

    details = c2.get("details", {})
    if details:
        lines.extend([
            "### 檢測詳情",
            "",
            f"- **驗收條件**: {'[PASS]' if details.get('has_acceptance_criteria') else '[FAIL]'} ({details.get('acceptance_count', 0)} 個)",
            f"- **測試規劃**: {'[PASS]' if details.get('has_test_plan') else '[FAIL]'} ({len(details.get('test_files', []))} 個測試檔案)",
            f"- **工作日誌**: {'[PASS]' if details.get('has_work_log') else '[FAIL]'} ({details.get('work_log_file', '')})",
            f"- **參考文件**: {'[PASS]' if details.get('has_references') else '[FAIL]'} ({details.get('reference_count', 0)} 個)",
            ""
        ])

        missing = details.get("missing_elements", [])
        if missing:
            lines.extend(["### 缺失元素", ""])
            lines.extend([f"- [FAIL] {elem}" for elem in missing])
            lines.append("")

    lines.extend(_build_recommendations_section(c2))
    return "\n".join(lines)


def _build_c3_section(results: Dict[str, Any]) -> str:
    """
    建立 C3 Ambiguous Responsibility 檢測章節

    Returns:
        str: Markdown C3 章節
    """
    checks = results.get("checks", {})
    if "c3_ambiguous_responsibility" not in checks:
        return ""

    c3 = checks["c3_ambiguous_responsibility"]
    emoji = "[FAIL]" if c3["status"] == "failed" else "[PASS]"
    lines = [
        f"## {emoji} C3. Ambiguous Responsibility 檢測",
        "",
        f"**狀態**: {c3['status']}",
        f"**信心度**: {c3['confidence']:.2f}",
        ""
    ]

    details = c3.get("details", {})
    if details:
        lines.extend([
            "### 檢測詳情",
            "",
            f"- **層級標示**: {'[PASS]' if details.get('has_layer_marker') else '[FAIL]'} ({details.get('layer_marker', '')})",
            f"- **職責描述**: {'[PASS]' if details.get('has_responsibility_desc') else '[FAIL]'} (清晰度: {details.get('responsibility_clarity', 'none')})",
            f"- **檔案範圍**: {'[PASS]' if details.get('file_scope_clear') else '[FAIL]'}",
            f"- **驗收限定**: {'[PASS]' if details.get('acceptance_aligned') else '[FAIL]'}",
            ""
        ])

        mismatched = details.get("mismatched_files", [])
        if mismatched:
            lines.extend(["### 層級不符檔案", ""])
            lines.extend([f"- {file}" for file in mismatched])
            lines.append("")

    lines.extend(_build_recommendations_section(c3))
    return "\n".join(lines)


def _build_recommendations_section(check_result: Dict[str, Any]) -> list:
    """
    建立修正建議章節

    Args:
        check_result: 單一檢測結果

    Returns:
        list: Markdown 建議列表
    """
    recs = check_result.get("recommendations", [])
    if not recs:
        return []

    lines = ["### 修正建議", ""]
    lines.extend([f"- {rec}" for rec in recs])
    lines.append("")
    return lines


def _build_human_review_section(results: Dict[str, Any]) -> str:
    """
    建立人工審查章節

    Returns:
        str: Markdown 人工審查章節
    """
    summary = results.get("summary", {})
    needs_review = summary.get("needs_human_review", [])
    if not needs_review:
        return ""

    lines = ["---", "", "## [WARNING] 需人工審查項目", ""]
    lines.extend([f"- {item}" for item in needs_review])
    lines.append("")
    return "\n".join(lines)


def _build_report_footer() -> str:
    """
    建立報告結尾

    Returns:
        str: Markdown 結尾
    """
    return """---

_此報告由 Ticket Quality Gate Hook 自動生成_"""


def generate_json_report(check_results: Dict[str, Any], file_path: str) -> str:
    """
    生成 JSON 格式的檢測報告

    Args:
        check_results: 完整檢測結果
        file_path: Ticket 檔案路徑

    Returns:
        str - JSON 格式報告
    """
    report = {
        "file_path": file_path,
        "check_time": check_results.get("check_time", datetime.now().isoformat()),
        "overall_status": check_results.get("overall_status", "unknown"),
        "overall_confidence": check_results.get("overall_confidence", 0.0),
        "summary": check_results.get("summary", {}),
        "checks": check_results.get("checks", {})
    }

    return json.dumps(report, ensure_ascii=False, indent=2)
