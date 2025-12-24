"""
Ticket Quality Gate - Code Smell 檢測函式

提供 C1/C2/C3 Code Smell 自動化檢測功能
"""

from typing import Dict, List, Any
from .extractors import (
    has_section,
    extract_section,
    extract_acceptance_criteria,
    extract_file_paths,
    count_steps
)
from .analyzers import (
    determine_layer,
    calculate_layer_span,
    estimate_hours
)


def check_incomplete_ticket_automated(ticket_content: str) -> Dict[str, Any]:
    """
    需求：[v0.12.G.2] C2. Incomplete Ticket Code Smell 自動化檢測

    業務規則：
    - BR-C2.1: 驗收條件必須包含至少 3 個可驗證項目
    - BR-C2.2: 測試規劃必須包含至少 1 個測試檔案路徑
    - BR-C2.3: 工作日誌必須規劃檔案路徑（docs/work-logs/）
    - BR-C2.4: 參考文件必須包含至少 1 個參考連結
    - BR-C2.5: 缺少任一必要元素即判定為 Incomplete Ticket

    約束：
    - 驗收條件提取依賴 extract_acceptance_criteria() 正則匹配
    - 測試檔案識別基於路徑前綴 test/
    - 工作日誌識別支援章節標題或路徑模式
    - 參考文件計數依賴列表項目 regex 匹配
    - 信心度固定為 1.0（明確缺失）或 0.95（全部存在）

    維護指引：
    - 修改檢測閾值時需同步更新 Phase 1 設計文件（v0.12.G.2 第 3.2 節）
    - 新增檢測項目需更新 missing_elements 列表和 recommendations 生成邏輯
    - 修改信心度計算需重新執行 Phase 2 測試驗證

    參考文件：v0.12.G.2 第 3.2 節 - C2 檢測標準

    Args:
        ticket_content: Ticket 內容（Markdown 格式）

    Returns:
        dict: 檢測結果（status, confidence, details, recommendations, needs_human_review）
    """
    elements = _check_required_elements(ticket_content)

    status = _determine_incomplete_status(elements)
    confidence = _calculate_incomplete_confidence(elements)
    details = _build_incomplete_details(elements)
    recommendations = _generate_incomplete_recommendations(elements)

    return {
        "status": status,
        "confidence": confidence,
        "details": details,
        "recommendations": recommendations,
        "needs_human_review": False
    }


def _check_required_elements(content: str) -> dict:
    """
    檢查必要元素

    Returns:
        dict: {acceptance, test_plan, work_log, references, missing}
    """
    import re

    # 驗收條件
    acceptance = extract_acceptance_criteria(content)
    has_acceptance = len(acceptance) >= 3

    # 測試規劃
    paths = extract_file_paths(content)
    test_files = [p for p in paths if p.startswith("test/")]
    has_test = len(test_files) > 0

    # 工作日誌
    has_work_log = has_section(content, "工作日誌") or "docs/work-logs/" in content
    work_log_file = ""
    if has_work_log:
        matches = re.findall(r"(docs/work-logs/[\w\-/.]+\.md)", content)
        work_log_file = matches[0] if matches else ""

    # 參考文件
    has_refs = has_section(content, "參考文件")
    ref_count = 0
    if has_refs:
        ref_section = extract_section(content, "參考文件")
        ref_count = len(re.findall(r"^-\s+(.+)", ref_section, re.MULTILINE))

    # 缺失元素
    missing = []
    if not has_acceptance:
        missing.append("acceptance_criteria")
    if not has_test:
        missing.append("test_plan")
    if not has_work_log:
        missing.append("work_log")
    if not has_refs or ref_count < 1:
        missing.append("references")

    return {
        "has_acceptance": has_acceptance,
        "acceptance_count": len(acceptance),
        "has_test": has_test,
        "test_files": test_files,
        "has_work_log": has_work_log,
        "work_log_file": work_log_file,
        "has_refs": has_refs,
        "ref_count": ref_count,
        "missing": missing
    }


def _determine_incomplete_status(elements: dict) -> str:
    """
    判斷 Incomplete Ticket 狀態

    Args:
        elements: 必要元素檢查結果

    Returns:
        str: "failed" 或 "passed"
    """
    return "failed" if len(elements["missing"]) > 0 else "passed"


