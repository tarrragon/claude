# IMP-019：資料結構投射到 CLI 介面假設錯誤

**錯誤碼**: IMP-019
**分類**: Implementation / Tool Usage
**風險等級**: 低（導致命令失敗和並行取消，無資料損失）
**發現日期**: 2026-03-06
**狀態**: 已記錄
**相關 Ticket**: 0.1.0-W2-016

---

## 症狀

呼叫 CLI 命令時使用了不存在的具名參數：

```bash
ticket track set-where 0.1.0-W2-016 --layer "Infrastructure" --files ".claude/scripts/sync-claude-pull.py"
```

結果：

```
ticket: error: unrecognized arguments: --layer --files .claude/scripts/sync-claude-pull.py
```

並行發出的其他命令（`set-why`、`set-how`）也因第一個失敗而被連帶取消。

---

## 根本原因

### 心智模型投射

知道 Ticket 的 YAML frontmatter 中 `where` 欄位有結構化子欄位：

```yaml
where:
  layer: Infrastructure (Python scripts)
  files:
  - .claude/scripts/sync-claude-pull.py
```

於是假設 CLI 的 `set-where` 命令也提供對應的 `--layer` 和 `--files` 具名參數。

### 實際介面

`set-where` 只接受一個位置參數 `value`（純字串）：

```
usage: ticket track set-where [-h] [--version VERSION] ticket_id value
```

正確用法是將整個值作為單一字串傳入：

```bash
ticket track set-where 0.1.0-W2-016 "layer: Infrastructure, files: [...]"
```

### 並行放大效應

三個 `set-*` 命令並行發出，第一個失敗後 Claude Code 自動取消了後面兩個。即使 `set-why` 和 `set-how` 的語法正確，也被連帶浪費。

---

## 行為模式

**觸發條件**：已知資料有結構化子欄位，需要透過 CLI 設定時

**錯誤行為**：假設 CLI 參數結構與資料模型一對一對應

**認知偏差**：「資料結構 = 介面結構」的投射假設

---

## 解決方案

### 立即修復

查閱 `--help` 確認實際語法後，改用正確的位置參數格式。

### 防護措施

1. **先查語法再組裝**：對不熟悉的 CLI 子命令，先執行 `--help` 確認參數格式
2. **並行前先驗證**：多個命令並行發出前，先對一個做語法確認，避免連帶取消
3. **區分資料模型和 CLI 介面**：不假設 CLI 參數結構與底層資料結構對應

---

## 與 PC-005 的關係

本模式與 PC-005（CLI 失敗時基於假設歸因）屬於同一家族：

| 模式 | 假設對象 | 防護措施 |
|------|---------|---------|
| PC-005 | 錯誤訊息的原因 | 字面解讀錯誤訊息，逐步調查 |
| IMP-019 | CLI 參數的結構 | 先 `--help` 確認語法再使用 |

共同根因：跳過 Step 1（查語法）直接基於假設行動。

---

## 檢查清單

使用不熟悉的 CLI 子命令前：

- [ ] 已執行 `--help` 確認參數格式
- [ ] 區分位置參數 vs 具名參數
- [ ] 多命令並行前，至少一個已驗證語法
- [ ] 不假設 CLI 結構與資料模型對應
