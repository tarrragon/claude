# 版本發布檢查清單

## 版本資訊

- **版本號**: v0.XX.X
- **UseCase**: UC-XX
- **發布日期**: YYYY-MM-DD
- **前置版本**: v0.XX.X

---

## 發布前檢查

### Phase 工作日誌驗證

- [ ] Phase 0 完成並標記為 ✅
- [ ] Phase 1 完成並標記為 ✅
- [ ] Phase 2 完成並標記為 ✅
- [ ] Phase 3a 完成並標記為 ✅
- [ ] Phase 3b 完成並標記為 ✅
- [ ] Phase 4 完成並標記為 ✅
- [ ] 所有工作日誌檔案位置正確

**相關檔案**:
- `docs/work-logs/v{VERSION}/v{VERSION}-main.md`
- `docs/work-logs/v0.XX.1-phase1-*.md`
- `docs/work-logs/v0.XX.2-phase2-*.md`
- `docs/work-logs/v0.XX.3-phase3a-*.md`
- `docs/work-logs/v0.XX.4-phase3b-*.md`
- `docs/work-logs/v0.XX.8-phase4-*.md`

### 技術債務驗證

- [ ] 所有技術債務已分類
- [ ] TD 都有指定目標版本
- [ ] `docs/todolist.yaml` 的「技術債務追蹤」區塊已更新
- [ ] 沒有遺留的未分類 TD

**技術債務狀態**:
| Ticket ID | 描述 | 目標版本 | 狀態 |
|-----------|------|---------|------|
|  | | | |

### 版本號同步驗證

- [ ] `pubspec.yaml` 版本號正確: v0.XX.X
- [ ] 當前分支為 `feature/v0.XX`
- [ ] 工作目錄乾淨（無未提交的修改）
- [ ] 所有版本相關檔案已更新

**版本檢查**:
```bash
# 執行以下指令驗證
uv run .claude/skills/version-release/scripts/version_release.py check --version 0.XX.X
```

### 文件完整性驗證

- [ ] `docs/todolist.yaml` 存在且格式正確
- [ ] `CHANGELOG.md` 存在且格式正確
- [ ] `pubspec.yaml` 存在且版本號正確
- [ ] 所有主要工作日誌檔案存在

---

## 文件更新

### CHANGELOG 更新

- [ ] 新增版本區塊: `## [0.XX.X] - YYYY-MM-DD`
- [ ] 包含 Added 區塊（新增功能）
- [ ] 包含 Changed 區塊（變更項目）
- [ ] 包含 Fixed 區塊（修復項目）
- [ ] 格式符合 Keep a Changelog 標準

**預期格式**:
```markdown
## [0.XX.X] - YYYY-MM-DD

**✅ UC-XX 功能名稱 - TDD 四階段完成**

### Added
- 功能項目 1
- 功能項目 2

### Changed
- 變更項目 1

### Fixed
- 修復項目 1
```

### Todolist 更新

- [ ] 版本系列標記為 ✅ 已完成
- [ ] 版本狀態表格已更新
- [ ] 技術債務追蹤區塊已更新

**預期變更**:
```markdown
| **v0.XX.x** | UC-XX | 功能描述 | ✅ 已完成 |
```

### Pubspec.yaml 驗證

- [ ] 版本號行存在: `version: 0.XX.X`
- [ ] 版本號與目標版本一致
- [ ] 無格式錯誤

---

## Git 操作

### 分支驗證

- [ ] 當前分支: `feature/v0.XX`
- [ ] main 分支存在並可訪問
- [ ] 遠端 origin 存在並可推送

### 合併準備

- [ ] 所有本地變更已提交
- [ ] 沒有衝突檔案
- [ ] 準備好進行 --no-ff 合併

### 發布操作步驟

**自動執行步驟** (由工具自動完成):

1. ✅ 提交檔案變更
   ```bash
   git add docs/todolist.yaml CHANGELOG.md
   git commit -m "docs: 版本 0.XX.X 發布準備"
   ```

