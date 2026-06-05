# PC-174: 命令閘門 hook 將描述性陳述誤判為命令 + 缺前置條件時硬阻擋而非引導

## 摘要

命令閘門類 hook（`command-entrance-gate-hook` 等以關鍵字辨識「開發命令」並要求 Ticket 前置條件者）有兩個系統性缺陷：(1) 用關鍵字 substring 辨識命令意圖時，無法區分「描述性陳述」（已經修復）與「命令意圖」（去修復），導致狀態陳述被誤判阻擋；(2) 偵測到缺前置條件（無 Ticket）時直接硬阻擋（exit 2），不提供下一步出路。修正方向：辨識層補對稱的「描述性前綴 + 後綴」判別，把過去式/完成態標記排除於命令意圖之外；體驗層把「無前置條件」從硬阻擋改為引導式放行（exit 0 + 注入 context 指示主線程用 AskUserQuestion 提供 建立/認領/放行 三選項）。

## 症狀

- 用戶以過去式描述已完成狀態（「這個分支現在已經修復，可以合併」）被閘門擋下，同一句連續觸發多次
- 純狀態陳述 / git 操作（合併 / merge / pull）因含開發關鍵字（修復）被判為開發命令
- 缺 Ticket 時 hook 只印「請建立或認領 Ticket」後 exit 2，用戶/主線程被迫先離開當前意圖去補 Ticket，無引導互動

## 根因（兩層）

| 層 | 缺陷 | 機制 |
|----|------|------|
| 辨識層 | 命令意圖判別不對稱 | `_is_command_keyword_occurrence` 只查描述性**後綴**（修復「的」「過」），未查描述性**前綴**（「已經」修復）；保守 fallback 把前綴情境判為命令 |
| 體驗層 | 缺前置條件即硬阻擋 | `main()` 對「無 Ticket」與「Ticket 畸形」一律 exit 2，未區分「可引導」與「須阻擋」 |

核心：關鍵字 substring 辨識自然語言意圖必有邊界漏洞（命令 / 陳述 / 修飾字面相同意圖相反）；閘門的價值是「確保可追蹤」，硬阻擋只是手段之一，引導同樣達成且摩擦更低。

**Consequence**：此缺陷不修，任何含開發關鍵字的完成態陳述都會被反覆假阻擋，迫使用戶離開當前意圖去補 Ticket；閘門從「確保可追蹤」退化為「阻斷正常溝通」，用戶對閘門的信任下降，極端情境下會以 `--no-verify` 類繞道規避，反而瓦解防護本身。

## 案例：command-entrance-gate-hook 引導式改善（2026-06-04，W1-036）

用戶請求合併已修復的分支，prompt「這個分支現在已經修復，可以合併」連續三次被 exit 2 阻擋。根因：「修復」命中 `ADJUSTMENT_KEYWORDS`，「已經」前綴未被辨識為完成態標記。用戶提案改引導式。落地：

| # | 修正 | 性質 |
|---|------|------|
| A1 | 新增 `_DESCRIPTIVE_PREFIXES`（已經/已/現已/剛剛/剛/都已）+ 規則 1.5 | 辨識層 |
| A2 | `MANAGEMENT_PATTERNS` 補 合併/merge/pull/rebase 白名單 | 辨識層 |
| B | 無 Ticket（`ticket_id is None`）改 exit 0 + 注入 `GUIDANCE_NO_TICKET`；畸形 Ticket（`ticket_id 非 None`）維持 exit 2 | 體驗層 |

## 技術邊界（必須誠實揭露）

`UserPromptSubmit` hook 是 Python 子行程，**無法直接呼叫 AskUserQuestion 或任何 Claude 工具**，只能 `exit` 與注入 `additionalContext`。「引導式閘門」以「放行 + 注入引導指令」間接達成——注入的 context 指示主線程改用 AskUserQuestion。設計同類 hook 時不可規劃「hook 直接呼叫 tool」，必須走間接注入。

## 防護

| 步驟 | 動作 | 目的 |
|------|------|------|
| 1 | 閘門辨識層對稱處理描述性前綴 + 後綴 | 過去式 / 完成態標記排除於命令意圖 |
| 2 | 缺前置條件（無 Ticket）→ 引導式放行而非硬阻擋 | 提供 建立/認領/放行 出路，降低假阻擋摩擦 |
| 3 | 阻擋僅保留給「前置條件存在但畸形」（如 Ticket 未認領 / 缺決策樹） | 真實品質問題才阻擋，判別用既有回傳值（`ticket_id is None`）推導 |
| 4 | block vs guide 判別不改既有函式契約 | 將測試破壞面降到最小（W1-036 僅 2 個 main() 測試需語意對齊） |

## 相關

- `.claude/hooks/command-entrance-gate-hook.py` v3.6.0（引導式落地）
- `.claude/rules/core/ai-communication-rules.md` 規則 5（主體性保護：引導取代單純阻止）
- W4-027（同 hook 的 L1 後綴判別 + L2 觸發限縮 + L3 relevance 閘門；本 PC 為 L1 的前綴對稱補強）
- ticket: 0.19.1-W1-036
