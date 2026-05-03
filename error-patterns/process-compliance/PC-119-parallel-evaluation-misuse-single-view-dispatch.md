---
id: PC-119
title: parallel-evaluation 用法誤解 — PM 單派 linux 視角而非並行三人組
category: process-compliance
severity: medium
status: active
created: 2026-05-03
related:
- PC-040
- PC-066
- PC-118
---

# PC-119: parallel-evaluation 用法誤解 — PM 單派 linux 視角而非並行三人組

## 問題描述

PM 派發 multi-view review 任務時，僅派發 linux 單一視角而非並行三人組（linux + bay + thyme），違反 `parallel-evaluation` SKILL 的核心設計（「派發三人組（含常駐委員 linux）並行掃描」）。

ticket 名稱含「派 parallel-evaluation linux 視角審查」字樣易誤導 PM 認為該 ticket 範圍只需 linux 一人——實則 ticket 內容（acceptance + Problem Analysis）才是權威，「parallel-evaluation」前綴本身已暗示三視角協議。

**Why**：parallel-evaluation 的價值在於「視角差異互補」——linux（good taste / 架構）+ bay（品質 / 穩定性）+ thyme（Python 慣例 / DRY）三組獨立審查能揭露單一視角盲區。PM 單派 linux 退化為「強勢評分主導」，違反 memory `parallel_eval_needs_wrap` 警告（linux 強勢評分不可直接轉執行）。

**Consequence**：單一視角審查報告會被誤認為「multi-view review 已完成」，後續決策（如 W17-008.5 group 結案、PC-105 文件補強）建立在不完整證據上。視角獨有發現（如 thyme 識別的 `_classify_argparse_error` index 取 pattern bad smell、bay 識別的 hook marker 跨檔同步風險）會被遺漏。

**Action**：

1. 派發任何含 parallel-evaluation / multi-view / 三視角審查 / multi_view_status 字樣的 ticket 前，先確認三人組（linux + bay + thyme）皆需並行派發
2. 寫 prompt 時將視角專屬重點寫入 ticket md Context Bundle 的「三視角分工」章節，每個視角從 Context Bundle 自取自己的審查重點，prompt 本體保持 ≤ 30 行（PC-040）
3. 三人組產出後 PM 整合三視角結論並寫入 ANA Solution 章節 + multi_view_status 標註

---

## 觸發案例

### 案例 1：W17-008.5.6.2 multi-view review 派發

**事件**（2026-05-03）：

W17-008.5.6.2 ticket 名稱「派 parallel-evaluation linux 視角審查 W17-008.5 group 錯誤通道設計」，PM 解讀為「ticket acceptance 只要求 linux 視角審查報告」，於是僅派 linux 單人 agent。

PM 在 ticket md 的 Problem Analysis 章節寫了 4 維度審查重點（設計合理性 / 未覆蓋盲區 / Follow-up 建議 / Good taste），但派發時未拆分視角專屬版本。linux agent 完成審查後寫入 ticket md 的 H2 自定義章節（後修為 H3 子章節）。

用戶指出「這裡應該是多視角審查，為什麼只開了一個代理人」，PM 才補派 bay + thyme 兩個視角並行（背景執行）。bay 與 thyme 各自貢獻獨有發現：

- thyme 獨有：`_classify_argparse_error` 用 index 取 pattern 屬 bad smell、`_emit_create_error` helper 抽取建議
- bay 獨有：exit_code=0 short-circuit 防護未被測試覆蓋、hook marker 跨檔同步風險詳細評估
- linux 獨有：integration-test 缺 INVALID_VALUE 場景

若僅依 linux 視角結論，後續 W17-008.5 group 結案會缺以上 P2/P3 follow-up 識別，三視角共識升級項（ErrnoCodes StrEnum 集中升 P1.5）也不會浮現。

### 共同特徵