2. ✅ 切換到 main 分支
   ```bash
   git checkout main
   ```

3. ✅ 拉取最新 main
   ```bash
   git pull origin main
   ```

4. ✅ 合併 feature 分支（保留合併記錄）
   ```bash
   git merge feature/v0.XX --no-ff -m "Merge v0.XX"
   ```

5. ✅ 建立 Tag
   ```bash
   git tag -a v0.XX.X-final -m "Release v0.XX.X"
   ```

6. ✅ 推送到遠端
   ```bash
   git push origin main
   git push origin v0.XX.X-final
   ```

7. ✅ 清理 feature 分支
   ```bash
   git branch -d feature/v0.XX
   git push origin --delete feature/v0.XX
   ```

---

## 發布命令

### 預覽模式（推薦先執行）

```bash
# 只執行檢查
uv run .claude/skills/version-release/scripts/version_release.py check

# 預覽完整發布流程
uv run .claude/skills/version-release/scripts/version_release.py release --dry-run
```

### 實際發布

```bash
# 自動偵測版本並發布
uv run .claude/skills/version-release/scripts/version_release.py release

# 指定版本並發布
uv run .claude/skills/version-release/scripts/version_release.py release --version 0.XX.X
```

---

## 發布驗證

### 發布完成後驗證

- [ ] ✅ 命令執行成功（無錯誤）
- [ ] ✅ 檔案變更已提交
- [ ] ✅ main 分支已更新
- [ ] ✅ Tag 已建立: `v0.XX.X-final`
- [ ] ✅ feature 分支已清理

### Git 狀態驗證

```bash
# 驗證 main 分支已更新
git log --oneline -5 main

# 驗證 Tag 已建立
git tag -l | grep v0.XX

# 驗證分支已清理
git branch -a | grep feature/v0.XX
```

### 遠端驗證

- [ ] main 分支已推送到 origin
- [ ] Tag 已推送到 origin
- [ ] GitHub 上可以看到最新提交
- [ ] GitHub Release 可見（如已配置自動建立）

---

## 後續操作

### 版本發布後

- [ ] 驗證 GitHub 上的版本記錄
- [ ] 如需要，手動建立 GitHub Release
- [ ] 發送版本公告（如適用）
- [ ] 更新相關文件（如產品文件）

### 下一個版本準備

- [ ] 決定下一個版本號和 UseCase
- [ ] 建立新的 feature 分支: `feature/v0.XX`
- [ ] 建立主工作日誌: `v{VERSION}-main.md`
- [ ] 規劃 Phase 1 任務

---

## 常見問題和解決方案

### Q: 如何修復版本號不匹配的問題？

```bash
# 1. 更新 pubspec.yaml
version: 0.XX.X

# 2. 重新執行檢查
uv run .claude/skills/version-release/scripts/version_release.py check
```

### Q: 如何修復 Phase 未完成的警告？

```bash
# 1. 檢查工作日誌內容
cat docs/work-logs/v0.XX.X-phaseX.md

# 2. 確認 Phase 標記為 ✅ 完成
# 3. 重新執行檢查
```

### Q: 如何回滾發布？

```bash
# 1. 刪除本地 Tag
git tag -d v0.XX.X-final

# 2. 刪除遠端 Tag
git push origin :refs/tags/v0.XX.X-final

# 3. 重置 main 分支（如需要）
git reset --hard <previous-commit>
```

---

## 檢查清單使用提示

1. **版本規劃階段**: 在 UC 開發前複製此清單並填入版本號
2. **開發執行階段**: 定期檢查 Phase 進度
3. **發布前檢查**: 在執行發布命令前完成所有項目
4. **發布執行**: 按照「發布命令」部分執行
5. **發布驗證**: 發布完成後驗證所有項目

---

**檢查清單版本**: v1.0
**建立日期**: 2026-01-06
**維護者**: rosemary-project-manager
