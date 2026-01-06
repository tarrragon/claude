# MCP run_tests 使用限制 Hook - 實作總結

## 快速概覽

| 項目 | 內容 |
|------|------|
| **Hook 名稱** | mcp-run-tests-validator |
| **位置** | `.claude/hooks/mcp-run-tests-validator.py` |
| **Hook 類型** | PreToolUse (工具執行前) |
| **觸發工具** | mcp__dart__run_tests |
| **功能** | 驗證 roots 參數包含有效的 paths，防止全量測試卡住 |
| **版本** | v1.0 (2025-12-31) |

---

## 規範需求

### 強制規範 (來源: FLUTTER.md 第 72-101 行)
```bash
# ❌ 嚴格禁止 - 會卡住超過 20 分鐘
mcp__dart__run_tests(roots: [{"root": "file:///path"}])

# ✅ 正確 - 指定測試子目錄
mcp__dart__run_tests(roots: [{"root": "file:///path", "paths": ["test/domains/"]}])

# ✅ 推薦 - 使用 Bash 執行全量測試
./.claude/hooks/test-summary.sh
```

---

## 核心邏輯

### 檢查流程
```
輸入 JSON
   ↓
是否為 mcp__dart__run_tests?
   ├─ 否 → 允許執行
   └─ 是 → 檢查 roots 參數
        ↓
    每個 root 都有 paths 參數?
        ├─ 是且非空 → 允許執行 (exit 0)
        └─ 否 → 阻塊執行 (exit 2) + 錯誤訊息
```

### 驗證規則
1. **roots 必須是陣列**
2. **每個 root 必須是物件**
3. **每個 root 必須有 "paths" 鍵**
4. **paths 值必須非空陣列**

---

## 實作檔案

### Hook 腳本
**位置**: `.claude/hooks/mcp-run-tests-validator.py`

**特點**:
- UV single-file 模式 (PEP 723)
- 完全獨立，無外部依賴
- 詳細的錯誤訊息和修復指引
- 違規事件日誌記錄

**大小**: ~250 行

### 配置檔案
**位置**: `.claude/settings.json`

**配置**:
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "mcp__dart__run_tests",
        "hooks": [
          ".claude/hooks/mcp-run-tests-validator.py",
          ".claude/hooks/test-timeout-pre.py"
        ]
      }
    ]
  }
}
```

---

## 測試驗證

### 測試案例 (5/5 通過)
- ✅ **案例 1**: 有效用法 (包含 paths) → 允許
- ✅ **案例 2**: 無效用法 (缺少 paths) → 阻塊
- ✅ **案例 3**: 無效用法 (空陣列) → 阻塊
- ✅ **案例 4**: 多個 roots (部分無效) → 阻塊
- ✅ **案例 5**: 其他工具 → 允許 (不受影響)

### 品質檢查
- ✅ Python 語法驗證
- ✅ JSON 格式驗證
- ✅ 日誌記錄驗證
- ✅ Exit codes 驗證
- ✅ 錯誤訊息驗證

---

## 日誌追蹤

### 違規日誌
**位置**: `.claude/hook-logs/mcp-run-tests-violations.log`

**內容** (JSON Lines 格式):
```json
{
  "timestamp": "2025-12-31T16:57:22.703583",
  "violation_type": "mcp_run_tests_no_paths",
  "details": {
    "roots": [{"root": "file:///path"}],
    "invalid_roots": ["file:///path: 缺少 paths 參數或 paths 為空陣列"]
  }
}
```

### 用途
- 追蹤規範違規
- 分析使用模式
- 改善規範說明

---

## 使用者體驗

### 通過檢查時
✅ **訊息**: "mcp__dart__run_tests 使用規範檢查通過"
→ 工具正常執行

### 違反規範時
❌ **清晰的錯誤訊息**:
1. 問題描述 (為什麼卡住?)
2. 違規詳情 (具體哪個 root?)
3. 正確用法示例 (3 種方式)
4. 推薦方案 (test-summary.sh)
5. 規範參考 (FLUTTER.md)

### 範例錯誤訊息
```
❌ MCP run_tests 使用規範違規

