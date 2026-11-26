---
name: dart-style-guardian
description: "Dart／Flutter 專案樣式與文字的執法工具：掃出裸色碼、裸間距、裸字級、裸圓角與寫死文字，指出各自該改用哪個 token 或 i18n key，並以 PostEdit hook 擋下新增違規。觸發詞：裸值、硬編碼顏色、寫死文字、樣式違規、style guardian、token 沒用到、i18n 漏翻。Do NOT use for 建立 token 體系（用 foundation-design）或元件契約設計（用 component-contract-design）。"
metadata:
  version: 1.14.0
  category: ui-design
---

# Dart Style Guardian

掃出程式碼裡沒有走 design token 與 i18n 的地方，並指出每一處該改成什麼。

**產出是兩樣東西**：掃描器輸出的違規清單（檔案、行號、違規類別、建議改法、豁免計數），以及依該清單改完的程式碼。清單本身不是交付物——違規歸零或每一條剩餘違規都有豁免標記，才算做完。

**本 skill 只回答「不該怎麼做」。** 正面的「該怎麼做」分屬兩處：token 體系該有哪些階、怎麼命名，是 `foundation-design` 的 UI 維度；元件該有哪些契約欄位、容器怎麼承載排列，是 `component-contract-design`。被本 skill 擋下之後要查的是那兩處，不是本檔。元件層約束原則（禁自製元件、豁免三條件、白名單治理、WARNING 升阻擋判準）見 `.claude/methodologies/component-library-bidirectional-constraint-methodology.md`，本 skill 是它的「工具執法」層實作。

## 起手

**第一個動作是讀 `.claude/project-integration/dart-style-guardian.json`**，確認本專案的 token 類別名（`tokens` 欄位）與 i18n 存取子形態（`i18n.accessor`）。不先讀它就掃，拿到的建議會是「改用專案 design system 的 color token」這種無法直接照做的描述性敘述。

校準檔缺席時**不要自己編一組類別名**——指名一套不存在的命名，讀者照做會寫出編譯不過的程式碼。缺席的正確處置見〈Project Calibration〉。

確認之後跑掃描：

```bash
uv run .claude/skills/dart-style-guardian/scripts/style_checker.py scan lib/
```

## 全程

| 步 | 做什麼 | 在哪 |
|----|--------|------|
| 起手 | 讀校準檔，確認 token 類別名與 i18n 存取子 | 本檔上一節、〈Project Calibration〉 |
| 1 | 跑掃描，取得違規清單 | 〈Detection Script Usage〉 |
| 2 | 逐條對照違規類別，查該類的正確寫法 | 下方〈五類約束〉表 |
| 3 | 改碼；改不動而確有正當理由者加豁免標記 | 〈Common Violations and Fixes〉、〈Project Calibration〉的 `exempt_markers` |
| 4 | 重掃確認歸零，並確認豁免計數與你標的數量相符 | 〈Detection Script Usage〉 |

**步 3「正當理由」不是自行判斷即可成立**：豁免須滿足 `.claude/methodologies/component-library-bidirectional-constraint-methodology.md`〈豁免三條件〉（結構性無法收斂／記錄理由／列入工具白名單，AND 全滿足），且由 PM 於票驗收時核可；執行端不得自行認定滿足三條件就加標記。

## 五類約束與按需讀取

正文的五節給的是速查與判定；要改的東西落在邊界上、或要新增階與新寫法時，讀對應的完整規範。

