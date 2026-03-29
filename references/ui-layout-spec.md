# UI 排版設計規範

本文件定義 Flutter 前端的 UI 排版規則，確保所有元件在不同視窗尺寸下具備一致的佈局行為。

> **來源**：0.2.1-W4-001 — 專案頁籤溢出觸發全面排版規範建立。

---

## 1. 整體佈局結構

```
+------------------+-------------------------------+
|                  |                               |
|    Sidebar       |        Main Area              |
|   (Session List) |   (Session Detail / Chat)     |
|                  |                               |
|   固定寬度範圍    |        彈性填滿               |
|   280px 預設     |        Expanded               |
|                  |                               |
+------------------+-------------------------------+
```

| 區域 | 角色 | 寬度策略 |
|------|------|---------|
| Sidebar | Session 列表、搜尋、專案頁籤 | 固定範圍（可拖曳調整） |
| Main Area | Session 詳細內容、對話檢視 | 彈性填滿剩餘空間 |

**層級關係**：

```
Scaffold
  └── Row
        ├── SizedBox(width: sidebarWidth)  // Sidebar
        │     └── Column
        │           ├── SearchBar
        │           └── Expanded(TabBarView)
        └── Expanded                        // Main Area
              └── SessionDetailView
```

---

## 1.1 現有排版尺寸一覽（Source of Truth）

以下為目前實作中所有 UI 區域的具體尺寸，修改任何值時必須同步更新此表。

### 主畫面分割

| 區域 | 寬度 | 比例（以 1200px 視窗計算） | 常數 |
|------|------|--------------------------|------|
| Sidebar | 280px（固定） | ~23% | `DashboardConstants.sidebarWidth` |
| Divider | 1px | < 1% | `DashboardConstants.dividerWidth` |
| Main Area | 剩餘（~919px） | ~77% | `Expanded`（彈性填滿） |

### Sidebar 內部元件

| 元件 | 高度 | 寬度 | 常數 |
|------|------|------|------|
| ConnectionStatusBar | 由 padding 決定（v:8 + 文字行高） | 滿寬 280px | `DashboardConstants.connectionBarPadding` |
| SearchBar | ~40px（v:4 padding + 32 輸入框） | 滿寬 280px | `SearchConstants.barPadding` |
| 專案頁籤（Tab） | 46px（Material 預設） | 最大 160px | `SessionListConstants.tabMaxWidth` |
| TabBarView（Session 列表） | Expanded（填滿剩餘） | 滿寬 280px | — |
| Session ListTile | ~56px（Material ListTile 預設） | 滿寬 280px | Flutter Material 預設 |
| GroupHeader | 由 padding 決定（h:16, v:8） | 滿寬 280px | `SessionListConstants.groupHeaderPadding` |
| 狀態指示點 | 10x10px | — | `SessionListConstants.statusIndicatorSize` |

### Main Area 內部元件

| 元件 | 高度 | 寬度 | 常數 |
|------|------|------|------|
| PanelHeader | 由 padding 決定（v:4 + icon 18） | 滿寬 | `SplitViewConstants.headerPadding` |
| PanelHeader 按鈕 | 28x28px | — | `SplitViewConstants.headerButtonMinSize` |
| MessageBubble | 由內容決定 | margin h:8 | `ConversationConstants.bubbleMargin` |
| Bubble 內距 | 12px（四邊） | — | `ConversationConstants.bubbleContentPadding` |
| 搜尋 match count | 由 padding 決定 | h:8 padding | `SearchConstants.matchCountHorizontalPadding` |

### 視覺比例示意

```
|<------ 1200px 視窗 ------>|
|<- 280px ->|1|<-- 919px -->|
|  Sidebar   | |  Main Area  |
|   (23%)    | |   (77%)     |
|            | |             |
| [Tab|Tab|] | | [Header   ] |
| [Session ] | | [Bubble   ] |
| [Session ] | | [Bubble   ] |
| [Session ] | | [Bubble   ] |
```

