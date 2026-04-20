# 框架元層管理方法論

> **定位**：本文件管理「框架內的知識載體分類」，決定何時建立 SKILL、何時建立 methodology、何時建立 rule。這是框架治理層的原則，不是寫作方法本身。

---

## 核心概念：SKILL vs 方法論 vs 規則

| 類型 | 定位 | 長度標準 | 讀者 |
|------|------|---------|------|
| **方法論** | 30 秒複習清單（核心概念 + 步驟 + 檢查清單） | < 1 頁 | 框架使用者：快速回憶 |
| **SKILL** | 完整實作指南（範例、決策樹、錯誤處理） | 不限 | 執行者：完整操作流程 |
| **規則（rules/）** | 強制底線（不可協商的品質基線） | 精簡 | 所有角色：自動載入 |

### 分類決策樹

```
有新知識需要記錄？
    |
    +-- 是強制底線、所有角色必須遵守 → rules/
    |
    +-- 是完整操作流程（含範例/錯誤處理/決策依據）
    |       |
    |       +-- 可獨立發佈到 marketplace（不依賴本框架） → skills/
    |       +-- 框架專屬操作流程 → skills/（內部 reference）
    |
    +-- 是可在 30 秒內複習的核心概念清單 → methodologies/
```

**關鍵判斷**：若知識只有在本框架內有意義（如「何時建 Ticket」「Phase 1-4 流程」），不適合放進 marketplace 可攜的 SKILL，應放 methodology 或 pm-rules。

---

## 撰寫/改寫方法論的檢查清單

### 新建方法論前評估

- [ ] 是否有完整操作流程需要保存？ → 改建 SKILL（方法論只留 30 秒摘要）
- [ ] 是否有程式碼範例、錯誤處理細節？ → 移到 SKILL reference
- [ ] 精簡後是否會流失關鍵資訊？ → 同時建 SKILL 保存
- [ ] 內容是否框架專屬（非 marketplace 可攜）？ → 仍可建 SKILL，但標記「內部 reference」

### 改寫既有方法論的觸發條件

- 方法論超過 1 頁（30 秒電梯測試失敗）
- 出現「完整流程」段落而非「核心原則」
- 有程式碼範例或大量決策表格
- 被多個代理人頻繁引用但細節部分差異大

### 改寫步驟

1. 識別「30 秒核心」（≤ 5 條要點）
2. 將其餘內容移至 SKILL reference
3. 方法論改為引用 SKILL：`詳見 [SKILL 名稱](./../skills/skill-name/SKILL.md)`
4. 執行 broken-link-check 確認引用有效

---

## 經驗分享文章的框架元層原則

### 體裁定位

經驗分享（retrospective）是**記錄自己的經歷**，讀者想看「發生了什麼、怎麼解決的」。  
不是 methodology（30 秒複習），不是 SKILL（完整操作指南）。

**存放位置**：`docs/work-logs/` 的附加章節，或獨立的 `retrospective.md`；**不是** `methodologies/`。

### 敘事結構要求

每個案例必須完整：**發現 → 找因 → 修復**。

| 環節 | 要問的問題 | 常見省略 |
|------|----------|---------|
| 發現 | 什麼現象讓你意識到有問題？ | 直接說「問題是 X」跳過發現過程 |
| 找因 | 怎麼一步步定位原因的？ | 只說「原因是 Y」跳過偵查過程 |
| 修復 | 最終的解決方式是什麼？ | 只說「改成 Z」不說為什麼是 Z |

### 框架知識萃取（retrospective → methodology/rule）

當 retrospective 中出現以下訊號，應萃取為框架知識：

| 訊號 | 萃取動作 |
|------|---------|
| 同類問題第二次出現 | 建 error-pattern（根因 + 預防） |
| 發現可重複的決策流程 | 建 methodology（30 秒版） |
| 發現強制底線被違反 | 強化 rules/（或補 PM 強制觸發 Hook） |
| 跨 session 容易忘記的事 | 寫入 memory（auto-load） |

---

## 相關文件

- `.claude/skills/methodology-writing/SKILL.md` - 方法論撰寫完整實作指南
- `.claude/skills/compositional-writing/references/writing-documents.md` - 寫作原則（含 30 秒電梯測試、六項準則）
- `.claude/methodologies/methodology-rewriting-methodology.md` - 改寫既有方法論的具體流程

---

**Last Updated**: 2026-04-18
**Version**: 1.0.0 - 從舊 methodology-writing 方法論提煉不重疊部分（SKILL vs 方法論分工、撰寫/改寫檢查清單、retrospective 敘事脈絡）建立本檔；原重疊內容已遷移至 writing-documents.md
