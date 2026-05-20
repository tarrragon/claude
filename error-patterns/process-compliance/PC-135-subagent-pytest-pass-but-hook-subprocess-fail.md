# PC-135: 子代理人 pytest 環境驗證通過但實際 hook 子進程環境失準

**類別**: process-compliance
**嚴重度**: High
**首次發現**: 2026-05-10（W17-181.1 → 即時補丁 c87e0aee）
**相關**: ARCH-020、PC-115、PC-110、W17-182（retrospective ANA 收斂中）

---

## 症狀

子代理人完成 IMP/重構後回報「測試全綠 + 手動驗證通過」，但實際在 hook 子進程 / 部署環境執行時失敗。常見表現：

1. pytest 環境（`uv run pytest`）所有測試通過
2. 手動以 `python3 lib_func.py` 直呼通過
3. **但 hook 觸發時靜默失敗**（例：silent fallback to stub、靜默吞 ImportError）
4. PM 審視 commit 看不出問題，需實機觸發才發現

---

## 根因

### 環境不對稱

| 環境 | 依賴管理 | 結果 |
|------|---------|------|
| pytest（`pyproject.toml` dev deps）| 完整 | 任意 import 都成功 |
| 手動 `uv run python3 X.py` | 繼承當前 cwd 的 venv | 看似可用 |
| **Hook subprocess（`uv run --script`）** | **僅 pep723 `dependencies = [...]` 內所列** | **未列即無，import 失敗** |

子代理人若不知 hook 用 `pep723` 隔離 dep，會以為「lib 改了，hook caller 自然受益」——實際 hook 因 dep 缺失靜默 fallback。

### 達及性（reachability）盲點

修復共用 lib 時，新引入的依賴（直接或 transitive）未隨之傳播到所有 caller 環境。pep723 `dependencies = []` 是顯性聲明，但子代理人通常只看 lib 自身、不掃 caller header。

### Silent fallback 放大 bug

caller 端 `try: from lib import X; except: def X(...): return False` 的設計把 ImportError 變成「無症狀回 False」，比明確 raise 更難偵測。

---

## 案例

### 案例 1：W17-181.1 lib SSOT regression

W17-181.1 將 `handoff_utils.is_ticket_completed` delegate 至 `find_ticket_file`。新引入 import chain：`handoff_utils → ticket_system.lib.constants → lib/__init__.py eager-import ticket_loader → parser → yaml`。

- Saffron 子代理人於 pytest 環境驗證通過（pyproject.toml 含 yaml）
- Saffron 手動執行 `python3 -c "from handoff_utils import ..."` 通過（因執行於專案 cwd）
- **三個 handoff hook（`handoff-auto-resume-stop-hook.py` / `handoff-prompt-reminder-hook.py` / `handoff-reminder-hook.py`）的 pep723 `dependencies = []` 缺 yaml**
- Hook 運行時：import handoff_utils → 觸發 yaml ImportError → silent fallback to L94 stub → 永遠回 `(False, "")`
- 症狀：W17-174 / W17-178.1 stale handoff 持續未被 GC，反覆 fire 提醒

時間軸：
- 23:00 W17-181.1 commit（pytest 11+ 測試綠）
- 23:03 PM 實機觸發 stop hook → 仍未 GC（log: 「非 stale，保留」）
- 23:06 PM 直接於 subprocess 呼叫 → `ModuleNotFoundError: No module named 'yaml'`
- 23:14 PM 補丁三 hook script header 加 pyyaml dep（commit c87e0aee）
- 23:14 GC log 確認三筆 stale JSON 全部刪除

---

## 防護

### 規則層

修復共用 lib（lib/utils/shared module）時，必須執行下列驗證：

1. **新增 import 鏈追蹤**：`grep -rn "import [新模組名]"` 確認傳遞性 dep
2. **Caller 環境清單檢查**：所有 import 該 lib 的位置（hook pep723 / pyproject / requirements / CI）是否含新 dep
3. **實機觸發驗證**：不只 pytest，需在 caller 實際執行環境觸發一次完整流程，確認無 silent fallback

### 派發提示

派發 lib 重構 IMP 時，prompt 加註：「修復後必須在所有 caller 的真實執行環境驗證一次（hook subprocess / CI / 部署 env），不接受『pytest 通過 = 完成』」。

### Hook 層（建議）

為 silent fallback 加 stderr warning：

```python
try:
    from handoff_utils import is_handoff_stale
except ImportError as e:
    sys.stderr.write(f"[WARN] handoff_utils import 失敗 ({e})，使用 stub。請檢查 pep723 deps\n")
    def is_handoff_stale(record, project_root=None):
        return False, ""
```