def _calculate_incomplete_confidence(elements: dict) -> float:
    """
    計算 Incomplete Ticket 信心度

    規則:
    - 有缺失: 1.0（明確缺失）
    - 全部存在: 0.95（高度確信）
    """
    if len(elements["missing"]) > 0:
        return 1.0
    else:
        return 0.95


def _build_incomplete_details(elements: dict) -> dict:
    """
    建立 Incomplete Ticket 檢測詳情

    Returns:
        dict: 包含所有檢測元素和狀態
    """
    return {
        "has_acceptance_criteria": elements["has_acceptance"],
        "acceptance_count": elements["acceptance_count"],
        "has_test_plan": elements["has_test"],
        "test_files": elements["test_files"],
        "has_work_log": elements["has_work_log"],
        "work_log_file": elements["work_log_file"],
        "has_references": elements["has_refs"],
        "reference_count": elements["ref_count"],
        "missing_elements": elements["missing"]
    }


def _generate_incomplete_recommendations(elements: dict) -> List[str]:
    """
    生成 Incomplete Ticket 修正建議

    Args:
        elements: 必要元素檢查結果

    Returns:
        List[str]: 修正建議
    """
    recs = []

    if "acceptance_criteria" in elements["missing"]:
        recs.append("新增「### 驗收條件」章節，至少包含 3 個可驗證的驗收項目")
    if "test_plan" in elements["missing"]:
        recs.append("規劃測試檔案，至少包含 1 個測試檔案路徑（test/.../*.dart）")
    if "work_log" in elements["missing"]:
        recs.append("規劃工作日誌檔案，格式: docs/work-logs/vX.Y.Z-feature-name.md")
    if "references" in elements["missing"]:
        recs.append("新增「### 參考文件」章節，至少包含 1 個參考文件連結")

    if len(elements["missing"]) == 0:
        recs.append("✅ 此 Ticket 符合 Incomplete Ticket 檢測標準")

    recs.append("參考文件: v0.12.G.2 C2 檢測標準")

    return recs


def check_god_ticket_automated(ticket_content: str) -> Dict[str, Any]:
    """
    需求：[v0.12.G.1] C1. God Ticket Code Smell 自動化檢測

    業務規則：
    - BR-C1.1: 檔案數量超過 10 個 = God Ticket（閾值可調整）
    - BR-C1.2: 層級跨度超過 1 層 = God Ticket（違反層級隔離原則）
    - BR-C1.3: 預估工時超過 16 小時 = God Ticket（2 個工作天上限）
    - BR-C1.4: 任一指標超標即判定為 God Ticket（組合邏輯）
    - BR-C1.5: 工時估算公式：step_count * 0.5 + file_count * 0.5 + layer_span * 2

    信心度評分規則（基於 Phase 1 設計）：
    - 檔案數量檢測：0.9-1.0（100% 自動化，依檔案數量調整）
    - 層級跨度檢測：0.3-1.0（依賴 determine_layer()，無法識別層級時降為 0.3）
    - 預估工時檢測：0.5-0.7（依賴經驗公式，信心度中等）
    - 整體信心度：加權平均（檔案 40%、層級 40%、工時 20%）

    約束：
    - 層級判斷依賴 determine_layer() 路徑模式匹配（可能無法識別新架構）
    - 工時估算依賴經驗公式，實際工時可能有 ±30% 誤差
    - 信心度 < 0.7 或無法識別層級時需人工審查
    - Infrastructure 層級（Layer 0）在跨度計算時忽略

    維護指引：
    - 修改檢測閾值時需同步更新 Phase 1 設計文件（v0.12.G.1 第 3.1 節）
    - 修改信心度計算邏輯需重新執行 Phase 2 測試驗證
    - 新增層級判斷規則需更新 analyzers.py 的 determine_layer()
    - 修改工時估算公式需更新 analyzers.py 的 estimate_hours()

    參考文件：v0.12.G.1 第 3.1 節 - C1 檢測標準、第 6.3 節 - 工時估算公式

    Args:
        ticket_content: Ticket 內容（Markdown 格式）

    Returns:
        dict: 檢測結果（status, confidence, details, recommendations, needs_human_review）
    """
    file_paths = extract_file_paths(ticket_content)
    metrics = _calculate_god_ticket_metrics(file_paths, ticket_content)

    status = _determine_god_ticket_status(metrics)
    confidence = _calculate_god_ticket_confidence(metrics)
    details = _build_god_ticket_details(metrics)
    recommendations = _generate_god_ticket_recommendations_from_metrics(metrics, file_paths)
    needs_review = _check_god_ticket_needs_review(metrics, confidence)

    return {
        "status": status,
        "confidence": confidence,
        "details": details,
        "recommendations": recommendations,
        "needs_human_review": needs_review
    }


