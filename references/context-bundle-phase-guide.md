# Context Bundle 各 Phase 欄位指引

> **上位規範**：`.claude/pm-rules/context-bundle-spec.md`（通用模板和核心原則）
>
> 本文件補充各 TDD Phase 的**特定欄位提示**，確保 PM（AI）在填寫 Context Bundle 時不遺漏關鍵資訊。

---

## 通用模板回顧

```markdown
### Context Bundle

**需求摘要**: ...
**API 簽名**: ...
**相關檔案**: ...
**驗收條件**: ...
**約束**: ...
**測試指令**: ...
```

以下列出每個 Phase 在通用模板基礎上**額外應填寫**的欄位。

---

## → Phase 1（功能設計，派發 lavender）

| 額外欄位 | 說明 | 範例 |
|---------|------|------|
| SA 審查結論 | 通過/有條件通過 + 條件摘要 | 「通過，需注意與 FilterEngine 的介面相容」 |
| 需求來源 | UC 編號或提案編號 | 「UC-06、PROP-007」 |
| 現有相關模組 | 路徑 + 一句話職責 | 「src/ui/search/core/search-engine.js — 文字搜尋」 |

---

## → Phase 2（測試設計，派發 sage）

| 額外欄位 | 說明 | 範例 |
|---------|------|------|
| Phase 1 規格路徑 | 設計文件位置 | `{ticket-id}-phase1-design.md` |
| 現有測試檔案 | 路徑 + 行數 + describe 結構摘要 | 「828 行，7 個 describe（1.Construction~7.Events）」 |
| 測試風格要點 | require 模式、mock 策略、命名慣例 | 「CJS require，mockIndexManager/EventBus/Logger，中文 test 名」 |
| 測試範圍 | 哪些函式/模組需要測試 | 「_matchesSearchCriteria 的 tag 相關邏輯」 |

---

## → Phase 3a（策略規劃，派發 pepper）

| 額外欄位 | 說明 | 範例 |
|---------|------|------|
| Phase 2 測試群組摘要 | 群組名稱 + 案例數 | 「A:建構(2)、B:新邏輯(4)、C:容錯(4)、D:相容(2)」 |
| Phase 2 設計路徑 | 測試設計文件位置 | `{ticket-id}-phase2-test-design.md` |
| 依賴模組介面 | 被依賴的 exports 摘要 | 「createTagResolver(deps) → { resolveTag, resolveTagName }」 |

---

## → Phase 3b（實作，派發 parsley/thyme）

| 額外欄位 | 說明 | 範例 |
|---------|------|------|
| 目標檔案路徑 | 要修改的 src 檔案 | `src/ui/search/core/search-engine.js` |
| 注入位置 | 精確的修改位置 | 「建構函式第 49 行的 destructure 新增 tagResolver」 |
| 測試檔案路徑 | 對應的測試 | `tests/unit/ui/search/core/search-engine.test.js` |
| 預期結果 | RED→GREEN 數量 | 「7 個 FAIL → 0 個 FAIL」 |
| Phase 3a 策略路徑 | 策略文件位置 | `{ticket-id}-phase3a-strategy.md` |

---

## → Phase 4a（多視角分析，派發審查代理人）

| 額外欄位 | 說明 | 範例 |
|---------|------|------|
| 變更檔案清單 | git diff --name-only 結果 | 「search-engine.js, search-engine.test.js」 |
| 測試結果摘要 | PASS/FAIL 數量 | 「全部 PASS，新增 12 個測試」 |
| Phase 3b 關鍵決策 | 實作中的重要取捨 | 「tagResolver 為 optional，無時沿用舊 book.tags」 |

---

## → 多視角審查（任何 Phase 後）

| 額外欄位 | 說明 | 範例 |
|---------|------|------|
| 差異摘要 | git diff 的核心變更描述 | 「新增 _tagResolver 屬性，修改 _matchesSearchCriteria」 |
| 設計取捨 | PM 已知的設計決策和理由 | 「選擇 OR 預設而非 AND，因為使用者期望更多結果」 |
| 已知限制 | 審查者應知的約束 | 「tagResolver 缺失時跳過 tag 搜尋，不報錯」 |

---

## 使用方式

PM 填寫 Context Bundle 時：
1. 先填通用模板的 6 個欄位
2. 查閱本文件對應 Phase 的額外欄位表
3. 按需補充（不是每個欄位都必填，但都應考慮）

---

**Last Updated**: 2026-04-06
**Version**: 1.0.0 - 初始建立（第二輪多視角審查建議）
