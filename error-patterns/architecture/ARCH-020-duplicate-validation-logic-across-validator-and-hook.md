# ARCH-020: 驗證邏輯在 Validator 與 Hook 兩處獨立重寫

## 錯誤症狀

同一領域的驗證邏輯在兩個獨立模組各自實作一份，造成以下問題：

- **Bug 無法同步修復**：修了 validator 端的 bug，hook 端仍有相同 bug；反之亦然
- **行為不一致**：兩處實作細節差異導致相同輸入得到不同驗證結果
- **重複測試成本**：每個邏輯變更要在兩處各寫一份單元測試
- **規範演進脫節**：Schema / 欄位定義更新時容易只改一邊

典型表現（本專案案例，W17-070 ANA 發現）：

- `.claude/skills/ticket/ticket_system/lib/ticket_validator.py` 函式 `_is_placeholder` 判斷章節內容是否為 placeholder
- `.claude/hooks/acceptance_checkers/execution_log_checker.py` 函式 `_is_section_empty` 也判斷章節是否為空
- 兩者都做「剝除 HTML 註解後判空」的邏輯，實作上各自獨立
- W17-032（2026-04-21）只修了 `_is_placeholder` 的 false positive 分支
- W17-056（2026-04-24，3 天後）同時暴露兩處 false negative：`_is_placeholder` 和 `_is_section_empty` 都未剝除 markdown 分隔符 `---`
- IMP-1（W17-071）修復時必須同步改兩處檔案，額外增加測試檔與風險

## 根因分析

### 根因 1：驗證執行時機分佈在兩個進程

Ticket 系統的 body-check 在兩個時機執行：

| 時機 | 執行者 | 邏輯模組 |
|------|--------|---------|
| PM 直接呼叫 `ticket track validate` / `complete` | CLI 進程（Python） | `ticket_validator.py` |
| Bash `ticket track complete` 被 Hook 攔截時 | Hook 進程（Python） | `execution_log_checker.py` |

兩個進程在載入時機、依賴管理、執行環境上有隔離需求（Hook 必須 PEP 723 單檔，不能 import 專案模組），但邏輯本身一致。設計者選擇「各自重寫」而非「尋找共享路徑」。

### 根因 2：跨進程共用 Python 模組的成本顧慮

`.claude/hooks/` 下的 Hook 腳本遵循 PEP 723 單檔 UV 執行模式，目的是讓 Hook 能獨立於專案環境執行。若要共用 `ticket_system.lib.ticket_validator`，Hook 必須加 `sys.path` 處理或安裝 `ticket` CLI 作為依賴。

這個成本被低估：「兩處實作都不長，複寫一次沒關係」。但長期維護成本遠高於初期共用成本——每個 bug 要跨兩檔同步修復、測試。

### 根因 3：兩處實作無交叉引用

兩處實作都沒有在註解中提示「另一處也有同樣邏輯」，導致：

- 只看 `_is_placeholder` 的人不知道 `_is_section_empty` 存在
- W17-032 修復時只修了 validator，沒人發現 hook 也要同步
- W17-056 再次暴露問題才被發現（saffron-system-analyst W17-070 ANA 重現實驗第 4 步）

## 建議做法

### 選項 A：共用 validator 模組（高 ROI，需一次性架構調整）

Hook 呼叫 `ticket_validator._is_placeholder` 實現：

- Hook 加 `sys.path` 指向 `.claude/skills/ticket/ticket_system/lib/`，直接 import
- 或打包 `ticket_system` 為 `uv tool` 提供給 Hook 使用（本專案已做）
- 優點：單一事實來源，bug 修一處即可
- 成本：Hook 初始化需多幾行 import 處理

### 選項 B：維持雙實作但強制交叉引用（低成本 patch）

在兩處函式 docstring 加入：

```python
def _is_placeholder(text: str) -> bool:
    """判斷章節是否為 placeholder。

    注意：與 .claude/hooks/acceptance_checkers/execution_log_checker.py
    的 `_is_section_empty` 為同構邏輯。修改此函式時必須同步修改彼處。
    (ARCH-020 防護措施)
    """
```

- 優點：零實作成本
- 缺點：依賴開發者看到註解，仍有遺漏風險
- 適用：選項 A 短期無法實施時的過渡方案

### 選項 C：自動化測試覆蓋雙實作行為一致性

寫一個跨模組測試：同一輸入 → 兩處實作必須返回相同結果。確保一致性即使兩處實作分開維護。

- 優點：行為契約顯式化
- 成本：測試檔獨立維護；需小心跨模組 import

## 判斷準則：哪些情境適用本 pattern

| 情境特徵 | 是否適用 ARCH-020 |
|---------|-----------------|
| 同領域驗證邏輯跨進程呼叫 | 是（核心場景） |
| CLI + Hook 共用欄位定義（Schema） | 是 |
| 跨語言實作（如 Dart + Python） | 不適用（無法共用模組） |
| 意圖不同的相似名稱函式 | 不適用（非重複實作） |

## 相關事件與 Ticket

| 事件 | 日期 | 說明 |
|------|------|------|
| W17-032 | 2026-04-21 | 只修 validator 端 false positive，未修 hook 端 |
| W17-056 | 2026-04-24 | 兩處 false negative 同時暴露（IMP ticket complete 漏擋） |
| W17-070 | 2026-04-24 | ANA 雙根因分析，saffron 重現實驗發現 hook 端同構 bug |
| W17-071 | 2026-04-24 | IMP-1 症狀修復（必須同步改兩處） |
| PC-110 | 2026-04-24 | body-check false negative 具體 bug 記錄 |

## 相關文件

- `.claude/skills/ticket/ticket_system/lib/ticket_validator.py` — `_is_placeholder` / `validate_execution_log`
- `.claude/hooks/acceptance_checkers/execution_log_checker.py` — `_is_section_empty`
- `.claude/rules/core/quality-baseline.md` 規則 5（所有發現必須追蹤）+ 規則 6（失敗案例學習）
- `.claude/error-patterns/process-compliance/PC-110-body-check-false-negative-via-schema-separator.md` — 本 pattern 的觸發 bug 記錄

---

**Last Updated**: 2026-04-24
**Version**: 1.0.0 — 初版；source W17-070 ANA（saffron-system-analyst）
