"""Plan 檔案解析器模組。

此模組負責解析 Markdown 格式的 Plan 檔案，將其轉換為結構化的任務清單。
主要功能包括：
1. 提取 Plan 標題和概述
2. 解析實作步驟清單
3. 識別修改檔案
4. 推斷任務類型和架構層級
5. 估算複雜度
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple
import re


@dataclass
class PlanTask:
    """Plan 中的單一任務項目。

    Attributes:
        title: 任務標題（如「建立 XX 模組」）
        description: 任務詳細說明（可選）
        action: 動詞（如「建立」「修改」「分析」）
        target: 目標（如「XX 模組」「YY 檔案」）
        files: 影響的檔案清單
        layer: 架構層級（Domain/Application/Infrastructure/Presentation/待定義）
        task_type: 任務類型（IMP/ADJ/ANA/RES/DOC）
        complexity: 認知負擔指數（1-15+）
        order: 任務在 Plan 中的順序（從 1 開始）
    """
    title: str
    description: str = ""
    action: str = ""
    target: str = ""
    files: List[str] = field(default_factory=list)
    layer: str = "待定義"
    task_type: str = "IMP"
    complexity: int = 5
    order: int = 0


@dataclass
class PlanParseResult:
    """Plan 檔案解析結果。

    Attributes:
        plan_title: Plan 標題（從第一個 # 標題提取）
        plan_description: Plan 描述（從 ## 概述 提取）
        tasks: 任務清單（PlanTask 清單）
        total_tasks: 任務總數
        success: 解析是否成功
        error_message: 錯誤訊息（若解析失敗）
    """
    plan_title: str = ""
    plan_description: str = ""
    tasks: List[PlanTask] = field(default_factory=list)
    total_tasks: int = 0
    success: bool = False
    error_message: str = ""


# 任務類型推斷規則
_TASK_TYPE_KEYWORDS = {
    "IMP": ["建立", "新增", "實作"],
    "ADJ": ["修改", "調整", "修正"],
    "ANA": ["分析", "研究", "調查"],
    "RES": ["研究"],
    "DOC": ["撰寫", "更新文件", "記錄"],
}

# 架構層級推斷規則
_LAYER_PATTERNS = {
    "Domain": [r"domain", r"entity", r"value_object"],
    "Application": [r"application", r"use_case", r"service"],
    "Infrastructure": [r"infrastructure", r"repository", r"data_source"],
    "Presentation": [r"presentation", r"widget", r"screen", r"page"],
}


def _infer_task_type(title: str) -> str:
    """根據標題推斷任務類型。

    Args:
        title: 任務標題

    Returns:
        任務類型（IMP/ADJ/ANA/RES/DOC）
    """
    title_lower = title.lower()

    for task_type, keywords in _TASK_TYPE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in title:
                return task_type

    return "IMP"  # 預設類型


def _infer_layer(files: List[str]) -> str:
    """根據檔案路徑推斷架構層級。

    Args:
        files: 檔案路徑清單

    Returns:
        架構層級（Domain/Application/Infrastructure/Presentation/待定義）
    """
    if not files:
        return "待定義"

    # 取第一個檔案來推斷層級
    file_path = files[0].lower()

    for layer, patterns in _LAYER_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, file_path):
                return layer

    return "待定義"


def _extract_action_and_target(title: str) -> Tuple[str, str]:
    """從標題提取動詞和目標。

    Args:
        title: 任務標題

    Returns:
        (action, target) tuple
    """
    # 嘗試匹配「動詞 目標」的模式
    match = re.match(r"(\S+)[\s]+(.+)", title)
    if match:
        action = match.group(1)
        target = match.group(2)
        return action, target

    return "", title


def _estimate_complexity(
    files: List[str],
    description: str,
    task_type: str
) -> int:
    """估算任務的認知負擔指數。

    複雜度估算邏輯：
    - 基礎複雜度：5
    - 每個檔案 +1（最多 +4）
    - 描述長度 > 100 字 +1
    - 描述長度 > 200 字 +2
    - DOC 類型 -1（通常簡單）
    - ANA 類型 +1（通常需要分析）

    Args:
        files: 修改檔案清單
        description: 任務描述
        task_type: 任務類型

    Returns:
        複雜度指數（1-15+）
    """
    complexity = 5

    # 檔案數量
    complexity += min(len(files), 4)

    # 描述長度
    if len(description) > 200:
        complexity += 2
    elif len(description) > 100:
        complexity += 1

    # 任務類型調整
    if task_type == "DOC":
        complexity = max(1, complexity - 1)
    elif task_type == "ANA":
        complexity += 1

    return min(complexity, 15)  # 上限 15


def _parse_implementation_steps(content: str) -> Tuple[List[PlanTask], str]:
    """解析實作步驟區段。

    Args:
        content: Markdown 內容

    Returns:
        (任務清單, 錯誤訊息)
    """
    tasks = []

    # 尋找 "## 實作步驟" 區段
    impl_pattern = r"##\s+實作步驟\s*\n(.*?)(?=##\s+|\Z)"
    match = re.search(impl_pattern, content, re.DOTALL)

    if not match:
        return [], "找不到實作步驟區段"

    impl_section = match.group(1)

    # 尋找有序清單項目（1. 2. 3. ...）
    # 支援的格式：
    # 1. 標題
    #    - 修改檔案：檔案1
    #    - 修改檔案：檔案2
    #    說明文字

    lines = impl_section.split("\n")
    current_task = None
    current_order = 0

    for line in lines:
        # 檢查有序清單項目
        list_match = re.match(r"^\d+\.\s+(.+)$", line.strip())
        if list_match:
            # 保存前一個任務
            if current_task:
                current_task.order = current_order
                tasks.append(current_task)

            # 建立新任務
            current_order += 1
            title = list_match.group(1).strip()

            current_task = PlanTask(
                title=title,
                action="",
                target="",
                files=[],
                description=""
            )
        elif current_task is not None:
            # 解析子項目和描述
            stripped = line.strip()

            # 檢查「修改檔案：」
            if "修改檔案：" in stripped:
                # 提取「修改檔案：」後的內容
                file_path = stripped.split("修改檔案：", 1)[1].strip()

                # 確保提取的是實際的檔案路徑（包含副檔名）
                if re.search(r".+\.(?:py|dart|md)$", file_path):
                    if file_path not in current_task.files:
                        current_task.files.append(file_path)
            # 其他以「-」開頭的項目或描述
            elif stripped and not stripped.startswith("-"):
                if current_task.description:
                    current_task.description += "\n" + stripped
                else:
                    current_task.description = stripped
            # 其他描述內容
            elif stripped and not stripped.startswith("-"):
                if current_task.description:
                    current_task.description += "\n" + stripped
                else:
                    current_task.description = stripped

    # 保存最後一個任務
    if current_task:
        current_task.order = current_order
        tasks.append(current_task)

    if not tasks:
        return [], "無法解析任務項目"

    return tasks, ""


def parse_plan(plan_file: Path) -> PlanParseResult:
    """解析 Plan 檔案。

    Args:
        plan_file: Plan 檔案路徑（Path 物件）

    Returns:
        PlanParseResult: 解析結果

    解析規則:
        1. 提取 Plan 標題（第一個 # 標題）
        2. 提取 Plan 描述（## 概述 區段）
        3. 解析實作步驟（## 實作步驟 區段）
        4. 推斷任務屬性：
           - action 和 target：從標題解析
           - layer：從檔案路徑推斷
           - task_type：從關鍵字推斷
           - complexity：根據檔案數和描述長度估算

    邊界條件處理:
        - 檔案不存在 -> success=False
        - 無實作步驟 -> success=False
        - 無任務項目 -> success=False
    """
    # 驗證檔案存在
    if not plan_file.exists():
        return PlanParseResult(
            success=False,
            error_message="檔案不存在"
        )

    # 驗證檔案副檔名
    if plan_file.suffix != ".md":
        return PlanParseResult(
            success=False,
            error_message="檔案副檔名必須為 .md"
        )

    try:
        # 讀取檔案內容
        content = plan_file.read_text(encoding="utf-8")
    except Exception as e:
        return PlanParseResult(
            success=False,
            error_message=f"無法讀取檔案: {str(e)}"
        )

    if not content.strip():
        return PlanParseResult(
            success=False,
            error_message="檔案為空"
        )

    # 提取 Plan 標題（第一個 # 標題）
    title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    plan_title = title_match.group(1).strip() if title_match else ""

    if not plan_title:
        return PlanParseResult(
            success=False,
            error_message="無法提取 Plan 標題"
        )

    # 提取 Plan 描述（## 概述 區段）
    desc_pattern = r"##\s+概述\s*\n(.*?)(?=##\s+|\Z)"
    desc_match = re.search(desc_pattern, content, re.DOTALL)
    plan_description = desc_match.group(1).strip() if desc_match else ""

    # 解析實作步驟
    tasks, error_msg = _parse_implementation_steps(content)

    if error_msg:
        return PlanParseResult(
            success=False,
            error_message=error_msg
        )

    # 推斷任務屬性
    for task in tasks:
        # 推斷 task_type
        task.task_type = _infer_task_type(task.title)

        # 推斷 layer
        task.layer = _infer_layer(task.files)

        # 提取 action 和 target
        action, target = _extract_action_and_target(task.title)
        task.action = action
        task.target = target if target != task.title else ""

        # 估算 complexity
        task.complexity = _estimate_complexity(
            task.files,
            task.description,
            task.task_type
        )

    return PlanParseResult(
        plan_title=plan_title,
        plan_description=plan_description,
        tasks=tasks,
        total_tasks=len(tasks),
        success=True,
        error_message=""
    )
