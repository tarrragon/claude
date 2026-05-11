# PC-139: Git index.lock 衝突來源誤判（外部 GUI app fork 漏列）

---

## 分類資訊

| 項目 | 值 |
|------|------|
| 編號 | PC-139 |
| 類別 | process-compliance |
| 風險等級 | 低（時間損耗，無資料損害） |
| 首發時間 | 2026-04-01 前後（memory `feedback_git_index_lock_external_app.md` 首次記錄） |
| 姊妹模式 | PC-079（Bash backtick CLI 參數）、`.claude/rules/core/bash-tool-usage-rules.md` 規則三（git 串接）同屬 Bash 與 git 操作紀律 |

---

## 症狀

遇到 `fatal: Unable to create '.git/index.lock': File exists.` 錯誤時，依既有 hook 訊息與 `feedback_git_index_lock_prevention.md` 規則，第一反應為「自己串接 git 寫入操作」或「hook 與 git 競爭」。實際情境中：

1. PM 已乖乖拆分獨立 Bash 呼叫（每個 git 寫入操作獨立）
2. 無 long-running hook 在跑 git 命令
3. lock 仍出現，且重試多次仍失敗

此時排查方向被既有規則錨定為「hook/Bash 串接」，遺漏外部 git GUI app（macOS Fork、GitKraken、SourceTree、VS Code Git 視圖等）週期性 fork `git status` / `git diff` 子進程的可能。

後果：花 5-15 分鐘排查不存在的串接問題，最後才意識到根因為外部工具，且錯失「直接 `rm .git/index.lock`」的安全捷徑。

---

## 實例（memory `feedback_git_index_lock_external_app.md` 累積觀察）

PM 完成獨立 commit，準備接續下一個 git 操作時遇 lock：

```
fatal: Unable to create '.git/index.lock': File exists.
```

PM 行為（誤判）：
1. 檢查命令是否串接 → 確認獨立呼叫 ✓
2. 等待 5 秒重試 → 仍失敗
3. 再等 10 秒 → 仍失敗
4. 排查 hook 是否有 background git → 無
5. 最終 `ps aux | grep -i fork | grep -v grep` 看到 `Fork.app` 進程持續 fork → 真根因浮現
6. `rm .git/index.lock` → 命令立即可執行

合計浪費約 5-15 分鐘排查方向錯位的時間。

---

## 根本原因

### 真根因

1. **既有規則覆蓋面不全**
   - `feedback_git_index_lock_prevention.md` 僅針對「同一 Bash 串接 commit + merge/push」
   - `.claude/rules/core/bash-tool-usage-rules.md` 規則三同此假設
   - 兩者皆未列「外部 GUI app fork process」為合法來源

2. **GUI git 工具的隱性行為**
   - Fork.app / GitKraken / SourceTree 為了即時顯示倉庫狀態，背景週期性執行 `git status` / `git diff` / `git for-each-ref` 等讀取命令
   - 部分操作（如 `git status --porcelain` 配合 lock-on-write）會瞬間建 `.git/index.lock`
   - GUI 自身會自動清除 lock，但時間窗（毫秒至秒級）剛好與 PM 命令重疊即失敗

3. **Hook 訊息措辭引導**
   - `task-dispatch-readiness-check` 等 hook 在 git 失敗時建議「拆分串接」
   - 措辭暗示「你串接了」，PM 順著訊息排查，遺漏「外部進程」可能

### 兩來源並陳

| 來源 | 觸發條件 | 處理方式 |
|------|---------|---------|
| Hook/Bash 串接 | 同一 Bash 呼叫含 `git commit && git merge`（或類似組合） | 拆分為獨立 Bash（PC 規則三 / feedback_git_index_lock_prevention.md） |
| 外部 GUI app fork | macOS Fork.app / GitKraken / SourceTree / VS Code Git 等背景 fork process | `rm .git/index.lock` 安全刪除，外部工具會自行重試 |
| 殘留 lock（罕見） | 系統當機 / Bash 強制中斷 | `ls -la .git/index.lock` 檢查 mtime > 30s 後 `rm` |

