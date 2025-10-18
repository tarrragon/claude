#!/usr/bin/env python3
"""
代理人分派智慧分析工具測試套件

測試範圍：
1. 數據讀取和模型建立
2. 模式識別分析
3. 根因分析
4. 改進建議生成
5. 趨勢追蹤
6. 報告生成

版本：v0.12.N.11
作者：basil-hook-architect
日期：2025-10-18
"""

import pytest
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any

# 假設分析工具模組可直接導入
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent_dispatch_analytics import (
    CorrectionRecord,
    WarningRecord,
    PatternAnalyzer,
    RootCauseAnalyzer,
    ImprovementSuggester,
    TrendTracker,
    generate_report,
)


# ===== 測試數據準備 =====

@pytest.fixture
def sample_corrections():
    """準備測試用的糾正記錄"""
    base_date = datetime.now()
    corrections = [
        {
            "timestamp": (base_date - timedelta(days=5)).isoformat(),
            "task_type": "Hook 開發",
            "wrong_agent": "parsley-flutter-developer",
            "correct_agent": "basil-hook-architect",
            "prompt_preview": "開發 Hook 腳本",
            "metadata": {
                "actual_task_type": "Hook 開發",
                "detected_task_type": "Hook 開發",
            }
        },
        {
            "timestamp": (base_date - timedelta(days=4)).isoformat(),
            "task_type": "Phase 4 重構評估（誤判為 Hook 開發）",
            "wrong_agent": "cinnamon-refactor-owl",
            "correct_agent": "basil-hook-architect",
            "prompt_preview": "v0.12.N Phase 4: 代理人分派檢查 Hook 重構評估",
            "metadata": {
                "actual_task_type": "Phase 4 重構",
                "detected_task_type": "Hook 開發",
                "reason": "關鍵字「Hook」導致誤判",
            }
        },
        {
            "timestamp": (base_date - timedelta(days=3)).isoformat(),
            "task_type": "文件整合",
            "wrong_agent": "parsley-flutter-developer",
            "correct_agent": "thyme-documentation-integrator",
            "prompt_preview": "整合工作日誌到方法論",
            "metadata": {}
        },
        {
            "timestamp": (base_date - timedelta(days=2)).isoformat(),
            "task_type": "Phase 4 重構評估（誤判為 Hook 開發）",
            "wrong_agent": "cinnamon-refactor-owl",
            "correct_agent": "basil-hook-architect",
            "prompt_preview": "Phase 4 重構評估: 檢查 Hook 系統",
            "metadata": {
                "actual_task_type": "Phase 4 重構",
                "detected_task_type": "Hook 開發",
                "reason": "關鍵字「Hook」導致誤判",
            }
        },
        {
            "timestamp": (base_date - timedelta(days=1)).isoformat(),
            "task_type": "程式碼格式化",
            "wrong_agent": "parsley-flutter-developer",
            "correct_agent": "mint-format-specialist",
            "prompt_preview": "格式化程式碼",
            "metadata": {}
        },
    ]
    return [CorrectionRecord(c) for c in corrections]


@pytest.fixture
def sample_warnings():
    """準備測試用的警告記錄"""
    base_date = datetime.now()
    warnings = [
        {
            "timestamp": (base_date - timedelta(days=3)).isoformat(),
            "warning_type": "關鍵字衝突",
            "severity": "high",
            "prompt_preview": "Hook 開發任務",
            "reason": "「Hook」關鍵字可能與其他任務混淆",
            "suggestion": "使用更具體的任務描述",
            "metadata": {}
        },
        {
            "timestamp": (base_date - timedelta(days=1)).isoformat(),
            "warning_type": "分派準確率低",
            "severity": "medium",
            "prompt_preview": "多階段任務",
            "reason": "複合任務容易誤判",
            "suggestion": "拆分為單一職責任務",
            "metadata": {}
        },
    ]
    return [WarningRecord(w) for w in warnings]


# ===== 測試案例 =====

