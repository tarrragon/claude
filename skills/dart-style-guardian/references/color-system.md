# Color System Reference

本檔是跨專案通用的顏色規則。下方的 `UIColors` 是示意類別名（見 `SKILL.md`〈Key Files〉後的說明）；每個專案的色票、亮暗數值與真實類別名不寫在這裡，寫在專案的設計文件、design system 原始檔與 `project-integration/` 落地層。

## 兩層 token

| 層 | 內容 | 畫面可以直接用嗎 |
|----|------|----------------|
| primitive | 固定色值（色階、品牌色），`static const`，不分亮暗 | 不行；只給語意層與主題組裝引用 |
| semantic | 依用途命名（surface、onSurface、error、warning…）；專案有暗色主題時亮暗各一組，掛在 `ThemeData.extensions` | 可以；畫面一律從這一層取色 |

專案有暗色主題時，畫面直接寫 `static const` 的色值，暗色主題不會切換，白底上的淺色字讀不到；這是兩層分開要擋的失敗。

## 依用途挑 token

| 用途 | 語意 token（示意名稱） |
|------|----------------------|
| 頁面底 / 面板 / 卡片 | `background` / `panel` / `surface` |
| 主要文字 / 次要文字 / 弱文字 | `onBackground` / `onSurface` / `onSurfaceMuted` |
| 焦點、連結、進度填色 | `primary`（其上的字 `onPrimary`） |
| 主動作的鍵面、選中反白 | `primaryStrong`（其上的字 `onPrimaryStrong`） |
| 選中、滑過的淡底 | `primaryContainer`（其上的字 `onPrimaryContainer`） |
| 失敗、錯誤、刪除、清空 | `error` / `errorContainer` / `onErrorContainer` |
| 提醒、注意、權限未授予、逾期 | `warning` / `warningContainer` / `onWarningContainer` |
| 成功、完成 | `success` / `successContainer` / `onSuccessContainer` |
| 分隔線、框線 | `border` / `borderStrong` |

前景色要跟它所在的底配對：放在 `xxxContainer` 上的字用 `onXxxContainer`，放在 `primary` 上的字用 `onPrimary`。

---

## 顏色歸類判準（error／warning／success 判不出來時）

分類依據是**元件本身傳達的狀態**，不是它所屬操作的業務後果：元件告訴使用者「失敗了」或「這個動作會破壞資料」就用 error；告訴使用者「需要注意、還沒完成」就用 warning；告訴使用者「完成了」就用 success。同一個操作前後出現的元件，各自依自己傳達的狀態分類。

【輸入】

```
情境：刪除按鈕觸發刪除動作；刪除完成後顯示「已刪除」提示；
      刪除前若有書籍還在借閱中，顯示「有 2 本借閱中」提醒
```

【產出】

```
形態：決策表

元件                       | 分類    | 理由
---------------------------|---------|------------------------------------------
刪除按鈕（觸發刪除動作）     | error   | 元件告訴使用者這個動作會破壞資料
「已刪除」完成提示           | success | 元件告訴使用者完成了，不因前置操作是刪除而改判
「有 2 本借閱中」提醒        | warning | 元件告訴使用者需要注意，沒有失敗也沒有破壞資料
```

【驗證】

```
檢驗問句
Q 分類依據是元件本身傳達的狀態，還是它所屬操作的業務後果？
  預期：元件本身傳達的狀態（判準段第一句）
Q 「已刪除」提示是否因跟隨一個刪除操作而改判 error？
  預期：否——它告訴使用者完成了，依判準段用 success
```

---

## 規則

- **錯誤與警告分開**：失敗與提醒用不同的 token。共用同一個顏色時，使用者分不出「操作失敗」與「需要注意」。
- **資料分類色不當強調色**：狀態、等級、類型這類資料分類，用專案定義的分類色組（前景與背景成對），不借用錯誤、警告或成功色；等級用同一色相的明度階梯，不用紅黃綠代表高中低。
- **對比**：文字 4.5:1、大字與非文字圖形（圖示、框線、進度條）3:1，專案有暗色主題時亮暗兩組都要達標。新增配對時先算對比，寫成測試（掛在主題上的 token、每組前景與背景）比只在文件註明可靠。
- **跟主題無關的固定色**：相機觀景窗、影片底這類不屬於介面配色的底，可以用固定的 primitive，在旁邊寫註解說明。
- **不靠色相單獨傳達資訊**：狀態除了顏色，還要有文字或圖示。

