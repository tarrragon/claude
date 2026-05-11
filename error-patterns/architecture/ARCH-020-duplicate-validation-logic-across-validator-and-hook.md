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

## 延伸案例：ticket 路徑解析 SSOT（2026-05-10 升級）

本案例將 ARCH-020 從「驗證邏輯重寫」延伸至「pure predicate 跨進程多份實作」的更廣模式。

### 模式描述

`is_ticket_completed(ticket_id) -> bool` 屬 pure predicate（同輸入必同輸出，無副作用）。此類函式在 lib + hook 多進程環境下若各自實作，會出現「同名 predicate 多處實作」的高風險訊號：

- **同名 predicate 多處實作即 ARCH-020 高風險訊號**——應升 lib 層 SSOT，不應允許「lib 一份 + hook 各一份」並存
- 三 caller 應全部 delegate 至 lib 唯一入口，禁止自定義同義函式

### 三次重爆軌跡（W17-181 三視角審查）

`is_ticket_completed` 在 stop hook / prompt-reminder hook / lib `handoff_utils` 三處各自實作，連續三次同病灶重爆：

| 事件 | 日期 | 修復範圍 | 遺漏 |
|------|------|---------|------|
| W17-165 | 2026-05-08 | stop hook 自定義版改用 `find_ticket_file` | 未同步 prompt-reminder hook、未同步 lib 層 |
| W17-176.2.1 | 2026-05-09 | prompt-reminder hook 自定義版改用 `find_ticket_file`（commit fdc3ee3e）| 未同步 lib 層 |
| W17-181 | 2026-05-10 | lib `handoff_utils.is_ticket_completed`（L49）/ `is_ticket_in_progress_or_completed`（L102）仍走 `load_and_validate_ticket` 舊路徑，子進程 cwd 非專案根 + `CLAUDE_PROJECT_DIR` 缺失時靜默回 False，導致 stale handoff 未被 GC | — |

### W17-181 三視角審查結論（共識）

| 視角 | 關鍵結論 |
|------|---------|
| Evidence | 根因 100% 坐實：lib L49 走 `get_project_root()` 無參數版，子進程環境路徑解析失敗回保守 False |
| Scope | 影響 8 個消費者路徑（lib 三處 + hook 三處 + CLI 兩處），lib 層 bug 透過 `is_handoff_stale` 傳染至三套 hook |
| linux universal | 「ticket completed?」pure predicate 有 3 份實作就是在邀請 ARCH-020 反覆發作。W17-165 修一處、W17-176.2.1 修一處、W17-181 又發現一處——非巧合，是缺 SSOT |

### 升級後的判別準則

新增「同名 pure predicate 多處實作」為 ARCH-020 高風險訊號：

| 訊號 | 是否觸發 ARCH-020 升 SSOT |
|------|----------------------|
| 同名 predicate（如 `is_X`、`has_Y`、`can_Z`）跨 lib + hook 多進程各有實作 | 是（核心新增訊號） |
| pure predicate 簽章不一致（如 `is_ticket_completed(ticket_id)` vs `is_ticket_completed(project_root, ticket_id, logger)`）並存 | 是（簽章漂移即實作漂移前兆） |
| lib 提供函式但 hook 自定義同義函式 | 是（必 delegate 至 lib，禁自定義） |
| 測試檔 UV script header 自行宣告 pytest deps（pytest 不解析 header，header 失效且跨檔漂移） | 是（必須升至 pyproject.toml `[dependency-groups.dev]` 集中宣告） |

## 延伸案例：測試檔 UV script header 宣告 pytest deps 反模式變體（2026-05-11 升級）

本案例將 ARCH-020 從「邏輯重寫」延伸至「**deps 宣告跨檔散落**」的同構模式：測試 deps 散落在每個測試檔的 UV script header，與「同名 predicate 多處實作」屬同類風險，差別僅在散落物件從「程式邏輯」換成「依賴宣告」。

### 模式描述

UV script header（`# /// script ... ///`）僅在 `uv run --script foo.py` 直接執行時生效。當 pytest 載入測試檔為 module 時，header 完全不被解析，導致：

- **deps 宣告失效**：測試檔自行宣告 `pyyaml>=6.0` 不會在 pytest 環境下生效
- **跨檔不一致**：每個測試檔各自宣告 deps 版本範圍，散落 N 份漂移風險
- **同步成本**：任一 deps 升級需在 N 個測試檔同步修改，與 ARCH-020 主案例「修一處漏 N-1 處」同構

### 根因引用（W17-190 ANA）

W17-190 ANA 重現實驗評估三方案：

