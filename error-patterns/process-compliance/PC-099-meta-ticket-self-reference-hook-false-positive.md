# PC-099: Meta-ticket 自我引用造成 Hook 誤報

## 基本資訊

- **Pattern ID**: PC-099
- **分類**: 流程合規（process-compliance）
- **來源版本**: v0.18.0
- **發現日期**: 2026-04-19
- **風險等級**: 中
- **相關 Pattern**: PC-093（YAGNI 累積反模式，PC-099 為其 hook 首次運作時發現）

---

## 問題描述

### 症狀

「偵測 X 反模式」的 Hook 在自己的設計 / 測試 / 實作 Ticket 上會誤報大量命中 —— 因為該 ticket md 必然引用被偵測的 phrase 作為 regex 字面量、測試 fixture、虛擬碼註解、設計文件範例。

### 首次案例（W10-082 PC-093 Hook）

- Phase 3b basil 實作完成後，執行 `ticket track phase 0.18.0-W10-082 phase4` 推入 Phase 4
- 剛註冊的 hook 阻擋自己 ticket 的 phase advance
- Hook 偵測結果：49 項命中 / 48 項為 meta-ticket 文件自我引用 / 1 項已正確豁免

### 命中區塊類型

| 區塊 | 為何誤報 |
|------|---------|
| Problem Analysis Context Bundle | 列出偵測目標 phrase 範例 |
| Phase 1 Solution §regex 清單 | regex 字面量本身含被偵測字 |
| Phase 2 Test Results §測試案例 | 正反例含被偵測 phrase |
| Phase 3a Solution §虛擬碼 | 函式註解引用 phrase |

---

## 根因分析

### 直接原因

Hook 偵測邏輯只看「文本含特定 phrase」，不區分「實際延後話術」vs「設計文件引用」。

### 深層原因

| 類型 | 說明 |
|------|------|
| A 設計盲點 | Hook Phase 1 設計未考慮「該 hook 會被用於其設計 ticket 自己」 |
| B 豁免機制不足 | 既有豁免語法需逐行標記，設計 ticket 幾十處命中逐一標記破壞可讀性 |
| C 缺少 ticket 級豁免 | 無「此 ticket 是 hook 自身的設計/實作 ticket」的整檔豁免機制 |

**真根因**：所有「規則偵測 hook」的 Phase 1 設計必須考慮 meta-level 自我引用。

---

## 防護機制

### 規則建議（適用於所有「偵測 X 反模式」Hook）

1. **Phase 1 必加 self-reference 豁免設計**：ticket frontmatter 加 `hook_self_reference: <hook-id>` 欄位；hook 執行時偵測此欄位自動豁免整檔
2. **豁免粒度多層化**：行級（現有 `<!-- PC-X-exempt -->`）+ 區塊級（code block / heading section）+ 檔級（frontmatter 宣告）
3. **Phase 2 必加 self-reference 測試案例**：設計 ticket 自己當 fixture，驗證 hook 不阻擋自己的 phase advance
4. **Hook 初次部署檢查清單**：新 hook 註冊到 settings.json 前，必跑一次「對自己設計 ticket 執行」確認不誤報

### Phase 1 設計 checklist

- [ ] Hook 是否會偵測到自己設計文件中的範例 phrase？
- [ ] 豁免機制是否能以最小干擾處理設計 ticket？
- [ ] 是否有 ticket 級豁免（而非只有行級）？
- [ ] Phase 2 是否包含 self-reference 測試案例？

---

## 適用範圍

此 pattern 適用於所有以下類型的 Hook：

- 偵測反模式話術（PC-093 延後決策 / PC-066 人性化表達）
- 偵測禁用字元（language-guard 簡體字）
- 偵測硬編碼（hardcoded-strings）
- 偵測未格式化內容

任何「掃描文本 phrase」類 hook 都有 meta-ticket 自我引用風險。

---

## 修復落地（W10-087）

**修復 Ticket**: 0.18.0-W10-087

**修復範圍**（acceptance-gate-hook #17 AUQ meta-ticket 誤觸發）：

| 項目 | 檔案 |
|------|------|
| 歸屬過濾模組 | `.claude/hooks/acceptance_checkers/error_pattern_attribution.py`（新增） |
| Hook orchestrator 接線 | `.claude/hooks/acceptance-gate-hook.py`（步驟 3 加入 `filter_error_patterns_by_ticket_scope`） |
| Regression 測試 | `.claude/hooks/tests/test_error_pattern_attribution.py`（9 案例覆蓋 frontmatter 匹配 / 跨 ticket / null fallback / legacy 無引用 / 讀取失敗保守歸屬等） |

**歸屬判定邏輯**（短路求值）：

1. PC 檔案 YAML frontmatter `source_ticket`：
   - 等於當前 ticket_id → 歸屬
   - 指向其他 ticket 或為空 / null → 過濾 / 回退
2. 無 frontmatter（legacy 格式）→ 回退至 ticket md 引用檢查：
   - ticket 內容含 PC ID（`PC-099`）或 PC basename → 歸屬
   - 完全無引用 → 過濾（meta-ticket / 跨 session 保護核心）

**驗證**：32 / 32 測試通過（9 new + 23 baseline），import smoke test 通過。

---

**Last Updated**: 2026-04-19
**Version**: 1.1.0（W10-087 修復落地）
**Source**: W10-082 PC-093 Hook Phase 3b 首次運作暴露