| 約束類別 | 正文速查 | 完整規範 | 什麼時候要讀完整規範 |
|---------|---------|---------|-------------------|
| 顏色 | 〈Color System〉 | `references/color-system.md` | 要新增色階、判不出某個顏色該用哪個語意 token（例如錯誤還是警告），或要讓顏色跟著亮暗主題切換 |
| 間距 | 〈Spacing System〉 | `references/spacing-system.md` | 需要的值不在〈Spacing Scale〉的八階上，要判斷是該取近似值還是該加一階 |
| 字級 | 〈Typography System〉 | `references/typography-system.md` | 需要的值不在〈Type Scale〉離散階上，要判斷是該取近似值還是該加一階；或要加響應式字級、新字重，處理跨形態的字級縮放 |
| 圓角 | 〈Border Radius System〉 | 無獨立 reference，正文即全部 | — |
| i18n | 〈Internationalization (i18n)〉 | `references/i18n-guidelines.md` | 寫使用者可見文字、ViewModel 要回傳訊息、或要判斷某段文字算不算使用者可見 |

## 與相鄰資產的交界

執行時不需要先讀本節。不確定某件事該由本 skill 還是別處處理時再查。

| 相鄰資產 | 它管什麼 | 交界落在哪 |
|---------|---------|-----------|
| `foundation-design` skill | 地基入口與路由；token 體系是它 UI 維度的產物 | 本 skill 消費 token 名並執法，不決定該有哪些 token。**掃不到東西時先查這裡**——token 層還沒建，本 skill 的掃描範圍就是空的 |
| `component-contract-design` skill | 元件契約欄位表、容器排列不變式；**原生元件直用的定義與判定權威在此**（見其〈用詞〉「元件庫」邊界與方法論〈禁自製元件〉判準） | 本 skill 的五類約束（顏色／間距／字級／圓角／i18n）不含原生元件直用；PostEdit hook（`dart-style-guardian-hook.py`）另含八個 pattern 攔下新增的原生元件直用，但批次掃描腳本 `scripts/style_checker.py` 不偵測。定義與清點權威仍在 `component-contract-design` 的 step-3〈原生元件禁用對照表〉——hook 的 pattern 屬執法實作，不是定義權威。**組合層的重疊與截斷本 skill 也掃不到**，同樣要靠該 skill 的判別問句 |
| `ux-design-evaluation` skill | 畫面級狀態、回饋的時間門檻與通知形式 | 本 skill 只看程式碼字面，不判斷回饋設計是否合理。「按鈕沒有 loading 態」不是本 skill 的違規類別 |
| `version-bootstrap` skill 地基波 | 編排 i18n → design-system → UX 審查 → 元件庫四塊的順序 | 本 skill 是四塊完成後的常態執法層。**四塊未完成時先不要接 hook**——baseline 表達形式（違規計數上限或檔案清單白名單）見 `foundation-design/SKILL.md`〈工作流〉步驟 5「首次接入執法載體必然大量失敗」段，本檔〈Project Calibration〉不重複定義 |

## Core Principles

### Design Principles

偵測與修正建議跨專案通用；每個專案的視覺方向（色票、形狀、深度表達）由該專案的設計文件決定，本 skill 不替專案選風格。專案專屬的色票與取用方式放在專案的落地層（`project-integration/`）。

| Principle | Description |
|-----------|-------------|
| Single source of truth | 顏色、間距、字級、圓角只在 design system 定義一次，畫面引用 token |
| Semantic over primitive | 畫面引用語意 token（surface、onSurface、error、warning…），不直接引用色階或色值 |
| Theme-aware | 顏色從當前主題取（例如掛在 ThemeData 的 `ThemeExtension`，經 `context` 存取），亮暗主題才會一起切換；`static const` 的色值只當 primitive |
| Error ≠ warning | 錯誤與警告用不同的 token，畫面分得出失敗與提醒 |
| Contrast | 文字 4.5:1、非文字圖形 3:1（WCAG 2.1 AA），亮暗兩組都要達標 |

### Key Files

檔案位置因專案而異，故以角色描述而非路徑列出——寫死某專案的路徑，其他專案讀到的就是一份指向不存在檔案的清單。實際位置見 `.claude/project-integration/dart-style-guardian.json` 的 `tokens` 欄位所指的類別，以及專案的 `l10n.yaml`。