def _calculate_god_ticket_metrics(paths: List[str], content: str) -> dict:
    """
    計算 God Ticket 指標

    Returns:
        dict: {file_count, layers, layer_span, step_count, estimated_hours, exceeded_metrics}
    """
    file_count = len(set(paths))
    layers = [determine_layer(p) for p in paths if determine_layer(p) > 0]
    layer_span = calculate_layer_span(layers) if layers else 0
    step_count = count_steps(content)
    estimated_hours = estimate_hours(step_count, file_count, layer_span)

    exceeded_metrics = []
    if file_count > 10:
        exceeded_metrics.append("file_count")
    if layer_span > 1:
        exceeded_metrics.append("layer_span")
    if estimated_hours > 16:
        exceeded_metrics.append("estimated_hours")

    return {
        "file_count": file_count,
        "layers": layers,
        "layer_span": layer_span,
        "step_count": step_count,
        "estimated_hours": estimated_hours,
        "exceeded_metrics": exceeded_metrics
    }


def _determine_god_ticket_status(metrics: dict) -> str:
    """
    判斷 God Ticket 狀態

    Args:
        metrics: 指標數據

    Returns:
        str: "failed" 或 "passed"
    """
    return "failed" if len(metrics["exceeded_metrics"]) > 0 else "passed"


def _calculate_god_ticket_confidence(metrics: dict) -> float:
    """
    計算 God Ticket 信心度

    策略:
    - God Ticket: 加權平均（檔案 40%、層級 40%、工時 20%）
    - 正常 Ticket: 最小值（保守評估）
    """
    file_count_conf = calculate_confidence_c1_file_count(metrics["file_count"])
    layer_span_conf = calculate_confidence_c1_layer_span(metrics["layers"], metrics["layer_span"])
    hours_conf = calculate_confidence_c1_estimated_hours(metrics["estimated_hours"])

    if len(metrics["exceeded_metrics"]) > 0:
        confidence = (file_count_conf * 0.4 + layer_span_conf * 0.4 + hours_conf * 0.2)
    else:
        confidence = min(file_count_conf, layer_span_conf, hours_conf)

    return round(confidence, 2)


def _build_god_ticket_details(metrics: dict) -> dict:
    """
    建立 God Ticket 檢測詳情

    Returns:
        dict: 包含所有檢測指標和狀態
    """
    return {
        "file_count": metrics["file_count"],
        "file_count_threshold": 10,
        "file_count_status": "failed" if metrics["file_count"] > 10 else "passed",
        "layer_span": metrics["layer_span"],
        "layer_span_threshold": 1,
        "layer_span_status": "failed" if metrics["layer_span"] > 1 else "passed",
        "estimated_hours": metrics["estimated_hours"],
        "estimated_hours_threshold": 16,
        "estimated_hours_status": "failed" if metrics["estimated_hours"] > 16 else "passed",
        "is_god_ticket": len(metrics["exceeded_metrics"]) > 0,
        "exceeded_metrics": metrics["exceeded_metrics"],
        "layers_involved": sorted(set(metrics["layers"]))
    }


def _generate_god_ticket_recommendations_from_metrics(metrics: dict, paths: List[str]) -> List[str]:
    """
    從指標生成修正建議

    Args:
        metrics: 指標數據
        paths: 檔案路徑列表

    Returns:
        List[str]: 修正建議
    """
    layers_involved = sorted(set(metrics["layers"]))
    return generate_god_ticket_recommendations(
        metrics["exceeded_metrics"],
        layers_involved,
        metrics["file_count"]
    )