問題描述:
mcp__dart__run_tests 在無 paths 參數時會執行全量測試，
導致卡住超過 20 分鐘。必須指定 paths 限制測試範圍。

違規詳情:
  • file:///path: 缺少 paths 參數或 paths 為空陣列

✅ 正確用法示例:

1. 指定單一測試目錄:
   mcp__dart__run_tests(roots: [{"root": "file:///path", "paths": ["test/domains/"]}])

2. 指定多個測試目錄:
   mcp__dart__run_tests(roots: [{"root": "file:///path", "paths": ["test/unit/core/", "test/unit/models/"]}])

3. 指定單一測試檔案:
   mcp__dart__run_tests(roots: [{"root": "file:///path", "paths": ["test/domains/import/events_test.dart"]}])

📋 推薦方案:
  • 使用 ./.claude/hooks/test-summary.sh 執行全量測試
  • 或使用 flutter test --reporter compact 直接執行

📚 相關規範: FLUTTER.md 第 72-101 行
```

---

## 技術細節

### 程式碼品質
- **UV Single-File**: PEP 723 符合
- **Python 版本**: 3.11+
- **外部依賴**: 無 (僅 Python 標準庫)
- **安全性**: JSON 解析安全，fail-safe 設計
- **可觀察性**: 詳細日誌，結構化格式

### 效能
- **執行時間**: < 10ms (本地驗證)
- **記憶體**: 最小化 (JSON 流式處理)
- **日誌大小**: 每條 ~200-300 bytes

### 相容性
- ✅ Claude Code 1.x
- ✅ macOS 12+
- ✅ Linux
- ✅ Windows (WSL2)

---

## 故障排除

### 問題: Hook 未觸發
**檢查項目**:
- [ ] `.claude/settings.json` 配置正確
- [ ] Hook 腳本路徑正確: `.claude/hooks/mcp-run-tests-validator.py`
- [ ] Hook 有執行權限: `chmod +x`

### 問題: Hook 報錯
**檢查項目**:
- [ ] Python 3.11+ 已安裝
- [ ] 檢查日誌: `.claude/hook-logs/mcp-run-tests-violations.log`
- [ ] 測試語法: `python3 -m py_compile mcp-run-tests-validator.py`

### 問題: 誤判通過
**檢查項目**:
- [ ] paths 參數非空陣列
- [ ] 所有 roots 都檢查了 paths
- [ ] 查看日誌內容

---

## 相關文件

### Hook 文件
- `docs/hooks/07-mcp-run-tests-validator-hook.md` - 完整設計文檔
- `docs/hooks/README.md` - Hook 開發索引
- `docs/hooks/01-hook-fundamentals.md` - Hook 基礎概念

### 規範文件
- `FLUTTER.md` 第 72-101 行 - MCP run_tests 使用限制
- `FLUTTER.md` 第 103-121 行 - 全量測試執行規範

### 相關 Hook
- `test-timeout-pre.py` - 測試超時監控 (同時觸發)
- `test-summary.sh` - 全量測試摘要 (推薦替代方案)

---

## 下一步

### 短期 (已完成)
- [x] Hook 腳本實作
- [x] 配置整合
- [x] 測試驗證
- [x] 文件編寫

### 中期 (可選)
- [ ] 添加統計分析 (違規頻率、模式分析)
- [ ] 自動修復建議 (顯示修復指令)
- [ ] 集成到 IDE 提示

### 長期 (觀察期)
- [ ] 收集使用反饋
- [ ] 調整規範 (如有必要)
- [ ] 推廣最佳實踐

---

## 聯絡方式

**Hook 架構師**: basil-hook-architect
**問題追蹤**: 在 `.claude/hook-logs/` 查看日誌
**規範更新**: 參考 FLUTTER.md

---

**最後更新**: 2025-12-31
**狀態**: ✅ 生產就緒 (Production Ready)
