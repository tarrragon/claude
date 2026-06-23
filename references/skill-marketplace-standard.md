# Skill 獨立上架標準

本文件定義 Skill 獨立上架（Skill Market 發佈）的設計標準與檢查清單。適用於所有規劃進入 Skill Market 的 skill。

> **與 skill-design-guide 的關係**：`skill-design-guide` 定義 Skill 的結構、frontmatter、description 寫作等通用設計規範；本文件聚焦「獨立上架」這個額外維度——一個結構正確的 skill 不一定能獨立上架，因為它可能依賴特定專案環境。

---

## 1. 設計方向

### 1.1 單一職責

一個 skill 解決一個問題領域。

| 判準 | 通過 | 不通過 |
|------|------|--------|
| 能用一句話描述 skill 做什麼 | 「WRAP 決策框架——防護認知偏誤與倉促決策」 | 「做很多事情的工具」 |
| description 的觸發詞集中在同一問題域 | stuck, blocked, loop, 分析, debug | 混合 deploy + test + lint |
| 移除任一 reference 後 skill 核心功能仍完整 | reference 是「深度補充」 | reference 是「必要元件」 |

### 1.2 環境解耦

Skill 不假設特定專案環境存在。

| 假設類型 | 禁止 | 替代 |
|---------|------|------|
| 專案特定路徑 | `docs/work-logs/v0.18.0/` | `專案工作日誌目錄` |
| 專案特定 CLI | `ticket track claim W17-001` | `專案任務追蹤系統`（若存在） |
| 專案特定 Hook | `acceptance-gate-hook 會攔截` | 不依賴特定 Hook 存在 |
| 專案特定術語 | `W17-001`、`PC-093`、`skip-gate` | 通用描述或條件語（「若專案已採用 X」） |

**Why**：上架後使用者環境不可控——沒有你的 Hook 系統、沒有你的 ticket CLI、沒有你的 error-pattern 編號。硬編碼這些會讓 skill 在其他環境產生 dangling reference 或無意義的指令。

**Action**：專案特定的整合邏輯（Hook 掛鉤、CLI 接線、任務系統串接）放在專案內的落地層文件（如 `references/project-integration/`），不放進 skill 主體。

### 1.3 分類軸：依專案類型而非語言

skill 的 references 與內部分類應以**專案類型**（WEB / APP / 後端 / CLI）為軸，而非程式語言（JS / Dart / Go）。

**Why**：語言是實作工具，不決定設計考量。同一語言可橫跨多種專案類型——JavaScript 可寫 WEB 前端與 Node 後端，架構模式與效能瓶頸完全不同。真正決定考量的是專案類型的架構模式。

**Action**：skill 承載「判斷概念」（抽象原則、決策框架），不承載「實作方法」（具體怎麼寫）——方法因專案架構而異，屬各專案範疇。

---

## 2. Skill 獨立性設計原則

### 2.1 Companion Skill 缺席時優雅降級

Skill 引用其他 skill 時，必須假設該 companion skill 可能不存在於使用者環境。

| 禁止 | 替代 |
|------|------|
| 硬相對連結 `[x](../case-first/SKILL.md)` | 條件語「若專案已採用 case-first workflow」 |
| 直接綁特定環境識別符 | 通用化措辭 + 條件語 |
| `Read ../sibling-skill/references/x.md` | 說明概念，附「詳見 [skill-name] skill（若已安裝）」 |

**Why**：sync/回流到缺對應資產的專案後，硬連結成 dangling reference、環境識別符成找不到的對象。Skill 上架後使用者環境更不可控，獨立性是上架前提。

### 2.2 最小跨 Skill 依賴

盡量降低對其他 skill 的強依賴。

| 依賴類型 | 可接受性 | 說明 |
|---------|---------|------|
| 概念引用（「WRAP 框架建議先擴增選項」） | 可接受 | 讀者可自行查閱 |
| 條件觸發（「若專案已採用 X skill，可搭配使用」） | 可接受 | 降級為無 X 時仍可運作 |
| 強依賴（「必須先執行 /other-skill 才能使用」） | 避免 | 使 skill 無法獨立運作 |
| 隱性依賴（假設某 reference 已存在但不檢查） | 禁止 | 靜默失敗 |

### 2.3 不可拆分判準

真正成套運作的功能**不應拆成多個 skill**。

| 判準問題 | 答案為「是」→ 不該拆 |
|---------|---------------------|
| 拆開後，單獨一邊能否對使用者產生價值？ | 否 → 不該拆 |
| 兩者是否共享同一份 state 或同一個工作流步驟？ | 是 → 不該拆 |
| 使用者是否會只安裝其中一個？ | 不會 → 不該拆 |

**Why**：拆分不可分割的功能只會增加安裝摩擦和跨 skill 依賴管理成本，違反 §2.2 最小依賴原則。

