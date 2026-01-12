# 層級隔離快速開始指南

**主文件**: [層級隔離派工方法論](./layered-ticket-methodology.md)

---

## PM 快速開始

**目標**：學會拆分符合層級隔離原則的 Ticket

**4 步快速上手**：
1. 理解五層架構 → 閱讀 [五層架構定義](./layered-ticket-methodology.md#22-五層架構完整定義)
2. 使用決策樹 → 閱讀 [決策樹](./layered-ticket-methodology.md#24-判斷程式碼屬於哪一層的決策樹)
3. 按層級拆分 Ticket → 閱讀 [Ticket 範例](./layered-ticket-methodology.md#53-良好的-ticket-設計範例)
4. 檢查粒度標準 → 閱讀 [量化指標](./layered-ticket-methodology.md#52-量化指標定義)

**快速檢查清單**：
- [ ] 每個 Ticket 只修改單一層級？
- [ ] 檔案數在 1-5 個之間？
- [ ] 預估工時在 2-8 小時？
- [ ] 有明確的驗收條件？

---

## 開發人員快速開始

**目標**：執行符合層級隔離原則的單層修改

**4 步快速上手**：
1. 確認 Ticket 層級定位 → 檢查 Ticket 標題是否標明 [Layer X]
2. 遵循單層修改原則 → 閱讀 [單層修改原則](./layered-ticket-methodology.md#31-單層修改原則定義)
3. 遵循從外而內順序 → 閱讀 [從外而內實作](./layered-ticket-methodology.md#41-為什麼從外而內實作)
4. 確保測試通過 → 閱讀 [測試範圍分析](./layered-architecture-quality-checking.md#測試範圍分析法)

**開發前檢查清單**：
- [ ] 確認此 Ticket 只修改單一層級？
- [ ] 確認依賴的內層介面已存在？
- [ ] 準備好 Mock 或 Stub（如果內層未完成）？
- [ ] 測試檔案路徑對應層級結構？

**開發後檢查清單**：
- [ ] 所有測試 100% 通過？
- [ ] 沒有跨層直接呼叫？
- [ ] 依賴方向正確（外層依賴內層）？

---

## Code Reviewer 快速開始

**目標**：快速檢查 PR 是否符合層級隔離原則

**3 步快速檢查**：
1. 檢查單層修改原則 → 使用 [檔案路徑分析法](./layered-architecture-quality-checking.md#檔案路徑分析法)
2. 檢查測試覆蓋率 → 使用 [測試範圍分析法](./layered-architecture-quality-checking.md#測試範圍分析法)
3. 識別違規模式 → 參考 [違規模式識別](./layered-architecture-quality-checking.md#違規模式識別)

**Code Review 快速檢查清單**：
- [ ] 此 PR 是否只修改單一層級？（看檔案路徑）
- [ ] 依賴方向是否正確？（看 import 語句）
- [ ] 測試檔案路徑是否對應層級？（看 test/ 路徑）
- [ ] 測試覆蓋率是否達到 100%？

**快速判斷技巧**：
- **5 秒檢查**：看檔案路徑，判斷是否跨層
- **10 秒檢查**：看 import 語句，判斷依賴方向
- **30 秒檢查**：看測試檔案，判斷測試範圍

---

## Reference

- [層級隔離派工方法論](./layered-ticket-methodology.md) - 完整方法論
- [層級檢查機制](./layered-architecture-quality-checking.md) - 檢查工具和違規模式
- [實踐案例](./layered-ticket-examples.md) - 完整範例
- [常見問題 FAQ](./layered-ticket-faq.md) - Q&A 和參考資料
