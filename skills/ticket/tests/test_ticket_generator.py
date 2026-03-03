"""
Ticket 生成模組單元測試
"""

import pytest
from ticket_system.lib.plan_parser import PlanParseResult, PlanTask
from ticket_system.lib.ticket_generator import (
    generate,
    GeneratedTicket,
    GenerationResult,
    _get_tdd_stages,
    _map_tdd_stages,
    _assign_wave,
)


class TestGetTddStages:
    """測試 _get_tdd_stages 函式"""

    def test_imp_low_complexity(self):
        """測試 IMP 類型低複雜度"""
        stages = _get_tdd_stages("IMP", 5)
        assert "phase1" in stages
        assert "phase3b" in stages
        assert "phase4" in stages
        assert "phase0" not in stages

    def test_imp_high_complexity(self):
        """測試 IMP 類型高複雜度"""
        stages = _get_tdd_stages("IMP", 12)
        assert "phase0" in stages
        assert "phase1" in stages
        assert stages[0] == "phase0"

    def test_adj_type(self):
        """測試 ADJ 類型"""
        stages = _get_tdd_stages("ADJ", 5)
        assert stages == ["phase3b", "phase4"]

    def test_doc_type(self):
        """測試 DOC 類型"""
        stages = _get_tdd_stages("DOC", 5)
        assert stages == []

    def test_unknown_type(self):
        """測試未知類型"""
        stages = _get_tdd_stages("UNKNOWN", 5)
        assert "phase3b" in stages


class TestMapTddStages:
    """測試 _map_tdd_stages 函式"""

    def test_single_task(self):
        """測試單一任務"""
        task = PlanTask(title="測試任務", task_type="IMP", complexity=5, order=1)
        result = PlanParseResult(
            plan_title="計畫",
            tasks=[task],
            total_tasks=1,
            success=True,
        )

        stages = _map_tdd_stages(result)
        assert "1" in stages
        assert "phase1" in stages["1"]

    def test_multiple_tasks(self):
        """測試多個任務"""
        tasks = [
            PlanTask(title="任務1", task_type="IMP", complexity=5, order=1),
            PlanTask(title="任務2", task_type="ADJ", complexity=8, order=2),
            PlanTask(title="任務3", task_type="DOC", complexity=3, order=3),
        ]
        result = PlanParseResult(
            plan_title="計畫",
            tasks=tasks,
            total_tasks=3,
            success=True,
        )

        stages = _map_tdd_stages(result)
        assert len(stages) == 3
        assert "phase1" in stages["1"]
        assert stages["2"] == ["phase3b", "phase4"]
        assert stages["3"] == []


class TestAssignWave:
    """測試 _assign_wave 函式"""

    def test_single_task_same_wave(self):
        """測試單一任務"""
        task = PlanTask(title="測試", complexity=5, order=1)
        result = PlanParseResult(
            plan_title="計畫",
            tasks=[task],
            total_tasks=1,
            success=True,
        )

        waves = _assign_wave(result, base_wave=5)
        assert waves["1"] == 5

    def test_low_complexity_same_wave(self):
        """測試低複雜度任務同 Wave"""
        tasks = [
            PlanTask(title="任務1", complexity=3, order=1),
            PlanTask(title="任務2", complexity=4, order=2),
            PlanTask(title="任務3", complexity=5, order=3),
        ]
        result = PlanParseResult(
            plan_title="計畫",
            tasks=tasks,
            total_tasks=3,
            success=True,
        )

        waves = _assign_wave(result, base_wave=5)
        assert waves["1"] == 5
        assert waves["2"] == 5
        assert waves["3"] == 5

    def test_high_complexity_separate_waves(self):
        """測試高複雜度任務分離 Wave"""
        tasks = [
            PlanTask(title="任務1", complexity=12, order=1),
            PlanTask(title="任務2", complexity=11, order=2),
        ]
        result = PlanParseResult(
            plan_title="計畫",
            tasks=tasks,
            total_tasks=2,
            success=True,
        )

        waves = _assign_wave(result, base_wave=5)
        assert waves["1"] == 5
        assert waves["2"] == 6  # 高複雜度任務後增加 Wave