讓 silent fallback 變 noisy fallback，下次同樣症狀立刻可見。

### Lib 層（正本清源）

handoff_utils 應改用 `ticket_system.constants`（top-level package，無 yaml 鏈）取代 `ticket_system.lib.constants`，徹底斷開 lib 對 yaml 的傳遞性依賴。已開 W17-181.4 追蹤。

---

## 與其他 pattern 的關係

| Pattern | 關係 |
|---------|------|
| ARCH-020 | 跨進程同構邏輯反模式；本案是 ARCH-020 修復過程的子症狀（環境異質） |
| PC-115 | subagent claude-dir edit 真因待調查；本案展示「subagent 完成回報不可全信」的另一種失準路徑 |
| PC-110 | subagent 自定義 H2 切斷 schema；本案展示「subagent 自我驗證範圍不足」的不同表現 |
| W17-182 | retrospective ANA 收斂「結構性修復未掃 callers」反模式；本案是該模式的當下重現案例 |

---

## 後續觀測

- 若 W17-181.4 未落地（lib 改用 top-level constants），本案會在其他 hook 加新 dep 時重現
- 應觀測 hook script 是否陸續出現「補 dep」commit；若達 3+ 次同類補丁，需強化派發 prompt 規範
- 重啟調查鏈累積閾值：W17-179 → W17-181 → W17-181.1 commit → c87e0aee 補丁，本鏈累 2 次重啟，第 3 次需考慮升級為強制 hook 檢查

---

## 案例追加 #2（2026-05-14，commit 1bc42b70）

### 重現

W17-127.1（commit 20041166）抽出 `.claude/hooks/lib/framework_paths.py` 共用模組（含 `import yaml`）。4 個 caller 中：

| Caller | 修復狀態 |
|--------|---------|
| `commit-msg-layer2-marker-check-hook.py` | 同 commit 已改 shebang + 加 pyyaml |
| `framework-rule-edit-skill-trigger-hook.py` | 同 commit 已改 shebang + 加 pyyaml |
| `layer-boundary-validator-hook.py` | 同 commit 已改 shebang + 加 pyyaml |
| **`agent-dispatch-validation-hook.py`** | **漏改**：shebang 仍 `#!/usr/bin/env python3`，`dependencies = []` |

### 隱患期間

從 W17-127.1（2026-05-XX）到 2026-05-14 commit 1bc42b70，每次 PreToolUse:Agent 觸發都 import 階段 `ModuleNotFoundError: No module named 'yaml'`，因 hook 失敗 non-blocking，traceback 只在 UI 一閃，dispatch 仍放行。

期間所有 Agent 派發都缺：
- ARCH-015 worktree 強制檢查
- target-based 路徑分類（`.claude/` vs 非 `.claude/`）
- ARCH-019/032 防護點

### 為何抽 lib 時漏掉 1/4

W17-127.1 修改清單可能依「grep import framework_paths」找出 caller，但 caller 的 shebang/PEP723 deps 修改是**獨立的另一個動作**——若用「修改 import statement」作為清單，會自動覆蓋；若用「修改 dep 宣告」作為清單，需另開 grep。兩個動作的 checklist 不對齊就會漏。

### 閾值升級訊號

PC-135 觀測閾值「3+ 次同類補丁」已達標：
- 案例 #1：c87e0aee（2026-05-10，handoff_utils → lib.constants → yaml）
- 案例 #2：1bc42b70（2026-05-14，agent-dispatch-validation → lib.framework_paths → yaml）
- 累積：2 次（觀測單位為「分立 caller 漏 sync」），若再現第 3 次需強制 hook 檢查

### 強制檢查設計（待 ticket）

| 防護層 | 設計 |
|--------|------|
| PreCommit hook | 偵測 `import yaml` / `import <非標準 lib>` 在 `.claude/hooks/**/*.py`，掃描 PEP723 deps，缺失即阻擋 |
| Lib refactor checklist | 抽 lib 時必須產出「所有 caller × shebang × deps × import」四欄對照表，PR description 強制附 |
| Dispatch validation 自檢 | hook 啟動時可選地把自己加入 `dispatch-active.json` 健康度欄位，PM 接手新 session 時可查 |

---

**Last Updated**: 2026-05-14 | **Version**: 1.1.0 — 追加案例 #2（agent-dispatch-validation-hook 漏 sync）+ 強制檢查設計待 ticket | **Source**: W17-181.1 c87e0aee + W14 post-revert commit 1bc42b70
