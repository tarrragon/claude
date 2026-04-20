# PC-083: framework 檔案 footer/metadata 誤寫專案 Wave/Patch 識別符

---

## 分類資訊

| 項目 | 值 |
|------|------|
| 編號 | PC-083 |
| 類別 | process-compliance |
| 風險等級 | 低（Hook layer1/2 邊界驗證已能攔截） |
| 首發時間 | 2026-04-17（升級 writing-prompts 為 ai-communication-rules 框架規範 session） |
| 姊妹模式 | feedback_framework_no_ticket_references（框架禁引用專案 ticket ID）— 本模式是其 footer/metadata 子場景 |

---

## 症狀

PM 建立或更新 `.claude/rules/` `.claude/references/` `.claude/skills/` 等 framework 檔案時，在檔案結尾的 `**Version**` 或 `**Source**` 或 changelog 行寫入專案特定的 Wave / Patch 識別符（`W14-012`、`0.18.0-W14` 等）作為追蹤標記。

典型觸發：
1. PM 剛用 Ticket 流程建立新規則檔
2. 習慣性在 footer 加「追蹤 ticket」標記以方便回溯
3. 忽略 framework 檔案會 sync 到其他專案，Wave/Patch 是本專案特定概念
4. 被 Hook layer1/2 邊界驗證攔下

---

## 實際案例（升級 writing-prompts session）

**原本寫法**（被 Hook 攔）：

```markdown
**Version**: 1.0.0 — 從 compositional-writing/writing-prompts.md 提煉通用對話規範（0.18.0-W14-012）
```

**Hook 警告**：

```
[WARNING] Layer 1/2 邊界驗證警告
位置：Line 107, Column 81
禁止項：Wave/Patch 版本概念
內容：W14
建議：改為「執行週期」
```

**修正寫法**：

```markdown
**Version**: 1.0.0 — 從 compositional-writing/writing-prompts.md 提煉通用對話規範，升級為框架級 auto-load 規則
```

---

## 根本原因

### 真根因

1. **PM 追蹤本能與框架中立性衝突**：
   - PM 受 PC-053 / quality-baseline 規則 5 訓練「所有修改都要追蹤」，自動想在 footer 標註 ticket
   - framework 檔案的跨專案 sync 本質要求「去專案化」
   - 兩個正確原則在 footer 欄位碰撞

2. **Footer 欄位的語義模糊**：
   - `**Source**`「這個檔案從哪裡來」
   - `**Version**`「版本變更摘要」
   - 兩者都是元資料欄位，PM 預設可以放追溯標記
   - 但 Wave/Patch 是 framework 閱讀者（其他專案）無法理解的座標

3. **既有規則覆蓋盲區**：
   - `feedback_framework_no_ticket_references` 強調「不引用 ticket ID」
   - 但焦點在「內文引用」（`see 0.17.0-W5-003` 這類）
   - Footer 的「版本變更摘要附 ticket」是額外習慣場景

### 為何容易發生

- 本人剛完成 Ticket 追蹤流程，Ticket ID 在工作記憶頂端
- 寫 footer 是檔案收尾最後一步，注意力已分散
- framework vs 專案的邊界意識在長 session 中容易模糊

---

## 常見陷阱模式

| 陷阱表述 | 為何仍構成違反 |
|---------|--------------|
| 「Footer 只是元資料」 | framework 檔案 sync 到其他專案後，Wave 概念不存在 |
| 「只是方便回溯 ticket」 | 回溯靠 git log + blame，不需在檔案內嵌入專案座標 |
| 「Source 欄位保留脈絡有助理解」 | 功能性描述（「從 X 提煉」）比版本座標更跨專案可讀 |

---

## 防護措施

| 層級 | 措施 | 狀態 |
|------|------|------|
| Hook | Layer 1/2 邊界驗證已攔截 `W\d+` `Patch` 字串 | 已實施（驗證成功） |
| 流程 | framework 檔案 footer 僅用功能性描述（動詞 + 受詞），禁用版本座標 | 行為準則 |
| 流程 | 追蹤 ticket 由 git commit message 承擔，不寫入 framework 檔案內文 | 行為準則 |
| 規則 | `rules/core/document-format-rules.md` 規則 5（檔案命名）可補充 footer 範例對照 | 建議實施 |
| Memory | 記錄本模式作為 PM 習慣提醒 | 已實施 |

---

## 檢查清單（PM 建立 framework 檔案前自我檢查）

- [ ] 檔案位於 `.claude/rules/` `.claude/references/` `.claude/skills/` 或 `.claude/error-patterns/` 等 framework 目錄？
- [ ] Footer 的 `**Version**` / `**Source**` / `**Last Updated**` 是否含 Wave/Patch/W\d+ 字串？
- [ ] 如需標示變更動機，改用功能性描述（「從 X 提煉為 Y」「簡化 auto-load 預算」）
- [ ] 追蹤 ticket 歸 git commit message，不嵌入 framework 檔案內文
- [ ] Commit 前檢查 Hook layer1/2 警告是否出現，是則立即修正（不可豁免）

---

## 教訓

1. **Footer 是框架中立性的最後一哩路**：PM 在 footer 欄位的自然語言習慣最容易反射寫入專案座標，這是 framework sync 邊界的暗流
2. **元資料欄位沒有豁免權**：framework 檔案的每一行、每一欄位都可能被其他專案閱讀，Wave/Patch 在那裡不存在
3. **Hook 攔截是下限不是解方**：Hook 攔住是最後防線；PM 在「寫」的當下就該意識到，避免依賴 Hook 修正
4. **追蹤需要與中立性雙軌**：ticket 追蹤在 git history 側承擔，檔案內文側保持 framework 中立，兩者各司其職

---

## 象限歸類

本模式的防護屬 **摩擦力管理 C 象限（增加摩擦）**：寫 footer 時多一步「是否含專案座標」自檢增加摩擦，換取 framework 檔案跨專案 sync 的純淨度。代價（幾秒自檢）遠低於收益（避免 sync 污染）。

---

## 相關文件

- `.claude/references/framework-asset-separation.md` — 框架資產 vs 專案產物分離
- `.claude/rules/core/document-format-rules.md` — 文件格式規範（可補充 footer 範例）
- Hook: `.claude/hooks/` layer1/2 邊界驗證 — 攔截 Wave/Patch 字串

---

**Last Updated**: 2026-04-17
**Version**: 1.0.0
**Source**: 建立新 framework 規則檔時 Hook 攔下 footer 的 Wave 版本引用，揭示「追蹤本能 × 框架中立性」衝突場景