class TestGenerate:
    """測試 generate 函式"""

    def test_generate_success(self):
        """測試成功生成"""
        task = PlanTask(
            title="實作功能 X",
            description="詳細說明",
            action="實作",
            target="功能 X",
            files=["lib/app.dart"],
            layer="Application",
            task_type="IMP",
            complexity=5,
            order=1,
        )
        result = PlanParseResult(
            plan_title="計畫",
            plan_description="計畫說明",
            tasks=[task],
            total_tasks=1,
            success=True,
        )

        gen_result = generate(result, version="0.31.0", base_wave=5)

        assert gen_result.success
        assert gen_result.total == 1
        assert len(gen_result.tickets) == 1

        ticket = gen_result.tickets[0]
        assert ticket.id.startswith("0.31.0-W")
        assert "實作功能 X" in ticket.title
        assert "phase1" in ticket.tdd_phases

    def test_generate_multiple_tickets(self):
        """測試生成多個 Tickets"""
        tasks = [
            PlanTask(
                title="建立模組 A",
                description="說明 A",
                files=["lib/a.dart"],
                task_type="IMP",
                complexity=5,
                order=1,
            ),
            PlanTask(
                title="修改模組 B",
                description="說明 B",
                files=["lib/b.dart"],
                task_type="ADJ",
                complexity=8,
                order=2,
            ),
        ]
        result = PlanParseResult(
            plan_title="計畫",
            tasks=tasks,
            total_tasks=2,
            success=True,
        )

        gen_result = generate(result, version="0.31.0", base_wave=5)

        assert gen_result.success
        assert gen_result.total == 2
        assert len(gen_result.tickets) == 2

        # 檢查第一個 Ticket
        assert "phase1" in gen_result.tickets[0].tdd_phases
        # 檢查第二個 Ticket
        assert gen_result.tickets[1].tdd_phases == ["phase3b", "phase4"]

        # 新增：驗證序號遞增且不重複
        id_0 = gen_result.tickets[0].id
        id_1 = gen_result.tickets[1].id
        assert id_0 != id_1, "同一迴圈中生成的 Ticket ID 不應重複"

        # 驗證序號遞增
        # 解析 Ticket ID 提取序號（格式: 版本-W波次-序號）
        seq_0 = int(id_0.split('-')[-1])
        seq_1 = int(id_1.split('-')[-1])
        assert seq_1 == seq_0 + 1, f"序號應遞增: {seq_0} → {seq_1}"

    def test_generate_parse_failure(self):
        """測試 Plan 解析失敗"""
        result = PlanParseResult(
            success=False,
            error_message="解析失敗",
        )

        gen_result = generate(result, version="0.31.0", base_wave=5)

        assert not gen_result.success
        assert gen_result.total == 0

    def test_generate_no_tasks(self):
        """測試無任務"""
        result = PlanParseResult(
            plan_title="計畫",
            tasks=[],
            total_tasks=0,
            success=True,
        )

        gen_result = generate(result, version="0.31.0", base_wave=5)

        assert not gen_result.success

    def test_generate_dry_run(self):
        """測試預演模式"""
        task = PlanTask(
            title="測試",
            task_type="IMP",
            complexity=5,
            order=1,
        )
        result = PlanParseResult(
            plan_title="計畫",
            tasks=[task],
            total_tasks=1,
            success=True,
        )

        gen_result = generate(result, version="0.31.0", base_wave=5, dry_run=True)

        assert gen_result.success
        assert gen_result.dry_run
        assert gen_result.total == 1

    def test_generated_ticket_content_format(self):
        """測試生成的 Ticket 內容格式"""
        task = PlanTask(
            title="實作功能",
            description="說明",
            task_type="IMP",
            complexity=5,
            order=1,
        )
        result = PlanParseResult(
            plan_title="計畫",
            tasks=[task],
            total_tasks=1,
            success=True,
        )

        gen_result = generate(result, version="0.31.0", base_wave=5)
        ticket = gen_result.tickets[0]

        # 檢查內容格式
        assert "---" in ticket.content  # YAML frontmatter
        assert "# Execution Log" in ticket.content  # Body 標題
        assert ticket.content.count("---") >= 2  # 至少有開始和結束 YAML 標記

    def test_generated_ticket_structure(self):
        """測試生成的 Ticket 結構"""
        task = PlanTask(
            title="建立應用程式",
            description="建立新應用程式",
            files=["lib/main.dart"],
            layer="Application",
            task_type="IMP",
            complexity=7,
            order=1,
        )
        result = PlanParseResult(
            plan_title="實作計畫",
            plan_description="計畫描述",
            tasks=[task],
            total_tasks=1,
            success=True,
        )

        gen_result = generate(result, version="0.32.0", base_wave=3)
        ticket = gen_result.tickets[0]

        # 檢查 Ticket 結構
        assert isinstance(ticket, GeneratedTicket)
        assert ticket.id.startswith("0.32.0-W3-")
        assert ticket.wave == 3
        assert len(ticket.tdd_phases) > 0
        assert isinstance(ticket.content, str)

    def test_generate_multiple_tickets_seq_increment(self):
        """測試同一 Wave 多個 Tickets 的序號遞增"""
        # 同一 Wave（低複雜度，都在 Wave 5）
        tasks = [
            PlanTask(
                title="任務 1",
                files=["lib/a.dart"],
                task_type="IMP",
                complexity=3,
                order=1,
            ),
            PlanTask(
                title="任務 2",
                files=["lib/b.dart"],
                task_type="IMP",
                complexity=4,
                order=2,
            ),
            PlanTask(
                title="任務 3",
                files=["lib/c.dart"],
                task_type="IMP",
                complexity=5,
                order=3,
            ),
        ]
        result = PlanParseResult(
            plan_title="計畫",
            tasks=tasks,
            total_tasks=3,
            success=True,
        )

        gen_result = generate(result, version="0.31.0", base_wave=5)

        assert gen_result.success
        assert gen_result.total == 3

        # 驗證所有 ID 不重複
        ids = [t.id for t in gen_result.tickets]
        assert len(ids) == len(set(ids)), "所有 Ticket ID 應唯一"

        # 驗證序號遞增
        seqs = [int(t.id.split('-')[-1]) for t in gen_result.tickets]
        assert seqs == sorted(seqs), f"序號應遞增: {seqs}"
        assert seqs[1] == seqs[0] + 1
        assert seqs[2] == seqs[1] + 1

    def test_generate_cross_wave_independent_seq(self):
        """測試跨 Wave 序號獨立計數"""
        # 高複雜度任務會分配到不同 Wave
        tasks = [
            PlanTask(
                title="任務 1",
                files=["lib/a.dart"],
                task_type="IMP",
                complexity=12,  # 高複雜度 → Wave 5
                order=1,
            ),
            PlanTask(
                title="任務 2",
                files=["lib/b.dart"],
                task_type="IMP",
                complexity=11,  # 高複雜度 → Wave 6（分離）
                order=2,
            ),
            PlanTask(
                title="任務 3",
                files=["lib/c.dart"],
                task_type="IMP",
                complexity=5,   # 低複雜度 → Wave 6
                order=3,
            ),
        ]
        result = PlanParseResult(
            plan_title="計畫",
            tasks=tasks,
            total_tasks=3,
            success=True,
        )

        gen_result = generate(result, version="0.31.0", base_wave=5)

        assert gen_result.success
        assert gen_result.total == 3

        # 驗證 Wave 分配
        ticket_0 = gen_result.tickets[0]
        ticket_1 = gen_result.tickets[1]
        ticket_2 = gen_result.tickets[2]

        assert ticket_0.wave == 5
        assert ticket_1.wave == 6
        assert ticket_2.wave == 6

        # 驗證序號：不同 Wave 可獨立計數
        # W5 應有一個序號，W6 應有兩個遞增序號
        seq_0 = int(ticket_0.id.split('-')[-1])
        seq_1 = int(ticket_1.id.split('-')[-1])
        seq_2 = int(ticket_2.id.split('-')[-1])

        # W6 中的序號應遞增
        assert seq_2 == seq_1 + 1, f"同一 Wave 內序號應遞增: W6-{seq_1} → W6-{seq_2}"
