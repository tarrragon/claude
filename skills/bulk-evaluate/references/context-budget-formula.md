# Context 預算公式（例外情況參考）

> 主文件: ../SKILL.md
>
> **注意**: 本文件是例外情況的參考。預設策略是 **1 個子任務 = 1 個 Agent**（單一職責原則）。
> 僅當平台限制無法派發足夠 Agent 時，才需要使用本公式計算合理的批次大小。

## 何時需要本公式

| 情境 | 需要本公式 |
|------|-----------|
| 平台限制 Agent 並行數量 | 是 |
| API 速率限制 | 是 |
| 成本考量需要減少 Agent 數量 | 是 |
| 一般情況（無限制） | 否（用 1:1 派發） |

## 基礎參數

| 參數 | 值 | 來源 |
|------|-----|------|
| 模型 context window | 200,000 tokens | Claude Opus/Sonnet |
| 系統 + 常駐規則開銷 | ~28,300 tokens | CLAUDE.md + Tier 1 rules |
| 安全係數 | 0.75 | 預留輸出空間 + 工具呼叫開銷 |
| 可用 context | ~128,775 tokens | (200,000 - 28,300) * 0.75 |

**注意**: Agent（subagent）的常駐開銷通常低於主線程，因為不載入完整規則系統。實際可用 context 可能更高，但公式使用主線程值作為保守估計。

## Token 估算方法

### 快速估算（推薦）

```
1 KB 原始文字 ≈ 300-400 tokens（中英混合）
1 KB 原始文字 ≈ 250-300 tokens（純英文）
1 KB 原始文字 ≈ 400-500 tokens（純中文）
```

**實測數據**（本專案 Markdown 檔案）:

| 類型 | 平均大小 | 估算 tokens | 實測 tokens/KB |
|------|---------|------------|---------------|
| Agent 定義 (.md) | 17 KB | ~5,100 | ~300/KB |
| Skill SKILL.md | 8.6 KB | ~2,580 | ~300/KB |
| 規則 (.md) | 6.2 KB | ~2,170 | ~350/KB |

### 精確估算（大規模掃描時使用）

使用 `wc -c` 量測位元組大小，除以 1024 得 KB，乘以 350（中英混合預設）得 tokens。

```bash
# 量測參考標準
ref_bytes=$(wc -c < reference_standard.md)
ref_tokens=$((ref_bytes * 350 / 1024))

# 抽樣目標檔案（取 5 個平均）
avg_bytes=$(wc -c target_1.md target_2.md target_3.md target_4.md target_5.md | tail -1 | awk '{print $1/5}')
avg_tokens=$((avg_bytes * 350 / 1024))
```

## 公式推導

### 每個 Agent 的 context 分配

```
usable_context = 128,775 tokens

每個 Agent 的 context 消耗:
  = reference_tokens              (讀取 1 次參考標準)
  + N * per_item_read_tokens      (讀取 N 個目標檔案)
  + N * per_item_write_tokens     (寫入 N 個子 Ticket 結論)
  + agent_overhead                (Agent 自身的 prompt + 工具呼叫)

其中:
  agent_overhead ≈ 5,000 tokens   (Agent prompt + 工具呼叫開銷)
  per_item_write_tokens ≈ 800     (每個子 Ticket 結論約 800 tokens)
```

### 最大項目數公式

```
max_items_per_agent = floor(
  (usable_context - reference_tokens - agent_overhead)
  / (per_item_read_tokens + per_item_write_tokens)
)
```

### 計算範例

**案例: 30 個 Skill SKILL.md（avg 8.6KB），參考標準 10KB**

```
usable_context    = 128,775 tokens
reference_tokens  = 10 * 300 = 3,000 tokens
agent_overhead    = 5,000 tokens
available         = 128,775 - 3,000 - 5,000 = 120,775 tokens

per_item_read     = 8.6 * 300 = 2,580 tokens
per_item_write    = 800 tokens
per_item_total    = 3,380 tokens

max_items = floor(120,775 / 3,380) = 35 個

→ 35 > 30，1 個 Agent 理論上夠，但考慮 output 累積建議 2 個
→ 查表: 小檔案 + 小參考標準 → 15 個/Agent → ceil(30/15) = 2 Agent
```

**案例: 59 個 Agent 定義（avg 17KB），參考標準 25KB**

```
usable_context    = 128,775 tokens
reference_tokens  = 25 * 350 = 8,750 tokens
agent_overhead    = 5,000 tokens
available         = 128,775 - 8,750 - 5,000 = 115,025 tokens

per_item_read     = 17 * 300 = 5,100 tokens
per_item_write    = 800 tokens
per_item_total    = 5,900 tokens

max_items = floor(115,025 / 5,900) = 19 個

→ 查表: 大檔案 + 中參考標準 → 5-8 個/Agent（保守）
→ ceil(59/8) = 8 Agent（保守）
→ ceil(59/19) = 4 Agent（精確計算）
→ 建議取中間值: 5-6 Agent
```

## 安全預設值推導

安全預設值是「不做精確計算時的保守估計」，推導邏輯如下:

```
可用 context = 128,775 tokens（最保守）

小檔案 + 小標準: (128,775 - 5,000 - 5,000) / (3,000 + 800) ≈ 31 → 取半 → 15
小檔案 + 大標準: (128,775 - 10,500 - 5,000) / (3,000 + 800) ≈ 29 → 取 1/3 → 10
大檔案 + 小標準: (128,775 - 5,000 - 5,000) / (9,000 + 800) ≈ 12 → 取 2/3 → 8
大檔案 + 大標準: (128,775 - 10,500 - 5,000) / (9,000 + 800) ≈ 11 → 取半 → 5
混合 + 小標準: 取大檔案值的下限 → 5
混合 + 大標準: 取大檔案值的更保守值 → 3
```

「取半」或「取 1/3」是因為:
1. Agent 的 output 會累積佔用 context
2. 工具呼叫有額外開銷
3. 安全預設值應寧可多分幾組也不要溢出

## 溢出風險指標

| 風險等級 | 指標 | 建議行動 |
|---------|------|---------|
| 低 | max_items > 1.5 * 分組大小 | 按計畫執行 |
| 中 | 1.0 < max_items/分組大小 <= 1.5 | 減少 1-2 個/Agent |
| 高 | max_items <= 分組大小 | 必須拆分更多組 |

## 相關文件

- ../SKILL.md - 主文件（快速流程和安全預設值）
- .claude/rules/guides/parallel-dispatch.md - 並行派發指南
- .claude/rules/core/cognitive-load.md - 認知負擔設計原則
