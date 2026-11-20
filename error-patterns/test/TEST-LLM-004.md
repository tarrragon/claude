---
id: TEST-LLM-004
title: "在舊版套件目錄以絕對路徑跑新版測試檔做正向對照，pytest 依測試檔位置決定 rootdir，實際 import 的是新版，對照誤報全綠"
severity: medium
status: active
related:
  - id: TEST-LLM-003
    kind: citation
  - id: PC-165
    kind: citation
---

# TEST-LLM-004: 在舊版套件目錄以絕對路徑跑新版測試檔做正向對照，pytest 依測試檔位置決定 rootdir，實際 import 的是新版，對照誤報全綠

## 基本資訊

| 項目 | 值 |
|------|-----|
| 分類 | test |
| 來源版本 | 3.5.0 |
| 風險等級 | 中 |
| 首次觀察 | 2026-11-13 |

**判準**：正向對照必須在「被測程式碼與測試檔同屬一棵目錄樹」的環境執行，並以 `module.__file__` 確認實際 import 的是舊版被測檔。cwd 位於舊版目錄，不代表 import 的是舊版。

## 症狀

- 為了證明新測試有鑑別力（`test-assertion-design` E1／E2），在舊版（如 main）的套件目錄下，以絕對路徑執行新版（如 worktree）的測試檔，預期轉紅。
- 結果全綠（實例：5 passed），看起來像「舊版也能通過」或「測試沒有鑑別力」，其實是對照本身沒有跑到舊版程式碼。
- 若把這次全綠解讀成「對照已做、測試通過」，一個沒驗過鑑別力的測試就被當成已驗證；若解讀成「測試無鑑別力」，則會去改一個其實沒問題的測試。兩種讀法都基於錯誤的觀察。

## 根因

- **rootdir 由命令列引數決定，不由 cwd 決定**：pytest 以引數路徑（測試檔）的共同祖先為起點，往上找 `pytest.ini`／`pyproject.toml`／`tox.ini`／`setup.cfg` 決定 rootdir 與 inifile。測試檔放在新版目錄樹時，rootdir 與 inifile 都取自新版。
- **pythonpath 相對於 rootdir 展開**：inifile 的 `pythonpath` 設定以 rootdir 為基準插入 `sys.path` 前端，於是新版套件排在最前面先被 import。
- **prepend import mode 也指向測試檔所在處**：預設 import mode 會把測試檔所在的（第一個不含 `__init__.py` 的）目錄插進 `sys.path`，同樣屬新版目錄樹。
- cwd 只在上述路徑都找不到模組時才可能介入；在這個配置下輪不到它。執行者看到的是「我在舊版目錄」，pytest 依據的是「測試檔在新版目錄」，兩者不一致且沒有任何輸出提示。

## 解決方案

1. **讓被測程式碼與測試檔同屬一棵目錄樹**，二選一：
   - 複製新版套件到暫存目錄（如 scratchpad），只把被測檔換回舊版，其餘（測試檔、pyproject、conftest）保留新版；在該複本內執行。
   - 在舊版（base）的 worktree 內放入新版測試檔，於該 worktree 內執行。
2. **以 `__file__` 確認 import 來源**：在對照環境內執行一次，印出被測模組的實際位置，確認指向舊版被測檔：
   ```bash
   python -c 'import <被測模組>; print(<被測模組>.__file__)'
   ```
   或在測試中暫時加入 `print(<被測模組>.__file__)` 並以 `pytest -s` 執行。需要同時確認 rootdir 時，看 pytest 輸出開頭的 `rootdir:` 與 `configfile:` 兩行。
3. **確認紅落在要驗的斷言上**：對照的紅必須是目標行為斷言失敗；收集錯誤、import 錯誤（如舊版缺新 API 而 `AttributeError`）不算驗到行為。遇到這種情況，只換回呼叫端、保留被呼叫的新模組，讓紅落到行為斷言上。
4. 實例：同一份測試改在「複製套件、只換回舊版被測檔」的暫存目錄執行後，得到 5 failed，才是有效的正向對照。

## 預防措施

- 正向對照的票面記錄附三項：執行目錄、pytest 輸出的 `rootdir:` 行、被測模組 `__file__`。只寫「已對照，轉紅／全綠」不足以讓讀者判斷對照是否有效。
- 跨目錄樹執行測試（以絕對路徑指向別處的測試檔）時，一律視為 rootdir 取自測試檔所在處，不以 cwd 推論 import 來源。
- 對照結果「全綠」時先懷疑對照環境，再懷疑測試：先查 `__file__`，確認確實跑到舊版之後，才下「測試無鑑別力」的結論。

## 案例

- 2026-11-13，統一 onboard 與 SessionStart 的 `.gitignore` 必要規則來源的修正：在主 checkout 的 `project-init` skill 目錄下，以絕對路徑執行 worktree 的新測試檔，意在驗證主線版 `onboard_checker` 會讓新測試轉紅，結果 5 passed。查證後發現 rootdir 取自 worktree，pyproject 的 `pythonpath` 讓 worktree 版套件先被 import。改在 scratchpad 複製套件、只換回主線版被測檔後，得到 5 failed。