---

## 常見陷阱模式

| 陷阱 | 為何錯誤 |
|------|--------|
| 「`rm .git/index.lock` 是危險操作」 | 不一定；確認非自己進程佔有時是安全動作（外部工具自動重試） |
| 「lock 一定是自己造成的」 | 忽略 GUI app fork process；外部工具不會在 PM 命令前提示 |
| 「等久一點 lock 會自己消失」 | 若外部 GUI app 持續 fork，lock 會週期性重現，等待無解 |
| 「Hook 訊息建議拆分 = 必然是串接問題」 | Hook 訊息為一般情境啟發式建議，不是診斷結論 |

---

## 防護措施

| 層級 | 措施 | 狀態 |
|------|------|------|
| 流程 | 遇 index.lock 失敗時，依檢查順序判別來源（見下方檢查清單） | 行為準則 |
| 規則 | `bash-tool-usage-rules.md` 規則三維持「禁止串接」；本 PC 處理「乖乖拆分後仍失敗」剩餘情境 | 邊界澄清 |
| 規則 | `feedback_git_index_lock_prevention.md` 維持原規則；本 PC 補充「GUI app」為另一合法來源 | 並陳 |
| 工具 | 強化 hook 訊息加入「若已拆分仍失敗，檢查外部 git GUI app fork process」（待 W17-194 落地） | 建議實施（W17-194） |

---

## 檢查清單（遇 `Unable to create .git/index.lock` 時）

依序判別來源：

- [ ] 本次 Bash 呼叫是否含 `git ... && git ...`（多 git 寫入串接）？
  - [ ] 是 → 拆分為獨立 Bash 呼叫（PC 規則三 / feedback_git_index_lock_prevention.md）
  - [ ] 否 → 進入下一檢查
- [ ] `ps aux | grep -iE "fork|gitkraken|sourcetree|tower" | grep -v grep` 是否見外部 git GUI app？
  - [ ] 是 → `rm .git/index.lock` 安全動作；GUI 自動重試或 detect
  - [ ] 否 → 進入下一檢查
- [ ] `ls -la .git/index.lock` 看 mtime
  - [ ] mtime > 30 秒 → 殘留 lock，`rm` 安全
  - [ ] mtime < 30 秒 → 有進程剛建；等 10 秒重試
- [ ] 仍無解 → `lsof .git/index.lock`（macOS）或 `fuser .git/index.lock`（Linux）查佔有進程

---

## 教訓

1. **規則覆蓋面是動態的**：既有規則涵蓋 80% 情境不代表剩 20% 不存在；「乖乖按規則仍失敗」是真實訊號，不是規則錯誤
2. **Hook 訊息為啟發式，非診斷**：訊息建議拆分時應視為「最常見可能」，仍須親自驗證根因
3. **`rm .git/index.lock` 危險度被高估**：在確認非自己進程佔有的情境下，刪除是安全動作（外部工具設計為可重試）
4. **排查順序由近至遠**：先驗證自己（Bash 串接）→ 再看外部進程（GUI app）→ 最後看系統殘留（mtime）

---

## 相關文件

- `.claude/rules/core/bash-tool-usage-rules.md` — 規則三「禁止串接多個 git 寫入操作」（hook/Bash 來源）
- `feedback_git_index_lock_prevention.md`（memory）— PC-139 升級前的原規則描述
- `feedback_git_index_lock_external_app.md`（memory）— PC-139 直接來源觀察
- W17-194（pending）— 強化 hook 訊息加入 GUI app 外部進程偵測

---

**Last Updated**: 2026-05-11
**Version**: 1.0.0 — 首發記錄（W17-193 升級 memory feedback 為 framework error-pattern）
**Source**: memory `feedback_git_index_lock_external_app.md` 累積觀察；既有規則僅涵蓋 hook/Bash 串接情境，外部 GUI app fork 屬未列出合法來源
