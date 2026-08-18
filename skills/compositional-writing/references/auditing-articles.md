# Auditing Articles：對既有文章跑 reviewer-style audit

對「已寫完的高 stakes 內容」跑學術級 reviewer pass、找出 false sense of security / 對位失效 / context 缺 / citation 過時等 silent gap、輸出 ship-gate tier 化的 audit report。

跟「寫的時候自己跑的 multi-pass review」（[writing-multi-pass-review](./principles/writing-multi-pass-review.md) 的 stakes-conditional 追加輪 E）共享同一組 dimension、不同 trigger 跟 audience：

| 工具                  | Trigger                | Audience                   | 用途                                  |
| --------------------- | ---------------------- | -------------------------- | ------------------------------------- |
| Multi-pass 輪 E       | 寫文章時的 self-review | 作者                       | 預防 false sense of security 進入文字 |
| 本 reference 的 audit | 對既有文章做反向 audit | 作者重看 / 第三方 reviewer | 找已存在的 silent gap、產出 ship 決策 |

---

## 何時用本 reference

四個情境：

- 對高 stakes 章節（資安 / concurrency / distributed / financial / medical）做 quality gate
- 把過去寫的高 stakes 文章當素材二次擴寫前、先 audit 老文是否仍站得住
- Reviewer 視角審稿（自己寫的、別人寫的、AI 寫的高 stakes 內容）
- 教學 / 文件 ship 前的 final pass、決定 accept / revise / withdraw

不適用情境：

- 一般技術內容（layout / refactor / debug 教學）—— 5 輪基本 frame review 即可、不需要 audit
- 純概念說明 / 歷史背景內容 —— reader 不會直接照做、不需 verifiability-first
- 實驗性 / playful / 研究探討 —— reader 預期自行驗證

判別啟動的核心問題見 [risk-asymmetric-audit-standard](./principles/risk-asymmetric-audit-standard.md) 的高 stakes 識別四訊號。

---

## 通用 Reviewer-Pass 框架

學術 peer review 跑這幾個維度、本 audit 借同一組軸：

| 維度                     | Reviewer 在問什麼                                           |
| ------------------------ | ----------------------------------------------------------- |
| **Claim clarity**        | 核心主張是什麼？一句話講得出來？可不可被 falsified？        |
| **Evidence chain**       | claim → evidence 推論鏈完整？跳步驟了嗎？mechanism 寫了嗎？ |
| **Method rigor**         | 方法可重現嗎？前提條件 / 變因控制清楚嗎？                   |
| **Threats to validity**  | 什麼前提失效會 invalidate？作者有沒有承認邊界？             |
| **Internal consistency** | 定義有沒有飄移？前後論述衝突嗎？表格跟正文一致嗎？          |
| **Reproducibility**      | reader 照做能不能得到同樣結果？                             |
| **Citation accuracy**    | 引用版本對嗎？引用句意有沒有被扭曲？                        |

每個維度有對應的 audit 動作（見下「資安 lens」段；其他高 stakes 領域可類比）。

---

## 資安 Lens：維度具體展開

資安是高 stakes 內容最典型的 case。以下展開每個維度的 audit checklist——其他高 stakes 領域（concurrency / distributed / financial / medical）可類比、把 threat 換成 race / consistency violation / financial loss / patient harm。

### Dimension 1：Threat model 明確性（claim clarity + threats to validity）

每段 mitigation 論述要對稱寫「防什麼」+「不防什麼」。Audit checklist：

- [ ] 章節 lead 段有列整體 threat scope 嗎？
- [ ] 每個 mitigation 段配對應 threat + boundary 嗎？
- [ ] 「使用 X 防 Y」單句、Y 是抽象詞（傳輸風險 / 身分風險）—— 補 specific in-scope subset + out-of-scope threat
- [ ] reader 讀完最容易誤以為 X 也防的 B 是什麼？B 在文中標 out-of-scope 了嗎？

### Dimension 2：Mitigation 對位（evidence chain + method rigor）

Mitigation 名稱對位 threat 名稱是字面層（defense theater）、必須補 mechanism 層 + 前提層。Audit checklist：

- [ ] Mitigation 段有寫 mechanism 嗎？（X 在什麼抽象層擋、擋的是 threat 的哪一步）
- [ ] Mitigation 段有寫前提嗎？（X 成立的條件、條件失效時的 fallback）
- [ ] Mitigation 用 threat 類別名稱（brute force / SQLi / XSS）對位、還是具體攻擊行為（單 IP 高頻 / payload boundary / stored vs reflected）？
- [ ] 多 mitigation 並列時、有疊加 audit 嗎？聯集 mechanism 涵蓋整體 threat space？

