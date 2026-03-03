# RelatedTo 欄位功能說明

## 概述

`relatedTo` 是 Ticket 系統中用於表達多對多關聯的新欄位。它用於標記與當前 Ticket 相關但非層級關係的其他 Ticket。

## 與現有欄位的區別

| 欄位 | 關係類型 | 執行順序 | 用途 |
|------|---------|--------|------|
| `parent_id` | 層級（一對一） | 強制順序 | 子任務必須在父任務之後 |
| `children` | 層級（一對多） | 強制順序 | 父任務必須在子任務之前 |
| `blockedBy` | 依賴（阻塞） | 強制順序 | 當前 Ticket 被其他 Ticket 阻塞 |
| `relatedTo` | 關聯（資訊性） | 無強制順序 | 與其他 Ticket 有關聯但無執行順序限制 |

## 使用場景

### 共用模組場景

當多個功能都使用同一個共用模組時：

```
功能 A（實作 BookRepository）
  ↓
共用模組（BookRepository 可用）
  ↑ ↑
功能 B （使用 BookRepository）
功能 C （使用 BookRepository）
```

此時：
- A 和 B 沒有 `blockedBy` 關係（B 不必等 A 完成才能開始實作其他部分）
- 但 A 和 B 有 `relatedTo` 關聯（A 建立了 B 依賴的共用模組）

**Ticket 設置**：
- 0.31.0-W5-001（A - 實作 BookRepository）: `relatedTo: ["0.31.0-W5-002", "0.31.0-W5-003"]`
- 0.31.0-W5-002（B - 實作 Book 功能）: `relatedTo: ["0.31.0-W5-001"]`
- 0.31.0-W5-003（C - 實作 Author 功能）: `relatedTo: ["0.31.0-W5-001"]`

### 參考實作場景

當一個 Ticket 在實作時參考了另一個 Ticket 的成果：

- 0.31.0-W5-001: 實作通用 UI 組件
- 0.31.0-W5-002: 實作新頁面（使用通用 UI 組件）

此時 0.31.0-W5-002 的 `relatedTo` 可包含 `0.31.0-W5-001`

## 使用方式

### 建立 Ticket 時指定 relatedTo

```bash
uv run ticket create \
  --action "實作" \
  --target "新功能" \
  --wave 5 \
  --related-to "0.31.0-W5-001,0.31.0-W5-003"
```

相關 ID 用逗號分隔，無需空格。

### 在 Ticket YAML 中查看

```yaml
---
id: "0.31.0-W5-002"
title: "實作新功能"
relatedTo:
  - "0.31.0-W5-001"
  - "0.31.0-W5-003"
```

## 驗證規則

`validate_related_to()` 函式會進行以下驗證：

1. **格式驗證**: 每個 ID 必須符合 Ticket ID 格式
2. **自我參考檢查**: 不能指向當前 Ticket
3. **重複檢查**: 不能包含重複的 ID
4. **空值處理**: `None` 或空清單自動通過

### 驗證範例

```python
from ticket_system.lib.ticket_validator import validate_related_to

# 有效的關聯
valid, msg = validate_related_to("0.31.0-W5-001", ["0.31.0-W5-002", "0.31.0-W5-003"])
# 返回: (True, None)

# 無效：自我參考
valid, msg = validate_related_to("0.31.0-W5-001", ["0.31.0-W5-001"])
# 返回: (False, "自我參考錯誤訊息")

# 無效：格式錯誤
valid, msg = validate_related_to("0.31.0-W5-001", ["invalid-id"])
# 返回: (False, "無效的 Ticket ID 錯誤訊息")
```

## 技術詳解

### 資料結構

Ticket frontmatter 中的 `relatedTo` 是字串列表：

```python
class TicketConfig(TypedDict, total=False):
    related_to: Optional[List[str]]  # 相關的 Ticket IDs（多對多關聯）
```

### 前置值設定

建立新 Ticket 時，若未指定 `relatedTo`，預設為空清單：

```python
"relatedTo": config.get("related_to") or []
```

### 單向 vs 雙向

`relatedTo` 是單向的，類似於 `blockedBy`。

如果 A 和 B 有雙向關聯，需要在兩個 Ticket 中都設定：
- A 的 `relatedTo` 包含 B
- B 的 `relatedTo` 包含 A

## 注意事項

1. **執行順序**: `relatedTo` 不影響任務執行順序。系統不會自動排序或等待相關 Ticket
2. **資訊性**: `relatedTo` 主要用於文件和溝通，不被系統邏輯使用
3. **維護責任**: 當 Ticket 完成或刪除時，引用它的 Ticket 不會自動更新
4. **最佳實踐**: 若真正存在執行順序依賴，應使用 `blockedBy` 而非 `relatedTo`

## 測試覆蓋

### Ticket Builder 測試

- `test_create_ticket_frontmatter_with_related_to`: 驗證 relatedTo 正確添加到 frontmatter
- `test_create_ticket_frontmatter_empty_related_to`: 驗證預設空清單

### Ticket Validator 測試

- `test_validate_related_to_none`: None 值驗證
- `test_validate_related_to_empty_list`: 空清單驗證
- `test_validate_related_to_valid_single/multiple`: 有效 ID 驗證
- `test_validate_related_to_invalid_id`: 格式檢查
- `test_validate_related_to_self_reference`: 自我參考檢查
- `test_validate_related_to_duplicate`: 重複檢查

所有測試都通過，覆蓋率達到 100%。

## 版本資訊

- **實作版本**: 0.31.0-W7-005
- **檔案修改**:
  - `ticket_system/lib/ticket_builder.py`: 新增 TicketConfig 欄位和 frontmatter 初始化
  - `ticket_system/lib/ticket_validator.py`: 新增 validate_related_to() 函式
  - `ticket_system/commands/create.py`: 新增 --related-to 命令行參數
  - `tests/test_ticket_builder.py`: 新增 2 個測試
  - `tests/test_ticket_validator.py`: 新增 9 個測試

## 相關連結

- [Ticket 系統文件](./SKILL.md)
- [Ticket Builder 測試](./tests/test_ticket_builder.py)
- [Ticket Validator 測試](./tests/test_ticket_validator.py)
