# 規則系統

本目錄包含專案的所有規則和流程定義。

> **核心原則**：decision-tree 是所有決策的起點，其他規則都是它的支撐或延伸。

---

## 目錄結構

```
.claude/rules/
├── README.md                     # 本文件
│
├── core/                         # 核心決策 + 基本約束
│   ├── decision-tree.md          # 主線程二元決策樹（核心）
│   ├── askuserquestion-rules.md  # AskUserQuestion 強制使用規則
│   ├── cognitive-load.md         # 認知負擔設計原則
│   ├── document-format-rules.md  # 文件格式
│   ├── document-system.md        # 五重文件系統規則
│   ├── implementation-quality.md # 實作品質標準（跨語言）
│   ├── language-constraints.md   # 語言約束
│   ├── python-execution.md       # Python 執行規則
│   ├── bash-tool-usage-rules.md  # Bash 工具使用規則（cd 污染 / TaskOutput）
│   ├── quality-baseline.md       # 流程品質基線
│   └── verification-framework.md # 驗證責任分配框架
│
├── flows/                        # 執行流程
│   ├── tdd-flow.md               # TDD 流程
│   ├── incident-response.md      # 事件回應流程
│   ├── plan-to-ticket-flow.md    # Plan-to-Ticket 轉換流程
│   ├── tech-debt.md              # 技術債務流程
│   ├── ticket-lifecycle.md       # Ticket 生命週期
│   └── version-progression.md    # 版本推進決策規則
│
├── guides/                       # 操作指南
│   ├── methodology-index.md      # 方法論索引
│   ├── parallel-dispatch.md      # 並行派發指南
│   ├── query-vs-research.md      # 查詢 vs 研究決策指南
│   ├── skill-index.md            # Skill 指令索引
│   └── task-splitting.md         # 任務拆分指南
│
└── forbidden/                    # 禁止行為
    └── skip-gate.md              # Skip-gate 防護

代理人定義位於：.claude/agents/（按需載入，不常駐）
```

---

## 層級關係

```
                    ┌─────────────────────┐
                    │  core/decision-tree │  ← 絕對核心
                    └──────────┬──────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                      ▼
┌───────────────────┐    ┌─────────────────┐    ┌───────────────┐
│  .claude/agents/  │    │     flows/      │    │   forbidden/  │
│  代理人定義(按需) │    │    執行流程     │    │   禁止行為    │
└───────────────────┘    └─────────────────┘    └───────────────┘
        │
        ▼
┌───────────────┐
│   guides/     │
│   操作指南    │
└───────────────┘

約束層（decision-tree 必須遵守）：
┌─────────────────────────────────────────────────────────┐
│  core/quality-baseline, language-constraints, etc.     │
└─────────────────────────────────────────────────────────┘
```

---

## 快速導航

| 需求 | 文件 |
|------|------|
| 決策入口 | @.claude/rules/core/decision-tree.md |
| 代理人定義 | @.claude/agents/ |
| TDD 流程 | @.claude/rules/flows/tdd-flow.md |
| 錯誤處理 | .claude/rules/flows/incident-response.md |
| 任務拆分 | .claude/rules/guides/task-splitting.md |
| 品質要求 | @.claude/rules/core/quality-baseline.md |

---

## 讀取時機

| 目錄 | 讀取時機 |
|------|---------|
| `core/` | 每次對話開始、決策時 |
| `.claude/agents/` | 派發決策時（按需載入） |
| `flows/` | 進入特定流程時 |
| `guides/` | 需要操作指導時 |
| `forbidden/` | 持續監控 |

---

**Last Updated**: 2026-03-03
**Version**: 3.1.0 - 補齊所有實際存在的 rules 檔案（core +3, flows +2, guides +3）