| Role | 內容 |
|------|------|
| Design system tokens | 顏色、間距、字級、圓角的 SSOT；掃描器據此判定何謂「已使用 token」 |
| Theme | 組裝 tokens 為 ThemeData 的入口 |
| Localization 設定 | `l10n.yaml` 決定 ARB 位置與存取子形態 |
| UI 設計規格 | 設計稿與元件規範文件（如有） |

---

**下方〈Color System〉〈Spacing System〉〈Typography System〉〈Border Radius System〉〈Common Violations and Fixes〉〈Quick Reference Card〉出現的 `UIColors`／`UISpacing`／`UIFontSizes`／`UIBorderRadius` 一律是示意類別名，不是本專案的真實類別**——本 skill 為跨專案共用資產，正文用統一的示意名稱維持表格可讀，實際類別名以 `.claude/project-integration/dart-style-guardian.json`〈Project Calibration〉的 `tokens` 欄位為準：套用建議寫法時，把示意類別名換成該欄位對應的真實類別，階名（`primary`／`md`／`bodyMedium` 等）若校準檔沒有另外覆寫則沿用正文所列。

## Color System

寫死的顏色（`Colors.*`、`Color(0x…)`）一律換成語意 color token。依**用途**挑 token，不是依色相：

| 用途 | 語意 token（示意名稱） |
|------|----------------------|
| 頁面底 / 面板 / 卡片 | `UIColors.background` / `UIColors.panel` / `UIColors.surface` |
| 主要文字 / 次要文字 / 弱文字 | `UIColors.onBackground` / `UIColors.onSurface` / `UIColors.onSurfaceMuted` |
| 焦點、連結、進度 | `UIColors.primary` |
| 主動作的鍵面、選中反白 | `UIColors.primaryStrong` |
| 失敗、錯誤、刪除 | `UIColors.error` / `UIColors.errorContainer` / `UIColors.onErrorContainer` |
| 提醒、注意、權限未授予 | `UIColors.warning` / `UIColors.warningContainer` / `UIColors.onWarningContainer` |
| 成功、完成 | `UIColors.success` / `UIColors.successContainer` / `UIColors.onSuccessContainer` |
| 分隔線、框線 | `UIColors.border` / `UIColors.borderStrong` |

- 錯誤與警告不共用顏色。
- 資料分類（狀態、等級、類型）用專案定義的分類色，不借用錯誤或警告色。
- 專案有亮暗兩個主題時，語意 token 要從當前主題取（`ThemeExtension`），不從 `static const` 取；`static const` 的寫法在暗色主題不會切換。
- 跟主題無關的固定色（例如相機觀景窗的深色底）可以用 primitive，但要寫註解說明。

判不出該用哪個 token、或要新增色階時，讀 `references/color-system.md`。

---

## Spacing System (4dp Grid)

### SizedBox Spacing

`UISpacing.<階>` 是基礎常數，不含方向或尾綴；需要響應式縮放時依方向外加尾綴（垂直 `.h`、水平 `.w`），完整規則見 `references/spacing-system.md`〈UISpacing Constants〉。

| Hardcoded | UISpacing |
|-----------|-----------|
| `SizedBox(height: 4)` | `SizedBox(height: UISpacing.xxs.h)` |
| `SizedBox(height: 8)` | `SizedBox(height: UISpacing.xs.h)` |
| `SizedBox(height: 12)` | `SizedBox(height: UISpacing.sm.h)` |
| `SizedBox(height: 16)` | `SizedBox(height: UISpacing.md.h)` |
| `SizedBox(height: 24)` | `SizedBox(height: UISpacing.lg.h)` |
| `SizedBox(height: 32)` | `SizedBox(height: UISpacing.xl.h)` |
| `SizedBox(width: 8)` | `SizedBox(width: UISpacing.xs.w)` |

### EdgeInsets Padding

