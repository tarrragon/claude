# Claude 指令：Commit-As-Prompt

此命令可協助您建立格式良好的提交。

> ⚠️ **重要**: 此指令是 Claude Code 內建功能，在繼續對話或恢復 session 時可能不可用。若指令無效，請使用替代方案：`./scripts/check-work-log.sh` + 標準 `git commit` 流程。

## 使用方法

要建立提交，只需輸入：

```
/commit-as-prompt
```

## ⚠️ 指令不可用時的替代方案

```bash
# 手動執行標準提交流程
./scripts/check-work-log.sh        # 1. 工作日誌檢查
git add <files>                    # 2. 暫存變更
git commit -m "$(cat <<'EOF'       # 3. 提交 (WHAT/WHY/HOW格式)
<type>(<scope>): <description>

## WHAT
具體動作與對象

## WHY  
業務需求、技術債務背景、問題根因

## HOW
實作策略、相容性考量、驗證方式

🤖 Generated with [Claude Code](https://claude.ai/code)
Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

## 📝 背景 (Background)

本提示用於將 **Git 提交記錄** 轉換為供其他 AI 參考的問題上下文 Prompt，幫助其在程式碼審查、技術債評估或文件編寫時快速了解變更的 **目標 (WHAT)／動機 (WHY)／手段 (HOW)**。

---

## 🗣️ System

你是一名 **Commit-to-Prompt Engineer**。
你的職責：

1. 分析待提交的內容，以建立清晰的問題上下文為前提，精心挑選相關的文件聚合，拆分成多次提交
2. 為提交寫標題與內文，抽取 WHAT／WHY／HOW。
3. 產生遵循「Prompt 範本」的上下文，不添加任何多餘解釋或格式。

---

### 🏷️ Commit 類型與標題前綴

- **Context Prompt 提交**：標題請以 `prompt:` 開頭，例如 `prompt(dark-mode): 場景上下文`
- 適用於需被轉換為上下文 Prompt 的提交。
- **常規功能/修復提交**：沿用 Conventional Commits 前綴，如 `feat:`、`fix:`、`docs:` 等。
- 這些提交不進入 Prompt 轉換流程，但仍需遵守 WHAT/WHY/HOW 規範。

在同一分支工作時，若同時存在兩類提交，應分別提交，避免混合。

---

## 🤖 Assistant（執行步驟，必須依序執行）

以下步驟幫助你快速整理變更並產出符合 WHAT / WHY / HOW 規範的提交：

0. **三層文件管理自動化檢查系統** ⭐ 強化版本

```bash
# 1. 執行版號同步檢查 (確保 package.json 與實際開發版本同步)
./scripts/check-version-sync.sh

# 2. 執行工作日誌檢查 (小版本層級)
./scripts/check-work-log.sh

# 3. 執行下一步目標檢查 (中版本層級)  
./scripts/check-next-objectives.sh

# 4. 執行版本推進檢查 (整合決策)
./scripts/version-progression-check.sh
```

**四階段三層文件管理檢查**：
1. **版號同步檢查**: 確保 package.json 與實際開發進度同步
2. **工作日誌檢查**: 小版本層級的工作完成度檢查
3. **目標狀態檢查**: 中版本層級的 todolist.md 任務進度分析
4. **版本推進決策**: 整合分析，提供智能版本推進建議

**🤖 根據版本推進檢查結果，系統將提供對應的操作建議**：

### 狀況A: 繼續當前版本開發 (decision_code = 0)
```bash
# 當前工作尚未完成，繼續開發
./scripts/work-log-manager.sh
# 選擇選項 1: 📝 更新進行中的工作
```

### 狀況B: 小版本推進 (decision_code = 1)  
```bash
# 當前工作完成，推進到下一個小版本 (patch)
./scripts/work-log-manager.sh
# 選擇選項 2: 🆕 開始新的工作項目
# 系統會自動更新到下個 patch 版本 (如 0.10.12 → 0.10.13)
```

### 狀況C: 中版本推進 (decision_code = 2)
```bash
# 版本系列完成，推進到下一個中版本 (minor)
./scripts/work-log-manager.sh
# 選擇選項 2: 🆕 開始新的工作項目  
# 需要手動更新 package.json 到中版本 (如 0.10.12 → 0.11.0)
# 並更新 todolist.md 規劃新版本系列目標
```

### 狀況D: 完成當前工作並總結
```bash
# 當前工作項目需要完成總結
./scripts/work-log-manager.sh  
# 選擇選項 3: ✅ 完成當前工作
```

**📋 三層文件管理版本推進提醒**：
- 🎯 **版本推進智能決策**: 系統會根據工作日誌和 todolist 狀態自動建議版本推進策略
- 🔄 **三層架構同步**: 小版本工作日誌 → 中版本 todolist → 大版本用戶指令
- ⚠️ **版本號一致性**: package.json 必須與實際開發進度保持同步
- 📝 **完成狀態標記**: 工作完成必須有明確的總結和狀態標記
- 🚀 **版本推進條件**: 
  - 小版本推進 (patch): 工作完成但系列未完成
  - 中版本推進 (minor): 工作完成且系列完成
  - 大版本推進 (major): 需要用戶明確指令

1. **檢查工作區變更**

```bash
# 查看工作區與暫存區的差異 (在面板3執行Git指令)
if [[ -n "$TMUX" ]] && tmux list-panes 2>/dev/null | grep -q "^3:"; then
    tmux send-keys -t 3 "git status -s" C-m
    tmux send-keys -t 3 "git diff" C-m
    tmux send-keys -t 3 "git diff --cached" C-m
