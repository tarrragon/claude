---
name: continuous-learning
description: "Extracts reusable patterns from Claude Code sessions and captures knowledge as atomic memory units with capture-time triage: mature cross-project error learnings go directly to framework error-patterns, immature ones stay as deferred-tagged memory, project-specific context stays local. Use when session ends (Stop hook), when recording technical decisions, implementation insights, or lessons learned. Handles automatic pattern detection, structured memory capture with interconnected knowledge links, and deferred-upgrade harvesting to prevent cross-project principles being trapped in single-project memory."
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
2. **捕獲時分流**（記錄前必答）：錯誤學習類 + 跨專案適用 + 根因已過 Two-Phase Reflection → **直接 `/error-pattern add`**（canonical 層，隨 sync 跨專案傳播），memory 至多留一行 pointer，流程結束；根因未熟 → 續走 memory 路徑並於 frontmatter 標註 `upgrade: deferred` 與理由；專案特定 → `project_` 前綴
3. **分類和結構化**：判斷記憶類型，設計結論式標題
4. **建立連結**：識別與既有知識的關聯
5. **儲存到 memory/**：按標準結構建立記憶檔案（deferred 項含標註）
6. **分流複核**：非錯誤學習類（通用品質 / PM 行為 / 方法論 / skill 引導）依升級路徑表評估目的地

> **重要**：分流判斷在**寫入前**執行，不是寫入後補救。「寫入後補評估」的事後閉環經量化證明不執行（130 檔 feedback memory 標註率 4%，PC-061 模式的規模化實證）；deferred 積壓由發版稽核收割。
>
> - 分流判準權威來源：`.claude/pm-rules/pm-quality-baseline.md` 規則 7
> - 錯誤模式參考：`.claude/error-patterns/process-compliance/PC-061-memory-upgrade-blindness.md`
> - 完整決策樹（含捕獲時 Q0）：`references/upgrade-decision-tree.md`

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

### 分流落地與 deferred 收割（強制）

捕獲時分流（Memory Capture 步驟 2）是主路徑；本節處理兩個收尾場景：

| 場景 | 動作 | 工具/參考 |
|------|------|----------|
| 直寫 canonical 後 | memory 至多留一行 pointer（不複製全文）；既有同主題 memory 依「升級後處理」三步收尾 | `.claude/pm-rules/pm-quality-baseline.md` 規則 7 |
| deferred 收割（根因後續成熟、或發版稽核點名） | 走 Q1/Q2 決策樹判目的地 → 執行升級寫入 → 原檔頂部加註「已升級」+ 自 MEMORY.md 索引移除 | `references/upgrade-decision-tree.md`；promote 工具落地後一步完成 |

**為什麼分流在寫入前**：

事後升級依賴「額外步驟」的自律，量化證據（130 檔標註率 4%、頂部標註格式合規 0）證明必然被省略；捕獲時分流讓每筆知識寫入時態即確定（canonical / deferred+理由 / 專案特定），不可觀測的「已寫入未評估」中間態不再累積（PC-061「Memory upgrade blindness」的結構性解）。

**參考資源**：

- 強制規則：`.claude/pm-rules/pm-quality-baseline.md` 規則 7「錯誤學習知識捕獲時分流」
- 錯誤模式：`.claude/error-patterns/process-compliance/PC-061-memory-upgrade-blindness.md`
- 完整決策樹（含捕獲時 Q0）：`references/upgrade-decision-tree.md`

---

## Related

- [The Longform Guide](https://x.com/affaanmustafa/status/2014040193557471352) - Section on continuous learning
- `/learn` command - Manual pattern extraction mid-session

---

**Last Updated**: 2026-07-05
**Version**: 3.0.0 - Memory Capture 由「寫入後升級評估」改為「捕獲時分流」：新增步驟 2 分流判準（成熟錯誤學習直寫 error-pattern + deferred 顯式標註），原 Step 5 升級評估改為「分流落地與 deferred 收割」；依據 130 檔標註率 4% 實證事後閉環失效
**Version**: 2.1.0 - 新增 Step 5 升級評估，將 memory 寫入串接到 framework 升級流程（防範 PC-061）