| Hardcoded | UISpacing |
|-----------|-----------|
| `EdgeInsets.all(4)` | `EdgeInsets.all(UISpacing.xxs.w)` |
| `EdgeInsets.all(8)` | `EdgeInsets.all(UISpacing.xs.w)` |
| `EdgeInsets.all(16)` | `EdgeInsets.all(UISpacing.md.w)` |
| `EdgeInsets.symmetric(horizontal: 16)` | `EdgeInsets.symmetric(horizontal: UISpacing.md.w)` |
| `EdgeInsets.symmetric(vertical: 8)` | `EdgeInsets.symmetric(vertical: UISpacing.xs.h)` |

---

## Typography System

### Font Sizes

| Hardcoded | UIFontSizes | Purpose |
|-----------|-------------|---------|
| `fontSize: 10` | `UIFontSizes.overline` | Overline text |
| `fontSize: 12` | `UIFontSizes.bodySmall` | Small body text |
| `fontSize: 14` | `UIFontSizes.bodyMedium` | Standard body text |
| `fontSize: 16` | `UIFontSizes.bodyLarge` | Large body text |
| `fontSize: 18` | `UIFontSizes.titleMedium` | Medium titles |
| `fontSize: 20` | `UIFontSizes.titleLarge` | Large titles |
| `fontSize: 24` | `UIFontSizes.headline3` | Headlines |

### Responsive Font Sizes

優先使用 `UIFontSizes` token（getter 已內建 `.rsp`）。token 涵蓋不到的自訂字級才手動加 `.rsp`，完整判準見 `references/typography-system.md`〈Manual Responsive Text〉。

```dart
// Correct
TextStyle(fontSize: UIFontSizes.bodyMedium)  // Already includes .rsp
TextStyle(fontSize: 14.rsp)  // token 涵蓋不到時的正確手動寫法

// Incorrect
TextStyle(fontSize: 14)      // 未縮放
TextStyle(fontSize: 14.sp)   // 尾綴錯誤，非本專案的縮放機制
```

---

## Border Radius System

| Hardcoded | UIBorderRadius |
|-----------|----------------|
| `BorderRadius.circular(4)` | `BorderRadius.circular(UIBorderRadius.xs)` |
| `BorderRadius.circular(8)` | `BorderRadius.circular(UIBorderRadius.sm)` |
| `BorderRadius.circular(12)` | `BorderRadius.circular(UIBorderRadius.md)` |
| `BorderRadius.circular(16)` | `BorderRadius.circular(UIBorderRadius.lg)` |
| `BorderRadius.circular(20)` | `BorderRadius.circular(UIBorderRadius.xl)` |
| `BorderRadius.circular(999)` | `BorderRadius.circular(UIBorderRadius.circular)` |

專案的設計若是全部直角，直接寫 `BorderRadius.zero`，不必取 token。

---

## Internationalization (i18n)

所有使用者可見文字必須取自 ARB 產生的 localization 類別，禁止硬編碼字串。存取方式依專案的 `l10n.yaml` 設定而定，常見兩種：`AppLocalizations.of(context).keyName`（`nullable-getter: false`）或 `context.l10n!.keyName`（專案自建 extension）。動手前先讀專案的 `l10n.yaml` 與既有呼叫點確認慣例，勿沿用他專案的寫法。

**元件庫內建預設文案的 key 由誰擁有，本節不判定**——這是設計層問題，判準見 `.claude/methodologies/component-library-bidirectional-constraint-methodology.md`〈元件文字歸屬（i18n-first）〉的三條件 AND（走 i18n 系統非字面／參數可覆蓋／key 列入元件 API 契約）。本 skill 只確認呼叫端是否已改用 localization 存取，不判斷該 key 該掛在元件還是呼叫端名下。

**掃描器對元件庫目錄的既知盲區**：`scripts/style_checker.py` 的 `EXCLUDE_PATTERNS` 排除 `/design_system/`（或功能對等的目錄名）等整檔略過的路徑；元件庫實作若落在被排除的目錄，其內建預設文案不會被本掃描器檢查，i18n-first 是否合規需人工核對，不能以「掃描通過」當作已驗證。

---

## Common Violations and Fixes

### Violation 1: Hardcoded Colors