else
    git status -s
    git diff
    git diff --cached
fi
```

2. **理解並清理程式碼與檔案**

在任何自動化清理或重新命名前，**先閱讀並理解相關程式碼，確認改動不會破壞現有功能，沒有把握的程式碼請不要修改**。

- 刪除無用匯入、死程式碼

- 移除臨時日誌 / 偵錯語句（`console.log`, `debugger` 等）

- 重新命名臨時或非正式識別（如 `V2`, `TEMP`, `TEST` 等）

- 刪除臨時測試、鷹架或文檔
  如需自動修復，可執行： validate-redux --project-root 加指定路徑解決問題，例如 validate-redux --project-root ./project-directory

3. **選擇應納入本次提交的文件**

使用互動式暫存精準挑選相關變更：

```bash
# 互動式暫存 (在面板3執行Git指令)
if [[ -n "$TMUX" ]] && tmux list-panes 2>/dev/null | grep -q "^3:"; then
    echo "請切換至面板3執行: git add -p"
    echo "或指定檔案: git add <file>..."
    tmux select-pane -t 3
else
    git add -p # 按下區塊暫存
    git add <file> ... # 或按檔案暫存
fi
```

僅保留實現當前需求所需的程式碼、配置、測試、文件。
將純格式化、依賴升級或大規模重命名等雜訊變更**拆分為獨立提交**。4. **編寫提交資訊（Prompt 結構）**
對於**每個 `prompt:` 類型的提交**，其訊息正文應遵循 WHAT/WHY/HOW 結構，但不帶編號。這部分內容將用於後續的 prompt 生成。

**單一提交訊息正文格式：**

```bash
WHAT: ...
WHY: ...
HOW: ...
```

5. **面板3標準作業**

**🖥️ TMux面板分工設計**：根據開發環境配置，所有Git相關操作應在面板3執行，確保版本控制操作的集中管理和監控。

**操作方式**：
- 🔄 **自動切換模式**: 在TMux環境中，系統會自動在面板3執行Git指令
- 🖱️ **手動切換**: 若需要互動式操作 (如 `git add -p`)，系統會自動切換到面板3
- 💡 **提示導航**: 系統會顯示明確的面板切換提示和指令建議

**面板3的職責範圍**：
- Git狀態檢查 (`git status`, `git diff`)
- 檔案暫存操作 (`git add`)
- 提交執行 (`git commit`)
- 推送同步 (`git push`)
- 分支管理和版本控制相關操作

6. **推送並同步文件**

```bash
# ⚠️  提交前最後確認：確保工作日誌已更新並包含在提交中
if git diff --cached --name-only | grep -q "docs/work-logs/"; then
    echo "✅ 工作日誌已包含在提交中"
else
    if [[ -n "$TMUX" ]] && tmux list-panes 2>/dev/null | grep -q "^3:"; then
        tmux send-keys -t 3 "echo '⚠️ 工作日誌未包含，請在面板3執行: git add docs/work-logs/'" C-m
        tmux select-pane -t 3
    else
        echo "⚠️  工作日誌未包含，建議加入: git add docs/work-logs/"
    fi
fi

# 範例：提交一條 prompt 類型的變更 (在面板3執行Git指令)
if [[ -n "$TMUX" ]] && tmux list-panes 2>/dev/null | grep -q "^3:"; then
    tmux send-keys -t 3 'git commit -m "prompt(auth): 支援 OAuth2 登入" -m "WHAT: ...
WHY: ...
HOW: ..."' C-m
    tmux send-keys -t 3 "git push" C-m
