---
# Design System 規格模板
# 複製本檔案到 docs/spec/ 並重新命名為 design-system-spec.md
# 用途：定義專案的統一視覺規格（配色、間距、圓角、陰影、字體、元件尺寸）

id: SPEC-DESIGN-SYSTEM
title: "UI Design System 規格"
status: draft                    # draft / review / approved / deprecated
source_proposal: null            # 來源提案 ID
created: "YYYY-MM-DD"
updated: "YYYY-MM-DD"
version: "1.0"
owner: ""
domain: ui
subdomain: design-system
related_usecases: []
related_specs: []
---

# UI Design System 規格

**版本**: 1.0
**建立日期**: YYYY-MM-DD
**最後更新**: YYYY-MM-DD
**來源**: {PROP-NNN 或設計決策來源}

---

## 1. 概述

{一段話描述本專案的設計系統範圍、核心風格和適用平台。}

**核心原則**：

| # | 原則 | 說明 |
|---|------|------|
| 1 | 三色系統 | {主色調佔比 / 正向色佔比 / 負面色佔比} |
| 2 | 語意化命名 | 命名反映使用意圖（action/confirm/caution），非視覺層級 |
| 3 | 平面化設計 | {設計風格描述} |
| 4 | 4px 網格 | 所有間距為 4 的倍數 |
| 5 | Single Source of Truth | 所有視覺值定義於集中目錄，其他檔案引用 |

**實作檔案結構**：

{依專案技術棧填入，參考「跨語言目錄結構對照」章節。}

---

## 2. 配色系統

### 2.1 主色調

| Token | 色值 | Dart/JS 對應 | 用途 |
|-------|------|-------------|------|
| `primary` | `#______` | {UIColors.primary / --color-primary} | {用途} |
| `primaryLight` | `#______` | | |
| `primaryDark` | `#______` | | |

### 2.2 正向色

| Token | 色值 | Dart/JS 對應 | 用途 |
|-------|------|-------------|------|
| `positive` | `#______` | | {成功、確認} |
| `positiveLight` | `#______` | | |

### 2.3 負面色

| Token | 色值 | Dart/JS 對應 | 用途 |
|-------|------|-------------|------|
| `negative` | `#______` | | {警告、錯誤} |
| `negativeLight` | `#______` | | |

### 2.4 背景與表面色

| Token | 色值 | Dart/JS 對應 | 用途 |
|-------|------|-------------|------|
| `background` | `#______` | | 頁面主背景 |
| `surface` | `#______` | | 卡片表面 |
| `onBackground` | `#______` | | 主文字色 |
| `onSurface` | `#______` | | 次要文字色 |

### 2.5 功能色（如適用）

| Token | 色值 | Dart/JS 對應 | 用途 |
|-------|------|-------------|------|
| | | | |

### 2.6 禁止配色

{列出禁止使用的色彩組合，例如：超出三色系統的色相、違反 WCAG 的低對比組合。}

---

## 3. 狀態配色（如適用）

### 3.1 配色對照表

{如 ReadingStatus、訂單狀態等業務狀態的 badge 配色。}

| 狀態 | 文字色（fg） | 背景色（bg） | WCAG AA 對比度 |
|------|------------|------------|---------------|
| | | | |

> WCAG AA 最低要求：正文 4.5:1、大字 3:1。對比度計算公式：(L1 + 0.05) / (L2 + 0.05)，L 為相對亮度。

---

## 4. 語意化按鈕系統

### 4.1 按鈕類型

| 類型 | 語意 | 背景色 | 文字色 | 使用場景 |
|------|------|--------|-------|---------|
| **action** | 一般操作 | `primary` | 白色 | 儲存、提交 |
| **confirm** | 正向確認 | `positive` | 白色 | 確認、完成 |
| **caution** | 警告操作 | `negative` | 白色 | 刪除、清除 |
| **neutral** | 中性資訊 | `primaryLight` | `primaryDark` | 取消、關閉 |
| **ghost** | 輔助低調 | 透明 | `primary` | 輔助連結 |

### 4.2 按鈕尺寸

| 尺寸 | 高度 | padding |
|------|------|---------|
| small | 36px | 4px 12px |
| medium（預設） | 48px | 8px 16px |
| large | 56px | 12px 24px |

---

## 5. 間距系統（基於 4px 網格）

| Token | 值 | Dart/JS 對應 | 用途 |
|-------|-----|-------------|------|
| `xxs` | 2px | | 最小間距 |
| `xs` | 4px | | 緊湊元素 |
| `sm` | 8px | | 按鈕 padding、元素間距 |
| `md` | 16px | | 標準內容間距 |
| `lg` | 24px | | 區塊間距 |
| `xl` | 32px | | 大區塊間距 |
| `xxl` | 48px | | 頁面級間距 |

---

## 6. 圓角系統

| Token | 值 | Dart/JS 對應 | 用途 |
|-------|-----|-------------|------|
| `xs` | 4px | | badge、tag |
| `sm` | 8px | | 按鈕、輸入框 |
| `md` | 12px | | 卡片 |
| `lg` | 16px | | 對話框 |
| `xl` | 20px | | 特大圓角 |

---

## 7. 字體系統

