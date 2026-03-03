# Version Release CLI 輸出範例

## 完整發布流程（release）

```
+================================================================+
|           Version Release Tool - v0.19.8                       |
+================================================================+

-----------------------------------------------------------------
Step 1: Pre-flight Check
-----------------------------------------------------------------
  [PASS] Worklog 目標達成
     - docs/work-logs/v0.19.0-main.md: Phase 0-4 完成
     - docs/work-logs/v0.19.1-phase1-feature-design.md: 完成
     - docs/work-logs/v0.19.2-phase2-test-design.md: 完成
     - docs/work-logs/v0.19.3-phase3a-strategy.md: 完成
     - docs/work-logs/v0.19.4-phase3b-implementation.md: 完成
     - docs/work-logs/v0.19.8-phase4-final-evaluation.md: 完成

  [PASS] 技術債務已處理
     - 4 個 TD 已分類到 v0.20.0
     - 當前版本無待處理 TD

  [PASS] 版本同步
     - pubspec.yaml: v0.19.8 [PASS]
     - 當前分支: feature/v0.19 [PASS]
     - 工作目錄: 乾淨 [PASS]

-----------------------------------------------------------------
Step 2: Document Updates
-----------------------------------------------------------------
  更新 docs/todolist.yaml
     - 標記 v0.19.x 為已完成

  更新 CHANGELOG.md
     - 新增版本區塊 [0.19.8] - 2026-01-06
     - 分類: Added (8 items) | Changed (3 items) | Fixed (2 items)

  [PASS] 確認 pubspec.yaml 版本號: v0.19.8

  [PASS] 檔案變更已提交 (hash: abc1234)

-----------------------------------------------------------------
Step 3: Git Operations
-----------------------------------------------------------------
  合併 feature/v0.19 -> main
     [PASS] main 分支已更新到最新
     [PASS] 已合併 feature/v0.19 (hash: def5678)

  建立 Tag: v0.19.8-final
     [PASS] Tag 已建立 (v0.19.8-final)

  推送到遠端
     [PASS] main 已推送 (sync: main)
     [PASS] Tag 已推送 (v0.19.8-final)

  清理 feature 分支
     [PASS] 本地分支已刪除: feature/v0.19
     [PASS] 遠端分支已刪除: origin/feature/v0.19

-----------------------------------------------------------------
[PASS] 版本 v0.19.8 發布成功！

發布統計:
   - 合併提交: 1
   - 文件更新: 2
   - Tag 建立: 1
   - 分支清理: 1 本地 + 1 遠端
```

## 預覽模式（--dry-run）

```
+================================================================+
|           Version Release Tool - v0.19.8 (DRY RUN)             |
+================================================================+

[WARNING] 預覽模式：不會執行實際的 git 操作

[相同的 Pre-flight Check 和 Document Updates]

-----------------------------------------------------------------
Step 3: Git Operations (預覽)
-----------------------------------------------------------------
  [預覽] 將合併 feature/v0.19 -> main
     指令: git merge feature/v0.19 --no-ff

  [預覽] 將建立 Tag: v0.19.8-final
     指令: git tag v0.19.8-final

  [預覽] 將推送到遠端
     指令: git push origin main
     指令: git push origin v0.19.8-final

  [預覽] 將清理 feature 分支
     指令: git branch -d feature/v0.19
     指令: git push origin --delete feature/v0.19

[PASS] 預覽完成。執行不含 --dry-run 參數進行實際發布
```

## 只檢查（check）

```
+================================================================+
|           Version Release - Pre-flight Check                   |
+================================================================+

[PASS] 所有檢查通過！該版本已準備好發布

發布指令:
  uv run .claude/skills/version-release/scripts/version_release.py release

或預覽:
  uv run .claude/skills/version-release/scripts/version_release.py release --dry-run
```

## 錯誤情況

```
[FAIL] Pre-flight Check 失敗

-----------------------------------------------------------------

[FAIL] 問題 1: Worklog 未完成
   位置: docs/work-logs/v0.19.4-phase3b-implementation.md
   描述: Phase 3b 標記為進行中，需要完成
   修復: 完成 Phase 3b 並標記完成

[FAIL] 問題 2: 版本號不同步
   pubspec.yaml 版本: v0.19.8
   工作日誌版本: v0.19.4
   修復: 確認 pubspec.yaml 版本號是否正確

-----------------------------------------------------------------

修復後重新執行:
  uv run .claude/skills/version-release/scripts/version_release.py check
```
