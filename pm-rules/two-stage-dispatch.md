# Subagent 複雜任務分工規範

> **目標**：在 subagent 平台限制下（~20 tool calls/turn、32K output token），確保複雜任務能可靠完成。

---

## 平台限制背景

> 完整的限制數據和來源：`.claude/references/claude-code-platform-limits.md`
> 平台限制可能隨 Claude Code 版本更新而變化，數據以參考文件為準。

**核心約束**：subagent 約有 **~20 次工具呼叫/turn**、**32K output token**。每次 Read、Edit、Bash、Grep 各算一次。

---

## 任務複雜度評估

在派發 subagent 前，PM 需估算任務的 **tool call 預算**：

| 操作 | 預估 tool calls | 範例 |
|------|-----------------|------|
| 讀取目標檔案 | 1-2 | Read 檔案尾部確認結構 |
| 讀取設計文件/規格 | 1-3 | Read Ticket、設計文件 |
| 探索現有程式碼風格 | 3-8 | Read + Grep 多個檔案 |
| 寫入程式碼 | 1-3 | Edit 一次或多次 |
| 執行測試 | 1-2 | Bash npm test |
| Git 操作 | 1-2 | Bash git add + commit |
| **合計預算** | **~20** | |

### 判斷規則

| 估算 tool calls | 策略 |
|----------------|------|
| <= 15 | 單一 subagent 可完成 — 直接派發 |
| 16-25 | 風險區 — 精簡 prompt 或拆分 |
| > 25 | 必須拆分 — 使用分工模式 |

**關鍵指標**：如果任務需要 **探索 5+ 檔案**（5+ Read/Grep）才能開始寫程式碼，幾乎肯定超出預算。

---

## 分工模式

當任務超出單一 subagent 預算時，拆分為兩個獨立子任務：

### 任務 A：探索與設計（消耗 tool calls 在讀取上）

**角色**：sage / pepper / saffron

**目標**：閱讀程式碼、理解結構、產出完整的可貼入程式碼

**產出物**：設計文件或 Ticket Solution 區段，包含：
- 完整程式碼片段（可直接 Edit 注入）
- 目標檔案路徑和注入位置（精確的 old_string）
- 預期測試指令

**不做的事**：不修改 src/ 或 tests/ 檔案

### 任務 B：注入與驗證（消耗 tool calls 在寫入上）

**角色**：general-purpose / thyme / parsley

**Prompt 要點**：
- 告訴代理人從哪裡讀取程式碼（Ticket 路徑）
- 告訴代理人注入到哪裡（目標檔案 + 位置）
- 告訴代理人跑什麼測試
- **不包含程式碼本身**（程式碼在 Ticket/設計文件中）

**Tool call 估算**：Read 設計文件（1）+ Read 目標檔案尾部（1）+ Edit（1-2）+ Bash 測試（1）+ Bash commit（1）= **5-6 次**，充裕。

---

## Prompt 最佳化

無論是否拆分，prompt 應遵循以下原則減少 subagent 的 tool call 消耗：

| 原則 | 說明 |
|------|------|
| 提供精確位置 | 「第 828 行的 `})` 之前」比「在檔案尾部」省一次 Read |
| 引用 Ticket 路徑 | 程式碼放 Ticket 而非 prompt，避免佔用 output token |
| 指定 Edit 的 old_string | 代理人不需要 Read 就知道要替換什麼 |
| 明確「不要探索」 | 如果不需要理解上下文，明確告知代理人 |

---

## 何時不需要拆分

| 場景 | 原因 |
|------|------|
| 修改已知位置的少量程式碼 | tool calls < 10 |
| 主線程在 feature 分支直接操作 | 不受 subagent 限制 |
| 任務只需 Read + 分析（不需寫入） | 探索型任務 context 足夠 |

---

## 與其他規則的關係

| 規則 | 關係 |
|------|------|
| IMP-047 | 程式碼放 Ticket 而非 prompt（減少 output token 佔用） |
| task-splitting.md | 按 tool call 預算評估是否需要拆分 |
| parallel-dispatch.md | 任務 A 和 B 為序列關係，A 完成後才能派發 B |

---

**Last Updated**: 2026-04-06
**Version**: 2.0.0 - 從「行數閾值」改為「tool call 預算」模型（基於平台限制實證）
