# PC-074: 字元集守衛 Hook 實作時的繁簡共用字 false positive

---

## 分類資訊

| 項目 | 值 |
|------|------|
| 編號 | PC-074 |
| 類別 | process-compliance |
| 風險等級 | 低（偵測錯誤不是安全漏洞） |
| 首發時間 | 2026-04-17（W12-002.1 首次啟用 Hook session） |
| 姊妹模式 | PC-072（AUQ payload 字元集污染，本 Hook 的主目標） |
| 升級狀態 | 已升級至 `.claude/rules/core/language-constraints.md` 規則 5「字元集子集清單必須動態驗證」（2026-05-26 by W3-014 / W3-014.1） |

---

## 升級備註

本 PC 的「動態驗證取代靜態維護」防護原則已於 2026-05-26 升級為自動載入規則 `.claude/rules/core/language-constraints.md` 規則 5（W3-014 ANA 分析、W3-014.1 規則落地）。

**Why**：原 PC-074 屬「行為準則」層級（讀者需主動查 error-pattern 才能套用），W17-144.1 二度自證證實依賴主動讀取的防護在維護者 token 生成壓力下會反覆失效。升級至 `rules/core/` 自動載入層級後，所有角色 session 啟動即內化規則，覆蓋面從「Hook 設計者」擴大至「任何字元集子集清單維護者」。

**Consequence**：後續維護者新增字元集子集清單（簡體字、日漢字、異體字等）時應**優先參照規則 5**而非本 PC；本 PC 保留作為案例庫與動機脈絡，但「該做什麼」的權威來源已轉移。

**Action**：

| 場景 | 應參照 |
|------|-------|
| 新增字元集子集清單 / 設計字元辨識工具 | `.claude/rules/core/language-constraints.md` 規則 5（規範性權威） |
| 理解規則 5 的歷史脈絡與案例 | 本 PC「動態驗證取代靜態維護」章節（案例庫） |
| 排查既有 false positive | 本 PC「症狀」「根本原因」章節 |

---

## 症狀

字元集守衛 Hook（askuserquestion-charset-guard-hook.py）啟用後立即發生 false positive：
- 正常的繁體 payload 被擋下
- 擋下訊息指向一個**繁簡共用字**（例如「出」U+51FA）
- PM 需要手動修復 SIMPLIFIED_CHARS 清單才能繼續

---

## 根本原因

### 已驗證事實

1. **首次誤判字元**：「出」(U+51FA) — 繁體中文與簡體中文共用同一個字元，讀音與意義一致
2. **清單設計疏漏**：SIMPLIFIED_CHARS 清單直接從常見 zh-CN 詞彙中拆字，未逐字驗證「繁體中文是否也用此字元」
3. **測試盲點**：實作測試用了典型簡體詞（独立/简体等），未涵蓋繁簡共用字的正常繁體使用情境

### 真根因

1. **詞彙拆字 vs 字元獨立性混淆**：
   - 設計者看到簡體詞「进出」(jìnchū，意為 in and out)，誤以為「进」與「出」兩字都是簡體
   - 實際上「進/进」是繁簡有別，但「出」是繁簡共用

2. **繁簡對照表不可直接反轉**：
   - 常見做法：整理「zh-CN → zh-TW」對照表（例如 `进→進`、`简→簡`）
   - 陷阱：對照表中 zh-CN 欄位列出的字，不一定**全部**都是 zh-CN 專有
   - 「出 → 出」這種「對照後相同」的字，若誤認為 zh-CN 欄位都是簡體，就會誤判

3. **測試覆蓋不足**：
   - 只測「含污染」+「純繁體無誤判字」兩類 payload
   - 缺「繁體中含繁簡共用字」這類邊界案例

---

## 常見陷阱模式

