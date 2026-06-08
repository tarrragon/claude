# PC-150: Subagent 形似字 normalize 誤替換

---

## 分類資訊

| 項目 | 值 |
|------|------|
| 編號 | PC-150 |
| 類別 | process-compliance |
| 風險等級 | 中（靜默語意錯誤，人工抽查才能發現） |
| 首發時間 | 2026-05-15（W11-028 commit b847d8a2） |
| 姊妹模式 | PC-074（繁簡共用字 false positive）/ PC-085（CJK codepoint 鄰近性）/ PC-131（外部工具權威性質疑） |

---

## 症狀

Subagent 執行字元 normalize 任務（如「污→汙」變體字統一）時，將部分目標字替換為**形似但語意完全不同的字**，且 subagent 自我報告顯示認知錯誤字為正確——非 typo，而是系統性形似字混淆。

**Why**：LLM tokenizer 對字形相近的 CJK 字元（如水部字 汙 U+6C59 / 汲 U+6C72 / 汚 U+6C5A）辨識精度有限，特別是 haiku 等輕量 model + effort: low 設定下更容易發生。

**Consequence**：誤替換靜默通過 commit，產出語意錯誤的文件（如「Context 汲染」= 無意義詞組），只有人工 git diff 抽查才能發現。無自動偵測機制時，累積風險隨 normalize 任務數量線性增長。

**Action**：(1) normalize 任務 prompt 必須附目標字白名單 + 完成後 grep 自驗；(2) 建立 PreCommit 形似字混淆對掃描 hook（系統性防護）。

---

## 案例實證

### 案例 1：W11-028 mint 「污→汲」誤改（2026-05-15）

| 項目 | 值 |
|------|------|
| 執行 agent | mint-format-specialist（haiku, effort: low） |
| 任務 | 9 處「污」normalize 為 MoE 標準「汙」 |
| 結果 | 6/9 正確（污→汙）、3/9 錯誤（污→汲），錯誤率 33% |
| 錯誤字 | 汲 (U+6C72, 「汲取」之意) vs 正確目標 汙 (U+6C59, 「汙染」之意) |
| 發現方式 | PM 抽查 git diff |
| 修復 commit | 0aa3658a |
| 影響檔案 | `.claude/skills/compositional-writing/references/principles/agent-team-context-isolation.md` L17/L29/L74 |

**關鍵觀察**：commit message 中 mint 寫「改「汲」per MoE 標準」，顯示 mint 認知「汲」為正確目標字——這不是手滑（typo），而是 LLM 層面的形似字辨識錯誤。

---

## 根本原因

### 直接原因

LLM（haiku model）在處理字形相近的水部字（污 U+6C61 / 汙 U+6C59 / 汲 U+6C72）時，token embedding 空間中三字距離過近，導致 normalize 任務的目標字選擇錯誤。

### 系統性原因

1. **Subagent prompt 無字元驗證機制**：mint agent definition 不含 normalize 白名單或完成後自驗步驟
2. **無 post-commit 自動偵測**：目前無 hook 掃描 commit diff 中的已知形似字混淆對
3. **PC 家族覆蓋缺口**：PC-074/131/132 分別處理 hook false positive、外部工具權威性、hook log 回收，均不覆蓋「subagent 文字 normalize 誤改」場景

---

## 防護建議

| 層級 | 機制 | 說明 |
|------|------|------|
| Prompt 層（自律） | normalize 任務 prompt 附目標字白名單 | agent 完成後 grep 驗證目標字是否正確 |
| Hook 層（強制） | PreCommit 形似字混淆對掃描 | 維護已知混淆對清單，掃描 diff 是否引入混淆字 |

---

## 常見陷阱模式

| 陷阱表述 | 為何仍構成風險 |
|---------|--------------|
| 「LLM 認錯字是低機率事件」 | 本案 33% 錯誤率證明並非低機率；haiku + low effort 加劇 |
| 「subagent 會自己發現錯誤」 | mint 自我報告顯示認知「汲」為正確，無自我糾正能力 |
| 「git diff 抽查就夠了」 | 人工抽查依賴 PM 注意力，非系統性防護 |

---

**Last Updated**: 2026-05-17
**Version**: 1.0.0 — 初始建立：subagent 形似字 normalize 誤替換正常字元的防護（W17-202 ANA）
**Source**: 0.18.0-W17-202 / 0.18.0-W11-028