| Token | 值 | 用途 |
|-------|-----|------|
| `fontFamily` | {字體堆疊} | |
| `headline3` | 24px | 頁面標題 |
| `titleLarge` | 20px | 區塊標題 |
| `bodyMedium` | 14px | 標準內文 |
| `bodySmall` | 12px | badge 文字 |
| `caption` | 12px | 說明文字 |

字重定義：

| Token | 值 |
|-------|-----|
| `regular` | 400 |
| `medium` | 500 |
| `bold` | 700 |

---

## 8. 陰影系統

### 8.1 基礎陰影

| Token | 值 | 用途 |
|-------|-----|------|
| `card` | {box-shadow / BoxShadow 定義} | 卡片 |
| `button` | | 按鈕 |
| `floating` | | 浮動選單 |
| `dialog` | | 對話框 |

### 8.2 分割陰影（取代分隔線，如適用）

| Token | 值 | 用途 |
|-------|-----|------|
| `dividerSubtle` | | 細分隔 |
| `dividerNormal` | | 標準分隔 |

---

## 9. 元件尺寸

| 元件 | Small | Medium | Large |
|------|-------|--------|-------|
| 按鈕高度 | 36px | 48px | 56px |
| 輸入框高度 | - | 48px | 56px |
| 圖示 | 16px | 24px | 32px |

---

## 10. 常數配置策略

Design token 的程式碼配置位置依**消費者數量**決定：

| 消費者範圍 | 配置位置 | 範例 |
|-----------|---------|------|
| 僅 1 個 domain 使用 | `{domain}/constants/` | 某 feature 專屬的 badge 大小 |
| 跨 2+ domain 或跨層使用 | `core/design_system/`（Dart）或 `core/design-system/`（JS） | 色值、間距、圓角、陰影 |

**強制規則**：

- 所有 design token（色值、間距、圓角、陰影、字體）必須集中於 design system 目錄（Dart 用 `core/design_system/`，JS 用 `core/design-system/`）
- 禁止 design token 散落在各 feature 目錄
- 禁止跨層 import domain 常數（如 infrastructure 層 import domains/ 的常數）
- 純業務常數（如預設標籤名稱）不在本規則範圍，可留在所屬 domain

**判斷決策表**：

| 問題 | 是 | 否 |
|------|-----|-----|
| 此常數是否為視覺 token（色值/間距/圓角/陰影/字體）？ | 放 design system 集中目錄 | 繼續下題 |
| 此常數是否被 2+ domain 使用？ | 放 `core/` 對應子目錄 | 放所屬 `domain/constants/` |

**正確範例**：

```
lib/core/design_system/colors.dart    # 全專案色值 SSOT（Dart 用底線）
lib/domains/library/constants/tag_names.dart  # 僅 library domain 使用
```

**錯誤範例**：

```
lib/presentation/home/home_colors.dart  # 色值散落在 feature 目錄
lib/infrastructure/api/api_spacing.dart # 間距定義在 infrastructure 層
```

---

## 11. 跨語言目錄結構對照

不同技術棧的 design token 集中目錄慣例：

| 技術棧 | 集中目錄 | token 檔案形式 | import 方式 |
|--------|---------|---------------|------------|
| Flutter/Dart | `lib/core/design_system/` | `.dart` class（`static const`） | `import 'package:app/core/design_system/colors.dart'` |
| JS/TS（vanilla） | `src/core/design-system/` 或 `src/styles/tokens/` | `.ts` / `.js` export const | `import { colors } from '@/core/design-system'` |
| React | `src/theme/` 或 `src/design-tokens/` | theme object / CSS-in-JS | `import { theme } from '@/theme'` |
| Vue | `src/styles/tokens/` 或 `src/design-system/` | CSS custom properties / composable | `@use '@/styles/tokens'` |
| Electron | 同 React/Vue（renderer 端） | 同上 | 同上 |
| Chrome Extension | `src/core/design-system/` | `.js` export + CSS Variables | `import` + `var(--token)` |

**範本使用方式**：表格中的「Dart/JS 對應」欄填入各專案實際的 class/variable 名稱。例如：

- Flutter 專案填 `UIColors.primary`
- JS 專案填 `--color-primary` 或 `colors.primary`

---

## 12. 跨平台對齊（如適用）

{標注哪些 token 與其他平台共用、哪些是本平台獨有。}

| Token 類別 | 共用/獨有 | 說明 |
|-----------|----------|------|
| 配色系統 | 共用 | {與哪個平台共用} |
| 間距系統 | 共用 | |
| 元件尺寸 | 獨有 | {平台差異說明} |

---

## 13. 驗收標準

- [ ] design token 集中目錄存在且匯出完整 token
- [ ] 所有色值與跨平台基準一致（如適用）
- [ ] 現有硬編碼值替換為 token 引用
- [ ] ReadingStatus / 業務狀態 badge 使用本 spec 定義配色
- [ ] 語意化按鈕 class/widget 可用
- [ ] 測試中的色彩驗證引用 design-system 常數，非硬編碼值

---

## 變更歷史

| 版本 | 日期 | 變更內容 |
|------|------|---------|
| 1.0 | YYYY-MM-DD | 初始版本 |
