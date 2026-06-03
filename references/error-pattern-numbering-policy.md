# Error Pattern 編號區段治理 Policy（D2）

本文件定義 error-pattern（`PC` / `IMP` / `ARCH` / `TEST` / `DOC` / `CQ`）流水號的**編號區段約定**：framework 共享 error-pattern 使用 1–499，專案專屬 error-pattern 使用 500+。

> **定位（必讀）**：本約定為**文件層約定（documentation convention）**，**非強制機制（no enforcement mechanism）**。目前沒有 hook / CLI / validator 在建立 error-pattern 時檢查或阻擋編號落在錯誤區段。約定的價值在於人類維護者建立新 pattern 時依此自律分流，避免 framework sync 將專案專屬 pattern 污染到其他專案。
> **來源**：0.19.1-W1-018 D2 + 多視角審查 L3（無強制機制）。

---

## 為什麼需要編號區段約定

`.claude/error-patterns/` 隨 `.claude/` 同步機制（見 `.claude/scripts/README-subtree-sync.md`）跨專案推送 / 拉取。同步預設將整個 `.claude/error-patterns/` 視為 framework 共享資產一併傳播。

**Why**：若專案專屬的 error-pattern（例如僅在 Readmoo Chrome Extension 情境成立的流程瑕疵）與 framework 通用 error-pattern 混用同一段流水號，sync 後其他專案會拉到對自身無意義甚至誤導的 pattern，且編號連續性使後人無法一眼辨識某 pattern 是否該跨專案套用。

**Consequence**：缺乏區段約定會讓 framework error-pattern 知識庫被專案專屬內容稀釋；跨專案 sync 後，無關 pattern 佔用 `/error-pattern query` 結果，降低知識庫信任度，且難以在不破壞編號連續性的前提下事後分離。

**Action**：建立新 error-pattern 前，先依下方「編號區段表」判定其適用範圍（framework 通用 vs 專案專屬），再從對應區段取下一個可用流水號。

---

## 編號區段表

| 區段 | 適用範圍 | 範例 | 同步行為（現況） |
|------|---------|------|----------------|
| **1–499** | Framework 通用：跨專案皆成立的流程瑕疵 / 架構陷阱 / 實作模式 | `PC-001` ~ `PC-499`、`IMP-001` ~ `IMP-499` 等 | 隨 `.claude/` sync 跨專案傳播 |
| **500+** | 專案專屬：僅在本專案技術棧 / 業務情境成立 | `PC-500`、`IMP-500` 等（本專案目前尚無） | 預期不跨專案傳播（**目前 sync 無此過濾，靠人工或 manifest 約定**） |

**現況補述**：截至本文件建立時，本專案所有 error-pattern 編號皆落在 1–499（framework 區段），尚無 500+ 專案專屬 pattern。500+ 區段為**預留**，待首次出現「明確只適用本專案、不應跨專案傳播」的 pattern 時啟用。

---

## 區段判定準則

建立 error-pattern 時，先回答以下三問判定區段歸屬：

| 問題 | 判定 |
|------|------|
| 此 pattern 的根因是否與本專案特定技術棧 / 業務邏輯綁定？ | 是 → 傾向 500+；否 → 1–499 |
| 移植到另一個無關專案後，此 pattern 是否仍有警示價值？ | 有 → 1–499；無 → 500+ |
| 此 pattern 描述的防護措施是否可在 framework 層（rules / methodologies / hooks）落地？ | 可 → 1–499；僅能在專案層落地 → 500+ |

**判定原則**：三問偏向 framework（1–499）即放 1–499；明確偏向專案專屬（無跨專案價值）才放 500+。**有疑慮時預設 1–499**——framework 區段的誤分流成本（其他專案多一個可忽略的 pattern）低於專案區段的誤分流成本（framework 知識庫遺漏應共享的 pattern）。

---

## 非強制性說明（L3）

**本約定不被任何自動化機制強制**。具體而言：

| 機制 | 是否檢查編號區段 |
|------|----------------|
| `/error-pattern` skill | 否 |
| `.claude/` sync push / pull 腳本 | 否（按 `sync_exclude_manifest.py` 路徑分類過濾，非按編號區段） |
| acceptance-gate / 任何 PreToolUse hook | 否 |

**Consequence**：因無強制層，編號落在錯誤區段不會被阻擋，唯一防線是維護者建立 pattern 時主動套用本約定。若未來發現此約定被頻繁違反（例如多個 framework pattern 誤入 500+，或專案 pattern 污染 sync），應建 ANA 評估是否升級為強制機制（hook 檢查編號 vs sync manifest 按區段過濾）。

**Action（升級 trigger）**：本約定升級為強制機制的 trigger 為「累積 ≥ 3 個編號區段誤分流案例」，屆時建 ANA ticket 評估強制方案。在此之前維持文件約定。

---

## 與既有規範的邊界

| 文件 | 聚焦 | 與本 policy 差異 |
|------|------|----------------|
| `.claude/error-patterns/README.md` | error-pattern 檔案格式、分類前綴（PC/IMP/ARCH/TEST/DOC/CQ）、必填章節 | 本 policy 補充「同一前綴內的流水號區段約定」，README 不涉及區段 |
| `.claude/references/reference-stability-rules.md` 規則 8 | 框架禁引用專案層級識別符（ticket ID 等） | 本 policy 處理「編號區段分流」，stability-rules 處理「引用穩定性」，互補 |
| `.claude/scripts/README-subtree-sync.md` | `.claude/` 同步機制（push/pull/排除） | 本 policy 解釋區段約定存在的動機（sync 跨專案傳播），sync README 描述同步行為 |

---

**Last Updated**: 2026-06-03
**Version**: 1.0.0 — 初版：定義 PC/IMP/ARCH 等 error-pattern 編號區段約定（framework 1–499 / project 500+），明示為文件約定非強制機制（0.19.1-W1-018 D2 + 多視角 L3）
