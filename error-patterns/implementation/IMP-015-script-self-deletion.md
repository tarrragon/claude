# IMP-015: 腳本自我刪除導致執行中斷

## 分類

| 項目 | 值 |
|------|-----|
| ID | IMP-015 |
| 類型 | Implementation |
| 嚴重度 | 高 |
| 首次發現 | 2026-03-05 |
| 來源 | 0.1.0-W1-016 sync-pull 腳本修復 |

## 錯誤模式

Shell 腳本在執行過程中刪除自身所在的目錄，導致 bash 後續行無法讀取，腳本 hang 或靜默失敗。

## 觸發條件

腳本包含以下模式：
1. 腳本位於 `.claude/scripts/` 目錄下
2. 腳本中執行 `rm -rf .claude`（刪除自身所在目錄）
3. 刪除後仍有後續指令需要執行

## 根因分析

Bash 不保證一次將整個腳本讀入記憶體。在某些系統/情境下，bash 逐步讀取腳本檔案。當腳本的父目錄被 `rm -rf` 刪除後，bash 的 file descriptor 雖然可能仍有效（Unix unlink 語義），但行為取決於：

- Bash 版本和讀取策略（block read vs line read）
- 檔案系統實作
- 是否有 `cd` 改變工作目錄

結果是不確定性：有時成功、有時 hang、有時靜默失敗。

## 附帶發現

同一腳本還有兩個相關問題：

| 問題 | 說明 | 影響 |
|------|------|------|
| `git status --porcelain` 抓 untracked | `??` 前綴的檔案也被視為「未提交變更」 | stash 後仍被拒絕執行 |
| `git clone` 無 timeout | 網路問題時無限等待 | session 完全 hang |
| `rsync -v` 列出全部檔案 | 778 個檔案產生 31KB 輸出 | 觸發 output too large，Hook 誤判為 lint 警告 |

## 解決方案

### 自我刪除問題

將 `rm -rf` 之後的所有腳本內容放入變數，用 `eval` 執行：

```bash
SCRIPT_REMAINING='
# rm -rf .claude 之後的所有指令
rm -rf .claude
mkdir -p .claude
# ... 其餘指令 ...
'
eval "$SCRIPT_REMAINING"
```

或者：從 `/tmp` 執行腳本副本，避免自我刪除。

### untracked 檔案誤判

```bash
# 錯誤：git status --porcelain 包含 ?? (untracked)
git status --porcelain .claude | grep -q .

# 正確：只檢查 tracked 檔案的變更
git diff --name-only .claude | grep -q .
git diff --cached --name-only .claude | grep -q .
```

### clone timeout

```bash
GIT_HTTP_LOW_SPEED_LIMIT=1000 GIT_HTTP_LOW_SPEED_TIME=30 \
    git clone --depth 1 https://... "$TEMP_DIR"
```

### verbose 輸出

```bash
# 錯誤：rsync -av（列出每個檔案）
rsync -av source/ dest/

# 正確：rsync -a + 摘要
rsync -a source/ dest/
echo "已複製 $(find dest/ -type f | wc -l) 個檔案"
```

## 防護措施

| 措施 | 說明 |
|------|------|
| 腳本自我刪除檢查 | 任何 `rm -rf` 目標包含腳本所在路徑時，必須用 eval 或外部副本執行 |
| git status 精確性 | 需要區分 tracked/untracked 時，用 `git diff` 而非 `git status --porcelain` |
| 外部命令 timeout | git clone/fetch 等網路操作必須設定 timeout |
| 大輸出防護 | 檔案列表類操作避免 verbose，改用摘要 |

## 檢查清單

寫 shell 腳本時：

- [ ] 腳本是否會刪除自身所在目錄？ -> eval 或 /tmp 副本
- [ ] `git status --porcelain` 是否需要排除 untracked？ -> 改用 `git diff`
- [ ] 網路操作是否有 timeout？
- [ ] 輸出量是否可控？（避免 verbose 列出大量檔案）

## 相關文件

- .claude/scripts/sync-claude-pull.sh - 修復後的拉取腳本
- .claude/scripts/sync-claude-push.sh - 修復後的推送腳本
- .claude/rules/core/bash-tool-usage-rules.md - Bash 工具使用規則

---

**Last Updated**: 2026-03-05
**Version**: 1.0.0