def _check_god_ticket_needs_review(metrics: dict, confidence: float) -> bool:
    """
    判斷是否需要人工審查

    條件:
    - 信心度 < 0.7
    - 無法識別層級
    - 工時預估超過 16 小時
    """
    return (
        confidence < 0.7 or
        len(metrics["layers"]) == 0 or
        metrics["estimated_hours"] > 16
    )


def calculate_confidence_c1_file_count(file_count: int) -> float:
    """
    C1 檔案數量檢測信心度

    規則: 檔案數量檢測為 100% 自動化，信心度高
    """
    if file_count <= 3:
        return 1.0  # 完全確定：良好設計
    elif file_count <= 6:
        return 0.95  # 高度確信：需要檢查但可能合理
    else:  # file_count > 10
        return 0.9  # 高度確信：明確超標


def calculate_confidence_c1_layer_span(layers: List[int], layer_span: int) -> float:
    """
    C1 層級跨度檢測信心度

    規則: 層級判斷依賴 determine_layer()，可能有無法識別的路徑
    """
    if len(layers) == 0:
        return 0.3  # 極低信心度：無法識別任何層級
    elif layer_span == 1:
        return 1.0  # 完全確定：單層修改
    elif layer_span == 2:
        return 0.9  # 高度確信：可能合理（如 Facade 實作）
    else:  # layer_span > 2
        return 0.85  # 高度確信：明確違反原則


def calculate_confidence_c1_estimated_hours(estimated_hours: int) -> float:
    """
    C1 預估工時檢測信心度

    規則: 工時預估依賴經驗公式，信心度中等
    """
    if estimated_hours <= 4:
        return 0.7  # 中等信心度：簡單任務
    elif estimated_hours <= 8:
        return 0.6  # 中等信心度：中等任務
    else:  # estimated_hours > 16
        return 0.5  # 低信心度：複雜任務，需人工確認


def generate_god_ticket_recommendations(
    exceeded_metrics: List[str],
    layers_involved: List[int],
    file_count: int
) -> List[str]:
    """
    生成 God Ticket 修正建議

    Args:
        exceeded_metrics: 超標指標列表
        layers_involved: 涉及的層級
        file_count: 檔案數量

    Returns:
        List[str] - 修正建議列表
    """
    recommendations = []

    # 層級拆分建議
    if "layer_span" in exceeded_metrics and layers_involved:
        recommendations.append(
            f"將 Ticket 拆分為 {len(layers_involved)} 個子 Ticket（每個對應單一層級）"
        )
        layer_names = {
            1: "Layer 1 Ticket: UI/Presentation 實作",
            2: "Layer 2 Ticket: Application/Behavior 實作",
            3: "Layer 3 Ticket: UseCase 實作",
            4: "Layer 4 Ticket: Domain Events/Interfaces 實作",
            5: "Layer 5 Ticket: Domain Entities/Value Objects 實作"
        }
        for layer in sorted(layers_involved):
            if layer in layer_names:
                recommendations.append(layer_names[layer])

        recommendations.append("參考文件: v0.12.G.1 第 5.4 節 - Ticket 拆分指引")

    # 檔案數量拆分建議
    if "file_count" in exceeded_metrics:
        recommendations.append(
            f"檔案數量超標（{file_count} > 10），建議按模組或功能拆分"
        )

    # 層級跨度警告
    if "layer_span" in exceeded_metrics:
        recommendations.append(
            "層級跨度超標，建議按層級拆分（從外而內順序）"
        )

    # 工時預估拆分建議
    if "estimated_hours" in exceeded_metrics:
        recommendations.append(
            "預估工時超標，建議拆分為多個 2-4 小時的小任務"
        )

    # 通過建議
    if not exceeded_metrics:
        recommendations.append("✅ 此 Ticket 符合 God Ticket 檢測標準")

    return recommendations