---

## 2. 尺寸約束系統

### 2.1 Sidebar 約束

| 屬性 | 值 | 說明 |
|------|-----|------|
| 預設寬度 | 280px | 初始顯示寬度 |
| 最小寬度 | 200px | 拖曳縮小下限 |
| 最大寬度 | 400px | 拖曳放大上限 |

### 2.2 最小視窗尺寸

| 屬性 | 值 | 說明 |
|------|-----|------|
| 最小寬度 | 800px | 確保 Sidebar + Main 都可用 |
| 最小高度 | 500px | 確保列表和詳細內容都可見 |

### 2.3 元件尺寸約束

| 元件 | 約束 | 值 |
|------|------|-----|
| Tab（專案頁籤） | maxWidth | 160px |
| SessionListTile | height | 由內容決定，無固定高度 |
| SearchBar | height | 48px（Material 標準） |
| StatusIndicator | diameter | 10px |
| GroupHeader icon | size | 20px |

---

## 3. 間距系統

### 3.1 基準單位

**基準**：4px

所有間距必須為 4 的倍數：

| 名稱 | 值 | 用途 |
|------|-----|------|
| xxs | 2px | 圖示與文字間微距（例外，允許 2px） |
| xs | 4px | 緊湊元素間距 |
| sm | 8px | 同組元素間距 |
| md | 12px | 小區塊間距 |
| lg | 16px | 區塊間距、標準 padding |
| xl | 24px | 大區塊間距 |
| xxl | 32px | 頁面級間距 |

### 3.2 應用規則

| 場景 | 間距 | 值 |
|------|------|-----|
| GroupHeader 內距 | horizontal + vertical | 16px + 8px |
| GroupHeader icon-text 間距 | horizontal | 4px |
| ListTile 間距 | vertical | 由 ListTile 內建控制 |
| Tab 間距 | 由 TabBar 內建控制 | Material 預設 |
| SearchBar 與 TabBar 間距 | vertical | 0px（緊鄰） |

---

## 4. 溢出處理策略

### 4.1 策略類型

| 策略 | 說明 | 適用場景 |
|------|------|---------|
| 截斷（Ellipsis） | 超出寬度以 `...` 結尾 | 單行文字標籤 |
| 捲動（Scroll） | 可捲動檢視內容 | 列表、Tab 列 |
| 換行（Wrap） | 自動換行顯示 | 多行描述文字 |
| 收合（Collapse） | 摺疊/展開切換 | 分組標題 |

### 4.2 各元件溢出處理

| 元件 | 溢出策略 | 實作方式 |
|------|---------|---------|
| 專案頁籤（Tab） | 截斷 + 捲動 | `ConstrainedBox(maxWidth: 160)` + `isScrollable: true` |
| Session 標題 | 截斷 | `TextOverflow.ellipsis`, `maxLines: 1` |
| Session 摘要 | 截斷 | `TextOverflow.ellipsis`, `maxLines: 2` |
| 分組標題 | 截斷 | `TextOverflow.ellipsis`, `maxLines: 1` |
| Session 列表 | 捲動 | `ListView.builder` |
| 搜尋輸入 | 水平捲動 | TextField 內建行為 |

---

## 5. 文字截斷規範

### 5.1 截斷規則

| 規則 | 說明 |
|------|------|
| 使用 `TextOverflow.ellipsis` | 統一使用省略號截斷 |
| 設定 `maxLines` | 必須明確指定最大行數 |
| 搭配 `Tooltip` | 截斷的文字必須提供完整內容 Tooltip |

### 5.2 Tooltip 規則

| 場景 | Tooltip 內容 | 必要性 |
|------|-------------|-------|
| 專案頁籤 | 完整專案路徑 | 強制 |
| Session 標題 | 完整標題 | 建議（長標題時） |
| 路徑顯示 | 完整路徑 | 強制 |

---

