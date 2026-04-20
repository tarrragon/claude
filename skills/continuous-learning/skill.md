---
name: continuous-learning
description: "Extracts reusable patterns from Claude Code sessions and captures knowledge as atomic memory units, then evaluates whether each memory should be upgraded to framework-shared rules, methodologies, or error-patterns. Use when session ends (Stop hook), when recording technical decisions, implementation insights, or lessons learned. Handles automatic pattern detection, structured memory capture with interconnected knowledge links, and post-write upgrade decision flow to prevent cross-project principles being trapped in single-project memory."
---

# Continuous Learning

從 Claude Code 工作過程中自動提取可復用模式，並將洞察、決策和經驗記錄為結構化的原子記憶單位。

---

## 兩大功能

### 1. Session Pattern Extraction（自動）

透過 Stop hook 在 session 結束時自動執行：

1. **Session 評估**：檢查 session 訊息量是否足夠（預設 10+）
2. **模式偵測**：識別可提取的可復用模式
3. **Skill 產出**：將有用模式儲存到 `.claude/skills/learned/`

### 2. Memory Capture（按需）

將重要技術決策、實作方案和經驗教訓記錄為原子化記憶：

1. **提取核心結論**：從工作過程中識別值得記錄的結論
2. **分類和結構化**：判斷記憶類型，設計結論式標題
3. **建立連結**：識別與既有知識的關聯
4. **儲存到 memory/**：按標準結構建立記憶檔案
5. **升級評估**：判斷此原則是否需升級到框架共用層

> **重要**：memory 寫入**不是終點**，而是升級評估的起點。寫入 `feedback_*.md` 後必須執行升級評估，否則跨專案通用原則會被困在單一專案的 memory 中（PC-061）。
>
> - 升級評估規則：`.claude/pm-rules/pm-quality-baseline.md` 規則 7
> - 錯誤模式參考：`.claude/error-patterns/process-compliance/PC-061-memory-upgrade-blindness.md`
> - 完整決策樹：`references/upgrade-decision-tree.md`

**適用時機**：

| 時機 | 說明 |
|------|------|
| 重要技術決策完成 | 方案選擇後建立決策記錄 |
| 實作方案確定 | 新的實作模式或解決方案誕生 |
| 學習機會 | 測試失敗、問題排除、重構完成後的經驗總結 |
| Phase 4 完成 | 重構後進行知識沉澱 |
| 版本發布前 | 總結主要決策和經驗 |

### 根因型 memory 特殊處理（Two-Phase Reflection）

當記錄的 memory 核心是**根因分析**（error-pattern、代理人失敗歸因、用戶質疑「分析太表層」），必須套用兩階段深度反思：

1. **Phase 1 多假設 Reality Test**：列 5+ 候選動機、逐個自我觀察驗證、至少挖 2 層深因
2. **Phase 2 WRAP 檢驗**：結論產出後過 WRAP（Widen/Reality/Attain/Premortem）避免第一直覺陷阱

禁止只列 1-2 個假設就下結論，或跳過 Phase 2 直接落地。

> 完整方法論：`.claude/methodologies/three-phase-reflection-methodology.md`
> 案例：PC-087（表層版）→ PC-088（Phase 1+2 後的抽象層）

---

## Pattern Types

| Pattern | Description |
|---------|-------------|
| `error_resolution` | How specific errors were resolved |
| `user_corrections` | Patterns from user corrections |
| `workarounds` | Solutions to framework/library quirks |
| `debugging_techniques` | Effective debugging approaches |
| `project_specific` | Project-specific conventions |

---

## Configuration

Edit `config.json` to customize:

```json
{
  "min_session_length": 10,
  "extraction_threshold": "medium",
  "auto_approve": false,
  "learned_skills_path": ".claude/skills/learned/",
  "patterns_to_detect": [
    "error_resolution",
    "user_corrections",
    "workarounds",
    "debugging_techniques",
    "project_specific"
  ],
  "ignore_patterns": ["simple_typos", "one_time_fixes", "external_api_issues"]
}
```

---

## Hook Setup

Add to `.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/skills/continuous-learning/evaluate-session.py"
          }
        ]
      }
    ]
  }
}
```

---

## Memory Capture 詳細指引

記憶建立的完整規範（類型定義、結論式標題設計、標準結構、連結策略、原子性原則）：

**參考**: `references/memory-capture-guide.md`

### Step 5：升級評估（強制）

完成 Step 4「儲存到 memory/」後，**禁止直接結束**。必須對寫入的 memory 執行升級評估：

| 步驟 | 動作 | 工具/參考 |
|------|------|----------|
| 5.1 | 對每個新建的 `feedback_*.md` 檔案執行四問檢查 | `.claude/pm-rules/pm-quality-baseline.md` 規則 7 |
| 5.2 | 判斷升級目的地（六類分支） | `references/upgrade-decision-tree.md` |
| 5.3 | 執行升級寫入（rules / pm-rules / error-patterns / methodologies / references / skills） | 對應目錄 |
| 5.4 | 在原 memory 檔案頂部加註「已升級」標註 | 標註格式見決策樹 |

**為什麼必須執行**：

memory 寫入**不是終點**，而是升級評估的起點。若略過此步驟，跨專案通用的原則會被困在單一專案的 auto-memory 中，無法 sync 到其他專案，也不會被其他 session 自動載入（PC-061「Memory upgrade blindness」）。

**參考資源**：

- 強制規則：`.claude/pm-rules/pm-quality-baseline.md` 規則 7「Memory 寫入必須評估跨專案升級」
- 錯誤模式：`.claude/error-patterns/process-compliance/PC-061-memory-upgrade-blindness.md`
- 完整決策樹：`references/upgrade-decision-tree.md`

---

## Related

- [The Longform Guide](https://x.com/affaanmustafa/status/2014040193557471352) - Section on continuous learning
- `/learn` command - Manual pattern extraction mid-session

---

**Last Updated**: 2026-04-13
**Version**: 2.1.0 - 新增 Step 5 升級評估，將 memory 寫入串接到 framework 升級流程（防範 PC-061）
