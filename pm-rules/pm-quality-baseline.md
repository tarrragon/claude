# PM 品質基線規則

本檔承載原 `quality-baseline.md` 規則 6-7，屬 PM 情境專屬品質底線，由 PM 按需讀取（非 auto-load）。

> **適用對象**：主線程 PM（rosemary-project-manager）。代理人執行 Ticket 時不觸發這兩條規則，因此不納入 auto-load。
>
> **與 `quality-baseline.md` 的關係**：`quality-baseline.md` 規則 1-5 為所有角色通用品質底線（auto-load）；本檔規則 6-7 為 PM 行為規範（按需讀取），兩檔合稱完整品質基線。

---

## 強制規則

### 規則 6：框架修改優先於專案進度

**`.claude/` 框架改善的優先級永遠高於個別專案的功能進度**

> **來源**：PM 多次在 WRAP 分析中將框架改善延後到下版本，理由為「專案進度優先」。但框架是跨專案共用基礎設施，一次改善惠及所有後續工作，回報永遠最高。

**判斷標準**：

| 問題 | 若答「是」 | 行動 |
|------|-----------|------|
| 改善 `.claude/` 下的規則/方法論/代理人/Hook？ | 是 | 框架修改，優先處理 |
| 修復的問題會在其他 Ticket/版本重複出現？ | 是 | 框架修改，優先處理 |
| 改善僅影響當前 Ticket 的產品功能？ | 是 | 專案進度，正常排序 |

**禁止行為**：

| 禁止 | 原因 |
|------|------|
| 以「專案進度緊迫」為由延後框架修改 | 框架債務會在每個後續 Ticket 重複支付成本 |
| 將框架改善排入「下個版本」 | 延後 = 累積，每延後一次就多 N 個 Ticket 受影響 |
| 框架問題只記錄不立即處理 | 記錄不等於解決，必須當前 Wave 內處理 |

**執行原則**：
- 發現框架可改善時，**當前 Wave 內**建立 Ticket 並執行
- 框架修改 Ticket 的優先級自動提升為 P1（至少）
- 唯一允許延後的情況：框架修改依賴尚未完成的前置工作（技術阻塞，非時間阻塞）

---

### 規則 7：Memory 寫入必須評估跨專案升級

**寫入 feedback 類 memory 時，必須同時評估是否升級為框架規則**

> **來源**：W9-003 分析發現 PM 有 5/13（約 38%）的 feedback memory 僅存 memory 未升級，包含跨專案適用的原則（如「框架/產物分離」「Ticket 引導優先於 Hook」「/clear 前持久化」）。Memory 是**專案層級儲存**（`~/.claude/projects/<project>/memory/`），不會隨 `.claude/` sync 到其他專案；跨專案原則若僅存 memory，會在其他專案消失並可能重複踩同樣的雷。

**強制四問檢查**（寫入 feedback memory 時必須回答）：

| 檢查問題 | 回答「是」的升級路徑 |
|---------|-------------------|
| 此原則對其他專案也適用嗎？ | 至少升級到 `.claude/` 框架層；否則加 `project_` 前綴標示為專案特定 |
| 此原則是通用品質或流程原則嗎？ | 升級至 `.claude/rules/core/quality-baseline.md` 或新建 `rules/core/*.md` |
| 此原則是 PM 行為規範嗎？ | 升級至 `.claude/rules/core/pm-role.md` 或 `.claude/pm-rules/` |
| 此原則是錯誤學習嗎？ | 升級至 `.claude/error-patterns/`（PC/IMP/ARCH 對應分類） |
| 此原則是流程方法論嗎？ | 升級至 `.claude/methodologies/` |
| 此原則是 Skill 引導嗎？ | 升級至 `.claude/skills/<skill>/` |

**四問都回答「否」才允許僅存 memory**（代表確為專案特定 context 索引）。

**升級後處理**：
- 原 memory 檔案頂部註明「本原則已升級為框架規則」並列出升級目的地路徑
- 保留 memory 作為本專案的 context 提醒索引（不必刪除）
- 升級完成後才能視為「原則已落地」

**禁止行為**：

| 禁止 | 原因 |
|------|------|
| 以「之後再升級」為由僅寫 memory | 升級摩擦是永久性的，下次只會更不想動 |
| 寫入 feedback memory 時未執行四問檢查 | 評估缺失直接導致跨專案原則流失 |
| 將跨專案原則誤歸為「專案特定」以規避升級 | Memory 不是跨 session 知識庫，專案層級儲存不會自動傳播 |

**驗證方式**：定期（或每版本發布前）檢視 `MEMORY.md` 索引，確認每個 feedback 項目皆已標註升級位置或顯式標為專案特定。

---

## PM 品質檢查清單

以下兩項為 PM 專屬檢查（規則 1-5 的通用清單見 `quality-baseline.md`）：

- [ ] 發現框架可改善時，是否已在當前 Wave 建立 Ticket？（規則 6）
- [ ] 寫入 feedback memory 時已執行四問升級檢查？（規則 7，PC-061）

---

## 底線要求總結（PM 專屬）

| 要求 | 說明 | 可協商 |
|------|------|--------|
| 框架修改優先於專案進度 | `.claude/` 改善不可因專案進度延後 | 否 |
| Memory 寫入必須評估升級 | feedback memory 必須執行四問檢查，跨專案原則須升級框架 | 否 |

---

## 相關規則

- `.claude/rules/core/quality-baseline.md` - 通用品質基線（規則 1-5，auto-load）
- `.claude/rules/core/pm-role.md` - 主線程角色行為準則
- `.claude/pm-rules/plan-to-ticket-flow.md` - Plan 轉 Ticket 流程
- `.claude/error-patterns/process-compliance/PC-061-memory-upgrade-blindness.md` - 規則 7 錯誤模式來源
- `.claude/skills/continuous-learning/skill.md` - Memory 升級流程 Skill

---

**Last Updated**: 2026-04-16
**Version**: 1.0.0 - 從 quality-baseline.md v1.9.0 規則 6-7 外移；auto-load 僅保留通用品質底線（規則 1-5），PM 情境專屬規則移至此處按需讀取（對應 0.18.0-W10-073.4 WRAP 選項 B）