對位失效訊號（升級為 withdraw 的候選）：

- 「業界常用 X 防 Y」當論證（appeal to convention）
- 用名稱層對位作為步驟示範（reader 照做不擋實際 mechanism）
- 過時 mitigation 被當示範（MD5 / SHA-1 / 弱 PBKDF2 / 過時 cipher suite）沒標 deprecated

### Dimension 3：Mitigation 的 context-dependence（method rigor + reproducibility）

同 mitigation 在不同 deployment / config / scale / runtime / actor 條件下強度不同。Audit checklist：

- [ ] Mitigation 段有寫 deployment 條件嗎？（單實例 vs 多實例 / 標準 config vs 完整 config / mainstream browser vs 全部）
- [ ] 強度參數（work factor / iteration count）對應 actor 能力寫了嗎？
- [ ] 多實例 / 多區域部署的 mitigation、有寫 distributed 變數嗎？（rate limit local vs distributed counter / session local vs shared store）
- [ ] 「在 modern browser」「在 standard config」這類修飾詞展開了嗎？

四個 context dimension 必查：

| Context 維度      | 失效範例                                                                  |
| ----------------- | ------------------------------------------------------------------------- |
| Config 完整性     | HTTPS 沒 HSTS / JWT 沒 rotation / cookie 沒 SameSite                      |
| Scale / 多實例    | local rate counter / local session store 在多實例 silent 失效             |
| Runtime 環境      | CSP 在舊瀏覽器 / native webview 失效；SameSite 在 server-to-server 不適用 |
| Threat actor 能力 | bcrypt work factor 隨時間 decay；nation-state vs 個人攻擊者強度差異       |

### Dimension 4：Citation 時效性與精確度（citation accuracy）

Citation 涵蓋兩類：**外部** 標準（OWASP / RFC / NIST / CIS）跟 **內部** citation（knowledge-cards 連結 / 跨章引用作為 control-of-record）。兩者都跟一般技術引用不同——外部 best practice 衰退快、原文常被引用扭曲；內部沒版本號 anchor、反而更易 silent drift / broken。Audit checklist：

外部 citation：

- [ ] 引用 OWASP / RFC / NIST 有標版本 / 年份嗎？
- [ ] 引用是轉述還是原文 quote？沒原文 quote → 找一手來源 verify 句意
- [ ] 「OWASP **建議** X」「RFC **規定** Y」當 universal —— 補 conditional scope
- [ ] Crypto / hashing 強度參數是固定值（10 / 100k / 32 char）—— 補 review trigger（每 6-12 月 re-check）
- [ ] 章節寫於 N 年前、有 last reviewed 日期嗎？有下次 review trigger 嗎？

內部 citation（knowledge-cards / 跨章引用）：

- [ ] 章節用 internal link 作為 control-of-record、有 last-checked 標記 / sync owner 嗎？
- [ ] 內部連結還在、目標頁是否 slug / 內容已改、章節原本暗示的 control 跟現在還對應？
- [ ] 子頁大改時是否 broadcast 到引用方？沒 broadcast 時是否每 6 月 sweep？

引用 drift 三類（外部、重點 catch）：

- **Conditional → unconditional drift**：原文有條件、文中沒條件
- **Specific → general drift**：原文限特定 context、文中講通用
- **Recommendation → mandate drift**：原文是 consider / recommend、文中是 must / required

內部專屬失效模式：

- **Broken / dead link**：knowledge-card 改 slug / 移檔、章節連結 silent broken
- **句意 drift（內部版）**：章節用 control-name 暗示能力、子頁定義跟暗示不一致

外部 citation 至少有版本號當 anchor、internal citation 連版本概念都沒有——audit 跟 review trigger 對 internal 反而更嚴格。

### Dimension 5：跨章 / 跨檔一致性（internal consistency、跨章 corpus 形態）

當 audit 跨章節 / 跨檔的 corpus（多章節知識網、系列文章、多模組 spec）、單章 audit 不夠——必須 check 同議題在多檔的 ownership / SSoT。常見 pattern：

