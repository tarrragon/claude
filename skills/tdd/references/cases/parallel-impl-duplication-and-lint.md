# v0.17.0 Phase 3 實作品質案例

> 來源：0.17.0-W4-004（Phase 4 多視角審查報告）

---

## 案例 1：Dead Import — Bare Specifier 未被攔截

**問題編號**：P0-2

**發現位置**：BookSchemaV2.js:12

**問題描述**：
代理人建立新模組時預設加了 `require('src/core/errors/ErrorCodes')` 但未使用。bare specifier 在 Chrome Extension 環境中會阻斷 build。

**根因分類**：實作品質

**根因分析**：
- 代理人在建立新模組時，習慣性加入常用 import
- Phase 3b 完成前未執行 `npm run lint`
- ESLint no-unused-vars 規則本可攔截此問題

**防護措施**：
Phase 3b 完成前執行清單新增：「執行 `npm run lint` 並確認 0 errors」

**回測驗證**：
若代理人遵循執行清單中的 lint 步驟，ESLint 會報告 no-unused-vars error，代理人必須移除未使用的 import 才能通過清單。驗證有效。

---

## 案例 2：並行 Worktree 各自實作驗證框架

**問題編號**：P1-1 / P1-2

**發現位置**：BookSchemaV2.js:81-123, TagSchema.js:57-107

**問題描述**：
BookSchemaV2 和 TagSchema 分別在獨立 worktree 實作，各自建立了結構相同的驗證框架（型別檢查、必填欄位驗證、陣列格式驗證），重複率約 20%。同時 `mapV1StatusToV2`（BookSchemaV2.js:245）和 `migrateReadingStatus`（v1-to-v2.js:91）也有狀態轉換邏輯重複。

**根因分類**：規格盲點

**根因分析**：
- W1 規格分別定義了 Book Schema、Tag Schema、Migration 的規則
- 規格未指出驗證邏輯結構相同應共用
- Phase 3a 策略規劃未識別跨代理人的共用元件
- 每個 W3 代理人在獨立 worktree 各自實作，自然產生重複

**防護措施**：
1. 3b 拆分評估新增 Decision Question Q12：「Phase 1 的共用策略結論是什麼？是否已建立共用模組？」
2. 3b 拆分評估新增 Decision Question Q_new5：「各 worktree 子任務之間是否有共用的常數/版本號/配置？」
3. 拆分後並行安全檢查新增：「共用元件已就緒」

**回測驗證**：
若派發前回答 Q12，會發現 BookSchemaV2 和 TagSchema 的驗證邏輯結構相同，應先建立 ValidationEngine 共用模組。若回答 Q_new5，會發現版本號 "3.0.0" 在多處硬編碼，應由共用模組匯出。驗證有效。

---

## 案例 3：版本號硬編碼重複

**問題編號**：P2-4

**發現位置**：v1-to-v2.js:21, tag-storage-adapter.js:677

**問題描述**：
版本號 "3.0.0" 在 v1-to-v2.js 和 tag-storage-adapter.js 中各自硬編碼，屬 Coupling 問題。

**根因分類**：規格盲點（未定義共用常數策略）

**防護措施**：
Decision Question Q_new5 覆蓋此場景：「各 worktree 子任務之間是否有共用的常數/版本號/配置？」

---

**Last Updated**: 2026-04-04
**Version**: 1.0.0 - 初始建立（0.17.0-W4-005.3）
