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


class TestGenerateSparseCollisionGuard:
    """測試 generate 路徑稀疏佔用不覆寫既有票（1.0.0-W1-052）。

    根因：lib/ticket_generator.py 配號採 `wave_seq_map[wave] += 1` 純遞增無探測，
    稀疏佔用（起始可用但後續 seq 已被既有票佔用）時會配出撞號 ID，經
    get_ticket_path + save_ticket 靜默連鎖覆寫。修復後配號應經
    resolve_available_seq 探測檔案系統，跳過已佔用序號。
    """

    @staticmethod
    def _occupy(version, wave, seqs):
        """在 tmp tickets dir 預建指定 seq 的既有票檔案。"""
        from ticket_system.lib.paths import get_tickets_dir
        from ticket_system.lib.ticket_builder import format_ticket_id

        tickets_dir = get_tickets_dir(version)
        tickets_dir.mkdir(parents=True, exist_ok=True)
        for seq in seqs:
            ticket_id = format_ticket_id(version, wave, seq)
            (tickets_dir / f"{ticket_id}.md").write_text(
                f"---\nid: {ticket_id}\n---\n既有票\n", encoding="utf-8"
            )

    def test_sparse_occupancy_single_wave_skips_occupied_seq(self, mocker):
        """起始可用但後續 seq 已佔用時，配號跳過既有票不覆寫。

        場景：get_next_seq 回傳起始 1（例如 stale base worktree / 降級路徑掃不到
        較高的既有票），但檔案系統實際存在 002（稀疏佔用）。生成 3 票期望配
        001, 003, 004——跳過已佔用的 002。
        舊行為 `wave_seq_map += 1` 純遞增無探測會配 001, 002, 003，導致 002
        撞號經 save_ticket 靜默覆寫既有票（R1 殘留）。

        以 mock get_next_seq 固定起始值精確隔離 `+= 1` 遞增邏輯的撞號面，
        不依賴 get_next_seq 內部 max+1 行為（該行為對同集合天然不撞）。
        """
        version = "0.31.0"
        wave = 5
        self._occupy(version, wave, [2])
        mocker.patch(
            "ticket_system.lib.ticket_generator.get_next_seq",
            return_value=1,
        )

        tasks = [
            PlanTask(title=f"任務 {i}", files=[f"lib/{i}.dart"],
                     task_type="IMP", complexity=3, order=i)
            for i in range(1, 4)
        ]
        result = PlanParseResult(
            plan_title="計畫", tasks=tasks, total_tasks=3, success=True,
        )

        gen_result = generate(result, version=version, base_wave=wave)

        assert gen_result.success
        seqs = [int(t.id.split("-")[-1]) for t in gen_result.tickets]
        # 既有 002 必須被跳過
        assert 2 not in seqs, f"配號不應撞既有票 002: {seqs}"
        # ID 全唯一且遞增
        assert len(seqs) == len(set(seqs)), f"配號應唯一: {seqs}"
        assert seqs == sorted(seqs), f"配號應遞增: {seqs}"
        assert seqs == [1, 3, 4], f"應跳過 002 配 001,003,004: {seqs}"

    def test_sparse_occupancy_multi_wave_each_wave_guarded(self, mocker):
        """多 wave 並存時，每個 wave 各自跳過其佔用序號。

        ticket_generator 是真正 per-task 多 wave 的呼叫端（wave_seq_map 多 key
        並存）。W5 佔用 001（起始即撞），W6 佔用 001。每個 wave 的首張票都應
        跳過已佔用的 001——驗證 guard 對每個 wave_seq_map key 獨立生效。
        """
        version = "0.31.0"
        self._occupy(version, 5, [1])
        self._occupy(version, 6, [1])
        # 兩 wave 起始皆 mock 為 1，逼迫首張票即撞既有 001
        mocker.patch(
            "ticket_system.lib.ticket_generator.get_next_seq",
            return_value=1,
        )

        tasks = [
            PlanTask(title="任務 1", files=["lib/a.dart"],
                     task_type="IMP", complexity=12, order=1),  # → W5
            PlanTask(title="任務 2", files=["lib/b.dart"],
                     task_type="IMP", complexity=11, order=2),  # → W6
            PlanTask(title="任務 3", files=["lib/c.dart"],
                     task_type="IMP", complexity=5, order=3),   # → W6
        ]
        result = PlanParseResult(
            plan_title="計畫", tasks=tasks, total_tasks=3, success=True,
        )

        gen_result = generate(result, version=version, base_wave=5)

        assert gen_result.success
        by_wave = {}
        for t in gen_result.tickets:
            seq = int(t.id.split("-")[-1])
            by_wave.setdefault(t.wave, []).append(seq)

        # 每個 wave 都不得撞既有佔用的 001
        for wave, seqs in by_wave.items():
            assert 1 not in seqs, f"W{wave} 配號不應撞既有票 001: {seqs}"
            assert len(seqs) == len(set(seqs)), f"W{wave} 配號應唯一: {seqs}"
            assert seqs == sorted(seqs), f"W{wave} 配號應遞增: {seqs}"

    def test_consecutive_occupancy_resolves_past_block(self, mocker):
        """連續佔用區塊（001-003）時，配號應解析到區塊之後（004 起）。"""
        version = "0.31.0"
        wave = 5
        self._occupy(version, wave, [1, 2, 3])
        mocker.patch(
            "ticket_system.lib.ticket_generator.get_next_seq",
            return_value=1,
        )

        tasks = [
            PlanTask(title=f"任務 {i}", files=[f"lib/{i}.dart"],
                     task_type="IMP", complexity=3, order=i)
            for i in range(1, 3)
        ]
        result = PlanParseResult(
            plan_title="計畫", tasks=tasks, total_tasks=2, success=True,
        )

        gen_result = generate(result, version=version, base_wave=wave)

        assert gen_result.success
        seqs = [int(t.id.split("-")[-1]) for t in gen_result.tickets]
        assert min(seqs) >= 4, f"配號應跳過連續佔用區塊 001-003: {seqs}"
        assert seqs == [4, 5], f"應配 004, 005: {seqs}"
