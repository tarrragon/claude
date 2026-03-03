---
description: 從獨立 repo 拉取最新 .claude 配置和專案模板 (https://github.com/tarrragon/claude.git)
---

# 從獨立 Repo 拉取最新 .claude 配置

請執行以下流程，從獨立 repo 拉取最新的 .claude 配置和專案模板到本專案。

## 拉取內容

- `.claude/` 目錄所有檔案（Hook、Agent、方法論、規則）
- `FLUTTER.md` Flutter 特定規範（更新到專案根目錄）

## 不覆蓋內容

- 根目錄 `CLAUDE.md`（保留專案特定配置）

## 執行流程

1. **確認本地無未提交變更**
   - 檢查 `.claude`、`FLUTTER.md` 是否有未提交的變更
   - 如有變更，詢問用戶是否先提交或暫存

2. **覆蓋確認（強制使用 AskUserQuestion）**
   - 在執行腳本前，必須使用 AskUserQuestion 工具詢問用戶確認
   - 顯示即將被覆蓋的內容，讓用戶知情同意
   - AskUserQuestion 問題格式：
     ```
     question: "即將從 tarrragon/claude.git 拉取更新。以下內容將被覆蓋：
     - .claude/ 目錄所有內容（包含 hooks、agents、methodologies、rules 等）
     - FLUTTER.md

     根目錄 CLAUDE.md 不受影響。腳本會自動備份到 /tmp 臨時目錄。
     確認繼續？"

     options:
     - 確認拉取（腳本自動備份到 /tmp）
     - 先建立穩定備份再拉取（備份到 .claude-backup-{date}）
     - 取消
     ```

3. **根據用戶選擇執行**
   - **確認拉取**：直接執行 `./scripts/sync-claude-pull.sh`
   - **先備份再拉取**：先執行以下備份指令，再執行拉取腳本
     ```bash
     BACKUP_DIR=".claude-backup-$(date +%Y%m%d-%H%M%S)"
     cp -r .claude "$BACKUP_DIR/"
     [ -f FLUTTER.md ] && cp FLUTTER.md "$BACKUP_DIR/"
     echo "備份已建立：$BACKUP_DIR"
     ```
     然後執行：`./scripts/sync-claude-pull.sh`
   - **取消**：中止操作，不執行任何動作

4. **顯示備份位置**
   - 腳本會輸出備份目錄位置
   - 告知用戶如需還原可使用備份

5. **建議測試 Hook 系統**
   - 提醒用戶測試 Hook 系統是否正常運作
   - 建議重啟 Claude Code Session 驗證

## 新專案初始化

如果是新專案，需要手動建立 CLAUDE.md：

1. 複製 `.claude/templates/CLAUDE-template.md` 到根目錄
2. 重命名為 `CLAUDE.md`
3. 填入專案特定資訊（專案目標、技術選型、MCP 配置）
4. 驗證所有連結有效

## 還原方式

如果拉取後發現問題，可使用備份還原：

```bash
# 備份位置會在拉取時顯示
cp -r /tmp/備份目錄/.claude .
cp /tmp/備份目錄/FLUTTER.md .
```

## 注意事項

- 自動備份當前配置和專案模板到臨時目錄
- 拉取會完全替換本地 .claude 和 FLUTTER.md 檔案
- 不會覆蓋根目錄 CLAUDE.md（專案特定配置）
- 拉取後建議檢查 settings.local.json 是否需要調整
- 拉取後建議重啟 Claude Code Session