---

## 3. 落地層架構

需要專案特定整合時，採用落地層分離：

```
your-skill/
├── SKILL.md                           # 通用規則（上架內容）
├── references/
│   ├── core-concepts.md               # 通用深度內容（上架內容）
│   └── project-integration/           # 專案落地層（不隨 skill 上架）
│       ├── pm-rules-map.md            # 專案任務系統整合
│       ├── triggers-alignment.yaml    # 專案 Hook 對齊
│       └── case-studies.md            # 專案特定案例
```

| 層 | 內容 | 上架時 |
|----|------|--------|
| 通用層（SKILL.md + references/） | 判斷概念、決策框架、通用範例 | 包含 |
| 落地層（references/project-integration/） | Hook 掛鉤、CLI 接線、專案術語映射、專案案例 | 排除 |

**Why**：通用層與落地層混合會使 skill 無法脫離原生專案獨立上架。分離後通用層可直接打包，落地層留在專案內。

---

## 4. 上架前檢查清單

### 4.1 環境無關性

- [ ] SKILL.md 和通用 references 無專案特定路徑（`docs/work-logs/`、`.claude/hooks/`）
- [ ] 無專案特定 ticket ID（`W17-001`、`PC-093`）或 error-pattern 編號
- [ ] 無專案特定 CLI 命令（`ticket track`、`npm run test:hooks`）
- [ ] 無專案特定 Hook 名稱（`acceptance-gate-hook`、`skip-gate`）
- [ ] 專案整合內容已分離至 `references/project-integration/`

### 4.2 獨立性

- [ ] 無硬相對連結指向同集姊妹 skill（`../other-skill/`）
- [ ] companion skill 缺席時不產生 dangling reference 或錯誤
- [ ] 不強依賴其他 skill（條件引用可接受，強依賴不可接受）
- [ ] 真正成套運作的功能未被拆分成多個 skill

### 4.3 分類與術語

- [ ] references 分類軸為專案類型（WEB/APP/後端）而非語言
- [ ] 承載判斷概念而非實作方法
- [ ] 術語通用化——不使用「在我們的專案中」「本框架」等自指表述

### 4.4 結構品質（與 skill-design-guide §12 交叉）

- [ ] SKILL.md body < 500 行
- [ ] description < 250 字且含觸發詞
- [ ] 無 README.md / CHANGELOG.md / INSTALLATION_GUIDE.md
- [ ] references 引用只一層深
- [ ] 無 skill 目錄內的設計過程紀錄或測試報告

---

## 5. 對照案例：wrap-decision

wrap-decision skill 是獨立上架設計的參考實作。

### 5.1 通用層設計

| 設計決策 | 做法 |
|---------|------|
| 開頭聲明獨立性 | 「本 SKILL 為通用 WRAP 規則，獨立於任何專案框架」 |
| 觸發條件通用化 | 以行為模式（連續失敗、被困住）而非專案事件描述 |
| 概念自包含 | W/R/A/P 四步驟在 SKILL.md 內完整定義，不依賴外部 skill |

### 5.2 落地層分離

| 檔案 | 層級 | 內容 |
|------|------|------|
| `SKILL.md` | 通用 | WRAP 框架定義、觸發條件、執行步驟 |
| `references/project-integration/pm-rules-map.md` | 落地 | 本專案 PM 規則與 WRAP 步驟的對應表 |
| `references/project-integration/triggers-alignment.yaml` | 落地 | 本專案 Hook 觸發與 WRAP 情境的對齊設定 |
| `references/project-integration/case-studies.md` | 落地 | 本專案實際案例（含專案 ticket ID） |

### 5.3 缺席降級示範

wrap-decision 被其他 skill 引用時的正確寫法：

| 禁止 | 正確 |
|------|------|
| 「執行 /wrap-decision 完成分析」 | 「以 WRAP 框架擴增候選方案（若專案已採用 wrap-decision skill，可執行 /wrap-decision）」 |
| 「依 `.claude/skills/wrap-decision/references/...` 查閱」 | 「擴增選項的方法論可參考 WRAP 決策框架」 |

---

## 相關文件

- `.claude/skills/skill-design-guide/SKILL.md` — Skill 通用設計規範（結構、frontmatter、description）
- `.claude/methodologies/knowledge-carrier-allocation-methodology.md` — 知識該寫進哪個載體
- `.claude/references/framework-asset-separation.md` — 框架資產 vs 專案產物分離

---

**Last Updated**: 2026-06-23
**Version**: 1.0.0 — 初版建立（1.3.0-W1-001 + W1-001.1 合併落地）
**Source**: W12-001 驗收 F 案外移規則需求 + W8-012 跨專案回流 dangling reference + memory feedback（skill 獨立性三準則）