| 失效 pattern                      | 範例                                                                                                                                  |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| 同議題出現在多章、無 SSoT 標記    | 「供應商身分鏈傳導」同時出現在 7.2 / 7.5 / 7.6 / 7.12 四章、reader 不知道 anchor 在哪                                                 |
| 同術語跨章定義不一致              | 「最小權限」在不同章節各自詮釋、reader 無法 trace 到 canonical 定義                                                                   |
| 跨章 mitigation chain 推不通      | 章 A 說「交給 B 處理」、章 B 沒明示 anchor 自己接、責任 chain 斷裂                                                                    |
| Required cross-chapter scope 缺失 | 「必連章節」段列了下游、但下游章節沒反向 link、形成單向 reference、reader 一跳到下游就斷                                              |
| 同一對象被兩篇各自分解一次        | 兩篇各給一套階段表 / 欄位組 / 責任清單（成員數與切點不同）、**雙向連結齊備仍然失效**——reader 帶著一套的判讀結果到另一篇對不到任何一格 |

Audit checklist：

- [ ] 每個跨章重複出現的議題、有沒有 canonical 章節標記（「本議題的 SSoT 在 7.X」）？
- [ ] 同術語（最小權限 / 收斂 / 擴散）是否在 canonical 章節定義一次、其他章節 link 過來而非各自詮釋？
- [ ] 「下一步路由」「必連章節」是否雙向（A 連 B、B 也連回 A 的 hand-off context）？雙向是必要條件不是充分條件——互相連結、語彙不同、各自宣稱處理另一半的兩篇，仍可能是同一對象的兩套分解
- [ ] 兩篇各有一張表描述同一類對象時，把鍵欄並置跑雙向對映（成員能不能互相對映完整、對映前先對齊粒度與層級）與動作測試（reader 會不會為這件事做同一個動作兩次）；不相容時先指定載體再談各章視角
- [ ] 跨章 mitigation chain 是否完整（章 A 說「下游處理」、追到下游有對應 receiver）？
- [ ] 跨章節同 case 是否一致歸類（同 incident 在多章引用作 evidence、視角差異有沒有衝突）？

跟 [false-sense-of-security-as-primary-failure](./principles/false-sense-of-security-as-primary-failure.md) 的 methodology layer 同骨——跨章重複議題沒 SSoT 標記、reader 拿著「議題在多章被討論」的印象就走、不知道哪章 implement-ready、停在 routing layer = methodology-layer false sense 的 cross-chapter 變體。

修法不是「把跨章重複議題 collapse 到一章」（會犧牲多視角 evidence）、是 **明示 canonical chapter + 各章視角的責任邊界**：

- Canonical 章寫議題的 SSoT 定義 + threat / mitigation chain
- 其他章引用 canonical、只補自己 layer 的視角差異（不重新定義）
- 跨章 cross-link 雙向、reader 在任一章都能 trace 到 SSoT

### Dimension 6：強度對齊（claim clarity + evidence chain）

強度詞（形容詞量級、模態、頻率）是 claim 的一部分、audit 要檢查強度與事實、證據是否對齊——兩個方向：升格（誇飾、overclaim）與降格（嚴重性寫得雲淡風輕）。誇飾的合法性由**段落位置的功能**決定、判斷單位是段落、以文件或文體整體一刀切兩個方向都會錯：

| 文體契約 | 行動耦合低                      | 行動耦合高                                  |
| -------- | ------------------------------- | ------------------------------------------- |
| 預期修辭 | 誇飾自由區：slogan、詩、賀詞    | 管制邊界區：廣告誘導購買、募資頁面          |
| 預期字面 | 有限使用區：教學 hook、開場敘事 | 零容忍區：規格、SLA、判準段、翻譯、安全陳述 |

高 stakes 內容的正文幾乎全落在零容忍區；hook / 引言段是有限使用區、誇飾合法、進判準段要收——audit 時對入口段的強度不加分扣分、對判準段與宣稱段逐條檢查。Audit checklist：

- [ ] 技術宣稱位的強度詞通過**支撐存在測試**嗎？（「快 10 倍」旁邊有 benchmark 是宣稱、裸的是誇飾佔位）
- [ ] 轉述位（引用、翻譯、摘要）比原文更強嗎？（「證明了」常是原文「suggests」的升格、二手內容加倍警惕、回一手來源比對）
- [ ] 「這一步非常關鍵」這類強調、後面有機制支撐嗎？（無支撐的空誇擠掉了本該放機制的位置）
- [ ] 安全陳述位有「絕對安全」「不可能被繞過」句型嗎？（假防護感的入口形態、進本檔「Audit Recommendation Tier 化」的決策樹）
- [ ] **自評位**：作者對自己產出的品質 verdict（「教科書級」「完美」）有技術理由支撐嗎？（對應 keyword bank 的自評誇飾 grep、命中後用兩軸判定）
- [ ] **反比操縱訊號**：越難驗證的段落話講得越滿嗎？（「話最滿的段落恰好最難查證」這種全篇分布比單點升格更難歸因於無意的文風滑動、所以警惕等級最高）
- [ ] **降格側**：風險段落的強度與嚴重性對位嗎？（RCE 寫成「可能造成一些影響」會讓應變者依錯的緊急度行動、incident report 尤其要掃）

