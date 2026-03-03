# 派發決策樹完整版

完整的二元決策樹結構，用於快速判斷任務派發方向。

## 決策樹流程圖

```
任務進入
    |
    v
包含錯誤關鍵字? ─是→ [強制] incident-responder
    |
    └─否→ 包含不確定性詞彙? ─是→ [確認機制] 向用戶確認
              |
              └─否→ 複雜需求（觸發 3+ 代理人）? ─是→ [確認機制]
                        |
                        └─否→ 是問題? ─是→ 是查詢類? ─是→ 執行查詢命令
                                    |           |
                                    |           └─否→ 派發諮詢代理人
                                    |
                                    └─否→ 是開發命令? ─是→ [驗證 Ticket]
                                              |              └→ TDD 階段派發
                                              |
                                              └─否→ 是除錯命令? ─是→ incident-responder
                                                        |
                                                        └─否→ 其他處理
```

## 決策判斷點詳解

### 1. 錯誤檢測（第0層第1步）

**識別關鍵字**：
- "failed", "failing", "fail"
- "error", "crash", "exception"
- "bug", "problem", "issue"（有明確錯誤現象時）
- "TypeError", "AttributeError" 等異常名稱

**判斷邏輯**：
- 包含上述關鍵字 → 強制派發 incident-responder
- 不包含 → 進入第2步

**incident-responder 的角色**：
- 分析錯誤原因
- 分類錯誤類型
- 建立錯誤 Ticket
- 提供派發建議（不決定，由 PM 決定）

### 2. 不確定性詞彙檢測（第0層第2步）

**識別關鍵字**：
- "好像", "可能", "似乎"
- "也許", "大概", "不太確定"
- "不知道該怎麼做", "需要確認"

**判斷邏輯**：
- 包含不確定性詞彙 → 啟動確認機制
- 用 AskUserQuestion 向用戶確認需求
- 不包含 → 進入第3步

### 3. 複雜需求檢測（第0層第3步）

**判斷標準**：
- 需要觸發 3 個以上不同領域的代理人
- 例如：同時涉及 SA（架構）、UI 設計、安全審查

**判斷邏輯**：
- 複雜度高（3+ 代理人）→ 啟動確認機制
- 用 AskUserQuestion 確認優先級和執行順序
- 否則 → 進入第1層

## 第一層：訊息類型判斷

### 是問題？

**識別特徵**：
- 包含問號
- 使用疑問詞：「怎麼」「為什麼」「如何」「是什麼」「進度」「狀態」
- 內容是詢問而非指令

#### 是查詢類問題

派發方向：
- 內部系統查詢（Ticket、進度、狀態）→ 直接回應
- 外部資源研究（GitHub、文檔、論壇）→ 派發 oregano-data-miner
- 技術諮詢（架構、安全、效能）→ 派發專業代理人

#### 非查詢類問題

派發方向：
- 派發專業代理人（system-analyst、security-reviewer 等）
- 或轉為開發命令派發

### 是開發/修改命令？

**識別特徵**：
- 動詞開頭：「實作」「建立」「修改」「更新」「調整」「優化」「重構」「新增」「刪除」

**驗證步驟**：
- [強制] 檢查是否有對應的待認領 Ticket
- Ticket 存在 → 標記為 in_progress 後派發
- Ticket 不存在 → 建議先執行 `/ticket create`

**TDD 階段派發**：
- Phase 1：lavender-interface-designer
- Phase 2：sage-test-architect
- Phase 3a：pepper-test-implementer
- Phase 3b：parsley-flutter-developer
- Phase 4：cinnamon-refactor-owl

### 是除錯命令？

**識別特徵**：
- 「測試」「debug」「診斷」「問題排查」
- 與 TDD Phase 無直接關係
- 多為臨時性故障排除

**派發方向**：
- 強制派發 incident-responder 分析
- 根據分析結果派發對應代理人

## 代理人快速查詢表

| 問題類型 | 代理人 | 觸發條件 |
|---------|-------|--------|
| **系統級** | | |
| 錯誤/失敗 | incident-responder | 任何錯誤現象 |
| 新功能/架構變更 | system-analyst | SA 前置審查（Phase 0） |
| 安全相關 | security-reviewer | 含 auth/crypto/token |
| UI 規範/設計 | system-designer | UI 相關設計 |
| 環境/編譯/依賴 | system-engineer | 環境配置問題 |
| 資料設計 | data-administrator | 資料結構 |
| 效能問題 | ginger-performance-tuner | 效能相關 |
| | | |
| **TDD 階段** | | |
| 功能設計 | lavender-interface-designer | Phase 1 |
| 測試設計 | sage-test-architect | Phase 2 |
| 實作策略 | pepper-test-implementer | Phase 3a |
| 實作執行 | parsley-flutter-developer | Phase 3b |
| 重構評估 | cinnamon-refactor-owl | Phase 4 |

## 決策記錄

每次重大派發決策應記錄：

```markdown
## 決策記錄

### 任務資訊
- 任務描述：[...]
- 提交時間：[時間]

### 決策路徑
1. 包含錯誤關鍵字？ [否/是]
2. 包含不確定性詞彙？ [否/是]
3. 複雜需求（3+ 代理人）？ [否/是]
4. 訊息類型：[問題/命令/其他]
5. 派發代理人：[...]

### 派發建議
- **代理人**：[...]
- **理由**：[...]
- **預期產出**：[...]

### 驗收標準
- [ ] Ticket 已建立
- [ ] 代理人已派發
- [ ] 工作日誌已更新
```

---

**Last Updated**: 2026-03-02
**Version**: 1.0.0