class TestDataModels:
    """測試數據模型"""

    def test_correction_record_creation(self):
        """測試糾正記錄建立"""
        data = {
            "timestamp": "2025-10-18T10:00:00",
            "task_type": "Hook 開發",
            "wrong_agent": "parsley-flutter-developer",
            "correct_agent": "basil-hook-architect",
            "prompt_preview": "開發 Hook",
            "metadata": {}
        }
        record = CorrectionRecord(data)

        assert record.timestamp == "2025-10-18T10:00:00"
        assert record.task_type == "Hook 開發"
        assert record.wrong_agent == "parsley-flutter-developer"
        assert record.correct_agent == "basil-hook-architect"

    def test_correction_record_misdetection_detection(self):
        """測試誤判檢測"""
        # 正常的糾正記錄
        normal_data = {
            "timestamp": "2025-10-18T10:00:00",
            "task_type": "Hook 開發",
            "wrong_agent": "parsley-flutter-developer",
            "correct_agent": "basil-hook-architect",
            "metadata": {}
        }
        record = CorrectionRecord(normal_data)
        assert record.is_misdetection is False

        # 誤判的糾正記錄
        misdetection_data = {
            "timestamp": "2025-10-18T10:00:00",
            "task_type": "Phase 4 重構評估（誤判為 Hook 開發）",
            "wrong_agent": "cinnamon-refactor-owl",
            "correct_agent": "basil-hook-architect",
            "metadata": {
                "actual_task_type": "Phase 4 重構",
                "detected_task_type": "Hook 開發",
            }
        }
        record = CorrectionRecord(misdetection_data)
        assert record.is_misdetection is True

    def test_warning_record_creation(self):
        """測試警告記錄建立"""
        data = {
            "timestamp": "2025-10-18T10:00:00",
            "warning_type": "關鍵字衝突",
            "severity": "high",
            "reason": "衝突原因",
            "suggestion": "改進建議",
            "metadata": {}
        }
        record = WarningRecord(data)

        assert record.warning_type == "關鍵字衝突"
        assert record.severity == "high"


class TestPatternAnalyzer:
    """測試模式識別"""

    def test_analyze_correction_patterns(self, sample_corrections, sample_warnings):
        """測試糾正模式分析"""
        analyzer = PatternAnalyzer(sample_corrections, sample_warnings)
        patterns = analyzer.analyze_correction_patterns()

        assert patterns["total_corrections"] == 5
        assert patterns["misdetection_rate"] == 40.0  # 2 個誤判 / 5 總數
        assert "Hook 開發" in patterns["task_type_distribution"]

    def test_agent_confusion_matrix(self, sample_corrections, sample_warnings):
        """測試代理人混淆矩陣"""
        analyzer = PatternAnalyzer(sample_corrections, sample_warnings)
        patterns = analyzer.analyze_correction_patterns()

        matrix = patterns["agent_confusion_matrix"]
        assert "parsley-flutter-developer" in matrix
        assert "cinnamon-refactor-owl" in matrix
        assert matrix["parsley-flutter-developer"]["basil-hook-architect"] >= 1

    def test_analyze_warning_patterns(self, sample_corrections, sample_warnings):
        """測試警告模式分析"""
        analyzer = PatternAnalyzer(sample_corrections, sample_warnings)
        patterns = analyzer.analyze_warning_patterns()

        assert patterns["total_warnings"] == 2
        assert "high" in patterns["by_severity"]
        assert patterns["by_severity"]["high"] == 1

    def test_most_confused_pairs(self, sample_corrections, sample_warnings):
        """測試最容易混淆的代理人對"""
        analyzer = PatternAnalyzer(sample_corrections, sample_warnings)
        patterns = analyzer.analyze_correction_patterns()

        pairs = patterns["most_confused_agent_pairs"]
        assert len(pairs) > 0
        # 驗證格式：(wrong_agent, correct_agent, count)
        assert len(pairs[0]) == 3
        assert isinstance(pairs[0][2], int)


