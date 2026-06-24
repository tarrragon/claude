# PC-APP-003: 衝突解決以量取代設計正確性

## 症狀

sync-pull 衝突解決時，以「本地版本行數更多 = 更完整」為判據保留本地版本，實際上本地多出的行是冗餘設計。

## 根因

衝突解決的心智模型偏向「超集安全」——認為保留更多行不會壞事。此啟發法在內容性衝突（文件段落多寡）可能合理，但在設計性衝突（程式碼路徑配置）中，多出的行可能是冗餘甚至錯誤的。

## 觸發條件

- sync-pull 產生衝突
- 兩版本差異為「行數不同」而非「內容衝突」
- 未查閱上游設計標準即做決策

## 解決方案

衝突解決判據優先序：

| 優先級 | 判據 | 說明 |
|-------|------|------|
| 1 | 設計標準 | 是否有上游標準文件定義正確做法（如 `hook-sys-path-template.md`） |
| 2 | 設計意圖 | 每一行的存在是否有對應的技術需求（import 是否真的需要該路徑） |
| 3 | 最小充分 | 滿足需求的最小配置，冗餘行應移除 |

**禁止判據**：行數多寡、「保留更多比較安全」。

## 預防措施

1. sync-pull 衝突解決前，先搜尋上游是否有對應的設計標準文件
2. 對程式碼衝突逐行驗證：每行是否有對應的 import 或功能需求
3. 衝突解決的 commit message 應說明「為何採此版本」而非「此版本更完整」

## 實際案例

**場景**：`main-thread-edit-restriction-hook.py` 的 sys.path 設定衝突

- 本地：3 行（parent + parent.parent + parent.parent/"lib"）
- 上游：2 行（parent + parent.parent）
- 錯誤決策：「本地更完整，採 local」
- 正確決策：上游 2 行符合 `hook-sys-path-template.md` 標準，第 3 行冗餘（`parent.parent` 已覆蓋 `lib.*` 的 import 解析）

## 相關

- `.claude/references/hook-sys-path-template.md` — 觸發本次發現的設計標準
- sync-pull SKILL.md 衝突解決決策表 — 三選項判斷流程

---

**Discovered**: 2026-06-24
**Source**: sync-pull 衝突解決 session
