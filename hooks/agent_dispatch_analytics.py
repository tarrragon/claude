#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "jsonschema>=4.0",
# ]
# ///
"""
代理人分派智慧分析工具

從糾正歷史和警告記錄中識別模式、分析根因、提供改進建議、追蹤趨勢。

使用方法：
  python agent_dispatch_analytics.py analyze    - 分析糾正歷史模式
  python agent_dispatch_analytics.py suggest    - 生成改進建議
  python agent_dispatch_analytics.py trends     - 追蹤誤判率趨勢
  python agent_dispatch_analytics.py report     - 生成完整分析報告

版本：v0.12.N.11
作者：basil-hook-architect
日期：2025-10-18
"""

import json
import sys
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict, Counter
import statistics


# ===== 配置 =====

PROJECT_ROOT = Path(".").resolve()
CORRECTION_LOG_FILE = PROJECT_ROOT / ".claude/hook-logs/agent-dispatch-corrections.jsonl"
WARNINGS_LOG_FILE = PROJECT_ROOT / ".claude/hook-logs/agent-dispatch-warnings.jsonl"
REPORT_FILE = PROJECT_ROOT / ".claude/hook-logs/agent-dispatch-analysis-report.md"


# ===== 數據模型 =====

class CorrectionRecord:
    """糾正記錄"""
    def __init__(self, data: Dict[str, Any]):
        self.timestamp = data.get("timestamp")
        self.task_type = data.get("task_type", "未知")
        self.wrong_agent = data.get("wrong_agent", "未知")
        self.correct_agent = data.get("correct_agent", "未知")
        self.prompt_preview = data.get("prompt_preview", "")
        self.metadata = data.get("metadata", {})
        self.actual_task_type = self.metadata.get("actual_task_type")
        self.detected_task_type = self.metadata.get("detected_task_type")
        self.reason = self.metadata.get("reason")

    @property
    def is_misdetection(self) -> bool:
        """是否是任務類型誤判（actual != detected）"""
        if self.actual_task_type is None or self.detected_task_type is None:
            return False
        return self.actual_task_type != self.detected_task_type


class WarningRecord:
    """警告記錄"""
    def __init__(self, data: Dict[str, Any]):
        self.timestamp = data.get("timestamp")
        self.warning_type = data.get("warning_type", "未知")
        self.severity = data.get("severity", "medium")  # low, medium, high
        self.prompt_preview = data.get("prompt_preview", "")
        self.reason = data.get("reason", "")
        self.suggestion = data.get("suggestion", "")
        self.metadata = data.get("metadata", {})


# ===== 數據讀取 =====

