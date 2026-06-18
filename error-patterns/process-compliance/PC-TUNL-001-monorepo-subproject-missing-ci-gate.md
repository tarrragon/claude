# PC-TUNL-001: monorepo 子端可編譯產物未納入 CI 守門（本機綠燈遮蔽 reproducibility）

---

## 分類資訊

| 項目 | 值 |
|------|------|
| 編號 | PC-TUNL-001 |
| 類別 | process-compliance |
| 來源版本 | v1.1.0 |
| 發現日期 | 2026-06-18 |
| 風險等級 | 中 |
| 相關 Ticket | app_tunnel v1.1.0 發布後流程分析 |

## 症狀

- monorepo 其中一端（如 Go server）有 CI 自動守門，另一端（如 Flutter app）只有「本機測試綠燈」，無 CI gate。
- 某端的可編譯產物（pubspec/package 版本約束、編譯設定）在開發者本機長期可編譯，換一台機器或乾淨環境卻無法解析依賴 / 無法編譯。
- 問題在開發完成後數版才引爆，且引爆點與當初開發行為脫節（換機、SDK 版本變動才顯現）。

## 根因分析

### 行為模式

CI 設定檔常在某張「單端」ticket 內順手誕生（例：server 硬化 ticket 建立 `ci.yml`，只含該端 job）。該 ticket 的 scope 決定了 CI 的 scope，而沒有後續 ticket 以「另一端也要進 CI」為交付項。於是 monorepo 兩端的守門責任不對稱：一端是 CI 強制，另一端停留在「本機跑綠」的執行責任。

### 結構性原因

1. **CI scope 由「誰建立它」決定，非由「整體交付」決定**：CI 誕生於單端 ticket，無人負責補齊另一端。
2. **開發環境與約束耦合，無 reproducibility gate**：開發當時本機 SDK 恰好滿足 scaffold 自帶的版本約束，本機永遠跑得過，約束從未被別的環境壓力測試；CI 正是「用獨立環境重現」的 gate，而它對該端缺席。
3. **acceptance 只看單票產出，無專案級 DoD**：每張 ticket 的 acceptance 聚焦自身（本機測試綠），無專案層級的「新增可編譯產物必須有 CI job 守門」要求。
4. **最接近的訊號被窄化消化**：Phase 4 審查曾標「CI 穩定性風險」，卻被解讀成「修某個 flaky test」，沒有人往上追問「這端到底有沒有在 CI 裡？」

### 與 quality-baseline 規則 1 的關係

本 pattern 是「測試綠燈 ≠ 可重現綠燈」的具體案例：單一環境的綠燈是環境的幸運，非真實 baseline。執行責任（本機跑測試）未升級為守門責任（CI 強制 + 跨環境重現）。

## 解決方案

### 事後處理（本次採用）

- 降除無功能依據的 scaffold 約束至本機可編譯版本，實測 pub get / analyze / test 全通過。
- 補上缺席端的 CI job（analyze + test），釘住 CI 用的 SDK 版本。

### 預防措施

| 措施 | 說明 |
|------|------|
| **CI 對稱性檢查** | monorepo 每新增一個可獨立編譯的子端時，同 wave 或同版本必須有對應 CI job；缺則建 ticket 追蹤，不可只靠本機綠燈 |
| **reproducibility gate** | 版本約束（SDK / 語言版本）不可只在開發者本機驗證；CI 用獨立環境跑是最低限度的跨環境重現 |
| **專案級 DoD** | 在專案 CLAUDE.md / 規則加入「新增可編譯產物必須有 CI job 守門」作為 Definition of Done |
| **CI 誕生時標注 scope** | CI 設定檔在單端 ticket 誕生時，於 ticket 標注「本 CI 僅覆蓋 X 端，Y 端待補」，避免缺口無人認領 |

## 相關

- `.claude/rules/core/quality-baseline.md` 規則 1（測試綠燈 ≠ Runtime 正確 / 少量綠燈 ≠ always 綠燈）
- `.claude/error-patterns/process-compliance/PC-178-ticket-body-uncommitted-git-restore-overwrite.md`（單環境綠燈遮蔽類）
