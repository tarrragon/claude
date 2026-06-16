# PC-V1-010: 子代理人完成摘要把測試總數誤報為通過數，遮蔽紅燈

**類別**: process-compliance
**嚴重度**: High
**相關**: tool-output-trust-rules 規則 5（記錄平面 vs 世界平面）、quality-baseline 規則 1（測試通過率 100% / 綠燈邊界）、PC-028（代理人報告未經驗證）、PC-135（pytest 過但 hook 子進程失準）

---

## 症狀

子代理人完成 IMP/修復後，於完成摘要的測試結果欄位寫「全套件 N passed」，但 N 實為**測試總數**而非實際通過數：

1. 摘要標題：`全套件 ... 187 passed`
2. PM 獨立重跑同一指令實得：`186 passed, 1 failed`（187 為 total）
3. 失敗測試確實存在，代理人可能在另一段「需 PM 追蹤的發現」誠實揭露，但標題計數仍誤導
4. 若 PM 採信摘要標題、未獨立重跑，會把帶紅燈的 repo 當成 100% 綠通過

> 與 PC-135 區別：PC-135 是「環境不對稱致 pytest 過而 hook 子進程失敗」（兩環境結果不同）；本模式是「同一環境同一指令，摘要計數與實跑不符」（回報層失準）。

## 根因

1. **total 與 passed 語意混淆**：pytest 輸出 `X passed, Y failed in Zs`；代理人讀到測試檔總數或新增數，於摘要寫成「N passed」，未逐字引用實跑的 `X passed, Y failed` 行。
2. **可能以 deselect / 子集方式跑套件**：代理人為驗證自身新增測試，可能只跑新檔或 deselect 已知失敗項，得到的「全綠」非全套件全綠。
3. **記錄平面 ≠ 世界平面**（tool-output-trust 規則 5）：完成摘要是代理人的記錄平面陳述，與 filesystem 實跑的世界平面語意不對稱；摘要計數不可作為 ground truth。

## 影響

- PM 若採信摘要，repo 帶紅燈仍被當「100% 綠」收尾，違反 quality-baseline 規則 1。
- 紅燈可能 pre-existing（如本案 pull 端 YAML fail-loud 缺陷），被摘要的樂觀計數掩蓋而長期潛伏。
- 後續 ticket 在帶紅燈 baseline 上開發，污染 baseline（PC-168 假 baseline 連鎖崩塌的近鄰風險）。

## 解決方案

PM 驗收任何聲稱「測試通過」的 ticket 時，必須以固定值獨立重跑全套件，讀實跑的 `X passed, Y failed` 行而非採信摘要標題：

```bash
# 獨立重跑，讀末尾固定格式輸出（整數計數無法腦補）
uv run --with pytest python -m pytest <test_dir>/ -q 2>&1 | tail -4
# 判據：必須見 "N passed" 且無 "failed"；有 failed 即未達 100% 綠
```

- 數字不符即以實跑為準，不採信摘要。
- 發現 pre-existing 紅燈依 quality-baseline 規則 5 建 ticket 追蹤，並查證是否本 ticket 引入（固定值查 commit 變更檔案清單）。

## 預防措施

### 規則：完成摘要的測試計數必須逐字引用實跑輸出行

| 角色 | 動作 |
|------|------|
| 子代理人 | 摘要的測試結果欄逐字貼 pytest 末行（`X passed[, Y failed] in Zs`），不自行改寫為「N passed」；若有 deselect / 子集執行須明示 |
| PM 驗收 | 不採信摘要計數，獨立重跑全套件，讀實跑 `X passed, Y failed` 行；數字不符以實跑為準 |

### 派發 prompt 補強

派發測試相關 ticket 時，prompt 要求代理人「Test Results 欄逐字引用 pytest 末行，禁改寫計數；若 deselect 任何測試須明示理由」。

---

**Provenance**: 框架跨專案治理 wave 接手 session，W1-087 驗收時 PM 重跑全套件揪出摘要「187 passed」實為 186+1 failed。
