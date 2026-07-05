# 制式化內容生成方法論（Structured Content Generation）

> **核心主張**：有確定性 schema 的內容，結構由工具生成，人/agent 只提供語意值。Hook 檢查是保險，不是主防線。

---

## 1. 問題定義

當內容同時包含「確定性結構」（格式、欄位名、排列順序）和「語意值」（具體內容），讓撰寫者同時處理兩者會導致：

- 格式錯誤反覆發生（heading vs flat key-value、YAML 縮排、欄位遺漏）
- Hook 事後警告無法引導正確格式（agent 不知正確寫法，只知被拒）
- 相同格式錯誤跨 session 重複出現（LLM 無跨 session 記憶）

**Why**：格式結構是確定性函式（input → output 映射固定），語意值是創造性輸入（需人/agent 判斷）。把確定性工作交給確定性工具（函式/腳本），是工程設計的基本分離。

**Consequence**：不分離時，格式錯誤率隨 schema 複雜度和 agent 多樣性上升；每次 hook 警告消耗一輪 tool call + context token，累積成本遠高於一次性 CLI 化。

---

## 2. 適用判準

一個寫入點是否應 CLI 化，依以下三條件 AND 判定：

| 條件 | 說明 | 範例 |
|------|------|------|
| (1) 有確定性 schema | 欄位名、格式、排列順序可程式化定義 | multi_view_status: `{status}` + `{reason}` |
| (2) 多個寫入者 | 2+ agent 或人+agent 共同使用此寫入點 | PM + 各 agent 都寫 Completion Info |
| (3) 格式錯誤有歷史 | 已觀察到格式錯誤（hook 警告 / 手動修正） | W5-018 multi_view_status heading 錯誤 |

三條件全滿足 → **應 CLI 化**。僅 (1) 滿足但 (2)(3) 不滿足 → 暫不 CLI 化（收益不足）。

### 不適用場景

| 場景 | 原因 |
|------|------|
| 純自由文字章節（Problem Analysis 內文） | 無確定性 schema，語意值就是全部 |
| 一次性文件（方法論、規則） | 寫入者單一，格式由作者決定 |
| 格式簡單到不會寫錯（如 checklist 勾選） | 已有 set-acceptance 或格式極簡 |

---

## 3. 設計模式

### 模式 A：CLI 子命令（推薦）

將結構化寫入封裝為 CLI 子命令，接收語意值作為參數。

```bash
# 範例：multi_view_status
ticket track set-multi-view-status <id> --status skipped --reason "理由"

# 範例：Exit Status
ticket track set-exit-status <id> --status success --confidence 1.0 \
  --acceptance-met "1,2,3" --artifacts "path/to/file"

# 範例：Completion Info
ticket track set-completion-info <id> --agent rosemary-project-manager \
  --review-status completed --summary "變更摘要"
```

**優勢**：格式零錯誤、參數驗證（枚舉值檢查）、auto-commit 復用既有機制。

**適用條件**：寫入頻率高、多 agent 使用、schema 穩定。

### 模式 B：模板函式（輕量替代）

對 CLI 化成本過高的場景，提供生成模板的輔助函式，agent 填值後由 append-log 寫入。

```bash
# 生成填空模板
ticket track template <id> --section "Exit Status"
# 輸出：
# status: {success|needs_context|blocked|partial_success|failed}
# reason: ""
# confidence: {0.0-1.0}
# ...

# agent 填值後 append-log
ticket track append-log <id> --section "Exit Status" "$(填好的模板)"
```

**適用條件**：schema 經常變動、寫入頻率低、CLI 化投入不合理。

---

## 4. 三層防護模型

| 層級 | 角色 | 機制 | 覆蓋範圍 |
|------|------|------|---------|
| 第 1 層（源頭） | **CLI/函式制式化生成** | 確定性 schema → CLI 命令接收語意值，格式由程式碼產生 | 格式正確性 100% |
| 第 2 層（即時引導） | WARNING 訊息含格式範例 | hook 偵測缺失/錯誤時，顯示正確格式範例供 copy | 降低修正成本 |
| 第 3 層（保險） | Hook 事後檢查 | acceptance-gate-hook 各 checker 驗證最終結果 | 攔截遺漏 |

**設計順序**：先 CLI 化（第 1 層），CLI 化前先加格式範例（第 2 層），hook 始終保留（第 3 層）。

**Why**：第 1 層從源頭消除格式錯誤，是唯一能達到 0% 錯誤率的手段。第 2 層和第 3 層是漸進改善和安全網，不應作為主防線。

---

## 5. 與既有原則的關係

| 原則 | 關係 |
|------|------|
| opinionated-default-design 主張 1 | 本方法論是主張 1 的具體落地模式——「預設行為 > 文件規範」的實現方式就是 CLI 化 |
| opinionated-default-design 主張 3 | AI agent 無跨 session 記憶，CLI 即時引導是唯一可靠防線——本方法論直接回應此主張 |
| tool-output-trust 規則 | CLI 輸出是確定性的，不存在 confabulation 風險——與自由文字寫入形成對比 |
| quality-baseline 規則 4 | Hook 失敗必須可見——第 3 層保險不因第 1 層存在而移除 |

---

## 6. 檢查清單

設計新的寫入點（CLI 命令、ticket body 章節、設定欄位）時：

- [ ] 此寫入點有確定性 schema 嗎？
- [ ] 有 2+ 寫入者嗎？
- [ ] 已觀察到格式錯誤嗎？
- [ ] 三條件全滿足 → 已規劃 CLI 子命令或模板函式？
- [ ] CLI 化前的過渡期 → WARNING 訊息已包含正確格式範例？
- [ ] Hook 事後檢查已建立（即使已 CLI 化，保險層不移除）？

---

## 相關文件

- `.claude/rules/core/opinionated-default-design.md` — 主張 1 和主張 3
- `.claude/rules/core/structured-content-generation.md` — 本方法論的規則層速查
- `.claude/hooks/acceptance_checkers/multi_view_checker.py` — 第 3 層保險範例
- 1.5.0-W5-018 — 觸發案例（multi_view_status heading 格式錯誤）

---

**Last Updated**: 2026-07-05
**Version**: 1.0.0 — 初始建立（1.5.0-W5-020）
**Source**: 用戶設計洞察 + W5-018 根因分析 + opinionated-default-design 原則
