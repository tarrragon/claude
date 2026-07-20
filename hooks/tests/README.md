# Hook 測試執行 SOP

本目錄存放 `.claude/hooks/` 的 Python 測試。**執行測試請一律指向 `.claude/hooks` 這個 uv 專案**，不要從 repo 根目錄以臨時環境執行，否則會踩到下方「常見陷阱」。

---

## 1. 正式指令（全量套件）

```bash
uv run --directory .claude/hooks pytest
```

不需要任何 `--with` 旗標。`testpaths = ["tests"]` 已在 `pyproject.toml` 設定，故不必再指定路徑。

**為何零旗標即可運作**：`.claude/hooks/pyproject.toml` 已宣告 `pyyaml>=6.0`（`[project].dependencies`）與 `pytest>=7.0` + `pyyaml>=6.0`（`[dependency-groups].dev`），並有 `uv.lock` 鎖定版本。`--directory` 使 uv 以該處為專案根，依 lockfile 建立或重用 `.venv`，所有宣告的依賴自動到位。首次執行會自動建立 `.venv`，不需手動 `uv sync`。

---

## 2. 常見陷阱：從 repo 根目錄執行會缺 PyYAML

以下指令**會失敗**，且失敗形態極具誤導性：

```bash
uv run --with pytest python -m pytest .claude/hooks/tests/    # 不要用
```

輸出為：

```text
ModuleNotFoundError: No module named 'yaml'
Interrupted: 9 errors during collection
```

**原因**：repo 根目錄沒有 `pyproject.toml`，uv 向上搜尋不到專案，因而建立只含 `--with` 所列套件的臨時環境，`.claude/hooks/pyproject.toml` 宣告的依賴完全不被採用。缺的是環境裡的 PyYAML，不是測試或 hook 有缺陷。

**為何值得特別記載**：`Interrupted: 9 errors during collection` 與「9 個模組真的壞了」在輸出上無法區分。剛改完程式的人最容易誤判為自己造成的回歸，回頭去查無關的程式碼。受影響的 9 個模組中，只有 `test_wrap_decision_tripwire_hook.py` 直接 `import yaml`，其餘 8 個是經由所匯入的模組傳遞取得依賴，因此逐檔加 import 保護無法解決。

**處置**：改用第 1 節的正式指令。若你的情境非用臨時環境不可，需補上 `--with pyyaml`，但這只是權宜手段——手動旗標會隨新依賴加入而再次失準，正式指令則由 lockfile 保證。

---

## 3. 單檔與指定測項

路徑相對於 `.claude/hooks`，故以 `tests/` 開頭：

```bash
# 單一檔案
uv run --directory .claude/hooks pytest tests/test_hook_utils.py

# 指定測試類別或關鍵字
uv run --directory .claude/hooks pytest tests/test_hook_utils.py -k "TestIsHandoffRecoveryModeCache"

# 指定單一測項（node id）
uv run --directory .claude/hooks pytest "tests/test_agent_dispatch_check.py::test_agent_to_task_map_shortcircuit"
```

---

## 4. 含 PEP 723 inline metadata 的測試檔

以下三個檔案在檔頭宣告了 inline script metadata：

```text
tests/test_agent_dispatch_check.py  -> pytest, pyyaml
tests/test_frontmatter_parser.py    -> pytest>=7.0, pyyaml>=6.0
tests/test_ticket_tracker.py        -> pytest
```

這三者所需依賴（`pytest`、`pyyaml`）都是專案 dev group 的子集，因此**第 1 節的正式指令已完整涵蓋，不需另外處理**，node id 選取也照常運作。

若要單獨以 inline metadata 執行某一檔（例如驗證該檔頭宣告本身是否正確），才需要讓 uv 直接執行檔案：

```bash
uv run .claude/hooks/tests/test_frontmatter_parser.py
```

此不變式（tests 下 PEP 723 依賴不超出專案環境）由 `tests/test_pep723_dependency_subset.py` 機械驗證，不需靠人工記得檢查。新增測試檔若宣告了專案環境以外的依賴，該測試會失敗並指出具體檔名與缺少的套件；處置方式是將套件加入 `.claude/hooks/pyproject.toml` 的 `[dependency-groups].dev`，或改用環境已有的套件。

---

## 5. 其他注意事項

不要以裸 `pytest` 作為驗證指令。本機沒有 pytest entrypoint 只能證明當前 shell 缺 pytest，不能證明 hook 測試壞掉。

Ticket 的 Test Results 應記錄實際使用的完整指令與通過數，優先採用第 1 節的正式指令形式。