## 6. 響應式設計規則

### 6.1 斷點定義

| 類別 | 寬度範圍 | 佈局策略 |
|------|---------|---------|
| compact | < 600px | Sidebar 隱藏，底部導航 |
| medium | 600px - 1200px | Sidebar 可收合 |
| expanded | > 1200px | Sidebar 常駐顯示 |

### 6.2 響應式行為

| 場景 | compact | medium | expanded |
|------|---------|--------|----------|
| Sidebar | 隱藏（Drawer） | 可收合 | 常駐 280px |
| Main Area | 全寬 | 全寬 - Sidebar | 全寬 - 280px |
| Tab 數量多 | 捲動 | 捲動 | 捲動 |

> 目前階段以桌面（expanded）為主，compact/medium 為未來擴展。

---

## 7. 元件約束檢查清單

新增或修改 UI 元件時，確認：

- [ ] 文字元素設定 `maxLines` 和 `TextOverflow.ellipsis`
- [ ] 截斷的文字提供 `Tooltip` 顯示完整內容
- [ ] 容器設定 `constraints`（minWidth/maxWidth/minHeight/maxHeight）
- [ ] 列表使用 `ListView.builder`（非 `Column + children`）
- [ ] 水平排列元素考慮溢出（`Flexible`/`Expanded`/`ConstrainedBox`）
- [ ] 間距值為 4 的倍數
- [ ] 數值常數提取到對應 Constants 類別

---

## 8. 專案頁籤溢出修復方案

### 8.1 問題

TabBar 中的 Tab 無最大寬度約束，長專案名稱佔滿 280px sidebar，其他 Tab 被推到不可見區域。

### 8.2 修復

| 項目 | 修改 |
|------|------|
| 常數 | `SessionListConstants.tabMaxWidth = 160.0` |
| Tab Widget | 包裹 `ConstrainedBox(maxWidth: 160)` |
| 截斷 | `TextOverflow.ellipsis` + `maxLines: 1` |
| Tooltip | 顯示完整專案路徑 |
| TabBar | `isScrollable: true` + `tabAlignment: TabAlignment.start` |

---

## 9. 常數檔案組織規則

| 常數類型 | 存放位置 |
|---------|---------|
| Session List 相關 | `session_list_constants.dart` |
| 全域佈局（Sidebar 寬度等） | `app_constants.dart` |
| 時間相關 | `duration_constants.dart` |
| 樣式數值 | `style_constants.dart` |

**命名規範**：

| 類型 | 命名模式 | 範例 |
|------|---------|------|
| 寬度 | `{element}Width` / `{element}MaxWidth` | `tabMaxWidth` |
| 高度 | `{element}Height` | `searchBarHeight` |
| 間距 | `{element}Padding` / `{element}Spacing` | `groupHeaderPadding` |
| 尺寸 | `{element}Size` | `statusIndicatorSize` |

---

## 10. 圓角與觸控區域

### 10.1 圓角半徑規範

| 層級 | 值 | 用途 |
|------|-----|------|
| sm | 4px | 小元件（Badge、Tag） |
| md | 8px | 卡片、輸入框 |
| lg | 12px | 對話框、面板 |
| xl | 16px | 大型容器 |

### 10.2 觸控區域規範

| 要求 | 值 | 說明 |
|------|-----|------|
| 最小觸控區域 | 28x28px | 桌面應用最低要求 |
| 建議觸控區域 | 48x48px | Material Design 標準（行動裝置） |

> 桌面應用以 28x28 為底線，行動裝置以 48x48 為目標。

---

## 相關文件

- ui/lib/core/constants/session_list_constants.dart - Session List 常數
- ui/lib/core/constants/app_constants.dart - 全域常數
- .claude/rules/core/quality-common.md - 通用品質基線（1.3 常數管理）

---

**Last Updated**: 2026-03-28
**Version**: 1.0.0 - 初始建立（0.2.1-W4-001）