| 陷阱表述 | 為何仍構成誤判 |
|---------|--------------|
| 「把常見簡體詞拆開列入清單就好」 | 詞是由字組成，但字的繁簡屬性獨立於詞 |
| 「中文字只要出現在簡體文本就列入」 | 繁簡共用字在所有中文文本都出現，不構成污染證據 |
| 「Hook 擋到不會錯」 | false positive 會打斷正常流程，比 false negative 更影響信任 |

---

## 防護措施

| 層級 | 措施 | 狀態 |
|------|------|------|
| 清單驗證 | 擴充 SIMPLIFIED_CHARS 前，每個候選字查《繁簡對照字典》或實測繁體字典確認不共用 | 已升級至 `.claude/rules/core/language-constraints.md` 規則 5（2026-05-26 / W3-014.1） |
| 測試強化 | Hook 測試新增「繁體中含繁簡共用字」類別（「出/入/口/人/大/小/年/月/日」等） | 建議實施 |
| 程式註解 | SIMPLIFIED_CHARS 清單旁註明「每字須通過繁簡不共用驗證」 | 建議實施 |
| 文件 | Hook docstring 加入已知 false positive 清單與加字時的檢查步驟 | 建議實施 |
| Memory | 記錄跨 session 提醒 | 已實施（配對本檔） |

---

## 已知繁簡共用字（不可列入 SIMPLIFIED_CHARS）

以下字元繁簡完全相同，列入清單會產生 false positive：

- **基本**：出、入、口、人、大、小、一、二、三、四、五、六、七、八、九、十
- **方位**：上、下、左、右、中、前、不
- **自然**：日、月、火、水、木、金、土、天、地、山、川
- **人稱**：你、我、他、她
- **時間**：年、月、日、時（注意：簡體「时」≠「時」，但「時」本身繁體也用）

實際上非常多中文字元繁簡相同。擴充清單前應**正面列舉簡體專屬字**（不是反向排除繁簡共用），並逐字驗證。

---

## 建議的清單擴充流程

1. 收集新污染案例中的可疑字元
2. 對每個字元查繁簡對照字典（例如 OpenCC、ChineseTool 等資源）
3. 確認「繁體中文是否使用此字元」：
   - 是 → 繁簡共用，禁止加入清單
   - 否 → 簡體專屬，可加入清單
4. 新增後跑繁體回歸測試：
   ```python
   test_cases = [
       "繁體中文文本含基本字：出入口人大小",
       "含時間字：年月日時分秒",
       "含數字：一二三四五六七八九十",
   ]
   for text in test_cases:
       assert scan_payload_text(text) == [], f"False positive: {text}"
   ```

---

## 教訓

1. **安全 Hook 優先避免 false positive**：false positive 打斷流程，比 false negative 更影響用戶信任；寧願漏擋幾個也不能誤擋
2. **字元集設計要正面列舉**：簡體專屬字清單比「常見簡體詞拆字」可靠
3. **首次啟用 Hook 立即測試**：Hook 啟用後的第一次真實呼叫就能暴露設計缺陷；本 session 的啟用→誤判→即修循環只花 2 分鐘，驗證機制運作正確
4. **依賴維護者記憶力區分共用字 vs 簡體字會反覆失敗（W17-144.1 二度自證）**：詳見「動態驗證取代靜態維護（根本性解法）」章節

---

## 動態驗證取代靜態維護（根本性解法）

> **來源**：W17-144.1（codepoint-aware detector 落地過程）。本 ticket 在實作 KNOWN_SIMPLIFIED_ANCHORS 黑名單時**二度自證 PC-074**：第一輪自製 SIMPLIFIED_SET 含「件/本/保/言/系/明」共用字，第三輪 ANCHORS 又從中文詞抽字（「资本」「证件」「语言」）再次混入相同共用字。Self-test 揪出後 PM 才意識到問題本質。

### 現象

每次新增「明確簡體字清單」時，維護者仍會把繁簡共用字混入。即使讀過 PC-074 警告也不能避免。

### 根因