class TestRootCauseAnalyzer:
    """測試根因分析"""

    def test_analyze_root_causes(self, sample_corrections, sample_warnings):
        """測試根因分析"""
        analyzer = RootCauseAnalyzer(sample_corrections, sample_warnings)
        analysis = analyzer.analyze_root_causes()

        assert analysis["misdetection_count"] == 2  # 2 個誤判
        assert len(analysis["root_causes"]) > 0
        assert "affected_agents" in analysis

    def test_root_cause_structure(self, sample_corrections, sample_warnings):
        """測試根因結構"""
        analyzer = RootCauseAnalyzer(sample_corrections, sample_warnings)
        analysis = analyzer.analyze_root_causes()

        if analysis["root_causes"]:
            cause = analysis["root_causes"][0]
            assert "cause" in cause
            assert "frequency" in cause
            assert "examples" in cause

    def test_keyword_conflict_analysis(self, sample_corrections, sample_warnings):
        """測試關鍵字衝突分析"""
        analyzer = RootCauseAnalyzer(sample_corrections, sample_warnings)
        analysis = analyzer.analyze_keyword_conflicts()

        assert "keyword_conflict_summary" in analysis


class TestImprovementSuggester:
    """測試改進建議"""

    def test_generate_suggestions(self, sample_corrections, sample_warnings):
        """測試改進建議生成"""
        analyzer = PatternAnalyzer(sample_corrections, sample_warnings)
        patterns = analyzer.analyze_correction_patterns()

        root_cause_analyzer = RootCauseAnalyzer(sample_corrections, sample_warnings)
        root_causes = root_cause_analyzer.analyze_root_causes()

        suggester = ImprovementSuggester(patterns, root_causes)
        suggestions = suggester.generate_suggestions()

        assert suggestions["total_suggestions"] > 0
        assert len(suggestions["suggestions"]) > 0

    def test_suggestion_structure(self, sample_corrections, sample_warnings):
        """測試建議結構"""
        analyzer = PatternAnalyzer(sample_corrections, sample_warnings)
        patterns = analyzer.analyze_correction_patterns()

        root_cause_analyzer = RootCauseAnalyzer(sample_corrections, sample_warnings)
        root_causes = root_cause_analyzer.analyze_root_causes()

        suggester = ImprovementSuggester(patterns, root_causes)
        suggestions = suggester.generate_suggestions()

        if suggestions["suggestions"]:
            suggestion = suggestions["suggestions"][0]
            assert "category" in suggestion
            assert "priority" in suggestion
            assert "issue" in suggestion
            assert "suggestion" in suggestion
            assert "impact" in suggestion

    def test_suggestion_prioritization(self, sample_corrections, sample_warnings):
        """測試建議優先級排序"""
        analyzer = PatternAnalyzer(sample_corrections, sample_warnings)
        patterns = analyzer.analyze_correction_patterns()

        root_cause_analyzer = RootCauseAnalyzer(sample_corrections, sample_warnings)
        root_causes = root_cause_analyzer.analyze_root_causes()

        suggester = ImprovementSuggester(patterns, root_causes)
        suggestions = suggester.generate_suggestions()

        if len(suggestions["suggestions"]) > 1:
            # 驗證優先級排序
            priorities = [s["priority"] for s in suggestions["suggestions"]]
            # high 應該在 medium 之前
            if "high" in priorities and "medium" in priorities:
                assert priorities.index("high") < priorities.index("medium")


class TestTrendTracker:
    """測試趨勢追蹤"""

    def test_track_error_trends(self, sample_corrections):
        """測試趨勢追蹤"""
        tracker = TrendTracker(sample_corrections)
        trends = tracker.track_error_trends()

        assert "trend_data" in trends
        assert "average_error_rate" in trends
        assert "trend_direction" in trends
        assert "prediction" in trends

    def test_trend_data_structure(self, sample_corrections):
        """測試趨勢數據結構"""
        tracker = TrendTracker(sample_corrections)
        trends = tracker.track_error_trends()

        if trends["trend_data"]:
            data = trends["trend_data"][0]
            assert "date" in data
            assert "total" in data
            assert "misdetections" in data
            assert "error_rate" in data

    def test_trend_calculation(self, sample_corrections):
        """測試誤判率計算"""
        tracker = TrendTracker(sample_corrections)
        trends = tracker.track_error_trends()

        # 平均誤判率應該是 40%（2 個誤判 / 5 總數）
        assert trends["average_error_rate"] > 0

    def test_empty_corrections_handling(self):
        """測試空糾正記錄處理"""
        tracker = TrendTracker([])
        trends = tracker.track_error_trends()

        assert trends["trend_data"] == []
        assert trends["average_error_rate"] == 0
        assert trends["trend_direction"] == "穩定"


