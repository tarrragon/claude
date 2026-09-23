# 版本發布流程詳細設計

本文件包含三步驟發布流程的完整偽程式碼和檢查邏輯。

---

## Step 1: Pre-flight 檢查

驗證發布前置條件是否滿足：

**前置關卡（Step 1 之前）**：`check_version_frozen(version)` 先確認目標版本
於 `todolist.yaml` 已標 `scope: frozen`。scope_blocker 判定只在凍結後才有
意義——未凍結版本的 blocker 恆為 0，對「可發布」判定沒有鑑別力。未凍結時
`check` 與 `finish` 皆印 FAIL 並 exit 非 0，不進入 blocker 計算；`finish`
的此關卡在 Step 0（migrate overflow tickets）之前，未凍結不產生 migrate
副作用。

```python
def preflight_check(version: str):
    """
    1.1 確認 worklog 目標達成
        - 掃描 docs/work-logs/v{VERSION}*.md
        - 掃描 tickets/ 目錄，依 status 與 scope_blocker 分組（見 SKILL.md
          〈發版判準：blocker 阻擋、其餘前移〉）：in_progress 與帶
          scope_blocker 的 pending 阻擋；無 blocker 的 pending 列入前移
          清單，不阻擋發版

    1.2 檢查技術債務狀態
        - 讀取 todolist.yaml 的「技術債務追蹤」區塊
        - 確認當前版本的 TD 是否都已處理或延遲到下一版本
        - 驗證沒有未分類的 TD

    1.3 版本同步檢查
        - package.json / manifest.json 版本 vs worklog 版本一致
        - 當前分支是否為 feature/v{VERSION}
        - 工作目錄是否乾淨（沒有未提交的修改）

    1.4 檔案存在檢查
        - CHANGELOG.md 存在
        - 主工作日誌存在 (v{VERSION}-main.md)
        - todolist.yaml 存在
    """
```

**檢查項目**:

- [x] 無 in_progress Ticket、無帶 scope_blocker 的 pending Ticket（無 blocker 的 pending 列前移清單不阻擋）
- [x] 技術債務已分類和處理
- [x] 版本號在所有地方一致
- [x] 當前分支正確
- [x] 工作目錄乾淨

---

## Step 2: 文件更新

更新 CHANGELOG、todolist 等文件：

```python
def update_documents(version: str):
    """
    2.1 清理 todolist.yaml
        - 找出當前版本系列在任務表格中的行
        - 標記該版本為已完成
        - 更新版本狀態表格的 「開發狀態」 列
        - 格式: [完成] Phase 3b 完成 → [完成] 已完成

    2.2 更新 CHANGELOG.md（Keep a Changelog 格式）
        - 讀取工作日誌提取功能變動
        - 生成版本區塊: ## [X.Y.Z] - YYYY-MM-DD
        - 分類: Added, Changed, Fixed, Removed
        - 複製到 CHANGELOG.md 頂部（在其他版本之前）

    2.3 確認 package.json 和 manifest.json 版本號正確
        - 驗證 "version" 欄位存在且一致
        - 與 worklog 版本號一致
    """
```

**更新檔案**:

- `docs/todolist.yaml` - 標記版本為已完成
- `CHANGELOG.md` - 新增版本變動記錄
- `package.json` / `manifest.json` - 驗證版本號

---

## Step 3: Git 操作

執行 Git 相關操作：

```python
def git_merge_and_push(version: str, dry_run: bool = False):
    """
    3.1 提交所有變更（如果有未提交的）
        staged 範圍 = 執行前 baseline（finish/release 入口的 git status 快照）
        與目前狀態的差集，過濾出屬 docs/ 或 CHANGELOG.md 者，逐檔 add
        （不用 -A／目錄）——涵蓋 Step 0 前移產生的 ticket rename，取代舊版
        寫死的 `git add docs/todolist.yaml CHANGELOG.md`
        git commit -m "docs: 版本 {version} 發布準備"

    3.2 切換到 main 分支
        git checkout main

    3.3 git pull origin main（確保最新）
        git pull origin main

    3.4 合併 feature 分支（--no-ff 保留合併記錄）
        git merge feature/v{VERSION} --no-ff -m "Merge v{VERSION}"

    3.5 建立 Tag（v{VERSION}-final，如 v0.19-final）
        git tag v{VERSION}-final
        git tag -a v{VERSION}-final -m "Release v{VERSION}"

    3.6 推送到遠端（包含 tag）
        git push origin main
        git push origin v{VERSION}-final

    3.7 刪除本地和遠端 feature 分支
        git branch -d feature/v{VERSION}
        git push origin --delete feature/v{VERSION}

    3.8 推進下一版本為 active（啟動，冪等）
        讀取 todolist.yaml，依 semver 排序選最小的 planned/pending 候選版本
        呼叫 ensure_version_activated(next_version)：逐項檢查 todolist
        status、worklog 主檔、版本檔版號、CHANGELOG In Development 段落，
        只補缺的項目並印 [OK]/[補]；全部就位時不改動任何檔案（含 mtime）
        （與 start 對既有版本走的補齊路徑共用同一常式，避免副作用集合與
        執行路徑不對齊）
        若無 planned/pending 候選版本，跳過（非錯誤）

    3.9 第二次收尾提交（Commit Version Activation）
        Mark Version Completed 與 Activate Next Version 在 3.1 之後才寫入
        todolist.yaml，故對同一 baseline 差集再跑一次 3.1 的 add + commit
        邏輯，把這兩步的變更一併納入版本控制

    3.10 exit 前殘留守衛
        對 baseline 差集（不限 docs/ 或 CHANGELOG.md）做最終檢查；非空即
        列出殘留路徑並以非 0 結束，不自動 add——避免吸入非本次 finish
        產生的變更
    """
```

**Git 操作順序**:

1. 提交檔案變更（差集範圍）
2. 切換到 main 分支
3. 拉取最新 main
4. 合併 feature 分支（保留合併記錄）
5. 建立 Tag
6. 推送 main + Tag
7. 刪除本地/遠端 feature 分支
8. 標記版本完成、推進下一版本為 active
9. 第二次收尾提交（涵蓋標記完成與版本啟用的變更）
10. exit 前殘留守衛（非空即非 0 退出並列殘留清單）