else
    git commit -m "prompt(auth): 支援 OAuth2 登入" -m "WHAT: ...
WHY: ...
HOW: ..."
    git push
fi
```

7. **檢查剩餘變更並詢問用戶**

**⭐ 完整提交流程的關鍵步驟**：每次提交完成後，必須檢查工作區是否還有未提交的變更。

```bash
# 提交完成後立即檢查剩餘變更
REMAINING_CHANGES=$(git status --porcelain | wc -l)
if [ "$REMAINING_CHANGES" -gt 0 ]; then
    echo "📋 發現工作區還有 $REMAINING_CHANGES 個檔案的變更未提交："

    # 顯示剩餘變更摘要
    git status --short

    # 分類變更類型
    echo ""
    echo "📊 變更分類分析："

    # 檢查刪除的檔案
    DELETED_FILES=$(git status --porcelain | grep "^.D\|^D." | wc -l)
    if [ "$DELETED_FILES" -gt 0 ]; then
        echo "🗑️  刪除檔案: $DELETED_FILES 個"
        git status --porcelain | grep "^.D\|^D." | sed 's/^.../   - /'
    fi

    # 檢查修改的檔案
    MODIFIED_FILES=$(git status --porcelain | grep "^.M\|^M." | wc -l)
    if [ "$MODIFIED_FILES" -gt 0 ]; then
        echo "🔧 修改檔案: $MODIFIED_FILES 個"
        git status --porcelain | grep "^.M\|^M." | sed 's/^.../   - /'
    fi

    # 檢查新增的檔案
    UNTRACKED_FILES=$(git status --porcelain | grep "^??" | wc -l)
    if [ "$UNTRACKED_FILES" -gt 0 ]; then
        echo "📄 未追蹤檔案: $UNTRACKED_FILES 個"
        git status --porcelain | grep "^??" | sed 's/^.../   - /'
    fi

    echo ""
    echo "🤔 是否繼續處理剩餘變更？"
    echo "1️⃣  繼續提交所有變更 - 將所有變更打包為下一個提交"
    echo "2️⃣  分批提交 - 選擇性提交相關變更"
    echo "3️⃣  暫停檢查 - 讓用戶檢視變更內容後再決定"
    echo "4️⃣  結束 - 保留變更在工作區，完成當前提交流程"
    echo ""
    echo "💡 建議的處理方式："

    # 根據變更類型提供建議
    if [ "$DELETED_FILES" -gt 0 ] && [ "$MODIFIED_FILES" -gt 0 ]; then
        echo "   - 發現檔案刪除和程式碼修改，建議選擇 2️⃣ 分批提交"
    elif [ "$DELETED_FILES" -gt 0 ]; then
        echo "   - 發現檔案刪除，建議選擇 1️⃣ 繼續提交作為清理提交"
    elif [ "$MODIFIED_FILES" -gt 5 ]; then
        echo "   - 修改檔案較多，建議選擇 2️⃣ 分批提交避免混合主題"
    else
        echo "   - 變更數量適中，建議選擇 1️⃣ 繼續提交"
    fi

else
    echo "✅ 工作區乾淨，所有變更已提交完成"
    echo "📋 commit-as-prompt 流程執行完畢"
fi
```

**後續文件同步檢查**：

```bash
# 檢查是否需要更新其他文件記錄
if [[ -f "docs/todolist.md" ]]; then
    echo "📋 檢查 TODO 清單是否需要更新"
fi

if [[ -f "CHANGELOG.md" ]]; then
    echo "📝 檢查變更記錄是否需要更新"
fi
```

### 📂 檔案挑選原則

- 僅包含實現本需求所必需的程式碼、配置、測試、文件。
- 排除格式化、依賴升級、產生檔案等雜訊變更。
- 純重命名或大規模格式化應作為獨立提交。
- 暫存中如含多個主題，請拆分為多次提交。

### 💡 提交資訊通用原則

- **有意義的命名與描述**：提交標題應簡潔、明確，描述變更內容和目的，避免“修復 bug”“更新代碼”等模糊詞。
- **結構化與規範化**：推薦採用 Conventional Commits（如 `feat`, `fix`, `docs` 等）並包含作用域與簡短主題，正文補充細節，便於自動產生變更日誌。
- **解釋 Why 而非列舉 What**：正文重點說明動機或背景，而不僅僅是修改了哪些文件。

### 📝 WHAT / WHY / HOW 寫重點

- **WHAT（做什麼）**：一句話描述動作與對象，使用祈使動詞，不包含實現細節。例如 `Add dark theme to UI`。
- **WHY（為什麼做）**：深入闡述業務、用戶需求、架構權衡或缺陷背景，避免泛泛而談；可引用 Issue / 需求編號，如 `Fixes #1234`、`Improve a11y for dark environments`。
- **HOW（怎麼做）**：概述採用的整體策略、相容性 / 依賴、驗證方式、風險提示及業務（用戶）影響；可補充上下文依賴或前置條件；無需羅列具體文件（diff 已體現細節）。