def read_corrections(limit: Optional[int] = None) -> List[CorrectionRecord]:
    """讀取糾正歷史記錄"""
    if not CORRECTION_LOG_FILE.exists():
        return []

    records = []
    with open(CORRECTION_LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                records.append(CorrectionRecord(data))
            except json.JSONDecodeError:
                continue

    if limit:
        return records[-limit:]
    return records


def read_warnings(limit: Optional[int] = None) -> List[WarningRecord]:
    """讀取警告記錄"""
    if not WARNINGS_LOG_FILE.exists():
        return []

    records = []
    with open(WARNINGS_LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                records.append(WarningRecord(data))
            except json.JSONDecodeError:
                continue

    if limit:
        return records[-limit:]
    return records


# ===== 模式識別模組 =====

class PatternAnalyzer:
    """模式識別分析"""

    def __init__(self, corrections: List[CorrectionRecord], warnings: List[WarningRecord]):
        self.corrections = corrections
        self.warnings = warnings

    def analyze_correction_patterns(self, limit: int = 100) -> Dict[str, Any]:
        """分析最近 N 筆糾正記錄的模式"""
        recent = self.corrections[-limit:] if len(self.corrections) > limit else self.corrections

        if not recent:
            return {
                "total_corrections": 0,
                "task_type_distribution": {},
                "agent_confusion_matrix": {},
                "misdetection_rate": 0,
                "most_confused_agents": [],
                "common_keywords_in_errors": [],
            }

        # 1. 任務類型分佈
        task_type_counter = Counter(r.task_type for r in recent)

        # 2. 代理人混淆矩陣
        agent_confusion = defaultdict(lambda: defaultdict(int))
        for r in recent:
            agent_confusion[r.wrong_agent][r.correct_agent] += 1

        # 3. 誤判率
        misdetections = [r for r in recent if r.is_misdetection]
        misdetection_rate = len(misdetections) / len(recent) if recent else 0

        # 4. 最容易混淆的代理人對
        agent_pairs = []
        for wrong, corrects in agent_confusion.items():
            for correct, count in corrects.items():
                agent_pairs.append((wrong, correct, count))
        agent_pairs.sort(key=lambda x: -x[2])

        # 5. 常見的錯誤關鍵字
        keywords = defaultdict(int)
        for r in recent:
            if r.reason:
                # 提取「Hook」「Phase」等關鍵字
                for keyword in re.findall(r"[A-Za-z\u4e00-\u9fff]+", r.reason):
                    if len(keyword) > 1:
                        keywords[keyword] += 1

        top_keywords = sorted(keywords.items(), key=lambda x: -x[1])[:10]

        return {
            "total_corrections": len(recent),
            "task_type_distribution": dict(task_type_counter),
            "agent_confusion_matrix": {
                wrong: dict(corrects)
                for wrong, corrects in agent_confusion.items()
            },
            "misdetection_rate": round(misdetection_rate * 100, 2),
            "most_confused_agent_pairs": agent_pairs[:5],
            "common_error_reasons": [
                {
                    "detected_type": r.detected_task_type,
                    "actual_type": r.actual_task_type,
                    "reason": r.reason,
                    "count": sum(1 for x in misdetections
                               if x.detected_task_type == r.detected_task_type
                               and x.actual_task_type == r.actual_task_type)
                }
                for r in misdetections
            ][:5],
        }

    def analyze_warning_patterns(self) -> Dict[str, Any]:
        """分析警告記錄模式"""
        if not self.warnings:
            return {
                "total_warnings": 0,
                "by_severity": {},
                "by_type": {},
                "high_severity_warnings": [],
            }

        severity_counter = Counter(w.severity for w in self.warnings)
        warning_type_counter = Counter(w.warning_type for w in self.warnings)

        # 高優先級警告
        high_warnings = [w for w in self.warnings if w.severity == "high"]
        high_warnings_summary = [
            {
                "type": w.warning_type,
                "reason": w.reason,
                "suggestion": w.suggestion,
                "timestamp": w.timestamp,
            }
            for w in high_warnings[-5:]
        ]

        return {
            "total_warnings": len(self.warnings),
            "by_severity": dict(severity_counter),
            "by_type": dict(warning_type_counter),
            "high_severity_warnings": high_warnings_summary,
        }


# ===== 根因分析模組 =====

class RootCauseAnalyzer:
    """根因分析"""

    def __init__(self, corrections: List[CorrectionRecord], warnings: List[WarningRecord]):
        self.corrections = corrections
        self.warnings = warnings

    def analyze_root_causes(self) -> Dict[str, Any]:
        """分析誤判的根本原因"""
        misdetections = [r for r in self.corrections if r.is_misdetection]

        if not misdetections:
            return {
                "misdetection_count": 0,
                "root_causes": [],
                "affected_task_types": [],
                "affected_agents": [],
            }

        # 1. 根因分組
        cause_groups = defaultdict(list)
        for record in misdetections:
            cause_groups[record.reason].append(record)

        # 2. 任務類型分析
        actual_task_types = Counter(r.actual_task_type for r in misdetections)
        detected_task_types = Counter(r.detected_task_type for r in misdetections)

        # 3. 相關代理人
        affected_agents_set = set()
        for r in misdetections:
            affected_agents_set.add(r.wrong_agent)
            affected_agents_set.add(r.correct_agent)

        root_causes = [
            {
                "cause": cause,
                "frequency": len(records),
                "examples": [
                    {
                        "actual_type": r.actual_task_type,
                        "detected_type": r.detected_task_type,
                        "wrong_agent": r.wrong_agent,
                        "correct_agent": r.correct_agent,
                        "prompt_preview": r.prompt_preview[:100],
                    }
                    for r in records[:2]
                ],
            }
            for cause, records in sorted(
                cause_groups.items(),
                key=lambda x: -len(x[1])
            )
        ]

        return {
            "misdetection_count": len(misdetections),
            "root_causes": root_causes,
            "affected_actual_task_types": dict(actual_task_types),
            "affected_detected_task_types": dict(detected_task_types),
            "affected_agents": sorted(list(affected_agents_set)),
        }

    def analyze_keyword_conflicts(self) -> Dict[str, Any]:
        """分析關鍵字衝突"""
        conflicts = defaultdict(lambda: {
            "wrong_detections": [],
            "correct_tasks": [],
            "conflict_rate": 0,
        })

        # 收集所有含有相同關鍵字的誤判
        for record in self.corrections:
            if record.is_misdetection:
                # 提取關鍵字
                keywords = set()
                for keyword in re.findall(r"Phase [0-9a-zA-Z]+|Hook|文件|重構|測試", record.prompt_preview):
                    keywords.add(keyword)

                for kw in keywords:
                    conflicts[kw]["wrong_detections"].append({
                        "detected_as": record.detected_task_type,
                        "actually": record.actual_task_type,
                    })

        return {
            "keyword_conflict_summary": {
                kw: {
                    "conflict_count": len(data["wrong_detections"]),
                    "example_conflicts": data["wrong_detections"][:2],
                }
                for kw, data in conflicts.items()
                if data["wrong_detections"]
            }
        }


# ===== 改進建議模組 =====

class ImprovementSuggester:
    """改進建議生成"""

    def __init__(self, pattern_analysis: Dict, root_cause_analysis: Dict):
        self.pattern_analysis = pattern_analysis
        self.root_cause_analysis = root_cause_analysis

    def generate_suggestions(self) -> Dict[str, Any]:
        """生成改進建議"""
        suggestions = []

        # 1. 基於最常見的混淆對
        if self.pattern_analysis.get("most_confused_agent_pairs"):
            for wrong, correct, count in self.pattern_analysis["most_confused_agent_pairs"][:3]:
                suggestions.append({
                    "category": "代理人分派優化",
                    "priority": "high",
                    "issue": f"{wrong} 經常被誤判為 {correct}（{count} 次）",
                    "suggestion": f"檢查 {wrong} 的任務類型檢測邏輯，加強與 {correct} 的區分",
                    "impact": "減少重試次數，提升分派效率",
                })

        # 2. 基於關鍵字衝突
        if self.root_cause_analysis.get("affected_detected_task_types"):
            top_misdetected = sorted(
                self.root_cause_analysis["affected_detected_task_types"].items(),
                key=lambda x: -x[1]
            )
            if top_misdetected:
                wrong_type, count = top_misdetected[0]
                suggestions.append({
                    "category": "關鍵字檢測改進",
                    "priority": "high",
                    "issue": f"「{wrong_type}」是最常見的誤判類型（{count} 次誤判）",
                    "suggestion": "檢查該任務類型的關鍵字匹配邏輯，避免與其他類型混淆",
                    "impact": "直接降低誤判率",
                })

        # 3. 基於根因
        if self.root_cause_analysis.get("root_causes"):
            for cause in self.root_cause_analysis["root_causes"][:2]:
                suggestions.append({
                    "category": "檢測規則改進",
                    "priority": "medium",
                    "issue": f"根因：{cause['cause']}（出現 {cause['frequency']} 次）",
                    "suggestion": f"調整相關檢測規則以避免此根因",
                    "impact": f"可減少 {cause['frequency']} 次誤判",
                })

        # 4. 基於誤判率
        misdetection_rate = self.pattern_analysis.get("misdetection_rate", 0)
        if misdetection_rate > 20:
            suggestions.append({
                "category": "整體策略調整",
                "priority": "high",
                "issue": f"誤判率較高（{misdetection_rate}%）",
                "suggestion": "考慮採用分層檢測策略或加強訓練數據",
                "impact": "顯著提升分派準確率",
            })

        return {
            "total_suggestions": len(suggestions),
            "suggestions": sorted(suggestions, key=lambda x: (
                {"high": 0, "medium": 1, "low": 2}.get(x["priority"], 3),
                -len(x["issue"])
            )),
        }


# ===== 趨勢追蹤模組 =====

class TrendTracker:
    """趨勢追蹤"""

    def __init__(self, corrections: List[CorrectionRecord]):
        self.corrections = corrections

    def track_error_trends(self) -> Dict[str, Any]:
        """追蹤誤判率趨勢"""
        if not self.corrections:
            return {
                "trend_data": [],
                "average_error_rate": 0,
                "trend_direction": "穩定",
                "prediction": "無法預測",
            }

        # 按時間分組
        time_groups = defaultdict(lambda: {"total": 0, "misdetections": 0})

        for record in self.corrections:
            try:
                date = record.timestamp[:10]  # YYYY-MM-DD
                time_groups[date]["total"] += 1
                if record.is_misdetection:
                    time_groups[date]["misdetections"] += 1
            except (TypeError, AttributeError):
                continue

        # 排序並計算誤判率
        sorted_dates = sorted(time_groups.keys())
        trend_data = [
            {
                "date": date,
                "total": time_groups[date]["total"],
                "misdetections": time_groups[date]["misdetections"],
                "error_rate": round(
                    (time_groups[date]["misdetections"] / time_groups[date]["total"] * 100)
                    if time_groups[date]["total"] > 0 else 0,
                    2
                ),
            }
            for date in sorted_dates
        ]

        # 計算平均誤判率
        error_rates = [d["error_rate"] for d in trend_data]
        avg_error_rate = statistics.mean(error_rates) if error_rates else 0

        # 趨勢方向
        if len(error_rates) >= 2:
            recent_avg = statistics.mean(error_rates[-3:])
            older_avg = statistics.mean(error_rates[:-3]) if len(error_rates) > 3 else error_rates[0]
            if recent_avg < older_avg * 0.8:
                trend_direction = "改善中 ↓"
            elif recent_avg > older_avg * 1.2:
                trend_direction = "惡化中 ↑"
            else:
                trend_direction = "穩定"
        else:
            trend_direction = "數據不足"

        # 簡單預測
        if len(error_rates) >= 3:
            diffs = [error_rates[i+1] - error_rates[i] for i in range(len(error_rates)-1)]
            avg_diff = statistics.mean(diffs)
            if avg_diff < -1:
                prediction = "預期會持續改善"
            elif avg_diff > 1:
                prediction = "預期會持續惡化，需要採取行動"
            else:
                prediction = "預期保持穩定"
        else:
            prediction = "數據不足，無法預測"

        return {
            "trend_data": trend_data,
            "average_error_rate": round(avg_error_rate, 2),
            "trend_direction": trend_direction,
            "prediction": prediction,
            "data_points": len(trend_data),
        }


# ===== 報告生成 =====

def generate_report(
    pattern_analysis: Dict,
    root_cause_analysis: Dict,
    keyword_analysis: Dict,
    suggestions: Dict,
    trends: Dict,
) -> str:
    """生成完整的分析報告"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report = f"""# 代理人分派智慧分析報告

**生成時間**: {timestamp}

---

## 📊 總體統計

### 基本指標
- **總糾正次數**: {pattern_analysis.get("total_corrections", 0)}
- **任務類型誤判率**: {root_cause_analysis.get("misdetection_count", 0)} 次
- **平均誤判率**: {trends.get("average_error_rate", 0)}%
- **趨勢**: {trends.get("trend_direction", "未知")}

### 任務類型分佈
"""

    if pattern_analysis.get("task_type_distribution"):
        for task_type, count in sorted(
            pattern_analysis["task_type_distribution"].items(),
            key=lambda x: -x[1]
        ):
            report += f"- {task_type}: {count} 次\n"

    report += f"""
---

## 🔍 常見誤判模式

### 代理人混淆矩陣

最容易混淆的代理人對：

"""

    if pattern_analysis.get("most_confused_agent_pairs"):
        for wrong, correct, count in pattern_analysis["most_confused_agent_pairs"]:
            report += f"- {wrong} → {correct}: {count} 次\n"

    report += f"""
### 誤判原因

"""

    if root_cause_analysis.get("root_causes"):
        for cause_info in root_cause_analysis["root_causes"][:3]:
            report += f"""#### {cause_info['cause']}

**出現頻率**: {cause_info['frequency']} 次

**範例**:
"""
            for example in cause_info["examples"]:
                report += f"""- 實際任務: {example['actual_type']}
  - 誤判為: {example['detected_type']}
  - 相關代理人: {example['wrong_agent']} → {example['correct_agent']}
  - 任務描述: {example['prompt_preview']}...

"""

    report += """---

## 💡 關鍵字衝突分析

"""

    if keyword_analysis.get("keyword_conflict_summary"):
        for keyword, data in keyword_analysis["keyword_conflict_summary"].items():
            report += f"""### 關鍵字「{keyword}」

**衝突次數**: {data['conflict_count']}

**範例衝突**:
"""
            for conflict in data["example_conflicts"]:
                report += f"- 誤判為: {conflict['detected_as']}, 實際是: {conflict['actually']}\n"

    report += """
---

## 💡 改進建議

"""

    if suggestions.get("suggestions"):
        for i, suggestion in enumerate(suggestions["suggestions"], 1):
            priority_emoji = {
                "high": "🔴",
                "medium": "🟡",
                "low": "🟢",
            }.get(suggestion["priority"], "⚪")

            report += f"""### {i}. {suggestion['category']} {priority_emoji}

**問題**: {suggestion['issue']}

**建議**: {suggestion['suggestion']}

**預期影響**: {suggestion['impact']}

"""

    report += f"""---

## 📈 趨勢追蹤

### 誤判率變化趨勢

"""

    if trends.get("trend_data"):
        report += "| 日期 | 總數 | 誤判 | 誤判率 |\n"
        report += "|------|------|------|--------|\n"
        for data in trends["trend_data"]:
            report += f"| {data['date']} | {data['total']} | {data['misdetections']} | {data['error_rate']}% |\n"

    report += f"""
### 趨勢分析

- **平均誤判率**: {trends.get("average_error_rate", 0)}%
- **趨勢方向**: {trends.get("trend_direction", "未知")}
- **預測**: {trends.get("prediction", "無法預測")}
- **數據點**: {trends.get("data_points", 0)} 天

---

## 🎯 後續行動計畫

### 第 1 優先級（立即執行）

1. 優先實施高優先級建議
2. 關注「{pattern_analysis.get('most_confused_agent_pairs', [('', '', 0)])[0][0] if pattern_analysis.get('most_confused_agent_pairs') else '代理人'}」的分派邏輯

### 第 2 優先級（本週完成）

1. 改進關鍵字檢測機制
2. 加強測試覆蓋率

### 第 3 優先級（持續改進）

1. 定期追蹤誤判率趨勢
2. 收集用戶反饋改進分派規則

---

## 📝 技術說明

**分析工具**: agent_dispatch_analytics.py (v0.12.N.11)

**數據來源**:
- 糾正歷史: `.claude/hook-logs/agent-dispatch-corrections.jsonl`
- 警告記錄: `.claude/hook-logs/agent-dispatch-warnings.jsonl`

**分析方法**:
- 模式識別: 統計分析誤判模式
- 根因分析: 提取共同的根本原因
- 建議生成: 基於數據的可操作建議
- 趨勢追蹤: 時序數據分析

---

**報告完成**
"""

    return report


# ===== CLI 工具 =====

def cmd_analyze():
    """分析糾正歷史"""
    corrections = read_corrections(limit=100)
    warnings = read_warnings()

    analyzer = PatternAnalyzer(corrections, warnings)
    patterns = analyzer.analyze_correction_patterns()
    warnings_patterns = analyzer.analyze_warning_patterns()

    print("\n📊 代理人分派模式分析\n")
    print(f"總糾正次數: {patterns['total_corrections']}\n")

    print("任務類型分佈:")
    for task_type, count in sorted(patterns['task_type_distribution'].items(), key=lambda x: -x[1]):
        print(f"  {task_type}: {count}")

    print("\n最容易混淆的代理人對:")
    for wrong, correct, count in patterns['most_confused_agent_pairs']:
        print(f"  {wrong} → {correct}: {count} 次")

    print(f"\n誤判率: {patterns['misdetection_rate']}%")

    if warnings_patterns['total_warnings'] > 0:
        print(f"\n警告記錄: {warnings_patterns['total_warnings']}")


def cmd_suggest():
    """生成改進建議"""
    corrections = read_corrections(limit=100)
    warnings = read_warnings()

    analyzer = PatternAnalyzer(corrections, warnings)
    patterns = analyzer.analyze_correction_patterns()
    root_causes = RootCauseAnalyzer(corrections, warnings).analyze_root_causes()

    suggester = ImprovementSuggester(patterns, root_causes)
    suggestions = suggester.generate_suggestions()

    print("\n💡 改進建議\n")
    print(f"總建議數: {suggestions['total_suggestions']}\n")

    for i, suggestion in enumerate(suggestions['suggestions'], 1):
        print(f"{i}. [{suggestion['priority'].upper()}] {suggestion['category']}")
        print(f"   問題: {suggestion['issue']}")
        print(f"   建議: {suggestion['suggestion']}")
        print(f"   影響: {suggestion['impact']}")
        print()


def cmd_trends():
    """追蹤趨勢"""
    corrections = read_corrections()
    tracker = TrendTracker(corrections)
    trends = tracker.track_error_trends()

    print("\n📈 誤判率趨勢\n")
    print(f"平均誤判率: {trends['average_error_rate']}%")
    print(f"趨勢: {trends['trend_direction']}")
    print(f"預測: {trends['prediction']}\n")

    print("最近 10 天誤判率:")
    for data in trends['trend_data'][-10:]:
        bar = "█" * int(data['error_rate'] / 5) + "░" * (20 - int(data['error_rate'] / 5))
        print(f"  {data['date']}: {bar} {data['error_rate']}%")


def cmd_report():
    """生成完整報告"""
    corrections = read_corrections(limit=100)
    warnings = read_warnings()

    # 進行各種分析
    analyzer = PatternAnalyzer(corrections, warnings)
    patterns = analyzer.analyze_correction_patterns()
    keyword_analysis = analyzer.analyze_warning_patterns()

    root_cause_analyzer = RootCauseAnalyzer(corrections, warnings)
    root_causes = root_cause_analyzer.analyze_root_causes()
    keyword_conflicts = root_cause_analyzer.analyze_keyword_conflicts()

    suggester = ImprovementSuggester(patterns, root_causes)
    suggestions = suggester.generate_suggestions()

    tracker = TrendTracker(corrections)
    trends = tracker.track_error_trends()

    # 生成報告
    report = generate_report(
        patterns,
        root_causes,
        keyword_conflicts,
        suggestions,
        trends,
    )

    # 保存報告
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n✅ 報告已生成: {REPORT_FILE}\n")
    print("報告內容摘要:\n")
    print(report[:1000] + "\n...\n")


def main():
    """命令列主程式"""
    if len(sys.argv) < 2:
        print("""
代理人分派智慧分析工具

使用方法：
  python agent_dispatch_analytics.py analyze  - 分析模式
  python agent_dispatch_analytics.py suggest  - 改進建議
  python agent_dispatch_analytics.py trends   - 趨勢追蹤
  python agent_dispatch_analytics.py report   - 完整報告
""")
        return

    command = sys.argv[1]

    if command == "analyze":
        cmd_analyze()
    elif command == "suggest":
        cmd_suggest()
    elif command == "trends":
        cmd_trends()
    elif command == "report":
        cmd_report()
    else:
        print(f"未知命令: {command}")


if __name__ == "__main__":
    main()
