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
│   ├── cognitive-load.md         # 認知負擔設計原則
│   ├── document-system.md        # 五重文件系統規則
│   ├── quality-baseline.md       # 品質基線
│   ├── language-constraints.md   # 語言約束
│   └── document-format-rules.md  # 文件格式
│
├── agents/                       # 代理人系統
│   ├── overview.md               # 職責矩陣 + 升級規則
│   ├── incident-responder.md     # 錯誤回應（Level 1）
│   ├── security-reviewer.md      # 安全審查（Level 3）
│   ├── system-analyst.md         # 系統分析（Level 2）
│   ├── system-designer.md        # UI/UX 設計
│   ├── system-engineer.md        # 環境問題
│   ├── data-administrator.md     # 資料設計
│   ├── memory-network-builder.md # 知識記憶
│   ├── lavender-interface-designer.md   # TDD Phase 1
│   ├── sage-test-architect.md           # TDD Phase 2
│   ├── pepper-test-implementer.md       # TDD Phase 3a
│   ├── parsley-flutter-developer.md     # TDD Phase 3b
│   └── cinnamon-refactor-owl.md         # TDD Phase 4
│
├── flows/                        # 執行流程
│   ├── tdd-flow.md               # TDD 流程
│   ├── incident-response.md      # 事件回應流程
│   ├── ticket-lifecycle.md       # Ticket 生命週期
│   └── tech-debt.md              # 技術債務流程
│
├── guides/                       # 操作指南
│   ├── task-splitting.md         # 任務拆分指南
│   └── parallel-dispatch.md      # 並行派發指南
│
└── forbidden/                    # 禁止行為
    └── skip-gate.md              # Skip-gate 防護
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
┌───────────────┐    ┌─────────────────┐    ┌───────────────┐
│    agents/    │    │     flows/      │    │   forbidden/  │
│  代理人定義   │    │    執行流程     │    │   禁止行為    │
└───────────────┘    └─────────────────┘    └───────────────┘
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
| 決策入口 | [core/decision-tree](core/decision-tree.md) |
| 代理人總覽 | [agents/overview](agents/overview.md) |
| TDD 流程 | [flows/tdd-flow](flows/tdd-flow.md) |
| 錯誤處理 | [flows/incident-response](flows/incident-response.md) |
| 任務拆分 | [guides/task-splitting](guides/task-splitting.md) |
| 品質要求 | [core/quality-baseline](core/quality-baseline.md) |

---

## 讀取時機

| 目錄 | 讀取時機 |
|------|---------|
| `core/` | 每次對話開始、決策時 |
| `agents/` | 派發決策時 |
| `flows/` | 進入特定流程時 |
| `guides/` | 需要操作指導時 |
| `forbidden/` | 持續監控 |

---

## 舊目錄遷移說明

以下舊目錄已合併到新結構中，將在後續版本移除：

| 舊目錄 | 新位置 |
|-------|-------|
| `decision-tree/` | `core/decision-tree.md` |
| `boundaries/` | `agents/overview.md` |
| `agent-triggers/` | `agents/*.md` |
| `workflows/` | `flows/` + `guides/` |

---

**Last Updated**: 2026-01-23
**Version**: 2.0.0