### 🚀 高品質提交最佳實踐

1. **結構化與聚合**：一次提交聚焦單一主題；大型變更可拆分多步，每步都有獨立 WHAT/WHY/HOW。
2. **深入 WHY**：在 WHY 關聯業務目標、使用者需求或瑕疵編號；若為架構決策，簡述權衡背景。
3. **具體 HOW**：描述整體改動策略、相容性 / 依賴、驗證方式、風險提示及業務影響，而非逐條羅列文件。
4. **清晰語言與格式**：標題和正文避免模糊詞（如“調整”），使用英文祈使句；遵循 Conventional Commits。
5. **自動化與追溯**：內文引用 Issue/PR/需求編號，保持與 changelog、CI 流程連動。
6. **上下文完整性**：對 prompt: 提交，在 `<Context>` 中補充依賴或前置信息，方便 AI 理解。

7. 輸出結果必須嚴格符合以下“Prompt 範本”，除模板內容外不得輸出解釋、標題、程式碼區塊標記或空白行。

### Prompt 生成模板

此範本用於**聚合多個 `prompt:` 類型的提交**，產生最終的上下文。每個編號項（`1.`, `2.`）對應一個獨立的提交。

```
<Context>
1. [WHAT] ...
 [WHY] ...
 [HOW] ...
2. [WHAT] ...
 [WHY] ...
 [HOW] ...
</Context>
```

---

## ✅ 範例：從獨立提交到聚合提示

**第 1 步：進行兩次獨立的 `prompt:` 提交**

_提交 1:_

```bash
# 在面板3執行提交指令
if [[ -n "$TMUX" ]] && tmux list-panes 2>/dev/null | grep -q "^3:"; then
    tmux send-keys -t 3 'git commit -m "prompt(auth): 支援 OAuth2 登入" -m "WHAT: 重構認證中間件以支援 OAuth2 登入
WHY: 符合新的安全策略，允許第三方登錄，對應需求 #2345
HOW: 引入 OAuth2 授權碼流程替換 BasicAuth；向下相容舊 Token；透過單元測試驗證；需更新用戶端設定"' C-m
else
    git commit -m "prompt(auth): 支援 OAuth2 登入" -m "WHAT: 重構認證中間件以支援 OAuth2 登入
WHY: 符合新的安全策略，允許第三方登錄，對應需求 #2345
HOW: 引入 OAuth2 授權碼流程替換 BasicAuth；向下相容舊 Token；透過單元測試驗證；需更新用戶端設定"
fi
```

_提交 2:_

```bash
# 在面板3執行提交指令
if [[ -n "$TMUX" ]] && tmux list-panes 2>/dev/null | grep -q "^3:"; then
    tmux send-keys -t 3 'git commit -m "prompt(api): 移除廢棄介面" -m "WHAT: 移除廢棄 API 端點
WHY: 為 v2.0 版本做清理，減少維護成本
HOW: 下線 v1 Legacy 端點並更新 API 文件；版本標識提升至 v2；通知客戶端遷移"' C-m
else
    git commit -m "prompt(api): 移除廢棄介面" -m "WHAT: 移除廢棄 API 端點
WHY: 為 v2.0 版本做清理，減少維護成本
HOW: 下線 v1 Legacy 端點並更新 API 文件；版本標識提升至 v2；通知客戶端遷移"
fi
```

**第 2 步：工具根據這兩次提交，自動產生聚合後的 Prompt**

_產生的 Prompt 輸出:_

```text
<Context>
1. [WHAT] 重構認證中間件以支援 OAuth2 登入
 [WHY] 符合新的安全策略，允許第三方登錄，對應需求 #2345
 [HOW] 引進 OAuth2 授權碼流程取代 BasicAuth；向下相容舊 Token；透過單元測試驗證；需更新用戶端設定
2. [WHAT] 移除廢棄 API 端點
 [WHY] 為 v2.0 版本做清理，減少維護成本
 [HOW] 下線 v1 Legacy 端點並更新 API 文件；版本標識提升至 v2；通知客戶端遷移
</Context>
```

---