```dart
// Violation
Container(color: Colors.blue)
Container(color: Color(0xFF2196F3))

// Fix
Container(color: UIColors.primary)
// 有亮暗主題時，從掛在主題上的語意 token 取（存取子名稱依專案而定）
Container(color: Theme.of(context).extension<UIColors>()!.primary)
```

### Violation 2: Hardcoded Spacing

```dart
// Violation
SizedBox(height: 16)
Padding(padding: EdgeInsets.all(8))

// Fix
SizedBox(height: UISpacing.md)
Padding(padding: EdgeInsets.all(UISpacing.xs))
```

### Violation 3: Hardcoded Font Size

```dart
// Violation
TextStyle(fontSize: 14)

// Fix
TextStyle(fontSize: UIFontSizes.bodyMedium)
```

### Violation 4: Hardcoded Border Radius

```dart
// Violation
BorderRadius.circular(8)

// Fix
BorderRadius.circular(UIBorderRadius.sm)
BorderRadius.zero // 直角設計
```

### Violation 5: Hardcoded Text

使用者可見文字直接寫在 widget 內，未取自 ARB。`style_checker.py scan` 以 `[i18n]` 標記回報這類違規；修正方式是把字串移入 ARB 檔並改以 localization 類別存取（存取語法見上方 Internationalization 節）。

### Violation 6: ViewModel Hardcoded User Messages

**Scope**: `lib/presentation/**/viewmodel.dart`, `lib/presentation/**_viewmodel.dart`

**Detection Pattern**: String literals assigned to error/message state properties

ViewModel 不持有 `BuildContext`，不可呼叫 `context.l10n!`。錯誤狀態只存錯誤碼或例外物件，翻譯留給持有 context 的呈現層以 `ErrorHandler` 轉譯（分層規則呼應 `references/i18n-guidelines.md`〈Violation 2〉）。

```dart
// Violation - Hardcoded user messages in ViewModel
state = state.copyWith(errorMessage: 'Invalid file format');
state = state.copyWith(errorMessage: '網路連線失敗');
_errorMessage = 'Something went wrong';

// Fix - ViewModel 只存錯誤碼，不在此處翻譯
state = state.copyWith(errorCode: AppErrorCode.invalidFileFormat);

// Fix - 呈現層持有 context，在此處轉譯後才顯示
Text(ErrorHandler.getUserMessage(context, state.errorCode))
```

**Allowed Exceptions**:
- `e.toString()` for unknown system exceptions（僅供記錄，不對使用者顯示）

**Related**（Flutter 專案適用）: ViewModel 層使用者訊息規範見專案根目錄 `FLUTTER.md`（僅 Flutter 專案存在；非 Flutter 專案略過 Violation 6）

---

## Project Calibration

偵測規則本身跨專案通用（硬編碼的顏色、間距、字級一律該進 design system），但**替代方案的名字是專案專屬的**。校準檔告訴掃描器本專案的詞彙：

`.claude/project-integration/dart-style-guardian.json`

```json
{
  "tokens": {
    "color": "AppPalette",
    "spacing": "AppSpacing",
    "font_size": "AppTypography",
    "border_radius": "AppRadius"
  },
  "i18n": {
    "accessor": "AppLocalizations.of(context).keyName",
    "compliance_pattern": "AppLocalizations\\.of\\("
  },
  "exempt_markers": ["magic-exempt", "i18n-exempt"]
}
```

| 欄位 | 作用 |
|------|------|
| `tokens.*` | 修正建議指名的類別；同時作為「此行已合規」的判定依據 |
| `i18n.accessor` | i18n 建議中顯示的存取語法 |
| `i18n.compliance_pattern` | 判定該行已使用 localization 的正則 |
| `exempt_markers` | 行內註解含此標記即豁免，並計入報告的 exempt 計數 |

**缺此檔時**：掃描器仍偵測硬編碼，但建議改為描述性敘述（「改用專案 design system 的 color token」），並在 stderr 提示。這是刻意的——指名某套命名等於斷言它是對的，而讀者照著不存在的類別動手會寫出編譯不過的程式碼。

