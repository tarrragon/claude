# 本專案 pm-rules 索引（WRAP 相關）

本文件索引 `.claude/pm-rules/` 中與 WRAP 決策框架銜接的規則檔案。

> **讀取原則**：遇到 WRAP 觸發場景時，先讀 SKILL.md（通用原理）；遇到本專案特定情境（Ticket claim、incident、個人化建議、提案評估）時，讀對應的 pm-rules 檔案取得可執行規格。

---

## 核心銜接規則

| pm-rules 檔案 | WRAP 銜接 | 為何存在 |
|--------------|----------|---------|
| `decision-tree.md` | 觸發條件權威來源 | 收束 SKILL/本專案觸發清單，避免 DRY 違反（PC-066） |
| `personalized-advice-rules.md` | Step 0 個人化建議落地 | PC-071 三層機制（識別/分級/誠實） |
| `incident-response.md` 的「Reality Test 閘門」章節 | R 階段強制前置 | PC-063 防護（禁止未重現實驗就列方案） |
| `proposal-evaluation-gate.md` | 完整 WRAP 強制場景 | 提案評估前必須跑完整 WRAP |

---

## 觸發條件整合

**權威來源**：`decision-tree.md` 中的 WRAP 觸發表格指向以下檔案：
- SKILL.md 的「觸發條件」章節（抽象類別）
- `.claude/config/wrap-triggers.yaml`（機器可讀）
- 本目錄 `triggers-alignment.md`（三層對應）

pm-rules 其他檔案若需引用 WRAP 觸發條件，應**指向上述權威來源**，不複述清單（DRY 原則，PC-066 教訓）。

---

## Reality Test 閘門（PC-063 防護 2/4）

`incident-response.md` 的 Reality Test 閘門章節（W5-034 建立）為 ANA/incident-response/WRAP Widen 三類流程的共同前置閘門：

**核心規則**：分析階段中，**禁止在未完成重現實驗前列候選方案**。

觸發條件：
- WRAP Widen 階段提出方案前未完成重現 → 強制閘門
- WRAP Widen 收斂於同質假設變體 → 強制閘門（偽 Widen 警示）

WRAP W 階段若觸發此閘門，回到 R 階段執行重現實驗，才能繼續 W 階段列方案。

完整規格見 `incident-response.md` 該章節。本目錄的 `pseudo-widen-guard.md` 為此閘門的「WRAP 視角」說明。

---

## 反覆失敗處理

`incident-response.md` 規定：反覆失敗 3 次以上 → 執行 `/wrap-decision`（快速模式）重新擴增選項。

此規定對應 SKILL 的「連續失敗」觸發類別 + YAML 的 `consecutive_failures` 訊號。

---

## 個人化建議（PC-071 落地）

`personalized-advice-rules.md` 為 Step 0 資料充足度在個人化建議場景的完整實作。

詳細銜接說明見本目錄的 `personalized-advice.md`。

---

## 提案評估

`proposal-evaluation-gate.md` 規定提案進入開發前必須執行完整 WRAP（含 R 階段）。對應 SKILL 的「提案評估」觸發類別。

---

## 方法論層級（非強制規則）

本專案的 methodologies 目錄包含方法論說明（非強制規則）：

| 檔案 | 內容 |
|------|------|
| `.claude/methodologies/friction-management-methodology.md` | 摩擦管理方法論（包含 WRAP 在摩擦決策中的使用） |
| `.claude/methodologies/personalized-consultation-methodology.md` | 個人化諮詢方法論（PC-071 衍生） |

方法論提供思考框架與脈絡，不是強制規則；強制規則由 pm-rules/ 與 SKILL 定義。

---

## error-patterns 交叉引用

以下 PC（process-compliance）error-patterns 與 WRAP 有直接關聯：

| Error Pattern | 與 WRAP 的關係 |
|--------------|---------------|
| `PC-051` | WRAP 建立動機（代理人失敗歸因案例） |
| `PC-063` | 偽 Widen 防護案例 → 衍生 `pseudo-widen-guard.md` |
| `PC-066` | 決策品質自動駕駛 → 衍生 Hook 自動觸發設計 |
| `PC-067` | ANA plan 未審查 → 衍生「ANA 強制完整 WRAP」規則 |
| `PC-071` | 個人化建議資料充足度盲點 → 衍生 Step 0 + personalized-advice-rules |

詳細情境見 `case-studies.md`。

---

## 依賴方向備忘

- pm-rules → SKILL：允許（pm-rules 引用 WRAP 原理）
- pm-rules → 本目錄：允許（pm-rules 引用本專案落地規格）
- SKILL → pm-rules：**禁止**（SKILL 保持跨專案可用）
- SKILL → 本目錄：**禁止**（SKILL 不耦合本專案）
- 本目錄 → SKILL：允許（本目錄引用 SKILL 作為上游原理）

---

**Last Updated**: 2026-04-16
**Version**: 1.0.0 — 建立本索引作為 pm-rules ↔ SKILL 的橋接文件
