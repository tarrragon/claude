# 層級隔離派工 FAQ

**主文件**: [層級隔離派工方法論](./layered-ticket-methodology.md)

---

## 方法論理解

### Q1：為什麼一定要單層修改？

**短期**：多層一起改看起來快
**長期**：測試困難、Code Review 複雜、問題定位困難、回滾困難

**結論**：單層修改是風險管理，不是效率損失。

---

### Q2：Infrastructure 層如何處理？

Infrastructure 不在五層架構討論範圍，是獨立的技術實作任務。

```markdown
Ticket：[Infrastructure] 實作 SQLite Book Repository
依賴：實作 IBookRepository 介面（Layer 4）
```

---

### Q3：決策樹無法判斷時怎麼辦？

問自己「變更原因是什麼？」：
- 視覺變更 → Layer 1
- 互動變更 → Layer 2
- 業務流程變更 → Layer 3
- 契約變更 → Layer 4
- 業務規則變更 → Layer 5

如果仍無法判斷 → 職責不單一，需要拆分。

---

## 實務操作

### Q4：Ticket 粒度太小怎麼辦？

**合併原則**：
- 同一層級的小修改可以合併
- 變更原因相同可以合併

```markdown
❌ Ticket 1：修改按鈕顏色（1 行）
❌ Ticket 2：調整間距（2 行）

✅ Ticket：調整書籍詳情頁 UI 樣式
```

---

### Q5：粒度超出標準怎麼辦？

| 超出項目 | 處理方式 |
|---------|---------|
| 檔案數 > 5 | 強制拆分 |
| 程式碼 > 300 行 | 檢查重複邏輯 |
| 時間 > 1 天 | 重新評估複雜度 |

---

### Q6：內層還沒完成怎麼測試？

使用 Mock 或 Stub：

```dart
// Layer 2 開發時，Layer 3 尚未完成
class MockSearchBookUseCase implements SearchBookUseCase {
  Future<OperationResult<List<Book>>> execute(String query) async {
    return OperationResult.success([mockBook]);
  }
}
```

---

## 團隊協作

### Q7：團隊對五層架構理解不一致？

1. 組織架構培訓（1-2 小時）
2. Code Review 時加強溝通
3. 建立架構決策文件（ADR）
4. 定期架構回顧會議

---

### Q8：層級定位有爭議？

1. 使用決策樹客觀判斷
2. 團隊討論 15 分鐘
3. 架構師裁決
4. 記錄到 ADR

---

### Q9：多人開發同一功能？

**按層級分工**，使用 Mock 並行開發：

```text
Day 1：全員同時開始（各自用 Mock）
Day 2-4：逐層整合真實實作
Day 5：整合測試完成
```

---

## 品質衡量

### Q10：如何衡量執行品質？

| 指標 | 目標 |
|------|------|
| 單層修改率 | ≥ 90% |
| 粒度合規率 | ≥ 85% |
| 測試覆蓋率 | 100% |
| Review 時間 | ≤ 30 分鐘 |

---

## 參考資料

### 核心文獻

- **Clean Architecture** - Robert C. Martin
- **Domain-Driven Design** - Eric Evans
- **Test-Driven Development** - Kent Beck

### 專案方法論

- [TDD 四階段流程](../tdd-collaboration-flow.md)
- [敏捷重構方法論](./agile-refactor-methodology.md)
- [5W1H 決策方法論](./5w1h-self-awareness-methodology.md)

### 延伸閱讀

- Hexagonal Architecture - Alistair Cockburn
- Onion Architecture - Jeffrey Palermo
- Growing Object-Oriented Software, Guided by Tests

---

## Reference

- [層級隔離派工方法論](./layered-ticket-methodology.md) - 完整方法論
- [快速開始指南](./layered-ticket-quick-start.md) - 角色快速入門
- [層級檢查機制](./layered-architecture-quality-checking.md) - 品質檢查
- [實踐案例](./layered-ticket-examples.md) - 完整範例
