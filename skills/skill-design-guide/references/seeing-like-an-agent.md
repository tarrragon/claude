# Seeing like an Agent: 工具設計哲學與進階模式

來源：Anthropic 官方 "Lessons from Building Claude Code: Seeing like an Agent" + Best Practices

---

## 核心哲學

> "Designing the tools for your models is as much an art as it is a science."

### 工具要匹配模型能力

想像被給了一道數學題 — 你想要什麼工具？取決於你自己的能力：
- **紙** = 最低限度，受限於手動計算
- **計算機** = 更好，但需要知道進階功能
- **電腦** = 最強大，但需要會寫和執行程式碼

設計 Skill 同理：給模型**匹配其能力的工具**。

### 如何知道模型的能力？

**觀察、閱讀輸出、實驗。學會像 Agent 一樣看世界。**

---

## Claude Code 團隊的演進教訓

### 教訓 1：AskUserQuestion 工具的誕生

**問題**：Claude 可以用純文字提問，但回答這些問題感覺不必要地耗時。

| 嘗試 | 方法 | 結果 |
|------|------|------|
| #1 | 在 ExitPlanTool 加參數 | 混淆 — 同時要求計畫和問題，答案可能衝突 |
| #2 | 修改輸出格式（markdown 列表） | 不保證 — Claude 會附加額外句子、省略選項 |
| #3 | 專用 AskUserQuestion 工具 | 成功 — 結構化輸出、多選項、可組合 |

**關鍵洞見**：「即使設計最好的工具，如果 Claude 不理解如何呼叫它，也不會有用。」

### 教訓 2：TodoWrite → Task Tool 的演進

| 階段 | 工具 | 問題 |
|------|------|------|
| 初期 | TodoWrite | Claude 會忘記要做什麼 |
| 中期 | TodoWrite + 每 5 turn 提醒 | 提醒讓 Claude 覺得必須嚴格遵守清單 |
| 現在 | Task Tool | 支援依賴、跨子代理共享、可修改和刪除 |

**關鍵洞見**：「隨著模型能力增長，過去需要的工具可能現在反而在限制模型。定期重新審視工具需求。」

### 教訓 3：搜尋介面的演進

| 階段 | 方法 | 問題 |
|------|------|------|
| 初期 | RAG 向量資料庫 | 需要索引設定、跨環境脆弱、Claude 被給予 context 而非自己找 |
| 中期 | Grep 工具 | Claude 可以搜尋自己建構 context |
| 現在 | Progressive Disclosure (Skills) | Claude 讀取 Skill 檔案，遞迴發現更多相關檔案 |

**關鍵洞見**：「隨著 Claude 變得更聰明，如果給它正確的工具，它會越來越擅長自行建構 context。」

### 教訓 4：Progressive Disclosure 取代新增工具

**問題**：Claude 不知道如何使用 Claude Code 本身。

| 方案 | 結果 |
|------|------|
| 放入 system prompt | 造成 context rot，干擾主要工作（寫程式碼） |
| 給文件連結讓 Claude 搜尋 | Claude 載入太多結果 |
| 專用 Guide 子代理 | 有效 — Claude 被提示在被問到自身時呼叫子代理 |

**關鍵洞見**：「我們在不新增工具的情況下擴展了 Claude 的能力空間。」

---

## 進階 Skill 設計模式

### Evaluation-Driven Development（評估驅動開發）

**先建立評估，再寫文件**：

1. **識別缺口**：不用 Skill，在代表性任務上執行 Claude，記錄失敗點
2. **建立評估**：3 個測試場景
3. **建立基線**：測量無 Skill 時的表現
4. **寫最小指令**：只寫足以通過評估的內容
5. **迭代**：執行評估、比較基線、精煉

### Claude A/B 迭代開發法

用一個 Claude 實例（A）設計 Skill，另一個（B）測試使用：

1. **Claude A 完成任務** — 過程中自然提供 context
2. **識別可重用模式** — 哪些 context 未來類似任務也需要
3. **請 Claude A 建立 Skill** — 直接說 "Create a Skill that captures this pattern"
4. **審查精簡度** — 移除不必要解釋
5. **改善資訊架構** — 組織 reference 檔案
6. **Claude B 測試** — 在新實例上用 Skill 處理相關任務
7. **迭代** — 將 B 的行為觀察帶回 A 改進

### Workflow Checklist 模式

複雜工作流提供可複製的進度追蹤清單：

```markdown
## 工作流程

複製此清單追蹤進度：

Task Progress:
- [ ] Step 1: 分析輸入
- [ ] Step 2: 建立對應表
- [ ] Step 3: 驗證對應表
- [ ] Step 4: 執行轉換
- [ ] Step 5: 驗證輸出
```

### Feedback Loop 模式

**驗證→修正→重複**，大幅提升輸出品質：

```markdown
1. 執行操作
2. 立即驗證：`python scripts/validate.py`
3. 如果驗證失敗：
   - 仔細閱讀錯誤訊息
   - 修正問題
   - 再次驗證
4. 只有驗證通過才繼續下一步
```

### Verifiable Intermediate Outputs（可驗證中間產出）

**Plan-Validate-Execute** 模式：

1. 分析 → **建立計畫檔案**（如 `changes.json`）
2. **驗證計畫** → 腳本檢查計畫正確性
3. 計畫通過 → 執行變更
4. 驗證結果

**適用場景**：批量操作、破壞性變更、複雜驗證、高風險操作。

### Solve, Don't Punt（解決問題，不推給 Claude）

腳本應處理錯誤，而非讓 Claude 猜測：

```python
# 正確：明確處理錯誤
def process_file(path):
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError:
        print(f"File {path} not found, creating default")
        with open(path, "w") as f:
            f.write("")
        return ""

# 錯誤：推給 Claude 處理
def process_file(path):
    return open(path).read()  # 失敗時 Claude 要自己想辦法
```

常數也需要自解釋（避免 "voodoo constants"）：

```python
# 正確
REQUEST_TIMEOUT = 30  # HTTP requests typically complete within 30 seconds

# 錯誤
TIMEOUT = 47  # 為什麼是 47？
```

---

## 觀察 Claude 如何使用 Skill

迭代 Skill 時注意：

| 觀察 | 可能原因 | 行動 |
|------|---------|------|
| 意外的檔案讀取順序 | 結構不夠直覺 | 重組 reference 結構 |
| 未跟隨 reference 連結 | 連結不夠明顯 | 更突出的連結指引 |
| 反覆讀取同一檔案 | 該內容應放在 SKILL.md | 上移到主指令 |
| 從未存取某 reference | 不需要或信號不佳 | 移除或改善 SKILL.md 中的指引 |

---

## 反模式

| 反模式 | 正確做法 |
|--------|---------|
| Windows 路徑（`\`） | 統一用 `/`（跨平台相容） |
| 提供太多選項 | 給一個預設方案 + 逃生出口 |
| 假設套件已安裝 | 明確列出依賴並提供安裝指令 |
| 巢狀引用（A→B→C） | 所有 reference 從 SKILL.md 一層直連 |

---

*Last Updated: 2026-03-02*
*Source: "Lessons from Building Claude Code: Seeing like an Agent" + Anthropic Best Practices*