**豁免的可見性**：被標記豁免的行不列為違規，但計數會出現在報告（`Exempt (marked in source): N`）。靜默略過的行與掃描器看不見的行無法區分，讀者也就無從判斷標記是否真的生效。

**兩種略過機制不是同一件事，不要混用**：`exempt_markers`（`magic-exempt`、`i18n-exempt`）與行內的 `// OK:`、`// ignore:` 都會讓那一行不被列為違規，但可見度不同——`exempt_markers` 命中會計入上面〈豁免的可見性〉的 exempt 計數，出現在報告裡；`// OK:`／`// ignore:` 屬於「視為該行已合規」的判斷（與校準檔 `tokens.*` 類別名同一機制），命中即整行跳過，**不計入任何計數**，報告上完全看不到痕跡。需要「這裡不是違規，但我要留下可稽核的紀錄」時用 `exempt_markers`；只是「這行本來就合規、掃描器判斷失準」時才用 `// OK:`／`// ignore:`。

**單一規則來源**：PostEdit hook（`.claude/hooks/dart-style-guardian-hook.py`）匯入 `style_checker` 的規則與校準，不另維護一份。兩套規則各自演化的結果是 hook 與 skill 給出互相矛盾的建議。

---

## Detection Script Usage

### Manual Scan

```bash
# Scan entire project
uv run .claude/skills/dart-style-guardian/scripts/style_checker.py scan lib/

# Scan specific directory
uv run .claude/skills/dart-style-guardian/scripts/style_checker.py scan lib/presentation/

# Generate report
uv run .claude/skills/dart-style-guardian/scripts/style_checker.py report
```

### Hook Integration

The style checker is integrated into PostEdit Hook:
- Automatically scans edited files in `lib/presentation/`
- Reports violations in hook output
- Suggests fixes based on this guide

---

## Related Documentation

### Project Files

同上節，以角色而非路徑指涉：design system token 定義、theme 組裝入口、`l10n.yaml` 與其指向的 ARB、設計規格文件。要知道本專案的實際位置，讀 `.claude/project-integration/dart-style-guardian.json` 與 `l10n.yaml`，或直接搜尋 token 類別名的定義處。

### Reference Files (in this SKILL)

四份，各自該在什麼時候讀見本檔上方〈五類約束與按需讀取〉表——此處只列存在，不重複判準：
`references/color-system.md`、`references/spacing-system.md`、`references/typography-system.md`、`references/i18n-guidelines.md`。

### External Resources
- [Material Design 3 Color System](https://m3.material.io/styles/color/overview)
- [WCAG 2.1 Contrast (Minimum)](https://www.w3.org/WAI/WCAG21/Understanding/contrast-minimum.html)
- [Flutter ThemeExtension](https://api.flutter.dev/flutter/material/ThemeExtension-class.html)

---

## Quick Reference Card

### Common Replacements

| Type | Hardcoded | Configuration |
|------|-----------|---------------|
| **Color** | `Colors.blue` | `UIColors.primary` |
| **Success** | `Colors.green` | `UIColors.success` |
| **Error** | `Colors.red` | `UIColors.error` |
| **Warning** | `Colors.orange` | `UIColors.warning` |
| **Spacing** | `16` | `UISpacing.md` |
| **Font** | `14` | `UIFontSizes.bodyMedium` |
| **Radius** | `8` | `UIBorderRadius.sm` |
| **Text** | `'My Library'` | `context.l10n!.libraryTitle` |

### Responsive Suffixes

| Suffix | Purpose | Example |
|--------|---------|---------|
| `.w` | Width scaling | `16.w` |
| `.h` | Height scaling | `16.h` |
| `.rsp` | Font scaling | `14.rsp` |
| `.r` | Radius scaling | `8.r` |

---

版本紀錄在同目錄的 `CHANGELOG.md`。
