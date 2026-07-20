# PC-BAL-001: 驗證端清單過期使建立端產出的 canonical 結構被判違規

## 症狀

工具的建立端（模板 / builder）自動產出某個結構元素，驗證端（hook / linter / checker）卻回報該元素為「非 Schema」「未定義」「違規」。執行者信任警告並移除該元素，實際移除的是 canonical 定義的必要結構；下次建立時同一元素再度產出，警告週期性復發，形成不收斂的噪音迴圈。

進階症狀：執行者在修正記錄中寫下錯誤歸因（「模板產生了禁止的元素」），使後人沿用錯誤前提繼續處理，錯誤方向被固化。

## 根因

同一概念的權威清單在程式碼庫中存在多份副本，建立端與驗證端各自引用不同副本且無同步機制。建立端清單較完整（含新增元素），驗證端清單停留在舊版本。

**關鍵不對稱**：建立端的清單直接決定實際產出，驗證端的清單只決定警告文字。「工具實際行為」永遠以建立端為準，驗證端的警告是對正確產出的誤報。執行者若以警告為真相來源，會反向修改正確的產出。

**generic 化**：跨領域可重現於任何「產生器 + 驗證器」成對存在但共享定義未收斂的系統——schema 定義與 migration、proto 定義與序列化端、API 契約與 mock server、i18n key 清單與掃描器。

## 案例

flutter_balance 專案 0.0.1-W1-002 執行中，`acceptance-gate-hook` 回報 ticket body 的 `## Spawn Requests` 為「非 Schema H2 章節（W17-072）」。

四份清單的實際狀態：

| 來源 | 角色 | 含 Spawn Requests |
|------|------|------------------|
| `ticket_system/constants.py` `CANONICAL_BODY_SECTIONS` | 建立端權威（註解自述「順序即 body 物理順序權威」） | 是 |
| `ticket_system/lib/ticket_builder.py` `SCHEMA_H2_SECTIONS` | 建立端（直接別名前者） | 是 |
| `hooks/acceptance_checkers/custom_h2_checker.py` `_SCHEMA_SECTION_NAMES` | 驗證端 | 否 |
| `execution_log_checker` / `ticket_validator` 各自的 `_SCHEMA_SECTION_NAMES` | 驗證端 | 檔頭自述須與 custom_h2_checker 同步 |

`custom_h2_checker.py` 檔頭已載明「三處將於 ARCH-020 refactor 收斂」，顯示框架知悉驗證端三份分裂，但未涵蓋建立端的 `CANONICAL_BODY_SECTIONS`，實為四份分裂。

執行者依警告移除該章節，並在 ticket 自檢段寫下「`ticket create` 模板與 schema 定義脫節」的錯誤歸因（真實方向相反：檢查器清單漏列 canonical 章節）。事後查證四份清單才更正。移除本身無功能後果——`execute_add_spawn_request` 透過 `insert_missing_schema_section` 在章節缺失時自動補回。

## 防護

防護目標是讓執行者在「警告」與「工具實際產出」衝突時，能定位真正的權威而非預設警告為真。

**判定順序**：收到「工具自動產生的東西違規」類警告時，先比對建立端與驗證端的定義來源，確認兩者一致再動手修改。兩者不一致時以建立端為準——建立端決定實際產出，驗證端只決定警告文字。

| 訊號 | 判定 | 動作 |
|------|------|------|
| 警告針對的元素由工具自動產生，非執行者撰寫 | 疑似驗證端過期 | 查建立端清單後再決定 |
| 建立端含該元素、驗證端不含 | 驗證端過期 | 不修改產出，記錄不一致 |
| 兩端皆不含該元素 | 真實違規 | 修改產出 |
| 驗證器檔頭載明「須與 X 同步」「待 refactor 收斂」 | 已知分裂風險，清單可信度低 | 一律查建立端 |

**根因解**：多份清單收斂為單一定義來源，驗證端 import 建立端常數而非各自維護副本。收斂前，每份副本檔頭標註同步對象與權威來源（本案 `custom_h2_checker.py` 已標註但漏列建立端）。

**記錄要求**：依警告修改產出後，於修改記錄註明所依據的權威來源與比對結果，使後人能判斷該修改是否基於過期清單。

## 相關

- 工具預設行為勝過文件規範：`.claude/rules/core/opinionated-default-design.md` 主張 1（本 pattern 是其反面案例——執行者信文件層的警告而非工具層的實際行為）
- 工具輸出信任判據：`.claude/rules/core/tool-output-trust-rules.md` 規則 3（關鍵事實用固定值交叉驗證；本案的固定值是清單成員的 grep 命中）
- 失敗案例學習原則：`.claude/rules/core/quality-baseline.md` 規則 6（錯誤歸因已寫入 ticket，採更正而非回退）

---

Last Updated: 2026-07-20 | Source: flutter_balance 0.0.1-W1-002 自檢階段