跟 Dimension 4 的分工：citation drift 三類（conditional → unconditional / specific → general / recommendation → mandate）是強度漂移在 citation 位的具體形態、Dimension 4 逐條對原文抓；本 dimension 涵蓋 citation 之外的所有位置（宣稱位、判準段、風險陳述、自評位）、並補反方向的降格檢查。詳見 [hyperbole-legitimacy-by-position-function](./principles/hyperbole-legitimacy-by-position-function.md)。

---

## Audit Recommendation Tier 化

每個 weakness 跑這個決策樹：

```text
Q1：reader 照這段實作會不會主動產生破口？
  是 → Withdraw（不可保留）
  否 → Q2

Q2：weakness 是結構性（多 dimension 同時失效）還是局部（單一 dimension 缺）？
  結構性 → Major revise
  局部 → Q3

Q3：補完 weakness 的 cost 是「補一句 / 一表」還是「重寫一段」？
  一句 / 一表 → Minor revise
  重寫一段 → Major revise

Q4：weakness 在容忍範圍（背景段 / 低 stakes 段、reader 不會直接照做）？
  在 → Accept（可選 minor 但不要求）
  不在 → 走 Q3
```

四 tier 的 ship gate 對應：

| Tier         | Fix 模式                                                 | Ship gate              |
| ------------ | -------------------------------------------------------- | ---------------------- |
| Accept       | 無 fix 或自願性 minor                                    | 不阻擋                 |
| Minor revise | 補 boundary / 加 contrast / 標版本 / 補連結              | 不阻擋（可 follow-up） |
| Major revise | 重寫段落 + 補 mechanism / 前提 / context                 | 阻擋直到 fix 完成      |
| **Withdraw** | 移除整段 / 加 deprecation banner + redirect / 全換現代版 | **阻擋直到處理**       |

### Withdraw 的具體訊號

四個訊號之一觸發、即視為 withdraw：

1. **過時 crypto / hashing primitive 沒 deprecation 標記**：教 MD5 / SHA-1 / 弱 PBKDF2 但沒明示「這是過時、不要用」
2. **扭曲 citation 改變原文語意**：把 OWASP conditional 引成 unconditional、或反向違反現行標準（如 NIST 2017 之後的 password 不應強制定期更換）
3. **違反 current best practice 的步驟說明**：教 reader 主動關閉 mitigation（disable HSTS / CSP / SameSite）作為 workaround、沒明示「workaround 引入的新 risk」
4. **Defense theater 例子當示範**：用名稱層 mitigation 對位（rate limit「擋」brute force）作為步驟、reader 照做不擋實際 mechanism

四訊號共通：**reader 照做後實作會主動 worse than not having read**。Withdraw 不是嚴格、是 risk-asymmetric（[risk-asymmetric-audit-standard](./principles/risk-asymmetric-audit-standard.md)）下的必要決策。

---

## Audit Report 輸出格式

Audit 完成後產出結構化報告——格式比照學術 peer review、但 weakness 對應到 ship gate：

```text
# Audit Report：<章節 / 文章 title>

## Summary
<1-2 句：主要 audit 結論 + 整體 tier>

## Strengths
- <段 / dimension 跟其優點>

## Weaknesses by dimension

### Dimension 1：Threat model 明確性
- [Tier]：段 N、[具體 weakness 描述]、[fix 建議]

### Dimension 2：Mitigation 對位
- ...

### Dimension 3：Context-dependence
- ...

### Dimension 4：Citation 時效精確
- ...

### Dimension 5：Cross-chapter consistency（僅跨章 corpus 適用）
- ...

### Dimension 6：強度對齊
- ...

## Blocking conditions
<必須 fix 才能 ship 的 weakness 清單、按 tier 排序>

## Recommendation
<Accept / Minor revise / Major revise / Withdraw + 整體決策說明>
```

格式特性：

