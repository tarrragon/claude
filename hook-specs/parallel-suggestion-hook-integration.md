# Parallel Suggestion Hook 整合指南

## 文件位置

### Hook 實作
```
.claude/hooks/parallel-suggestion-hook.py
```

### 設計文檔
```
.claude/hook-specs/parallel-suggestion-hook-design.md
```

### 測試報告
```
.claude/hook-specs/parallel-suggestion-hook-test-report.md
```

### 日誌位置
```
.claude/hook-logs/parallel-suggestion/
├── parallel-suggestion.log       # 詳細執行日誌
└── analysis-{YYYYMMDD}.log       # 分析統計日誌
```

---

## 配置說明

### settings.local.json 配置（待添加）

Hook 應在 `.claude/settings.local.json` 中配置如下：

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "name": "parallel-suggestion-hook",
        "description": "並行任務分析和建議",
        "type": "command",
        "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/parallel-suggestion-hook.py",
        "timeout": 5000,
        "enabled": true,
        "order": 10
      }
    ]
  }
}
```

#### 配置說明
- **name**: Hook 的唯一識別符
- **description**: Hook 的簡短描述
- **type**: "command" - 執行外部命令
- **command**: Hook 腳本的絕對路徑（使用 $CLAUDE_PROJECT_DIR）
- **timeout**: 執行超時（毫秒），建議 5000ms
- **enabled**: 是否啟用此 Hook
- **order**: 執行順序（較小的值先執行）

---

## 執行權限設置

Hook 需要可執行權限：

```bash
chmod +x .claude/hooks/parallel-suggestion-hook.py
```

驗證：
```bash
ls -la .claude/hooks/parallel-suggestion-hook.py
# 應該顯示: -rwxr-xr-x
```

---

## 依賴項檢查

### Python 版本要求
- 最低: Python 3.11
- 推薦: Python 3.12+

### 依賴模組
本 Hook 只使用 Python 標準庫，無外部依賴：
- sys
- json
- logging
- re
- pathlib
- datetime
- typing

### 環境驗證
```bash
python3 --version  # 應為 3.11+
python3 -m py_compile .claude/hooks/parallel-suggestion-hook.py  # 語法檢查
```

---

## 使用說明

### 自動觸發
Hook 在用戶提交以下關鍵字時自動執行：
- 繼續、繼續執行、繼續任務鏈
- 下一個、執行下一個
- 任務鏈、子任務
- 接續、接著做、批量

### 手動測試

#### 基本測試
```bash
echo '{"prompt":"繼續執行任務鏈"}' | ./.claude/hooks/parallel-suggestion-hook.py
```

#### 調試模式
```bash
HOOK_DEBUG=true echo '{"prompt":"繼續"}' | ./.claude/hooks/parallel-suggestion-hook.py
```

#### 檢查日誌
```bash
# 查看詳細日誌
tail -f .claude/hook-logs/parallel-suggestion/parallel-suggestion.log

# 查看分析結果
cat .claude/hook-logs/parallel-suggestion/analysis-$(date +%Y%m%d).log
```

---

## Hook 行為說明

### 觸發條件
1. Hook 事件: UserPromptSubmit（用戶提交 Prompt 時）
2. 關鍵字匹配: 識別繼續相關的關鍵字

### 執行流程
1. **識別關鍵字**: 檢查 Prompt 是否包含繼續相關詞彙
2. **掃描 Ticket**: 讀取所有 v0.31.0 版本的 Ticket 檔案
3. **分析任務鏈**: 找到最近完成的任務鏈根
4. **查詢待處理**: 在該鏈中找待處理子任務
5. **並行檢查**: 分析是否可並行執行
6. **生成建議**: 若有並行機會，輸出建議報告

### 輸出行為
- **有並行任務**: 在 additionalContext 中輸出建議報告
- **無並行任務**: 返回空輸出（不干擾用戶）
- **錯誤發生**: 輸出錯誤訊息和日誌位置

---

## 故障排除

### Hook 不執行

**症狀**: Hook 沒有運行

**排查步驟**:
1. 檢查配置: `.claude/settings.local.json` 中是否啟用
2. 檢查權限: `ls -la .claude/hooks/parallel-suggestion-hook.py`
3. 檢查日誌: `.claude/hook-logs/parallel-suggestion/`

### 性能問題

**症狀**: Hook 執行緩慢（>1 秒）

**排查步驟**:
1. 檢查 Ticket 數量: 應該 < 500 個
2. 查看日誌: 哪個步驟耗時長
3. 檢查磁盤: 確保 docs/work-logs 目錄可訪問

### 無法識別關鍵字

**症狀**: 明確的繼續請求未被識別

**排查步驟**:
1. 檢查關鍵字清單: CONTINUATION_KEYWORDS
2. 查看日誌: `grep "識別" parallel-suggestion.log`
3. 補充缺失的關鍵字（需修改源代碼）

### 並行分析不準確

**症狀**: 應該並行但被標記為有依賴

**排查步驟**:
1. 檢查 blockedBy 欄位: 是否正確
2. 檢查檔案列表: where_files/where_layer 是否完整
3. 查看日誌: 具體的檢查結果

---

## 監控和維護

### 定期檢查項目
- [ ] 日誌大小: `.claude/hook-logs/parallel-suggestion/` < 100MB
- [ ] Ticket 掃描時間: < 200ms
- [ ] Hook 執行時間: < 500ms
- [ ] 錯誤日誌: 是否有異常記錄

### 日誌輪換
建議每月清理舊日誌：
```bash
# 查看日誌大小
du -sh .claude/hook-logs/parallel-suggestion/

