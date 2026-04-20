---
id: PC-063
title: ANA 階段過早收斂於假設方案，未做重現實驗驗證根因
category: process-compliance
severity: medium
first_seen: 2026-04-13
---

# PC-063: ANA 階段過早收斂於假設方案，未做重現實驗驗證根因

## 症狀

- ANA Ticket 的 Problem Analysis 列出多個候選解法（如 4-5 個方案）
- 候選方案彼此差異看似很大（成本、根治程度、副作用），實際上**全部基於同一個未驗證的假設**
- WRAP Reality Test 階段執行重現實驗後，發現假設錯誤，所有候選方案皆偏離根因
- 真正根因在另一個方向（通常是更低層級、更簡單的修復）

## 真實案例（W5-031 → W5-032）

**問題**：測試範本 0.31.0 版本字面值污染真實 repo 的 docs/work-logs/

**ANA 初始假設**：「測試範本使用 0.31.0 版本字面值，所以要重構範本以避免污染」

**ANA 列出的 4 候選方案**（全部基於上述假設）：

| 方案 | 假設邏輯 |
|------|---------|
| A 哨兵版本號 | 把 0.31.0 改成 99.99.99-sentinel，不污染真實版本 |
| B .gitignore 遮罩 | 把 v0.31 加進 .gitignore，遮蔽污染 |
| C Session Hook 警告 | 偵測非 in-scope 版本目錄並警告 |
| D pytest fixture 檢查 | session 結束時 assert 無污染 |

**WRAP Reality Test 揭露真正根因**：

清理污染 → 跑單一檔案 → 觀察哪個檔案重新產生污染。發現：

- `test_track_batch.py` 4 處測試**完全未 mock save_ticket**，呼叫真實 save_ticket 寫入 repo
- `test_track_relations.py` 3 處 patch 路徑錯誤（patch 原始模組，但被測模組 `from X import Y` 已建立 local binding）

**真正方案 F**：修正測試 mock（~8 處改動，成本極低，根治程度極高）。

原 4 候選方案皆未涉及 mock 修正——因為 ANA 階段未做重現實驗，假設「這是版本字面值問題」而非「這是測試 mock 問題」。

## 根因

ANA Ticket 易於陷入**問題框架固化**：

| 反模式 | 後果 |
|-------|------|
| Problem Analysis 一次性列出所有候選方案 | 候選方案的差異是表面的（同假設下的變體），看似 WRAP 已 Widen 但未真正擴增 |
| 列方案前未做重現實驗 | 根因建立在猜測上，方案皆對應錯誤根因 |
| 用「方案越多代表分析越完整」自我安慰 | 4 個錯誤方案不會比 1 個正確方案更好 |
| 假設「用戶確認過就是真根因」 | 用戶的描述基於現象觀察，可能誤導真正機制 |

## 影響範圍

- 所有 ANA 類型 Ticket
- 特別是 debug/根因分析類任務
- 工具/框架類問題（測試/Hook/CLI）尤其容易誤判，因表象多層

## 解決方案

### 規則：ANA 列候選方案前必須通過 Reality Test 閘門

ANA Ticket 的 Solution 階段必須**先通過至少一次重現實驗**才能列候選方案。重現實驗的形式：

| 問題類型 | Reality Test 形式 |
|---------|-----------------|
| 測試污染/失敗 | 隔離跑、bisect、清理重跑、單檔案逐一驗證 |
| Hook 失效 | 強制觸發、檢查 hook-logs、stdin/stdout 直跑 |
| CLI 行為異常 | 最小重現範例、verbose mode、strace |
| 程式碼邏輯 bug | 編寫 failing test、加 print/log |

**禁止**：跳過重現直接列候選方案。

### WRAP Widen 的真正含義

| 偽 Widen | 真 Widen |
|---------|---------|
| 列出同一假設下的多個方案變體 | 列出基於不同假設、不同層級、不同方向的根本解法 |
| 比較成本/副作用差異 | 質疑假設本身是否成立 |
| 聚焦「怎麼修」 | 聚焦「真正的問題是什麼」 |

## 防護措施

| 措施 | 落地位置 |
|------|---------|
| ANA Ticket 模板新增「重現實驗結果」必填章節 | ticket_system 模板 |
| pm-rules/incident-response.md 強調 Reality Test 優先於方案列舉 | 規則文件 |
| WRAP SKILL 在「Widen Options」章節新增警告：避免同假設下的變體 | wrap-decision skill |
| 接手 ANA Ticket 時 PM 簡化三問新增第四問：「有做過重現實驗嗎？」 | ticket claim 提示 |

## 自我檢查清單

執行 ANA Ticket 時：

- [ ] 列候選方案前已重現問題至少一次？
- [ ] 候選方案是否基於不同層級的假設（非同假設變體）？
- [ ] 是否有「最樸素方案」（直接修根因）作為比較基準？
- [ ] 用戶描述的「現象」是否被獨立驗證？

## 相關 Error Pattern

- PC-054：分析視角錨定在防禦性限制而非品質目標（同一類分析品質問題）
- PC-058：ANA 代理人建立的 Ticket metadata 漂移（ANA 產出物品質問題）
- TEST-005：from X import Y 後 patch 路徑錯誤（W5-032 揭露的真正根因）

---

**Last Updated**: 2026-04-13
**Version**: 1.0.0 — 初始建立（W5-031 ANA 推翻 4 候選方案案例）
