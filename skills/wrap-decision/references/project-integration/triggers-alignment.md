# 本專案觸發條件與 Hook 整合

本文件為**本專案的 WRAP 觸發系統**規格：YAML 觸發條件、Hook 實作、SKILL 抽象類別的對應關係，以及 Source of Truth 責任劃分。

> **SKILL.md 的角色**：提供**抽象觸發類別**（連續失敗/被困住/偏離核心/分析任務/個人化建議）作為通用 WRAP 原理。本文件負責把抽象類別**落地為可執行的觸發條件**（關鍵字、閾值、事件源）。

---

## Source of Truth 責任劃分

| 層級 | 檔案 | 負責內容 |
|------|------|---------|
| **機器可讀觸發條件**（單一真相） | `.claude/config/wrap-triggers.yaml` | 關鍵字、閾值、事件源、訊息模板 |
| **Hook 實作** | `.claude/hooks/wrap-decision-tripwire-hook.py` | 動態讀取 YAML，判定觸發，輸出提醒 |
| **抽象觸發類別**（人類可讀原理） | `.claude/skills/wrap-decision/SKILL.md` | 概念說明：什麼情境該用 WRAP |
| **本專案觸發條件對應** | 本檔 | YAML 訊號 ↔ SKILL 類別 ↔ Hook 行為 |

**依賴方向**：
- YAML → Hook：Hook 動態讀 YAML（W10-052 約束，禁止硬編碼）
- SKILL → 本檔：SKILL 不引用本專案內容；本檔引用 SKILL 作為上游原理
- Hook → 本檔：Hook 文件中的「本專案行為說明」放在本檔
- pm-rules（如 `decision-tree.md`）→ 本檔：pm-rules 不複述觸發清單，指向本檔

---

## YAML 訊號 ↔ SKILL 抽象類別對應

| YAML 訊號 ID | 事件源 | 偵測方式 | SKILL 抽象類別 | Hook category |
|-------------|-------|---------|--------------|--------------|
| `consecutive_failures` | `PostToolUse(Task)` | 代理人派發連續失敗 ≥ 2 次 | 連續失敗 | `wrap_standard` |
| `restrictive_keywords` | `UserPromptSubmit` | 關鍵字命中（做不到/沒辦法/無法/不支援/CLI 不支援/禁止/不可能/impossible/限制性解法） | 被困住 | `wrap_standard` |
| `ana_claim` | `PostToolUse(Bash)` | `ticket claim` 且 ticket type: ANA | 分析任務（ANA） | `wrap_standard` |
| `reflection_depth_challenge` | `UserPromptSubmit` | 關鍵字命中（太表層/不夠深/再想想/這解釋不了/為何不是/更深一層/還有其他可能嗎/introspection）；語意：正向「想更深」，非否定「做不到」（S2） | 反思深度質疑 | `reflection_trigger` |

### 未來擴充（S5-S8）

| 訊號 | 偵測方式 | 對應 SKILL 類別 |
|------|---------|---------------|
| 期限型（S5） | 非核心問題計時 > 15 分鐘 | 救火排擠 |
| 偏離型（S6） | 連續 2+ 個 Ticket 不在核心 Wave | 偏離核心 |
| 回退型（S7） | 已回退過一次修改 | — |
| 嘗試型（S8） | 同一問題修改嘗試 2 次 | 連續失敗（細分） |
| 資料充足度強制型（S9） | 個人化建議關鍵字（我/我該/推薦給我）+ 具體品牌/型號/劑量 | 個人化建議 → 強制 Step 0 |

---

## 失敗判定條件（W10-052 + W10-056.3）

`consecutive_failures` 訊號的「失敗」判定條件，從 Python 硬編碼遷移到 YAML：

```yaml
failure_detection:
  keywords: ["error", "exception", "failed", "timeout"]
  structured_statuses: ["failed", "error"]
```

Hook 讀取邏輯：agent 回報中出現 `keywords` 任一項，或 structured output 的 status 欄位屬於 `structured_statuses`，即計入失敗。

**同步責任**：修改 `failure_detection` 需同步更新本檔，並以 W10-52 為變更參考。

---

## 關鍵字清單同步責任

`restrictive_keywords` 的完整清單：

```
做不到、沒辦法、無法、不支援、CLI 不支援、禁止、不可能、impossible、限制性解法
```

**同步點**：
- `wrap-triggers.yaml`（單一真相）
- SKILL.md 的 description frontmatter（人類/AI 觸發描述）
- 本檔

新增關鍵字時三處必須同步。

---

## 狀態追蹤

Hook 跨工具呼叫追蹤狀態：

```
狀態檔案：.claude/hook-state/wrap-tripwire-state.json
格式：
{
  "current_ticket": "{version}-W{wave}-{seq}",
  "consecutive_failures": 2,
  "last_failure_time": "2026-04-10T16:30:00"
}
```

**重置條件**：
- 代理人成功完成 → 歸零
- 切換到不同 Ticket → 歸零
- 手動執行 `/wrap-decision` → 歸零（已回應提醒）

---

## 提醒訊息設計原則

遵循絆腳索哲學 — **不告訴 PM 該怎麼做，只提醒「你是有選擇的」**。

範例（連續失敗訊號）：

```
[WRAP 絆腳索] 連續 N 次失敗（Ticket: {id}）。
你是有選擇的：
  /wrap-decision        — 系統性擴增選項
  搜尋社群             — 看看有沒有人解決過
  建 Ticket 延後       — 回到核心任務
```

範例（限制性結論）：

```
[WRAP 絆腳索] 偵測到限制性結論（關鍵字：{matched_keyword}）。
你是有選擇的：
  /wrap-decision        — 搜尋間接方案
  窮盡五問檢查         — tool-discovery.md 規則 1
  確認後再下結論       — 至少執行 ToolSearch
```

範例（ANA claim）：

```
[WRAP 絆腳索] 你正在 claim ANA Ticket（{ticket_id}）。
ANA 分析過程必須執行 WRAP（至少快速模式）。
你是有選擇的：
  /wrap-decision        — 執行完整 WRAP 流程
  在 Solution 寫三問     — W/A/P 三問作為 claim checkpoint
  降級為快速模式         — 錨點 + W + 基本率 + 決定
```

訊息模板的完整文字由 YAML 維護，本檔只記錄設計原則。

---

## Hook 模式設計

- **hook_mode**: `advisory` — 只提醒不阻擋（exit 0 + stderr）
- **warn_cooldown**: 300 秒 — 同一訊號類型 5 分鐘內不重複提醒（避免提醒疲勞）
- **Python 風格**: PEP 723 單檔腳本（可獨立執行，相依性內嵌）

---

## 修改流程

新增觸發訊號時的工作流程：

1. **設計訊號**：確認抽象類別（對應 SKILL 觸發類別），若是全新類別需先擴充 SKILL
2. **更新 YAML**：新增 `signals` 項目，含完整文字模板
3. **更新本檔**：新增訊號對應表一列
4. **更新 Hook**：實作訊號偵測邏輯（讀 YAML，不硬編碼）
5. **更新 SKILL（若需要）**：description frontmatter 新增關鍵字
6. **更新相關 pm-rules**：指向本檔，不複述清單

---

**Last Updated**: 2026-04-18
**Version**: 1.1.0 — 新增 S4 reflection_depth_challenge 對應（Hook category: reflection_trigger），調整未來擴充編號為 S5-S9（W15-019）
**Version**: 1.0.0 — 從原 tripwire-catalog.md 抽離本專案 Hook 設計；建立 YAML/Hook/SKILL 三層對應關係