| 方案 | 評估 |
|------|------|
| A. pyproject.toml `[dependency-groups.dev]` 集中宣告 | 推薦（單一 SSOT）|
| B. 個別測試檔直接 import yaml | 部分可行（測試碼侵入） |
| C. 測試檔 UV script header 補 deps | **不可行**：pytest 不解析 header，header 失效 |

方案 C 標為「不可行」的原因即本變體核心：UV script header 屬執行時宣告，pytest 載入測試屬模組宣告，兩種執行模型不相容。

### 升級結論

W17-191 落地方案 A（pyproject.toml 集中宣告）+ `npm run test:hooks` 統一入口，從架構層解決 ARCH-020 變體：

- W17-191.1：建立 `.claude/hooks/pyproject.toml` 含 `[dependency-groups.dev]`（pytest + pyyaml）
- W17-191.2：`package.json` 加 `test:hooks` script 透過 `uv run --project .claude/hooks pytest .claude/hooks/tests/`
- W17-191.3（本 ticket）：補 ARCH-020 條款收斂規則層

「為何不在每個測試檔加 header」未來再被提議時，本案例可作為直接駁回依據。

## 相關事件與 Ticket

| 事件 | 日期 | 說明 |
|------|------|------|
| W17-032 | 2026-04-21 | 只修 validator 端 false positive，未修 hook 端 |
| W17-056 | 2026-04-24 | 兩處 false negative 同時暴露（IMP ticket complete 漏擋） |
| W17-070 | 2026-04-24 | ANA 雙根因分析，saffron 重現實驗發現 hook 端同構 bug |
| W17-071 | 2026-04-24 | IMP-1 症狀修復（必須同步改兩處） |
| PC-110 | 2026-04-24 | body-check false negative 具體 bug 記錄 |
| W17-165 | 2026-05-08 | `is_ticket_completed` 第一次重爆（stop hook）|
| W17-176.2.1 | 2026-05-09 | `is_ticket_completed` 第二次重爆（prompt-reminder hook，commit fdc3ee3e）|
| W17-181 | 2026-05-10 | `is_ticket_completed` 第三次重爆（lib 層）；三視角審查確認需升 SSOT；spawn W17-181.1（lib SSOT）/ W17-181.2（hook delegate）/ W17-181.3（本次規則升級）/ W17-182（retrospective ANA）|
| W17-190 | 2026-05-11 | ANA 評估三方案解 PC-124 transitive deps gap；確認方案 C（測試檔 UV script header）技術不可行，推薦方案 A（pyproject.toml 集中）|
| W17-191 | 2026-05-11 | IMP 父 ticket：建立 `.claude/hooks/pyproject.toml` + `npm run test:hooks` 統一執行入口 |
| W17-191.1 | 2026-05-11 | 建立 `.claude/hooks/pyproject.toml` 含 `[dependency-groups.dev]`（pytest + pyyaml）+ 更新 CLAUDE.md §5 |
| W17-191.2 | 2026-05-11 | `package.json` 新增 `test:hooks` script（commit a996432b / merge bd490f04）|
| W17-191.3 | 2026-05-11 | ARCH-020 補「測試檔 UV script header 宣告 pytest deps 反模式變體」條款（本次升級）|

## 相關文件

- `.claude/skills/ticket/ticket_system/lib/ticket_validator.py` — `_is_placeholder` / `validate_execution_log`
- `.claude/hooks/acceptance_checkers/execution_log_checker.py` — `_is_section_empty`
- `.claude/rules/core/quality-baseline.md` 規則 5（所有發現必須追蹤）+ 規則 6（失敗案例學習）
- `.claude/error-patterns/process-compliance/PC-110-body-check-false-negative-via-schema-separator.md` — 本 pattern 的觸發 bug 記錄

---

**Last Updated**: 2026-05-11
**Version**: 1.2.0 — 新增「測試檔 UV script header 宣告 pytest deps 反模式變體」延伸案例：將模式從「邏輯/predicate 多處實作」延伸至「deps 宣告跨檔散落」；判別準則新增「測試檔 script header 自行宣告 pytest deps」訊號；補 W17-190 / W17-191（含 .1 / .2 / .3）相關事件記錄（W17-191.3 落地，PM 前台執行 PC-114 fallback）
**Version**: 1.1.0 — 新增「ticket 路徑解析 SSOT」延伸案例：將模式從「驗證邏輯重寫」延伸至「pure predicate 跨進程多份實作」；新增「同名 predicate 多處實作即 ARCH-020 高風險訊號」判別準則；補 W17-165 / W17-176.2.1 / W17-181 三次重爆軌跡與三視角審查結論（W17-181.3 落地）
**Version**: 1.0.0 — 初版；source W17-070 ANA（saffron-system-analyst）
