# 智慧分析工具快速參考

**工具**: `agent_dispatch_analytics.py` v0.12.N.11
**位置**: `.claude/hooks/`
**狀態**: ✅ 就緒

---

## 🚀 四大命令

### 1. analyze - 分析模式

```bash
python .claude/hooks/agent_dispatch_analytics.py analyze
```

**輸出**: 糾正次數、任務類型分佈、代理人混淆對、誤判率

**使用場景**: 快速了解系統狀況

---

### 2. suggest - 改進建議

```bash
python .claude/hooks/agent_dispatch_analytics.py suggest
```

**輸出**: 按優先級排序的改進建議（高/中/低）

**使用場景**: 決定下一步改進方向

---

### 3. trends - 趨勢追蹤

```bash
python .claude/hooks/agent_dispatch_analytics.py trends
```

**輸出**: 平均誤判率、趨勢方向、預測、最近 10 天圖表

**使用場景**: 監控改進效果

---

### 4. report - 完整報告

```bash
python .claude/hooks/agent_dispatch_analytics.py report
```

**輸出**: 存檔到 `.claude/hook-logs/agent-dispatch-analysis-report.md`

**使用場景**: 定期評審、存檔對比、團隊分享

---

## 📊 關鍵指標

| 指標 | 含義 |
|------|------|
| **總糾正次數** | 分派系統發生的錯誤次數 |
| **誤判率** | 任務類型誤判導致的糾正比例 |
| **混淆對** | 最常被混淆的代理人組合 |
| **趨勢** | ↓改善中 / ↑惡化中 / →穩定 |

---

## 🔍 常見場景

### 場景 1: 誤判率突然上升

```bash
# 1. 查看趨勢
python .claude/hooks/agent_dispatch_analytics.py trends

# 2. 如果 ↑ 惡化中，分析模式
python .claude/hooks/agent_dispatch_analytics.py analyze

# 3. 查看改進建議
python .claude/hooks/agent_dispatch_analytics.py suggest
```

### 場景 2: 想了解最常見問題

```bash
# 查看完整報告
python .claude/hooks/agent_dispatch_analytics.py report
cat .claude/hook-logs/agent-dispatch-analysis-report.md
```

### 場景 3: 評估優化效果

```bash
# 對比前後趨勢
python .claude/hooks/agent_dispatch_analytics.py trends

# 查看建議實施前後的變化
# (對比不同日期的報告)
```

---

## 💡 優先級解讀

- 🔴 **高** - 直接影響準確率，需立即處理
- 🟡 **中** - 重要改進，本週完成
- 🟢 **低** - 長期優化

---

## 📈 趨勢解讀

```text
↓ 改善中 - 最近誤判率 < 過去平均 80%
↑ 惡化中 - 最近誤判率 > 過去平均 120%
→ 穩定   - 誤判率波動 ±20%
```

---

## 🔧 Python API

```python
from agent_dispatch_analytics import (
    read_corrections,
    read_warnings,
    PatternAnalyzer,
    RootCauseAnalyzer,
    ImprovementSuggester,
    TrendTracker,
)

# 讀取數據
corrections = read_corrections(limit=100)
warnings = read_warnings()

# 進行分析
analyzer = PatternAnalyzer(corrections, warnings)
patterns = analyzer.analyze_correction_patterns()

# 訪問結果
print(f"誤判率: {patterns['misdetection_rate']}%")
print(f"總糾正: {patterns['total_corrections']} 次")
```

---

## 📚 完整文檔

- **使用指南**: `docs/agent-dispatch-analytics-guide.md`
- **實作報告**: `docs/work-logs/v0.12.N.11-analytics-tool.md`
- **執行摘要**: `ANALYTICS_TOOL_SUMMARY.md`

---

## ⚠️ 故障排除

### 無法導入模組

```bash
# 確保在專案根目錄
cd /path/to/book_overview_app

# 使用完整路徑
python3 ./.claude/hooks/agent_dispatch_analytics.py analyze
```

### 數據為空

```bash
# 檢查糾正歷史
head -5 .claude/hook-logs/agent-dispatch-corrections.jsonl

# Hook 系統應該在運作中記錄糾正
# 查看 task-dispatch-readiness-check.py
```

### 報告不生成

```bash
# 檢查目錄權限
ls -la .claude/hook-logs/

# 確保可寫
mkdir -p .claude/hook-logs/
```

---

**最後更新**: 2025-10-18
**版本**: v0.12.N.11
