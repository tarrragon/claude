# PC-106：規則失效跳過讀 code 直接判定規則設計錯誤

**類別**：process-compliance
**嚴重度**：中（誤診導致多餘工作、可能誤改正確規則）
**發現時機**：PM 遭 hook 阻擋或規則擋路時

---

## 症狀

PM 看到 hook/規則阻擋訊息後，直覺判斷「這是規則設計錯誤 / 規則與 X 衝突」，立即提議修改規則，而未先閱讀該 hook 的 classify 函式與主流程條件判斷。

典型語句：
- 「這個 hook 跟 ARCH-015 衝突，要改 hook」
- 「規則明顯有漏洞，要新增豁免分支」
- 「hook 強制 X 但情境需要 not-X，規則錯了」

---

## 根因

PM 從「症狀（阻擋訊息）」直接推論「病因（規則設計錯誤）」，跳過中間檢查：

1. **未讀 code**：依賴阻擋訊息的措辭推理規則意圖，而非實際邏輯
2. **錨定偏誤**：第一次看到阻擋就錨定「規則錯」，忽略 base rate 最低是「規則設計錯」（規則多半已被審查過）
3. **忽略自己的輸入**：PM 的 prompt/command/flag 可能缺豁免所需的線索，這個 base rate 遠高於「規則缺豁免」

---

## 防護

### 診斷順序（強制）

PM 遭 hook 阻擋時，按順序檢查：

| 步驟 | 檢查 | 工具 |
|------|------|------|
| 1 | 讀 hook 主流程條件判斷 | `Read` hook.py 或 `Grep` 主 return 0/2 路徑 |
| 2 | 讀 classify/分類函式 | `Grep` classify/分類/parse |
| 3 | 對照自己輸入 是否命中現有豁免條件 | 測試 `python3 -c` 或讀現有測試 |
| 4 | 若輸入缺觸發豁免線索 → 補輸入 | 不改 hook |
| 5 | 若輸入已符合豁免但仍阻擋 → 確認是 bug | 改 hook |
| 6 | 若豁免條件本身需擴充 → 評估 base rate | 新增豁免分支 |

**base rate 順序**（高到低）：

1. PM 輸入不完整（佔多數）
2. Hook 有 bug（判斷邏輯與註解不符）
3. 豁免條件需擴充（新情境）
4. Hook 規則設計錯誤（最罕見）

### 案例（W17-018）

- 症狀：派 thyme 得「必須使用 worktree」阻擋
- 誤診：PM 認為 `agent-dispatch-validation-hook` 與 ARCH-015 衝突，要修 hook 新增「全 .claude/ 豁免分支」
- 實情：hook 已有該豁免（line 1019-1026），只是 PM 短 prompt 省略 `.claude/` 路徑線索，classifier 判定全 False → fallback 到 worktree 強制
- 正確修法：讓 hook 在 prompt 路徑不明時，從 ticket ID 讀 `where.files` 補分類（非改規則而是補輸入來源）

---

## 與其他 PC 的關係

| PC | 關係 |
|----|------|
| PC-040 | 要求 context 存 ticket，W17-018 修法正好讓 hook 讀 ticket 補分類，符合 PC-040 精神 |
| PC-066 | WRAP 決策框架要求「考慮對立面」，本 PC 的防護順序是 WRAP 在規則修改情境的特化 |
| PC-088 | LLM tool selection bias——PM 從症狀直覺推論也是單步推理偏誤 |

---

## 檢查清單

PM 修規則前必自問：

- [ ] 讀過該 hook 的 classify 函式完整邏輯？
- [ ] 讀過 main flow 的 exit path？
- [ ] 測試過自己的輸入是否命中現有豁免？
- [ ] 確認自己的輸入已完整？
- [ ] 已排除前三個 base rate 較高的原因？
- [ ] 若修規則，修的是 bug / 豁免擴充 / 設計錯誤？哪類？

**Last Updated**: 2026-04-20
**Version**: 1.0.0
**Source**: W17-018 session 發現（diagnostic偏誤導致先建 hook 豁免 ticket，讀 code 後發現 hook 已豁免，真因是 prompt 線索不足）