人工撰寫過程是 token-by-token 生成，遇到「件保言系明」這類字元時記憶力分辨不出「這字是簡體還是共用」。**規則寫在文件上不等於 token 生成時會被檢查**。

### 解法：動態建構黑名單

把「驗證清單純度」的責任交給 OpenCC 自動執行：

```python
def _build_anchors(converter) -> frozenset[str]:
    """從種子字串過濾出 OpenCC 認可的簡體字（s2t(X) != X）"""
    return frozenset(ch for ch in _ANCHORS_SEED if converter.convert(ch) != ch)
```

種子字串可以隨意（含共用字也沒關係），OpenCC 會自動排除「s2t(X) == X」（即繁體共用字）的條目。

### 自驗證機制（self-test）

```python
# 第三層：黑名單不含繁簡共用字（PC-074 防護）
forbidden_in_anchors = [ch for ch in shared_chars if ch in KNOWN_SIMPLIFIED_ANCHORS]
assert not forbidden_in_anchors, f"PC-074 違規: {forbidden_in_anchors}"

# 第四層：黑名單所有字都應被 OpenCC 視為簡體（s2t(X) != X）
invalid_anchors = [ch for ch in KNOWN_SIMPLIFIED_ANCHORS if converter.convert(ch) == ch]
assert not invalid_anchors, f"非簡體字混入: {invalid_anchors}"
```

### 推廣原則

**「依賴維護者記憶力區分相似實體 vs 不同實體」的清單，必須改用工具自動驗證**：

| 場景 | 反模式 | 正確 |
|------|-------|------|
| 簡體字黑名單 | 人工列簡體字清單 | OpenCC 動態過濾 |
| 日漢字黑名單（PC-084） | 人工列日漢字清單 | unicodedata + JIS 表動態過濾 |
| 異體字白名單 | 人工列異體字 | OpenCC s2t/t2tw round-trip 動態判定 |
| 任何「字元集子集」清單 | 靜態維護 | 依規則動態建構，啟動時 self-test 驗證 |

### 與 PC-074 主文的關係

主文「字元集設計要正面列舉」的「正面列舉」原則仍正確；本章節補強的是「**正面列舉的清單也要由工具動態驗證，不能僅依賴人工**」。

---

## 象限歸類

本模式的防護屬 **摩擦力管理 C 象限（增加摩擦）**：擴充清單前多一步查字典驗證增加開發摩擦，換取下游不發生 false positive 打斷。代價（查字典）遠低於收益（避免誤擋正常繁體文本）。

---

## 相關文件

- `.claude/hooks/askuserquestion-charset-guard-hook.py` — Hook 實作
- `.claude/error-patterns/process-compliance/PC-072-askuserquestion-payload-charset-contamination.md` — 主要目標（防止污染）
- `.claude/error-patterns/process-compliance/PC-084-trad-jp-shared-char-false-positive.md` — 姊妹模式：繁日共用字誤判。CJK 字元集清單設計的另一維度，設計日文漢字清單時需同等驗證
- `.claude/rules/core/language-constraints.md` — 繁體/emoji 規則來源

---

**Last Updated**: 2026-05-26
**Version**: 1.3.0 — 新增「升級備註」章節 + 防護措施表「清單驗證」列狀態更新：動態驗證原則已升級至 `.claude/rules/core/language-constraints.md` 規則 5（W3-014 / W3-014.1）；本 PC 轉為案例庫定位，規範性權威轉移至 rules/core/

**Version**: 1.2.0 — W17-144.1 二度自證後新增「動態驗證取代靜態維護（根本性解法）」章節：人工維護黑名單會反覆混入共用字，須交給 OpenCC 自動過濾 + self-test 雙層機制；推廣原則覆蓋簡體字 / 日漢字 / 異體字 / 任何字元集子集場景

**Version**: 1.1.0 — 新增姊妹模式 PC-084 交叉引用（W14-014 落地）
**Source**: AUQ payload「產出」含「出」被誤判為簡體，Hook 啟用後 2 分鐘內暴露
