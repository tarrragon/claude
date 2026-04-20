# TEST-006: pytest plugin fixture 使用未宣告依賴導致全類 setup error

## 分類

測試（Test）

## 症狀

測試執行時 pytest 對整個 class（或整份檔案）的所有 test method 報 setup error：

```
ERROR at setup of TestXxx.test_yyy
E       fixture 'mocker' not found
>       available fixtures: cache, capfd, ..., monkeypatch, ...
```

關鍵特徵：

- 錯誤發生在 **setup phase**（fixture 解析），**尚未進入 assertion**
- 同一類（或同一檔案）中**所有用到該 fixture 的 test method 全部掛掉**
- `available fixtures` 清單**不包含**測試使用的 fixture 名稱
- 錯誤訊息指向測試檔案的 method 定義行，**誤導**開發者以為測試寫錯

## 根因：pytest plugin 是依賴，不是內建

pytest 只內建有限 fixture（`tmp_path`、`capsys`、`monkeypatch`…）。其餘 fixture 多由第三方 plugin 提供：

| Fixture | 來源 plugin |
|---------|------------|
| `mocker` | `pytest-mock` |
| `event_loop`（async）| `pytest-asyncio` |
| `testdir`（legacy）| `pytest` 內建（但需 `pytester` plugin enable）|
| `freezer` | `pytest-freezegun` |
| `benchmark` | `pytest-benchmark` |

當測試檔案 `import` 未使用（fixture 透過 pytest entry_points 注入不需 import），開發者容易忘記：**使用這些 fixture 必須在 `pyproject.toml` / `setup.cfg` / `requirements-test.txt` 宣告對應 plugin**。

宣告缺失後：

1. 開發者本機若曾手動 `pip install pytest-mock`，測試能跑（環境殘留）
2. CI 或他人 clone repo，`uv sync --extra test` 只裝 declared 依賴 → fixture not found
3. 錯誤訊息指向**測試檔案行號**，誤導開發者以為是測試邏輯問題

## 識別條件

同時滿足以下三項時高度懷疑為 TEST-006：

1. 錯誤訊息為 `fixture 'XXX' not found`
2. `available fixtures` 清單中**不存在** XXX
3. XXX 在 pytest 官方 builtin 清單中找不到（<https://docs.pytest.org/en/stable/reference/fixtures.html#builtin-fixtures>）

## 實際案例

### 案例：test_create_duplicate_detection.py 26 errors

**發生情境**：0.18.0-W12-005 實作期間產出 `test_create_duplicate_detection.py`，使用 `mocker` fixture 54 處。`.claude/skills/ticket/pyproject.toml` 的 `[project.optional-dependencies].test` 只宣告 `pytest`、`pytest-cov`，**未宣告 `pytest-mock`**。

結果：

- `TestDuplicateDetection`（13 tests）、`TestExtendedScopeDetection`（7 tests）、`TestIntegration`（4 tests）、`TestPerformance`（2 tests）全類 26 個 test method setup error
- 20 個不用 mocker 的 test 正常 pass（20 passed, 26 errors）
- 0.18.0-W14 階段才被發現

**錯誤訊息（節錄）**：

```
ERROR at setup of TestIntegration.test_i001_call_timing_verification
file tests/test_create_duplicate_detection.py, line 859
    def test_i001_call_timing_verification(self, mocker):
E   fixture 'mocker' not found
```

**修復**：

```diff
 [project.optional-dependencies]
 test = [
     "pytest>=7.0",
     "pytest-cov>=4.0",
+    "pytest-mock>=3.10",
 ]
```

`uv sync --extra test` 後：46 passed / 0 errors。

## 正確做法

### 規則 1：新增 fixture 前先驗證 plugin 已宣告

撰寫測試使用非內建 fixture 前：

```bash
# 確認 plugin 在依賴宣告中
grep -l "pytest-mock\|pytest-asyncio" pyproject.toml setup.cfg requirements*.txt
```

若缺失：先新增依賴 + `uv sync --extra test`，再寫測試。

### 規則 2：CI 必跑全 test suite

不能用子集測試（如 `pytest tests/test_foo.py`）判定健康。必須跑 `pytest` 全套，才能捕捉到「某 class 全類 setup error」類型的問題。

### 規則 3：識別 fixture not found 的診斷路徑

看到 `fixture 'XXX' not found` 時的診斷順序：

1. 先查 XXX 是否為 pytest builtin（`pytest --fixtures` 列出全部可用）
2. 若非 builtin，`pip show pytest-XXX` / `grep pytest-XXX pyproject.toml`
3. 確認依賴宣告 → `uv sync --extra test` / `pip install -e ".[test]"`
4. 最後才懷疑測試程式碼本身

## 防護措施

1. **架構層**：pre-commit hook 掃描 tests/ 目錄中 `def test_xxx(self, <fixture>)` 參數，比對 pyproject.toml 宣告
2. **CI 層**：乾淨環境每次跑 `uv sync --extra test && pytest` 全套，不依賴開發機殘留
3. **文件層**：README / CONTRIBUTING.md 記錄各 fixture 的依賴來源
4. **審查層**：PR review 檢查新測試 fixture 使用是否對應 pyproject.toml 宣告變更

## 關聯

- TEST-004（Mock Path Invalidation After Wrapper Refactor）— 同屬「測試環境與實作脫節」類別
- TEST-005（Mock Import Path Binding）— 同屬 mock 相關錯誤但根因不同（binding vs 依賴）
- IMP-017（Global CLI Stale After Source Fix）— 同屬「環境宣告與實際執行不一致」模式
- 相關 Ticket：0.18.0-W14-003（本案例）、0.18.0-W14-008（已作為重複被 close）

---

**建立日期**: 2026-04-17
**來源**: 0.18.0-W14-003 修復執行中 PM 前台根因分析
**Version**: 1.0.0