- **Strengths 段必填**：reviewer 視角不只 weakness、strengths 是 audit completeness 的訊號（也讓被 audit 的作者有 actionable feedback）
- **Weakness 按 dimension 分組**：方便後續 fix 時依 dimension 跑修正、不是「找到第 N 個問題」flat list
- **Blocking conditions 段**：明示哪些 tier 阻擋 ship、決策可被 ship gate 工具解析

---

## 跟 Multi-pass Review 第 6 輪的分工

兩者 dimension 共享、trigger 跟 audience 不同。具體分工：

| 階段     | Multi-pass 輪 E（self-review） | 本 reference（reviewer audit）            |
| -------- | ------------------------------ | ----------------------------------------- |
| 觸發點   | 寫的當下、ship 前最後 pass     | 文章已 ship、回頭 audit；或對他人寫的審稿 |
| 視角     | 作者視角                       | Reviewer 視角                             |
| 產出     | 修文                           | Audit report + ship gate 決策             |
| 認知狀態 | 還有寫作 context、改起來便宜   | 沒寫作 context、reviewer 距離較遠         |

實作建議：

- 寫作流程內：跑輪 E 預防 silent gap 進入文字
- 文章 ship 後：對 corpus 跑批量 audit、產出 audit report、依 tier 決策
- Audit 找到 withdraw / major：回到寫作流程修、修完再過 audit pass

---

## 過度 audit 反例

跟 [false-sense-of-security-as-primary-failure](./principles/false-sense-of-security-as-primary-failure.md) 的「過度警覺」段同骨——audit 也可能 over-apply：

- **每個段都評 tier**：文章變評分表、reviewer 投資爆炸；正解：tier 投資量級對應 reader 實作影響、background 段直接 accept
- **窮舉所有 deployment / threat 排列**：context 維度列十個 dimension × 五個值 = 50 個 case；正解：只列 reader 直覺會誤判的 dimension
- **每個 mitigation 列十個 out-of-scope**：文章變 audit-driven 而非 reader-driven；正解：1-2 個直覺 extrapolation 方向就夠
- **強行對非高 stakes 內容跑 audit**：稀釋 audit 紀律、5 輪基本 frame 在一般內容夠用

判別準則：「這個 audit 投資能不能對應到 reader 實作端的具體 risk reduction？」——能 → 投資合理、不能 → 過度

---

## 跟 principle 卡的關係

| Principle                                                                                                      | 關係                                                                                             |
| -------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| [false-sense-of-security-as-primary-failure](./principles/false-sense-of-security-as-primary-failure.md)       | 本 reference 的主要 audit 目標 —— 各 dimension 都在 catch false sense of security                |
| [risk-asymmetric-audit-standard](./principles/risk-asymmetric-audit-standard.md)                               | 本 reference 的啟動判準 —— 高 stakes 識別四訊號決定要不要跑 audit                                |
| [literal-interception-vs-behavioral-refinement](./principles/literal-interception-vs-behavioral-refinement.md) | 本 reference 的 ceiling 警示 —— 名稱層 mitigation 對位 = 字面層、stop at 字面 = false confidence |
| [writing-multi-pass-review](./principles/writing-multi-pass-review.md)                                         | 本 reference 是該卡「stakes-conditional 追加輪 E」的 reviewer-side 對應                          |
| [ease-of-writing-vs-intent-alignment](./principles/ease-of-writing-vs-intent-alignment.md)                     | 本 reference 的 audit weakness 模式 —— 含糊敘述是寫作便利、跟 verifiability 反向                 |
| [metadata-surface-in-writing-review](./principles/metadata-surface-in-writing-review.md)                       | Citation 是 metadata surface 的延伸 —— audit 範圍要涵蓋 citation 跟 title / heading 等讀者入口   |
| [hyperbole-legitimacy-by-position-function](./principles/hyperbole-legitimacy-by-position-function.md)         | Dimension 6 的判定框架 —— 兩軸四區定位強度合法性、支撐存在測試與反比操縱訊號、降格對齊           |

---

## 快速啟動

對章節跑 audit 的最小流程：

1. 確認啟動條件：高 stakes 識別四訊號至少一個觸發
2. 列章節所有 mitigation / claim / citation 清單
3. 對每條跑 dimension checklist（threat model / 對位 / context / citation / 強度對齊；跨章 corpus 加 consistency）
4. 每個 weakness 跑 tier 決策樹
5. 產出 audit report（含 strengths / weaknesses-by-dimension / blocking / recommendation）
6. 如有 withdraw / major：回寫作流程修、修完跑 audit pass 二次驗證
