# PC-131: 外部工具權威性預設質疑

---

## 分類資訊

| 項目 | 值 |
|------|------|
| 編號 | PC-131 |
| 類別 | process-compliance |
| 風險等級 | 中 |
| 首發時間 | 2026-05-05（W17-144.1 / W17-144.1.1） |
| 姊妹模式 | PC-074（字元集判定共用字陷阱）/ PC-088（LLM 工具選擇偏誤） |

---

## 症狀

PM 採用外部工具（如 OpenCC / 第三方 lint / 商用 API / 標準字典）作為判斷權威時，**預設工具的判斷正確且全集適用**，未實證工具對「目標場景」的偏差程度。事後發現工具有系統性偏差時，已在錯誤的工具基礎上累積邏輯。

具體案例：

| Session | 場景 | 錯誤假設 | 實際偏差 |
|---------|------|---------|---------|
| W17-144.1 | charset-pollution-detector.py 用 OpenCC s2t 判斷簡繁 | 「OpenCC 是權威簡繁映射工具」 | 對台灣現代繁體標準字（台/群/干）30% 誤判（OpenCC STCharacters 表來自中國大陸 GB 標準） |
| W17-144 | 用 zhtw-mcp 掃描污染源 | 「zhtw-mcp 是 zhtw 文字檢查工具，應能找污染」 | zhtw-mcp 自動 S2T 而非報錯，對「找污染」場景不適用 |

---

## 根本原因

1. **工具命名與目標場景的隱含承諾錯位**
   - OpenCC 全名「Open Chinese Convert」，承諾「簡繁轉換」，但實際是「中國大陸標準的雙向映射」。對「台灣現代繁體標準字」場景偏差。
   - zhtw-mcp 名稱含「zhtw」（繁中），承諾「繁中文字檢查」，但實際是「自動 S2T 轉換 + 跨海峽用語 + 翻譯腔」。對「污染偵測」場景不直接適用。

2. **工具設計者的目標 vs 使用者的目標**
   - 設計者目標通常為「最常見場景」（OpenCC：中國大陸用戶輸入簡體想轉繁體）。
   - 使用者目標可能完全不同（台灣用戶想找混入文件中的簡體字）。
   - 這兩個目標的字元集判斷策略可能相反。

3. **未對工具做「目標場景特化的精度實證」**
   - 直接用工具的 default 模式 / API 套用，未抽樣驗證對目標場景的判斷準確度。
   - 缺實證後遇到偏差案例時才發現問題。

---

## 防護措施

### 規則 1：採用外部工具前先做「目標場景精度實證」

對工具的判斷做抽樣測試（≥ 10 個目標場景案例），統計準確度。若準確度 < 95%，必須補位策略（雙權威源 / 反向過濾 / 種子手選 / 不採用）。

範例（W17-144.1.1）：

```python
# 對 OpenCC s2t 抽樣台灣標準字
taiwan_standard_samples = ["台", "群", "才", "干", "了", "只", "布", "丰", "个", "体"]
opencc_judges_simplified = sum(1 for ch in samples if s2t.convert(ch) != ch)
# 結果 3/10 誤判（30% 偏差，需補位）
```

### 規則 2：工具職責邊界顯性化於程式碼註解

採用工具時，註解必須明示：

| 必含項 | 範例 |
|--------|------|
| 工具職責（設計目標） | OpenCC s2t = STCharacters 表單向簡繁映射 |
| 已驗證偏差 | 對台灣標準字「台/群/干」30% 誤判 |
| 邊界（不適用場景） | 不可從 OpenCC STCharacters 全量抽取種子 |
| 補位策略 | 種子手選 + self-test 反向白名單 |

### 規則 3：self-test 反向驗證偏差案例

工具偏差案例必須寫入 self-test，啟動時驗證：

```python
def self_test():
    # 對工具偏差案例做反向驗證
    forbidden = [ch for ch in TOOL_BIAS_KNOWN_CASES if ch in OUR_DERIVED_SET]
    assert not forbidden, f"工具偏差案例混入: {forbidden}"
```

---

## 與其他規則的邊界

| 規則 / 模式 | 聚焦 | 與本模式差異 |
|-----------|------|------------|
| PC-088（LLM 工具選擇偏誤） | LLM 對工具的選擇偏誤（選錯工具） | 本模式為「選對工具但未驗證精度」 |
| PC-074（字元集共用字陷阱） | 自製清單內含共用字 | 本模式為「外部工具的判斷被當權威」 |
| `tool-discovery.md` | 探索 deferred tools 而非自製限制 | 本模式為「探索後選定工具仍需精度驗證」 |

---

## 教訓

1. **「工具命名」與「設計者目標」可能與你的場景錯位**：仔細讀 README 和 design philosophy，不要依名稱推斷能力。
2. **權威性是 case-by-case 的**：OpenCC 對「中國大陸標準簡繁映射」是權威；對「台灣現代繁體標準字」不是。
3. **採用工具的成本不止安裝 + 整合**：還含「精度實證 + 偏差案例固化到 self-test」。
4. **用戶 WRAP 質疑是寶貴訊號**：「OpenCC 是權威嗎？」這類質疑應立即實證，不要 hand-wave 過去。

---

## 象限歸類

防護屬 **摩擦力管理 C 象限（增加摩擦）**：採用工具前多一步精度實證 + 註解顯性化偏差，增加開發摩擦，換取下游不踩偏差雷區。代價（測試 10 字 + 寫註解）遠低於收益（避免 Layer 化的錯誤）。

---

## 相關文件

- `.claude/scripts/charset-pollution-detector.py` — W17-144.1 落地，含 _ANCHORS_SEED 警告 + TAIWAN_STANDARD_WHITELIST + self-test 第五層
- `docs/work-logs/v0/v0.18/v0.18.0/tickets/0.18.0-W17-144.1.1.md` — ANA 完整 WRAP 分析
- `.claude/error-patterns/process-compliance/PC-074-charset-guard-hook-shared-char-false-positive.md` — 字元集共用字陷阱（姊妹模式）
- `.claude/error-patterns/process-compliance/PC-088-llm-tool-selection-bias.md` — LLM 工具選擇偏誤（姊妹模式）

---

**Last Updated**: 2026-05-05
**Version**: 1.0.0 — 初始建立：外部工具權威性預設質疑（交叉驗證後再採信）（W17-144.1）
**Source**: 用戶 WRAP 質疑「OpenCC 並不是完全正確的權威資料」+ 實證 OpenCC 對台灣標準字 30% 誤判 + zhtw-mcp 對相同字組 100% 正確
