---
id: PC-146
title: PC-093 exempt marker 位置誤用 — 標記置於章節下方或獨立段落而非命中行緊鄰處
category: process-compliance
severity: low
created: 2026-05-13
related:
 - PC-093
 - W10-119
 - W10-123
---

# PC-146: PC-093 exempt marker 位置誤用

## 症狀

PC-093 phase4-decision-enforcement-hook 撞牆後，PM 在 ticket body 加 `<!-- PC-093-exempt: ... -->` 標記，但仍持續阻擋。重新檢視發現標記位置不對：

- 錯誤模式 A：把標記寫成獨立章節（如「### Hook 引用豁免說明」+ 標記內文）
- 錯誤模式 B：把標記寫在命中行**下方**而非上方
- 錯誤模式 C：標記與命中行之間隔 ≥ 2 行（超出 proximity）

## 觸發情境

| 條件 | 說明 |
|------|------|
| Ticket body 引用 W10-118 等含「Phase 5 再決定」字面的 source ticket | Context Bundle 自動抽取 source why，內含 hook 自身歷史案例 |
| PM 第一次加 exempt 標記 | 不熟悉 hook 對 marker 位置的 proximity 規則 |
| 標記置於非命中行緊鄰處 | hook 仍判 BLOCK |

## 根因

### 根因一：hook 的 EXEMPT_PROXIMITY_LINES = 1（僅命中行或前 1 行生效）

`phase4-decision-enforcement-hook.py` 規範：
```python
EXEMPT_PROXIMITY_LINES = 1  # marker 同行或前 1 行生效
```

換言之，marker 必須**緊鄰**命中行（同行或前一行），不能：
- 放在章節 header 之下、命中行之上（中間若有空行 / 標題等元素皆可能脫離 proximity）
- 放在命中行下方（無效）
- 放在獨立的「豁免說明章節」（與命中行物理分離）

### 根因二：PM 直覺認為「在 ticket 任一處宣告豁免即可」

PM 寫文件習慣「集中說明」（如「### 豁免說明」獨立章節），與 hook 「就地宣告」需求衝突。

### 根因三：錯誤訊息未指出 marker proximity 規則

Hook 訊息 `[PC-093 Phase 4 強制決斷] 偵測到延後話術` 雖列出豁免語法但未明示「marker 必須緊鄰命中行 1 行內」，PM 易反覆嘗試錯誤位置。

## 防護措施

### Layer A：作者端正確用法（觀察可行）

| 結構 | 正確 |
|------|------|
| 章節內單行命中 | marker 寫在命中行**上方**，無空行間隔（或同行行尾） |
| 章節內多行命中 | 每個命中行各加一個 marker（hook 行級判定，每行獨立） |
| Context Bundle 內 `- 0.18.0-W10-XXX why: ... Phase 5 再決定 ...` | marker 寫在該 list item 上一行 |

範例（正確）：
```markdown
### Rationale Chain

<!-- PC-093-exempt: ticket-tracked:本段為 source ticket why 引用，非延後決策 -->
- 0.18.0-W10-118 why: ...「Phase 5 再決定」...
```

範例（錯誤）：
```markdown
### Rationale Chain
- 0.18.0-W10-118 why: ...「Phase 5 再決定」...   ← 命中
... 中間其他章節 ...
### 豁免說明                                       ← marker 與命中行物理分離
<!-- PC-093-exempt: ... -->
```

### Layer B：hook 訊息加 proximity 提示（治本待落地）

在 hook stderr 訊息加註：
```
注意：marker 必須緊鄰命中行（同行或前 1 行內）；放在獨立章節無效
```

### Layer C：擴大 EXEMPT_PROXIMITY_LINES（替代治本）

選項：將 proximity 擴大到「同章節（H2/H3 級）內」，讓 PM 在章節內任一處宣告 marker 即生效。需評估副作用（過寬會弱化 PC-093 強制力）。

## 歷史案例

- 2026-05-13 W10-119（首例 a）：PM 寫「### multi_view_status」H3 + bullet list 卻發現 hook 不認 + acceptance-gate-hook 報缺 multi_view_status；同 session 接續發現 exempt marker 也需注意位置
- 2026-05-13 W10-123（首例 b）：PM 初次把 exempt marker 放在 ticket 末段「### Hook 引用豁免說明」獨立章節，與命中行物理分離，hook 仍 BLOCK；改放於命中行前 1 行後生效

## Action

| 情境 | 建議動作 |
|------|---------|
| 撞 PC-093 BLOCK | 套用 Layer A 規範：marker 緊鄰命中行（上方 1 行內或同行行尾） |
| 多個命中行 | 每個命中行各加 marker，不可共用一個 |
| 系統性根除 | 推進 Layer B（hook 訊息加 proximity 提示）或 Layer C（擴大 proximity 至章節內） |

---

**Last Updated**: 2026-05-13
**Version**: 1.0.0 - 初次記錄（W10-119 + W10-123 連續觸發 + Layer A/B/C 防護層設計）
