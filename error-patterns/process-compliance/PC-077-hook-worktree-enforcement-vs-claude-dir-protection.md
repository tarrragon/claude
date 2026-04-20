# PC-077: Hook 強制 worktree vs ARCH-015 `.claude/` 保護的派發死結

---

## 分類資訊

| 項目 | 值 |
|------|------|
| 編號 | PC-077 |
| 類別 | process-compliance |
| 風險等級 | 中 |
| 首發時間 | 2026-04-17（W13-003 實作中派發 thyme-python-developer 遭 Hook 擋） |
| 姊妹模式 | ARCH-015（subagent 對 `.claude/` Edit 在主 repo 和 worktree 均擋） |

---

## 症狀

PM 派發實作代理人（thyme-python-developer、parsley-flutter-developer、fennel-go-developer、cinnamon-refactor-owl 等）處理位於 `.claude/` 目錄的檔案（Hook / Skill / methodology / rules / error-patterns）時：

1. 若 PM 未加 `isolation: "worktree"` 參數：
   - 遇 `agent-dispatch-validation-hook` 阻擋，錯誤訊息「實作代理人 {name} 必須使用 isolation: "worktree" 派發」
2. 若 PM 加 `isolation: "worktree"` 重試：
   - 雖通過 dispatch 驗證，subagent 進入 worktree 後 Edit `.claude/` 被 CC runtime 擋（ARCH-015 hardcoded 保護）
   - subagent 回報失敗，PM 需重新派發
3. 最終結論：對 `.claude/` 的修改**無論是否使用 worktree 皆無法由 subagent 完成**，PM 必須前台執行

---

## 根本原因

### 真根因（Hook 要求與 Runtime 保護之間的死結）

1. **Hook 設計前提**：`agent-dispatch-validation-hook` 預設實作代理人會修改檔案和執行 git 操作，worktree 隔離能防止污染主 repo 的 `.git/HEAD`
2. **Runtime 保護**：CC runtime 對 `.claude/` 有 hardcoded 寫入保護（對應 ARCH-015），該保護不區分主 repo 或 worktree，一律阻擋 subagent 的 Edit / Write
3. **交集死結**：`.claude/` 內的實作任務同時觸發「Hook 要 worktree」和「Runtime 擋 subagent」兩條規則，subagent 無可行路徑
4. **缺乏 Hook 例外**：`agent-dispatch-validation-hook` 未針對 prompt 含 `.claude/` 關鍵字的情境豁免 worktree 要求或改走 PM 前台

---

## 常見陷阱模式

| 陷阱表述 | 為何錯誤 |
|---------|--------|
| 「加上 isolation: worktree 就能派發」 | worktree 無法突破 runtime 對 `.claude/` 的 hardcoded 保護 |
| 「換個更專精的代理人（basil-hook-architect）或許可行」 | 所有 subagent 對 `.claude/` 的 Edit 都被擋，問題在 runtime 不在代理人專精度 |
| 「PM 前台寫程式碼違反 pm-role」 | pm-role 禁令僅對「產品程式碼 src/」；`.claude/` 屬框架資產，PM 可改 |

---

## 防護措施

| 層級 | 措施 | 狀態 |
|------|------|------|
| 流程 | PM 派發前先判斷 prompt 是否含 `.claude/` Edit / Write 目標；若是直接 PM 前台處理，跳過派發 | 行為準則（已部分落地於 pm-role.md） |
| Hook | `agent-dispatch-validation-hook` 增加智慧判斷：prompt 含 `.claude/` 時提示「ARCH-015 建議 PM 前台」而非強制 worktree | 建議實施 |
| 規則 | pm-role.md 新增明確條款：`.claude/` 下的 Hook / Skill / rules / error-patterns / methodologies 修改由 PM 前台執行，無派發選項 | 建議實施 |
| 教育 | error-pattern PC-077 + ARCH-015 雙向引用，未來 PM 遇 Hook 擋時可快速定位 | 已實施（本檔） |

---

## 檢查清單（PM 派發前判斷）

- [ ] prompt 是否含 `.claude/` 的 Edit / Write 目標？
  - [ ] 是 → 不派發 subagent，改 PM 前台處理；跳過 isolation:worktree 決策
  - [ ] 否 → 依 isolation:worktree 要求派發實作代理人
- [ ] 若跨兩者（部分 `.claude/` + 部分其他）：
  - [ ] 拆分派發：`.claude/` 部分 PM 前台；其他部分 subagent worktree
- [ ] 若僅為閱讀 `.claude/` 不修改：
  - [ ] 可派發（Read-only），worktree 要求不受影響

---

## 教訓

1. **Hook 單一維度強制未考慮交集死結**：本例 Hook 只關心「實作代理人必須隔離」，未察覺與 runtime 保護的交集
2. **Runtime 保護優先級最高**：任何派發策略需先確認 runtime 不擋，再考慮 Hook 要求
3. **PM 前台不是違規而是合理路徑**：`.claude/` 作為框架資產層，PM 直接修改屬正常職責範圍，不違反 pm-role
4. **累積學習**：此為派發策略演進中的邊界情境，需由 error-pattern 體系持續收集以優化 Hook 判斷

---

## 相關文件

- `.claude/error-patterns/architecture/ARCH-015-subagent-claude-dir-hardcoded-protection.md` — Runtime 保護記錄
- `.claude/rules/core/pm-role.md` — PM 職責邊界（產品程式碼 src/ 禁令範圍）
- `.claude/pm-rules/parallel-dispatch.md` — Worktree 隔離章節
- `.claude/hooks/agent-dispatch-validation-hook.py` — Hook 實作

---

**Last Updated**: 2026-04-17
**Version**: 1.0.0 — 首發記錄（W13-003 PC-072 補強派發 thyme 遭 Hook 擋）
**Source**: 2026-04-17 W13-003 IMP 派發 thyme-python-developer 修改 `.claude/hooks/askuserquestion-charset-guard-hook.py` 被 agent-dispatch-validation-hook 擋 isolation:worktree 要求；對照 ARCH-015 確認即使加 worktree 仍被 runtime 擋
