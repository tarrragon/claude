---
name: continuous-learning
description: "Extracts reusable patterns from Claude Code sessions and captures knowledge as atomic memory units. Use when session ends (Stop hook), when recording technical decisions, implementation insights, or lessons learned. Handles both automatic pattern detection and structured memory capture with interconnected knowledge links."
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

**適用時機**：

| 時機 | 說明 |
|------|------|
| 重要技術決策完成 | 方案選擇後建立決策記錄 |
| 實作方案確定 | 新的實作模式或解決方案誕生 |
| 學習機會 | 測試失敗、問題排除、重構完成後的經驗總結 |
| Phase 4 完成 | 重構後進行知識沉澱 |
| 版本發布前 | 總結主要決策和經驗 |

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

---

## Related

- [The Longform Guide](https://x.com/affaanmustafa/status/2014040193557471352) - Section on continuous learning
- `/learn` command - Manual pattern extraction mid-session

---

**Last Updated**: 2026-03-02
**Version**: 2.0.0 - 整合 memory-network-builder 的記憶網路構建能力