| 特徵 | 說明 |
|------|------|
| ticket 名稱誤導 | 「派 parallel-evaluation linux 視角審查」字面易讀為「只需 linux」 |
| acceptance 不夠明示 | 第 1 項 acceptance「linux 視角審查報告」字面不違反，但隱含「multi-view 完整性」未被條件化 |
| skill 文件未在 ticket md 引用 | 派發時 PM 未對照 parallel-evaluation skill 描述「派發三人組（含常駐委員 linux）」 |
| 用戶事後糾正 | PM 自決判斷錯誤，由用戶外部反饋觸發修正 |

---

## 根因分析

### 直接原因

PM 將「ticket 名稱字面範圍」誤解為「ticket 完整意圖範圍」。ticket 名稱通常為簡短摘要，acceptance + Problem Analysis 才是權威；「parallel-evaluation」前綴已暗示三人組協議，但 PM 未將此前綴展開為派發實作。

### 結構性原因

1. **skill 用法的隱性約束未硬編碼於 ticket schema**：parallel-evaluation skill 描述「派發三人組（含常駐委員 linux）」屬人類可讀規則，沒有 hook 或 schema 強制 PM 在派發 multi-view ticket 時並行三 agent
2. **memory feedback 提醒的局限**：`parallel_eval_needs_wrap` memory 提醒「linux 強勢評分需 WRAP」，但未涵蓋「禁止單派 linux」這層更基本的協議
3. **ticket 名稱命名習慣**：PM 在 W17-117 originally 將此 ticket 命名為「派 parallel-evaluation linux 視角審查」，名稱本身強化了單一視角誤解

### 為何 PM 自律不可靠

memory feedback `parallel_eval_needs_wrap` 已存在但未阻止本次誤判。原因：memory 提供「使用後處理」建議（WRAP 擴增選項），未提供「使用前協議」（必並行）。PM 在派發時心智模型中「parallel-evaluation」與「linux 單人」混合，需要外部規範強制區分。

---

## 防護建議

### 短期（行為自律）

1. PM 派發 multi-view review 前，將 parallel-evaluation skill 描述「派發三人組」字樣明確列入 ticket md Context Bundle
2. ticket 命名避免「派 X agent 審查 Y」單人形式；改用「multi-view review Y（linux + bay + thyme）」三人並列
3. 視角專屬重點寫入 ticket md「三視角分工」章節，prompt 本體只引「讀 ticket Context Bundle」（PC-040）

### 長期（結構性防護）

1. **ticket schema 擴充**：multi-view ticket type 強制要求 frontmatter 含 `reviewers: [linux, bay-quality-auditor, thyme-python-developer]`，hook 偵測單派時 deny
2. **parallel-evaluation skill 補充強制條款**：skill description 加「Use NEVER for single-view dispatch」明示禁令
3. **agent dispatch hook 整合**：偵測 prompt 含「multi-view」/「parallel-evaluation」字樣但 session 內僅派一個 agent 時 warn

---

## 相關規則與 memory

- `.claude/skills/parallel-evaluation/SKILL.md` — 三人組協議定義（含常駐委員 linux）
- memory `parallel_eval_needs_wrap` — linux 強勢評分需 WRAP（使用後處理）
- memory `feedback_parallel_agent_conflict` — 並行代理人檔案衝突防護
- PC-040 — Context in Ticket not Prompt（視角專屬重點寫 Context Bundle）
- PC-066 — Decision quality autopilot under load（PM 自律失效防護）

---

## 結論

parallel-evaluation 是「並行協議」而非「派發框架」——其價值在於三視角差異互補，單派 linux 退化為「強勢評分主導」，違反設計意圖且遺漏視角獨有發現。

PM 派發 multi-view ticket 時必須：(1) 三人組並行（linux + bay + thyme）、(2) 視角專屬重點寫入 ticket Context Bundle、(3) 整合三視角結論並寫入 multi_view_status 標註。

ticket 命名應避免單人形式以降低誤導風險；schema / hook 強制機制屬長期防護方向。