# 清理 30 天前的日誌
find .claude/hook-logs/parallel-suggestion/ -name "*.log" -mtime +30 -delete
```

### 版本更新
當 Hook 有更新時：
1. 備份現有 Hook: `cp parallel-suggestion-hook.py parallel-suggestion-hook.py.bak`
2. 替換新版本
3. 檢查語法: `python3 -m py_compile parallel-suggestion-hook.py`
4. 清除日誌（可選）
5. 測試新版本

---

## 與其他系統的整合

### 與決策樹的整合
- 支援決策樹的「第四層半：並行化評估」
- 用戶的「繼續請求」會觸發並行分析
- 建議報告引導主線程進行並行派發

### 與票務系統的整合
- 掃描 `.claude/tickets/` 和 `docs/work-logs/*/tickets/`
- 識別 chain 結構中的任務鏈關係
- 檢查 blockedBy 和 where_files 欄位

### 與 Hook 系統的整合
- 作為 UserPromptSubmit Hook 執行
- 使用標準 hookSpecificOutput 格式
- 日誌記錄到標準位置

---

## 安全性考量

### 資料隱私
- Hook 只讀取 Ticket 檔案，不修改
- 不訪問用戶代碼或敏感資料
- 日誌不包含機密信息

### 執行隔離
- Hook 在獨立進程中執行
- 無法修改系統狀態
- 錯誤被隔離處理

### 性能隔離
- 長時間執行的操作有 timeout 保護
- 記憶體使用受限（~80MB）
- 不會導致系統卡頓

---

## 性能優化建議

### 短期優化
1. 緩存 Ticket 掃描結果（同一 session 內）
2. 只掃描當前版本的 Ticket
3. 並行讀取多個 Ticket 檔案

### 長期優化
1. 建立 Ticket 索引（加速搜尋）
2. 增量更新機制（只掃描新 Ticket）
3. 預計算任務鏈關係圖

---

## 擴展開發指南

### 添加新關鍵字
修改 Hook 中的 CONTINUATION_KEYWORDS：
```python
CONTINUATION_KEYWORDS = [
    # 現有關鍵字
    "繼續", "下一個", ...
    # 新增關鍵字
    "開始下一個", "繼續下一步"
]
```

### 改進並行分析
`find_parallelizable_tickets()` 函數可擴展以支援：
- 跨層級並行檢查
- 智能的檔案重疊檢測
- 優先級排序

### 增強報告格式
修改 `generate_parallel_suggestion_report()` 以支援：
- 並行分組可視化
- 時間估算
- 風險評估

---

## 相關文檔

### 規則文檔
- [decision-tree]($CLAUDE_PROJECT_DIR/.claude/rules/core/decision-tree.md) - 決策樹規則
- [parallel-dispatch]($CLAUDE_PROJECT_DIR/.claude/rules/guides/parallel-dispatch.md) - 並行派發指南

### 設計文檔
- [parallel-suggestion-hook-design.md](#) - 詳細設計
- [parallel-suggestion-hook-test-report.md](#) - 測試報告

### 方法論
- [manager-skill]($CLAUDE_PROJECT_DIR/.claude/skills/manager/SKILL.md) - 主線程管理哲學

---

## 版本歷史

### v1.0.0 (2026-02-03)
- 初始版本發布
- 完整的關鍵字識別
- 並行分析邏輯
- 詳細的日誌記錄
- 完整的文檔

---

## 常見問題

### Q: Hook 會影響性能嗎?
**A**: 否。Hook 執行時間 < 500ms，不會對用戶體驗造成影響。

### Q: 能否禁用 Hook?
**A**: 可以。在 `.claude/settings.local.json` 中設置 `"enabled": false`。

### Q: 日誌會持續增長嗎?
**A**: 是的。建議定期清理舊日誌（30 天以上）。

### Q: Hook 能否自動派發?
**A**: 否。Hook 只提供建議，派發決策由主線程做出。

### Q: 支援哪些版本?
**A**: 目前只支援 v0.31.0。未來可擴展到其他版本。

---

**文件版本**: 1.0.0
**最後更新**: 2026-02-03
**狀態**: 生產就緒
