# Claude 指令：Test-Progress

此命令執行帶視覺化進度條的測試流程，支援 TMux 環境下的進度顯示分離。

## 使用方法

要執行測試進度條，輸入：

```
/test-progress [模式]
```

## 🚀 系統指令

你是一名 **測試執行進度顯示專家**，負責提供視覺化的測試執行體驗。

## 📊 執行指令

執行帶進度條的測試腳本：

```bash
# 執行測試進度條腳本
./scripts/test-with-progress.sh [模式]
```

## 🎯 測試模式

### 完整測試模式（預設）
```bash
./scripts/test-with-progress.sh full
# 或
./scripts/test-with-progress.sh f
```
執行項目：
- 單元測試 (Unit Tests)
- 整合測試 (Integration Tests)  
- 程式碼檢查 (ESLint)
- 建置驗證 (Build Validation)

### 快速測試模式
```bash
./scripts/test-with-progress.sh quick
# 或
./scripts/test-with-progress.sh q
```
執行項目：
- 程式碼檢查 (ESLint)
- 建置驗證 (Build Validation)

## 🖥️ 顯示行為

### TMux 環境中
- **主畫面**：顯示測試執行狀態和錯誤輸出
- **面板4 (監控區)**：顯示彩色進度條和階段資訊
- **自動檢測**：如果面板4不存在，進度條顯示在主畫面

### 非 TMux 環境
- **主畫面**：同時顯示測試狀態和進度條
- **一體化顯示**：所有資訊集中在同一終端

## 🎨 進度條特色

- **視覺化進度**：50字符寬度的彩色進度條
- **階段指示**：清楚顯示當前執行的測試階段
- **即時更新**：每個測試階段的子進度即時顯示
- **結果統計**：錯誤和警告數量統計
- **彩色輸出**：綠色成功、紅色錯誤、黃色警告

## 📈 進度條格式

```
📊 測試執行進度
[████████████████████████████░░░░░░░░░░] 70%
階段 2/4: 整合測試 (Integration Tests)
```

## 🚨 錯誤處理

- **測試失敗**：顯示錯誤輸出的最後10行
- **警告處理**：ESLint 警告不中斷流程
- **建置錯誤**：顯示建置失敗的詳細資訊
- **最終統計**：提供完整的錯誤和警告計數

## 💡 使用建議

### 日常開發
```bash
# 快速檢查程式碼品質和建置
/test-progress quick
```

### 提交前檢查
```bash
# 完整測試確保程式碼品質
/test-progress full
```

### 持續整合
```bash
# 在 CI/CD 流程中使用
./scripts/test-with-progress.sh full
```

## 📋 輸出範例

### 成功情況
```
[INFO] 偵測到 TMux 環境，進度條將顯示在面板4 (監控區)
[START] 開始執行 單元測試 (Unit Tests)...
[SUCCESS] 單元測試 (Unit Tests) 完成
[START] 開始執行 整合測試 (Integration Tests)...
[SUCCESS] 整合測試 (Integration Tests) 完成
========================================
✅ 所有測試階段完成
========================================
```

### 錯誤情況
```
[ERROR] 單元測試 (Unit Tests) 失敗
錯誤輸出：
  FAIL tests/unit/example.test.js
    Example test suite
      ✕ should pass (5ms)
========================================
❌ 發現 1 個錯誤
========================================
```

## ⚙️ 技術特色

- **環境自適應**：自動偵測 TMux 環境
- **相容性優良**：使用 awk 而非 bc 進行數學運算
- **無外部依賴**：僅使用系統內建指令
- **錯誤恢復**：個別測試失敗不影響其他測試執行
- **白名單友善**：所有指令都已加入 Claude Code 白名單