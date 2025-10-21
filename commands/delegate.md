# Claude 指令：Delegate

此命令用於TMux面板協作 - 從面板0分派工作給面板2的Claude實例，提升開發效率。

## 使用方法

要分派任務給面板2，輸入：

```
/delegate <任務類型> [參數...]
```

## 🤝 系統指令

你是一名 **TMux面板協作協調員**，負責將工作智慧分派給不同面板的Claude實例。

## 🚀 協作指令

### 初始化協作環境
```bash
# 初始化面板2的Claude協作環境
./scripts/tmux-collaboration.sh init
```

### 分派任務給面板2

#### 程式碼審查任務
```bash
# 分派程式碼審查工作
./scripts/tmux-collaboration.sh code-review "檔案路徑" "審查重點"
```

#### 測試分析任務
```bash  
# 分派測試分析工作
./scripts/tmux-collaboration.sh test-analysis "測試檔案" "分析類型"
```

#### 文件撰寫任務
```bash
# 分派文件撰寫工作
./scripts/tmux-collaboration.sh documentation "文件類型" "目標檔案"
```

#### 重構任務
```bash
# 分派重構工作
./scripts/tmux-collaboration.sh refactoring "目標程式碼" "重構目標"
```

#### 自定義任務
```bash
# 分派自定義任務
./scripts/tmux-collaboration.sh custom "任務描述" "額外背景"
```

## 📋 任務類型詳解

### 1. 程式碼審查 (code-review)
**適用情境**：
- 新功能開發完成，需要專業審查
- 重要檔案修改，需要第二雙眼睛檢查
- 準備提交 PR 前的最後檢查

**範例**：
```bash
./scripts/tmux-collaboration.sh code-review "src/background/background.js" "安全性和效能"
```

### 2. 測試分析 (test-analysis)
**適用情境**：
- 測試覆蓋率分析
- 測試案例品質評估
- 測試策略規劃

**範例**：
```bash
./scripts/tmux-collaboration.sh test-analysis "tests/unit/error-handling/" "覆蓋率和品質分析"
```

### 3. 文件撰寫 (documentation)
**適用情境**：
- API 文件撰寫
- README 更新
- 技術規格文件

**範例**：
```bash
./scripts/tmux-collaboration.sh documentation "API文件" "src/api/chrome-extension.js"
```

### 4. 重構任務 (refactoring)
**適用情境**：
- 程式碼結構改善
- 效能優化
- 可讀性提升

**範例**：
```bash
./scripts/tmux-collaboration.sh refactoring "src/utils/data-processor.js" "提升可讀性和模組化"
```

### 5. 自定義任務 (custom)
**適用情境**：
- 特殊需求分析
- 技術研究
- 問題排查

**範例**：
```bash
./scripts/tmux-collaboration.sh custom "分析測試失敗的根本原因" "重點關注 error-recovery-strategies.test.js"
```

## 🖥️ 面板分工說明

### 面板0（主線程）
- 主要開發工作
- 任務分派和協調
- 最終整合和決策

### 面板2（協作執行）
- 接受分派的專門任務
- 獨立分析和處理
- 提供專業建議和結果

### 面板4（監控區）
- 顯示協作狀態
- 追蹤任務進度
- 協作結果摘要

## 📊 協作狀態管理

### 檢查協作狀態
```bash
./scripts/tmux-collaboration.sh status
```

### 清理協作環境
```bash
./scripts/tmux-collaboration.sh cleanup
```

## 🚀 使用流程

### 1. 準備階段
```bash
# 自動初始化協作環境 (會自動偵測並啟動面板2的Claude)
./scripts/tmux-collaboration.sh init

# 系統會自動：
# 1. 檢查面板2是否已運行Claude Code
# 2. 如果沒有，詢問是否自動啟動 (預設10秒後自動同意)
# 3. 自動啟動面板2的Claude Code
# 4. 設定協作環境和狀態顯示
```

### 2. 分派任務
```bash
# 從面板0分派具體任務給面板2
./scripts/tmux-collaboration.sh code-review "src/main.js" "效能和安全性"
```

### 3. 監控進度
- 面板4會顯示協作狀態
- 面板2會接收任務並開始處理
- 面板0可以繼續其他開發工作

### 4. 整合結果
- 面板2完成任務後，在面板0整合結果
- 更新TODO和工作日誌
- 繼續下一輪協作或正常開發

## 💡 協作最佳實踐

### 任務分派原則
- **專業分工**：讓各面板專注擅長的工作
- **並行處理**：同時處理不同類型的任務
- **結果整合**：統一收集和應用協作成果

### 效率提升策略
- **批次處理**：將相似任務一起分派
- **優先級管理**：重要任務優先分派
- **狀態追蹤**：定期檢查協作進度

### 協作溝通
- **清楚描述**：任務描述要具體明確
- **背景資訊**：提供充足的上下文
- **結果確認**：驗證協作成果品質

## ⚠️ 注意事項

1. **面板2必須啟動Claude**：協作前確保面板2運行Claude Code
2. **任務相依性**：避免分派有強相依性的任務
3. **資源管理**：合理分配各面板的工作負荷
4. **結果同步**：及時將協作結果同步到主線開發