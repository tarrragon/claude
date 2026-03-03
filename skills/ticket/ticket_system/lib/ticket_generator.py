"""
Ticket 生成模組

負責將 Plan 解析結果轉換為 Atomic Tickets。
提供 TDD 階段映射、Wave 分配和並行分組功能。
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from pathlib import Path

from ticket_system.lib.plan_parser import PlanParseResult, PlanTask
from ticket_system.lib.ticket_builder import (
    TicketConfig,
    format_ticket_id,
    format_child_ticket_id,
    get_next_seq,
    get_next_child_seq,
    create_ticket_frontmatter,
    create_ticket_body,
)


@dataclass
class GeneratedTicket:
    """生成的 Ticket 資訊。

    Attributes:
        id: Ticket ID（如 0.31.0-W5-001）
        title: Ticket 標題（「動詞 + 目標」格式）
        content: 完整 Ticket Markdown 內容（frontmatter + body）
        tdd_phases: TDD 階段清單（Phase 1-4）
        wave: Wave 編號
    """

    id: str
    title: str
    content: str
    tdd_phases: List[str] = field(default_factory=list)
    wave: int = 1


@dataclass
class GenerationResult:
    """Ticket 生成結果。

    Attributes:
        tickets: 生成的 Ticket 清單
        total: Ticket 總數
        success: 生成是否成功
        error_message: 錯誤訊息（若生成失敗）
        dry_run: 是否為預演模式
    """

    tickets: List[GeneratedTicket] = field(default_factory=list)
    total: int = 0
    success: bool = False
    error_message: str = ""
    dry_run: bool = False


# TDD 階段映射規則
_TDD_STAGE_MAP = {
    "IMP": ["phase1", "phase2", "phase3a", "phase3b", "phase4"],  # 新功能：完整 TDD
    "ADJ": ["phase3b", "phase4"],  # 調整：簡化 TDD
    "DOC": [],  # 文件：無 TDD
    "ANA": [],  # 分析：無 TDD
    "RES": [],  # 研究：無 TDD
}


def _get_tdd_stages(task_type: str, complexity: int) -> List[str]:
    """根據任務類型和複雜度取得 TDD 階段。

    Args:
        task_type: 任務類型（IMP/ADJ/DOC 等）
        complexity: 認知負擔指數（1-15+）

    Returns:
        TDD 階段清單
    """
    stages = _TDD_STAGE_MAP.get(task_type, ["phase3b", "phase4"])

    # 複雜度高時新增 Phase 0（SA 審查）
    if task_type == "IMP" and complexity > 10:
        stages = ["phase0"] + stages

    return stages


def _map_tdd_stages(
    parse_result: PlanParseResult,
) -> Dict[str, List[str]]:
    """映射每個任務的 TDD 階段。

    Args:
        parse_result: Plan 解析結果

    Returns:
        任務與 TDD 階段的對應字典 {task_order: [phases]}
    """
    task_stages: Dict[str, List[str]] = {}

    for task in parse_result.tasks:
        stages = _get_tdd_stages(task.task_type, task.complexity)
        task_stages[str(task.order)] = stages

    return task_stages


def _assign_wave(
    parse_result: PlanParseResult,
    base_wave: int,
) -> Dict[str, int]:
    """分配 Wave 編號給每個任務。

    簡單策略：根據任務複雜度分組
    - 低複雜度（< 6）：同 Wave
    - 中複雜度（6-10）：同 Wave
    - 高複雜度（> 10）：獨立 Wave

    Args:
        parse_result: Plan 解析結果
        base_wave: 基礎 Wave 編號

    Returns:
        任務與 Wave 的對應字典 {task_order: wave}
    """
    task_waves: Dict[str, int] = {}
    current_wave = base_wave
    last_high_complexity = False

    for task in parse_result.tasks:
        if task.complexity > 10 and last_high_complexity:
            # 高複雜度任務之間增加 Wave 分隔
            current_wave += 1

        task_waves[str(task.order)] = current_wave
        last_high_complexity = task.complexity > 10

    return task_waves


def _format_ticket_content(
    frontmatter: Dict[str, Any],
    body: str,
) -> str:
    """格式化 Ticket 內容（frontmatter + body）。

    Args:
        frontmatter: Frontmatter 字典
        body: Body Markdown 內容

    Returns:
        完整 Ticket Markdown 內容
    """
    import yaml

    # 轉換 frontmatter 為 YAML 字串
    yaml_str = yaml.dump(frontmatter, allow_unicode=True, sort_keys=False)

    # 組合 frontmatter 和 body
    content = f"---\n{yaml_str}---\n\n{body}"
    return content


def generate(
    parse_result: PlanParseResult,
    version: str,
    base_wave: int,
    dry_run: bool = False,
) -> GenerationResult:
    """根據 Plan 解析結果生成 Tickets。

    Args:
        parse_result: Plan 解析結果
        version: 版本號（如 "0.31.0"）
        base_wave: 基礎 Wave 編號
        dry_run: 是否為預演模式（不實際建立檔案）

    Returns:
        GenerationResult: 生成結果
    """
    # 驗證 Plan 解析結果
    if not parse_result.success:
        return GenerationResult(
            success=False,
            error_message=parse_result.error_message,
            dry_run=dry_run,
        )

    if not parse_result.tasks:
        return GenerationResult(
            success=False,
            error_message="無任務項目",
            dry_run=dry_run,
        )

    # 映射 TDD 階段和 Wave
    task_stages = _map_tdd_stages(parse_result)
    task_waves = _assign_wave(parse_result, base_wave)

    generated_tickets: List[GeneratedTicket] = []
    wave_seq_map: Dict[int, int] = {}  # 內部計數器：記錄每個 Wave 已使用的序號

    try:
        for task in parse_result.tasks:
            task_order_str = str(task.order)

            # 取得該任務的 TDD 階段和 Wave
            tdd_phases = task_stages.get(task_order_str, [])
            wave = task_waves.get(task_order_str, base_wave)

            # 產生 Ticket ID
            # 首次遇到此 Wave 時，從磁碟初始化序號；後續在迴圈中遞增
            if wave not in wave_seq_map:
                wave_seq_map[wave] = get_next_seq(version, wave)
            else:
                wave_seq_map[wave] += 1

            seq = wave_seq_map[wave]
            ticket_id = format_ticket_id(version, wave, seq)

            # 建立 TicketConfig
            config: TicketConfig = {
                "ticket_id": ticket_id,
                "version": version,
                "wave": wave,
                "title": task.title,
                "ticket_type": task.task_type,
                "priority": "P2",  # 預設優先級
                "who": "pending",  # 待指派
                "what": task.description or task.title,
                "when": "待定義",
                "where_layer": task.layer,
                "where_files": task.files,
                "why": parse_result.plan_description or "Plan 來源",
                "how_task_type": task.action or "Implementation",
                "how_strategy": "待定義",
                "tdd_phase": tdd_phases[0] if tdd_phases else None,
                "tdd_stage": tdd_phases,
                "acceptance": None,  # 使用預設驗收條件
            }

            # 產生 frontmatter 和 body
            frontmatter = create_ticket_frontmatter(config)
            body = create_ticket_body(frontmatter["what"], frontmatter["who"]["current"])

            # 格式化完整內容
            content = _format_ticket_content(frontmatter, body)

            # 建立 GeneratedTicket
            gen_ticket = GeneratedTicket(
                id=ticket_id,
                title=task.title,
                content=content,
                tdd_phases=tdd_phases,
                wave=wave,
            )

            generated_tickets.append(gen_ticket)

        return GenerationResult(
            tickets=generated_tickets,
            total=len(generated_tickets),
            success=True,
            error_message="",
            dry_run=dry_run,
        )

    except Exception as e:
        return GenerationResult(
            success=False,
            error_message=f"生成失敗: {str(e)}",
            dry_run=dry_run,
        )
