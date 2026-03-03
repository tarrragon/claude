"""
Ticket Quality Gate - 分析函式

提供層級判斷、工時預估等分析功能
"""

from typing import List


def determine_layer(file_path: str) -> int:
    """
    判斷檔案所屬層級

    基於 v0.12.G.1 第 6.2 節決策樹

    路徑規範:
    - lib/ui/, lib/presentation/widgets/ → Layer 1
    - lib/application/, lib/presentation/controllers/ → Layer 2
    - lib/usecases/ → Layer 3
    - lib/domain/events/, lib/domain/interfaces/ → Layer 4
    - lib/domain/entities/, lib/domain/value_objects/ → Layer 5
    - lib/infrastructure/ → 0 (Infrastructure)

    Args:
        file_path: 檔案路徑

    Returns:
        int - 層級編號 (1-5)，無法識別返回 0
    """
    normalized_path = _normalize_file_path(file_path)

    if _is_layer_1_ui(normalized_path):
        return 1
    elif _is_layer_2_controller(normalized_path):
        return 2
    elif _is_layer_3_use_case(normalized_path):
        return 3
    elif _is_layer_4_interfaces(normalized_path):
        return 4
    elif _is_layer_5_domain(normalized_path):
        return 5
    elif _is_infrastructure(normalized_path):
        return 0
    else:
        return 0


def _normalize_file_path(path: str) -> str:
    """
    標準化檔案路徑

    處理: 轉小寫、移除 lib/ 前綴
    """
    normalized = path.lower()
    return normalized.replace("lib/", "")


def _is_layer_1_ui(path: str) -> bool:
    """
    判斷是否為 Layer 1 (UI/Presentation)

    路徑模式: ui/, presentation/widgets/, presentation/pages/, etc.
    """
    patterns = [
        "ui/",
        "presentation/widgets/",
        "presentation/pages/",
        "presentation/screens/",
        "widgets/"
    ]
    return any(pattern in path for pattern in patterns)


def _is_layer_2_controller(path: str) -> bool:
    """
    判斷是否為 Layer 2 (Application/Behavior)

    路徑模式: application/, presentation/controllers/, blocs/, etc.
    """
    patterns = [
        "application/",
        "presentation/controllers/",
        "presentation/viewmodels/",
        "presentation/blocs/",
        "controllers/",
        "blocs/"
    ]
    return any(pattern in path for pattern in patterns)


def _is_layer_3_use_case(path: str) -> bool:
    """
    判斷是否為 Layer 3 (UseCase)

    路徑模式: usecases/, use_cases/, application/use_cases/
    """
    patterns = [
        "usecases/",
        "use_cases/",
        "application/use_cases/"
    ]
    return any(pattern in path for pattern in patterns)


def _is_layer_4_interfaces(path: str) -> bool:
    """
    判斷是否為 Layer 4 (Domain Events/Interfaces)

    路徑模式: domain/events/, domain/interfaces/, domain/protocols/
    """
    patterns = [
        "domain/events/",
        "domain/interfaces/",
        "domain/protocols/"
    ]
    return any(pattern in path for pattern in patterns)


def _is_layer_5_domain(path: str) -> bool:
    """
    判斷是否為 Layer 5 (Domain Implementation)

    路徑模式: domain/entities/, domain/value_objects/, domain/services/
    """
    patterns = [
        "domain/entities/",
        "domain/value_objects/",
        "domain/services/",
        "domain/aggregates/"
    ]
    return any(pattern in path for pattern in patterns)


def _is_infrastructure(path: str) -> bool:
    """
    判斷是否為 Infrastructure 層

    路徑模式: infrastructure/
    """
    return "infrastructure/" in path


def calculate_layer_span(layers: List[int]) -> int:
    """
    計算層級跨度

    公式: max(layers) - min(layers) + 1

    Args:
        layers: 層級列表

    Returns:
        int - 層級跨度，空列表返回 0
    """
    if not layers:
        return 0

    # 過濾掉 0（Infrastructure）
    filtered_layers = [layer for layer in layers if layer > 0]

    if not filtered_layers:
        return 0

    return max(filtered_layers) - min(filtered_layers) + 1


def estimate_hours(step_count: int, file_count: int, layer_span: int) -> int:
    """
    預估工時

    預估公式：基礎工時 + 檔案修正 + 層級修正
    公式：step_count * 0.5 + file_count * 0.5 + layer_span * 2

    Args:
        step_count: 步驟數量
        file_count: 檔案數量
        layer_span: 層級跨度

    Returns:
        int - 預估工時（小時）
    """
    base_hours = step_count * 0.5
    file_correction = file_count * 0.5
    layer_correction = layer_span * 2

    return int(base_hours + file_correction + layer_correction)