---

## Migration Guide

| 寫死 | 改成（示意名稱） |
|------|----------------|
| `Colors.white`（卡片底） | `UIColors.surface` |
| `Colors.white`（深色底上的字） | 該底的 `on*` token |
| `Colors.black87`、`Colors.grey[800]`（文字） | `UIColors.onBackground` 或 `UIColors.onSurface` |
| `Colors.grey[600]` | `UIColors.onSurfaceMuted` |
| `Colors.red` | `UIColors.error` |
| `Colors.orange`、`Colors.amber` | 依〈顏色歸類判準〉：失敗或破壞資料用 `UIColors.error`，提醒用 `UIColors.warning` |
| `Colors.green` | `UIColors.success` |
| `Colors.blue`、`Color(0xFF…)` | 依用途：`UIColors.primary`、`UIColors.primaryStrong` 或 `UIColors.primaryContainer` |
| `Colors.transparent` | 保留 |

`const` widget 吃到從 `context` 取來的顏色後要拿掉 `const`，只拿掉必要的那一層。沒有 `BuildContext` 的 helper（static 方法、getter）改成接收語意 token 物件或 `context`，並改所有呼叫點。

---

## Best Practices

1. **錯誤與警告分開** - 失敗用 `error`，提醒用 `warning`（〈顏色歸類判準〉）
2. **Avoid opacity modifiers** - Use pre-defined color variants（淡底用 `*Container` token）
3. **Use semantic names** - `UIColors.success` not `UIColors.green`
4. **Prefer theme colors** - Use `Theme.of(context).colorScheme` when available
5. **Test dark mode** - Ensure colors work in both themes

## Theme 與 Token 判準（〈Best Practices〉第 4 項「Prefer theme colors」與「一律用 token」的交界）

`SKILL.md`〈Key Files〉已定義 Theme 是「組裝 tokens 為 ThemeData 的入口」——Theme 的值來自 token，兩者不是互斥的兩套系統，判準是「Flutter 內建語意插槽是否已覆蓋這個 token 語意」。對應的內建語意插槽存在時用主題插槽，不存在時用 token。無法確定某語意是否有內建插槽時，查閱當前框架版本的 ColorScheme／TextTheme 官方欄位清單再判定，不憑記憶。

【輸入】

```
規則：Theme 由 token 組裝而成（SKILL.md〈Key Files〉「Theme」列）
情境：程式需要設定按鈕文字顏色為主要品牌色
```

【產出】

```
形態：決策表

情境                                    | 判定           | 理由
------------------------------------------|----------------|--------------------------------------------
內建主題插槽已覆蓋這個顏色語意             | 採用主題提供的對應插槽 | 主題由 token 組裝，兩者值一致，優先用內建插槽減少樣板碼
內建主題插槽未覆蓋這個顏色語意（如細分色階、專案自訂語意） | 直接採用元件庫顏色 token | 主題沒有這個語意插槽，繞過 token 會失去單一事實來源
```

【驗證】

```
檢驗問句
（本則驗證問句經非撰寫者兩輪複核仍無法由引文逐詞推出，已刪除；判定依據見本節判準段方向句）
```

附註（本專案語法查表，非三段鏈式範例本身；用途是讓讀者比對自己手上的 Dart 程式碼，不承載本判準的判定依據）：

```dart
// 內建主題插槽已覆蓋（ColorScheme.primary 對應 token 的 primary）
Theme.of(context).colorScheme.primary

// 內建主題插槽未覆蓋（例如 warning、success 這類 ColorScheme 沒有的語意）
UIColors.warning
```
