# 測試斷言設計規則（速查 stub）

> **完整論證與實證**：`.claude/references/test-assertion-design-details.md`（按需讀取，含各規則 Why/Consequence 全文、W1-017 / W1-018 實證數字、`tests/perf/` 檔頭範本、適用範圍表、兩個延伸路由章與 quality-baseline 交叉引用）。
> **概念框架**：跨專案通用斷言判斷框架（9 類型斷言問題、斷言品質三問、判斷決策表）→ `.claude/skills/test-assertion-design/SKILL.md`。本檔為本專案（Chrome Extension / JS / Jest）專屬落地約束。

本文件定義所有 JavaScript 測試（Jest / Puppeteer）中斷言設計的品質底線，防止計時依賴與高精度浮點斷言在 CI 或全套件負載下造成 flaky。**設計前提**：效能差是設計問題，測試的職責是驗證功能正確性，不是量測執行速度。

---

## 四規則速查

| 規則 | 核心約束 | 豁免 |
|------|---------|------|
| 1 主套件禁絕對計時門檻 | `tests/unit/` `tests/integration/` 禁用 `toBeLessThan(Nms)` 作 pass-fail 斷言 | mock 固定回傳值（需加註解標明非效能 SLA）；`tests/perf/` 內 |
| 2 計時斷言集中 perf | 計時斷言全數放 `tests/perf/`，走 `npm run test:perf` 獨立執行 | — |
| 3 toBeCloseTo 精度 ≤ 2 | `toBeCloseTo(v, numDigits)` 的 `numDigits` 不得 > 2 | 確定性整數計算（如 `5/5=1.0`，需同行附加說明） |
| 4 快取驗證禁計時比較 | 禁 `secondRunTime < firstRunTime * N`；改用命中率 `getHitRate()` 或 `toBe` 參考比較 | — |

> 識別真實計時（不適用 mock 豁免）：斷言對象為 `Date.now()` / `performance.now()` / `getTimestamp()` 差值。

---

## 延伸路由

| 主題 | 路由 |
|------|------|
| 各規則 Why/Consequence 全文 + W1-017/W1-018 實證 + perf 檔頭範本 + 適用範圍表 | `.claude/references/test-assertion-design-details.md` |
| 測試綠燈不等於 Runtime 正確（修復鏈 acceptance 含 runtime 驗證） | `.claude/error-patterns/process-compliance/PC-165-false-positive-fix-chain.md` |
| src 字串輸出變更 acceptance 設計（src 字面修改必含 `npm test` exit 0） | `.claude/pm-rules/ticket-body-schema.md`「IMP > src 字串輸出變更額外 acceptance」+ details 同名章節 |

---

## 檢查清單

撰寫或審查測試時確認：

- [ ] 新增斷言是否包含 `toBeLessThan`（計時類）？若是，確認放在 `tests/perf/` 而非主套件
- [ ] `toBeCloseTo` 的 `numDigits` 是否 ≤ 2？若 > 2，是否有確定性計算的說明
- [ ] 快取驗證是否使用命中率或參考比較（而非計時比較）
- [ ] 效能測試是否已建立 `tests/perf/` 檔頭標注

---

**Last Updated**: 2026-06-12
**Version**: 2.0.0 — 主文外移至 `.claude/references/test-assertion-design-details.md`，本檔降為速查 stub（四規則速查 + 延伸路由 + 檢查清單）。auto-load token 收斂（1.0.0-W7-004.1）。歷史 1.0–1.3 版主文見 references/ 與 git log。