def check_ambiguous_responsibility_automated(ticket_content: str) -> Dict[str, Any]:
    """
    需求：[v0.12.G.3] C3. Ambiguous Responsibility Code Smell 自動化檢測

    業務規則：
    - BR-C3.1: 必須包含層級標示（[Layer X] 或 Layer X:）
    - BR-C3.2: 必須包含職責描述章節（目標/職責）且內容清晰
    - BR-C3.3: 所有修改檔案必須屬於宣告層級（檔案範圍明確性）
    - BR-C3.4: 驗收條件必須對齊層級職責（≥50% 包含層級關鍵詞）
    - BR-C3.5: 任一項目不符即判定為 Ambiguous Responsibility

    職責描述清晰度判斷（啟發式規則）：
    - clear: 包含 ≥2 個職責關鍵詞（負責、專注、只、不包含等）且連接詞 ≤1 個
    - moderate: 包含 ≥1 個職責關鍵詞
    - unclear: 無職責關鍵詞或連接詞過多（暗示多重職責）

    層級關鍵詞對照表：
    - Layer 1 (UI): UI, Widget, 畫面, 顯示
    - Layer 2 (Controller): Controller, Bloc, ViewModel, 行為
    - Layer 3 (UseCase): UseCase, 使用案例, 業務流程
    - Layer 4 (Events/Interface): Event, Interface, Protocol, 介面
    - Layer 5 (Domain): Entity, Value Object, Domain, 領域

    信心度評分規則：
    - 層級標示信心度：1.0（明確匹配）
    - 職責描述信心度：0.8 (clear) / 0.6 (moderate) / 0.5 (unclear)
    - 檔案範圍信心度：1.0（全部對齊）/ 0.85（存在不對齊）
    - 驗收限定信心度：0.8（對齊）/ 0.6（未對齊）
    - 整體信心度：最小值（保守評估）

    約束：
    - 層級標示識別依賴正則表達式，可能誤判格式變體
    - 職責清晰度判斷為啟發式，需人工審查確認
    - 檔案範圍檢查依賴 determine_layer()，Infrastructure 層級忽略
    - 驗收對齊依賴關鍵詞匹配，可能誤判專業術語

    維護指引：
    - 修改檢測規則時需同步更新 Phase 1 設計文件（v0.12.G.3 第 3.3 節）
    - 修改清晰度判斷規則需更新啟發式關鍵詞列表
    - 修改層級關鍵詞對照表需同步更新測試案例
    - 職責描述評估需要人工審查確認（自動化信心度 < 1.0）

    參考文件：v0.12.G.3 第 3.3 節 - C3 檢測標準

    Args:
        ticket_content: Ticket 內容（Markdown 格式）

    Returns:
        dict: 檢測結果（status, confidence, details, recommendations, needs_human_review）
    """
    # 1. 檢測層級標示
    import re
    layer_marker_pattern = r"\[Layer\s+(\d)\]|Layer\s+(\d):"
    layer_match = re.search(layer_marker_pattern, ticket_content)
    has_layer_marker = layer_match is not None
    layer_marker = ""
    declared_layer = 0

    if has_layer_marker:
        # 提取層級編號
        declared_layer = int(layer_match.group(1) or layer_match.group(2))
        layer_marker = layer_match.group(0)

    # 如果沒有層級標示，直接回傳失敗
    if not has_layer_marker:
        return {
            "status": "failed",
            "confidence": 1.0,
            "details": {
                "has_layer_marker": False,
                "layer_marker": "",
                "has_responsibility_desc": False,
                "responsibility_clarity": "none",
                "file_scope_clear": False,
                "acceptance_aligned": False
            },
            "recommendations": [
                "新增層級標示，格式: [Layer X] 或 Layer X:",
                "參考文件: v0.12.G.3 C3 檢測標準"
            ],
            "needs_human_review": False
        }

    # 2. 檢測職責描述清晰度
    has_responsibility_desc = has_section(ticket_content, "目標") or \
                             has_section(ticket_content, "職責")
    responsibility_clarity = "none"

    if has_responsibility_desc:
        # 評估清晰度（啟發式規則）
        desc_section = extract_section(ticket_content, "目標") or \
                      extract_section(ticket_content, "職責")

        # 關鍵詞匹配
        clarity_keywords = ["負責", "專注", "只", "不包含", "排除", "限定"]
        matched_keywords = sum(1 for keyword in clarity_keywords if keyword in desc_section)

        # 連接詞計數（多連接詞 = 多職責 = 不清晰）
        connectors = ["和", "與", "以及", "同時", "還有"]
        connector_count = sum(1 for conn in connectors if conn in desc_section)

        if matched_keywords >= 2 and connector_count <= 1:
            responsibility_clarity = "clear"
        elif matched_keywords >= 1:
            responsibility_clarity = "moderate"
        else:
            responsibility_clarity = "unclear"

    # 3. 檢測檔案範圍明確性
    file_paths = extract_file_paths(ticket_content)
    file_scope_clear = True
    mismatched_files = []

    for path in file_paths:
        file_layer = determine_layer(path)
        if file_layer != declared_layer and file_layer != 0:  # 忽略 Infrastructure
            file_scope_clear = False
            mismatched_files.append(path)

    # 4. 檢測驗收限定對齊性
    acceptance_criteria = extract_acceptance_criteria(ticket_content)
    acceptance_aligned = True

    if acceptance_criteria:
        # 檢查驗收條件是否包含層級關鍵詞
        layer_keywords = {
            1: ["UI", "Widget", "畫面", "顯示"],
            2: ["Controller", "Bloc", "ViewModel", "行為"],
            3: ["UseCase", "使用案例", "業務流程"],
            4: ["Event", "Interface", "Protocol", "介面"],
            5: ["Entity", "Value Object", "Domain", "領域"]
        }

        relevant_keywords = layer_keywords.get(declared_layer, [])
        layer_specific_count = sum(
            1 for ac in acceptance_criteria
            if any(keyword in ac for keyword in relevant_keywords)
        )

        # 如果少於 50% 驗收條件包含層級關鍵詞，視為未對齊
        acceptance_aligned = (layer_specific_count / len(acceptance_criteria)) >= 0.5

    # 判斷是否為 Ambiguous Responsibility
    is_ambiguous = (
        not has_responsibility_desc or
        responsibility_clarity == "unclear" or
        not file_scope_clear or
        not acceptance_aligned
    )

    # 計算信心度（最小值）
    confidences = []

    # 層級標示信心度
    confidences.append(1.0)

    # 職責描述信心度
    if responsibility_clarity == "clear":
        confidences.append(0.8)
    elif responsibility_clarity == "moderate":
        confidences.append(0.6)
    else:
        confidences.append(0.5)

    # 檔案範圍信心度
    if file_scope_clear:
        confidences.append(1.0)
    else:
        confidences.append(0.85)

    # 驗收限定信心度
    if acceptance_aligned:
        confidences.append(0.8)
    else:
        confidences.append(0.6)

    confidence = min(confidences)

    # 生成修正建議
    recommendations = []

    if not has_responsibility_desc:
        recommendations.append("新增「### 目標」或「### 職責」章節，明確說明此 Ticket 的職責範圍")
    elif responsibility_clarity != "clear":
        recommendations.append("補充職責描述，明確說明此 Ticket 的邊界（負責什麼、不負責什麼）")

    if not file_scope_clear:
        recommendations.append(f"以下檔案不屬於宣告層級 Layer {declared_layer}: {', '.join(mismatched_files)}")
        recommendations.append("建議將這些檔案移至對應層級的 Ticket")

    if not acceptance_aligned:
        recommendations.append("建議在驗收條件中明確排除非此 Ticket 職責範圍的項目")
        recommendations.append("建議驗收條件使用層級相關的關鍵詞")

    if not is_ambiguous:
        recommendations.append("✅ 此 Ticket 符合 Ambiguous Responsibility 檢測標準")

    recommendations.append("參考文件: v0.12.G.3 C3 檢測標準")

    return {
        "status": "failed" if is_ambiguous else "passed",
        "confidence": round(confidence, 2),
        "details": {
            "has_layer_marker": has_layer_marker,
            "layer_marker": layer_marker,
            "declared_layer": declared_layer,
            "has_responsibility_desc": has_responsibility_desc,
            "responsibility_clarity": responsibility_clarity,
            "file_scope_clear": file_scope_clear,
            "mismatched_files": mismatched_files,
            "acceptance_aligned": acceptance_aligned
        },
        "recommendations": recommendations,
        "needs_human_review": responsibility_clarity != "clear"  # 職責描述評估需人工審查
    }
