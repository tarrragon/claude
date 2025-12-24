# 🚀 代理人分派錯誤恢復 - 快速參考卡片

## ⚡ 3 步驟快速恢復

### 1️⃣ 識別錯誤

**Hook 返回錯誤訊息格式**：

```text
❌ 代理人分派錯誤：
任務類型：Hook 開發
當前代理人：parsley-flutter-developer
正確代理人：basil-hook-architect  ← 找這一行
```

### 2️⃣ 找正確代理人

**關鍵欄位**：`正確代理人：XXX`

### 3️⃣ 重新分派

```python
Task(
    subagent_type="basil-hook-architect",  # 使用正確代理人
    description="開發 Hook 腳本",
    prompt="[原始 prompt]"
)
```

---

## 📋 錯誤訊息範例

### Hook 開發錯誤

```text
❌ 代理人分派錯誤：
任務類型：Hook 開發
當前代理人：parsley-flutter-developer
正確代理人：basil-hook-architect
```

**處理**：改用 `basil-hook-architect`

### 文件整合錯誤

```text
❌ 代理人分派錯誤：
任務類型：文件整合
當前代理人：parsley-flutter-developer
正確代理人：thyme-documentation-integrator
```

**處理**：改用 `thyme-documentation-integrator`

### Phase 4 重構錯誤

```text
❌ 代理人分派錯誤：
任務類型：Phase 4 重構
當前代理人：parsley-flutter-developer
正確代理人：cinnamon-refactor-owl
```

**處理**：改用 `cinnamon-refactor-owl`

---

## 🔍 判斷是否需要重試

### ✅ 需要重試

- 錯誤訊息包含「**代理人分派錯誤**」
- 錯誤訊息包含「**正確代理人：**」

### ❌ 不需要重試

- 其他錯誤（缺少參考文件、測試失敗等）
- 無法解析正確代理人
- 已達最大重試次數（預設 1 次）

---

## 🛠 工具指令

### 查看糾正歷史

```bash
# 查看最近 10 筆
python .claude/hooks/agent_dispatch_recovery.py history 10
```

### 查看統計資訊

```bash
# 查看統計
python .claude/hooks/agent_dispatch_recovery.py stats
```

---

## ⚠️ 常見誤判處理

### Phase 4 重構包含「Hook」關鍵字

**錯誤 prompt**：
```text
"v0.12.N Phase 4: 代理人分派檢查 Hook 重構評估"
```

**Hook 誤判為**：Hook 開發（錯誤）

**正確處理**：
```text
# 選項 A: 移除關鍵字
"v0.12.N Phase 4: 代理人分派檢查功能重構評估"

# 選項 B: 加前綴
"[Phase 4 重構] v0.12.N: 代理人分派檢查 Hook 重構評估"
```

---

## 📊 代理人對照表

| 任務類型 | 正確代理人 |
|---------|-----------|
| Hook 開發 | basil-hook-architect |
| 文件整合 | thyme-documentation-integrator |
| 程式碼格式化 | mint-format-specialist |
| Phase 1 功能設計 | lavender-interface-designer |
| Phase 2 測試設計 | sage-test-architect |
| Phase 3a 策略規劃 | pepper-test-implementer |
| Phase 3b Flutter 實作 | parsley-flutter-developer |
| Phase 4 重構執行 | cinnamon-refactor-owl |

---

## 🚨 無限循環防護

### 內建保護

- **最大重試次數**：1 次（預設）
- **解析失敗停止**：無法解析時立即停止
- **非分派錯誤停止**：其他錯誤不觸發重試

### 手動檢查

記錄已嘗試的代理人列表，避免 A → B → A 循環。

---

## 🔧 Hook 模式切換（v0.12.N.10+）

### 切換模式

**環境變數（臨時）**：
```bash
export HOOK_MODE=warning   # 警告模式
export HOOK_MODE=strict    # 嚴格模式（預設）
```

**配置檔案（持久）**：
```json
// .claude/hook-config.json
{
  "agent_dispatch_check": {
    "mode": "warning"
  }
}
```

### 模式說明

| 模式 | 行為 | 適用場景 |
|------|------|---------|
| **strict**（預設） | 阻擋執行 | 正式開發 |
| **warning** | 警告 + 允許執行 | 開發測試 |

### 查看警告記錄

```bash
# 查看所有警告
cat .claude/hook-logs/agent-dispatch-warnings.jsonl

# 最近 10 筆
tail -n 10 .claude/hook-logs/agent-dispatch-warnings.jsonl
```

---

## 📚 完整文件

**詳細指南**：`docs/agent-dispatch-auto-retry-guide.md`
**工具模組**：`.claude/hooks/agent_dispatch_recovery.py`
**測試套件**：`.claude/hooks/tests/test_error_recovery.py`
**配置範例**：`.claude/hook-config.json.example`

---

**版本**：v0.12.N.10+
**最後更新**：2025-10-18