class TestReportGeneration:
    """測試報告生成"""

    def test_generate_report(self, sample_corrections, sample_warnings):
        """測試報告生成"""
        analyzer = PatternAnalyzer(sample_corrections, sample_warnings)
        patterns = analyzer.analyze_correction_patterns()
        keyword_analysis = analyzer.analyze_warning_patterns()

        root_cause_analyzer = RootCauseAnalyzer(sample_corrections, sample_warnings)
        root_causes = root_cause_analyzer.analyze_root_causes()
        keyword_conflicts = root_cause_analyzer.analyze_keyword_conflicts()

        suggester = ImprovementSuggester(patterns, root_causes)
        suggestions = suggester.generate_suggestions()

        tracker = TrendTracker(sample_corrections)
        trends = tracker.track_error_trends()

        report = generate_report(
            patterns,
            root_causes,
            keyword_conflicts,
            suggestions,
            trends,
        )

        assert isinstance(report, str)
        assert "代理人分派智慧分析報告" in report
        assert "📊 總體統計" in report
        assert "💡 改進建議" in report

    def test_report_contains_key_sections(self, sample_corrections, sample_warnings):
        """測試報告包含所有關鍵區塊"""
        analyzer = PatternAnalyzer(sample_corrections, sample_warnings)
        patterns = analyzer.analyze_correction_patterns()
        keyword_analysis = analyzer.analyze_warning_patterns()

        root_cause_analyzer = RootCauseAnalyzer(sample_corrections, sample_warnings)
        root_causes = root_cause_analyzer.analyze_root_causes()
        keyword_conflicts = root_cause_analyzer.analyze_keyword_conflicts()

        suggester = ImprovementSuggester(patterns, root_causes)
        suggestions = suggester.generate_suggestions()

        tracker = TrendTracker(sample_corrections)
        trends = tracker.track_error_trends()

        report = generate_report(
            patterns,
            root_causes,
            keyword_conflicts,
            suggestions,
            trends,
        )

        required_sections = [
            "📊 總體統計",
            "🔍 常見誤判模式",
            "💡 改進建議",
            "📈 趨勢追蹤",
            "🎯 後續行動計畫",
        ]

        for section in required_sections:
            assert section in report, f"報告缺少必要區塊: {section}"


class TestEdgeCases:
    """測試邊界情況"""

    def test_empty_data_handling(self):
        """測試空數據處理"""
        analyzer = PatternAnalyzer([], [])
        patterns = analyzer.analyze_correction_patterns()

        assert patterns["total_corrections"] == 0
        assert patterns["task_type_distribution"] == {}
        assert patterns["misdetection_rate"] == 0

    def test_single_record(self):
        """測試單筆記錄"""
        record = CorrectionRecord({
            "timestamp": "2025-10-18T10:00:00",
            "task_type": "Hook 開發",
            "wrong_agent": "parsley-flutter-developer",
            "correct_agent": "basil-hook-architect",
        })

        analyzer = PatternAnalyzer([record], [])
        patterns = analyzer.analyze_correction_patterns()

        assert patterns["total_corrections"] == 1

    def test_duplicate_records(self):
        """測試重複記錄"""
        record = CorrectionRecord({
            "timestamp": "2025-10-18T10:00:00",
            "task_type": "Hook 開發",
            "wrong_agent": "parsley-flutter-developer",
            "correct_agent": "basil-hook-architect",
        })

        analyzer = PatternAnalyzer([record, record, record], [])
        patterns = analyzer.analyze_correction_patterns()

        assert patterns["total_corrections"] == 3


# ===== 執行測試 =====

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
