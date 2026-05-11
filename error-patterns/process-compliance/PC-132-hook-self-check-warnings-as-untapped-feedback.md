# PC-132: Hook self-check 警示是被忽視的反推資料源

---

## 分類資訊

| 項目 | 值 |
|------|------|
| 編號 | PC-132 |
| 類別 | process-compliance |
| 風險等級 | 中 |
| 首發時間 | 2026-05-05（W17-144.1.1.1 ANA Method 6 落地） |
| 姊妹模式 | PC-131（外部工具權威性質疑）/ PC-085（CJK codepoint 鄰近性） |

---

## 症狀

Hook 系統的 self-check 機制在每次執行時輸出 INFO 級警示（如「12 處漏網提示」），這些警示記錄到日誌但**從未被系統性收割回流到關聯清單**。維護者後續手動擴充清單時，未利用 hook 已知的反推資料，重複從外部源蒐集，浪費了現成的高 confidence 資料。

具體案例：

| 案例 | Hook self-check 內容 | 被忽視多久 |
|------|------|------|
| W17-144.1.1.1 | `askuserquestion-charset-guard-hook.py` 每次執行警示 12 個漏網簡體字（圖兩譯驛氣樂觀檢權鐵轉廣對應的簡體形式） | ≥ 1 週（2026-04-28 起反覆出現於 hook log） |

實際過程：
- W17-144.1（detector 初版）—— 從 PC-072 文件 + 中文常用詞抽取種子，**未檢視 hook log**
- W17-144.1.1（OpenCC 權威性質疑）—— 質疑工具但仍未檢視 hook log
- W17-144.1.1.1（Method 6 才發現）—— 用戶質疑「還有沒有別的方法」後才意識到 hook log 是反推資源

---

## 根本原因

1. **Self-check 警示的設計目的是「自我提醒」，不是「資料產出」**
   - Hook 設計者把 self-check 視為運行時健康檢查，輸出到 INFO log 即足夠。
   - 維護者把 INFO log 視為「執行記錄」，不會主動翻閱反推資料。
   - 兩者目的錯位，警示資料淪為「沉默的提醒」。

2. **缺反推回流機制**
   - Hook 警示「X 漏網」→ 預期動作是維護者擴充清單，但無自動化路徑（如 GitHub Issue / Ticket / TODO）。
   - 維護者擴充清單時依賴記憶或外部觸發（如 PC error-pattern），不會主動查 hook log。

3. **資料豐富度被「日誌格式單調」遮蔽**
   - INFO log 中 self-check 警示與其他訊息（執行時間 / 通過/阻擋計數）混合。
   - 高 value 的反推資料（已知漏網字清單）淹沒於低 value 的執行記錄中。

---

## 防護措施

### 規則 1：Hook self-check 警示必須可機器解析

Hook 輸出 self-check 警示時，採用結構化格式（JSON / TSV / 固定 prefix）：

```python
# 範例：askuserquestion-charset-guard-hook.py
log.info(
    "PC-085 self-check 漏網提示 %d 處（清單漸進擴充屬預期）：%s",
    len(missing),
    ["PC-085 漏網提示：%s / %s / %s 簡體 U+%04X 未在 SIMPLIFIED_CHARS" % ...]
)
```

機器解析範例（detector.py / 維護腳本）：

```bash
grep -h "PC-085 漏網提示" .claude/hook-logs/.../*.log | \
  sort -u | \
  awk -F'U\\+' '{print $2}' | \
  awk '{print $1}'  # 取 codepoint
```

### 規則 2：定期收割儀式

維護者每月（或在相關 ticket 觸發時）執行收割步驟：

| 步驟 | 操作 |
|------|------|
| 1. 列出 self-check 警示 | `find .claude/hook-logs -name "*.log" -mtime -30 -exec grep -l "self-check" {} \;` |
| 2. 提取漏網候選 | parse INFO log 結構化內容 |
| 3. 驗證候選 | 用權威工具（OpenCC s2t / zhtw-mcp）驗證 |
| 4. 擴充關聯清單 | 加入 hook 自身清單 / 關聯 detector 種子 |
| 5. 驗證 self-check 不再警示 | 重跑 hook 確認 INFO 計數歸零 |

### 規則 3：擴充清單時優先檢視 hook log

任何「擴充字元集 / 詞彙清單 / 關鍵字清單」的 ticket 啟動前，必須檢查相關 hook 是否已產出反推資料：

```bash
# 範例 checklist（可加入 ticket 模板）
ls .claude/hook-logs/<related-hook>/ | head -3
grep "self-check\|漏網\|missing" .claude/hook-logs/<related-hook>/*.log | head -5
```

---

## 與其他規則的邊界

| 規則 / 模式 | 聚焦 | 與本模式差異 |
|-----------|------|------------|
| PC-131（外部工具權威性質疑）| 工具的判斷準確性 | 本模式為「忽視內部工具自身警示」 |
| PC-085（CJK codepoint 鄰近性）| 簡繁鄰近字混淆物理基礎 | 本模式為「self-check 警示利用」 |
| PC-074（共用字陷阱）| 字元集設計的反模式 | 本模式為「資料源的反模式」 |
| `quality-baseline.md` 規則 4 | Hook 失敗必須可見 | 本模式延伸：可見不等於被使用 |

---

## 教訓

1. **Hook self-check 警示是「免費的反推資料」**：每次 hook 執行已產出，零新增成本。
2. **「設計者目的」 vs 「使用者目的」可重疊**：self-check 設計為自我提醒，但對維護者也是反推清單。
3. **INFO log 的高 value 資料容易淹沒**：必須結構化以便機器收割。
4. **擴充清單前先檢查內部資料源**：自家 hook log 可能比外部字典更貼合場景（已驗證 Method 6 直接給 12 字，無需解析教育部公開字表）。
5. **用戶質疑往往揭示盲點**：「還有沒有別的方法」直接觸發 Method 6 發現。

---

## 象限歸類

防護屬 **摩擦力管理 A 象限（自動化護欄）**：將「定期收割 hook log」內建為 ticket 啟動 checklist，避免每次手動擴充清單時忘記檢查內部資料源。代價（檢查命令）遠低於收益（高 confidence 候選免費供應）。

---

## 相關文件

- `.claude/scripts/charset-pollution-detector.py` — W17-144.1.1.1 落地，_ANCHORS_SEED 含 Method 6 反推 12 字
- `.claude/hooks/askuserquestion-charset-guard-hook.py` — PC-085 self-check 警示來源
- `docs/work-logs/v0/v0.18/v0.18.0/tickets/0.18.0-W17-144.1.1.1.md` — Method 6 ANA 完整分析
- `.claude/error-patterns/process-compliance/PC-085-cjk-codepoint-similarity-confusion.md` — 漏網警示的觸發 PC

---

**Last Updated**: 2026-05-05
**Version**: 1.0.0 — 初始建立（W17-144.1.1.1 落地）
**Source**: 用戶質疑「還有沒有別的方法判斷污染源」+ 即時實證 Hook log 反推 12 簡體字 + 意識到此資料源已被忽視至少 1 週
