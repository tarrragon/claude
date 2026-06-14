# Hook 系統 Operations 詳解

> **用途**：本檔為 `.claude/methodologies/hook-system-methodology.md` 的衛星參考檔，存放 per-hook 程式碼詳解、模組化開發規範、跨平台部署規範、Hook 設計完整決策樹與反模式清單。需要實作或修改 Hook 腳本、查跨平台防護措施、研讀完整設計決策樹時按需讀取。
>
> **核心方法論（系統架構 + Hook catalog + 六大設計原則 + 階段平衡 4 原則 + 生命週期與降級機制）**：`.claude/methodologies/hook-system-methodology.md`（需回顧系統概念、設計原則或階段平衡守則時讀）。
> **降級觀察追蹤（追蹤表 + Rollback SOP）**：`.claude/references/hook-system-downgrade-tracking.md`。

---

## Hook 清單 per-hook 詳解

### SessionStart Hook

**檔案**: `.claude/hooks/startup-check-hook.sh`

**方法論**：確保每個開發 session 都在已知良好的狀態下開始。檢查範圍涵蓋 Git 狀態、專案檔案、開發環境、版本一致性、LSP 環境。失敗時提供明確修復指引，但不阻止 session 啟動。

**關鍵決策邏輯**：
1. Git 同步狀態 -> 遠端領先時提示同步
2. 檔案載入確認 -> 缺失檔案時警告
3. 開發環境檢查 -> 依賴問題時建議重新安裝
4. 工作日誌狀態 -> 提供下一步開發建議
5. LSP 環境檢查 -> 缺失時顯示安裝指令

### UserPromptSubmit Hook

**檔案**: `.claude/hooks/prompt-submit-hook.sh` + `.claude/hooks/task-avoidance-detection-hook.sh`

**方法論**：在問題發生前攔截，而非事後修復。檢查 ESLint 錯誤、技術債務累積、任務逃避行為；發現關鍵問題時記錄追蹤，逃避行為時完全阻止。

**任務逃避偵測算法**：
```bash
# 1. 禁用詞彙掃描
for 詞彙 in 工作日誌, Git提交, TodoList:
    if 包含("太複雜", "暫時", "跳過", ...):
        標記逃避行為

# 2. 行為模式檢查
if 跳過測試數量 > 0 OR ESLint忽略 > 5 OR 技術債務 > 15:
    標記逃避行為

# 3. 完整性檢查
if 程式碼變更 > 0 AND 測試變更 == 0:
    標記逃避行為
```

**阻止機制**：建立 `$CLAUDE_PROJECT_DIR/.claude/TASK_AVOIDANCE_BLOCK` 檔案，觸發所有後續操作阻止。

### PreToolUse Hook

**檔案**: `.claude/hooks/task-avoidance-block-check.sh` + 工具特定檢查

**方法論**：防禦性檢查，確保操作在安全狀態下執行。檢查順序為阻止狀態 -> 工具特定安全檢查 -> 允許執行；任何阻止狀態都完全禁止操作。

**阻止狀態檢查流程**：
1. 檢查 `$CLAUDE_PROJECT_DIR/.claude/TASK_AVOIDANCE_BLOCK` 檔案存在性
2. 如果存在 -> 顯示詳細修復指引並退出（exit 1）
3. 如果不存在 -> 繼續執行

### PostToolUse Hook

**檔案**: 複合 hook 執行鏈

**方法論**：即時品質檢查和問題追蹤，確保變更不降低程式碼品質。執行順序為效能監控開始 -> 基礎檢查 -> 程式異味偵測 -> 文件更新提醒 -> 效能監控結束；非阻塞，檢查發現問題時記錄追蹤但不阻止開發流程。

**程式異味偵測演算法策略**：
```bash
# 複雜度偵測
函數長度 > 30行 -> 長函數異味
巢狀層級 > 4層 -> 深層巢狀異味
參數數量 > 5個 -> 過長參數列表異味

# 維護性偵測
重複程式碼塊 > 5處 -> 程式碼重複異味
魔術數字 > 3處 -> 魔術數字異味
類別行數 > 200行 -> 大型類別異味

# 架構偵測
依賴數量 > 10個 -> 高耦合異味
方法數量 > 10個 -> 神秘類別異味
```

**Agent 整合策略**：偵測到異味 -> 生成結構化報告 -> 建立 Agent 任務檔案（JSON 格式）-> 啟動背景 Agent 處理 TodoList 更新 -> 主流程繼續不中斷開發。

### Stop Hook

**檔案**: `.claude/hooks/stop-hook.sh`

**方法論**：自動化版本推進建議，基於工作完成狀態和目標達成情況。分析檔案變更量、工作日誌狀態、TodoList 完成度；提供明確的下一步行動建議，不強制執行。

**版本推進決策邏輯**：
```bash
if 檔案變更 > 0:
    if 工作日誌標記完成:
        if TodoList系列完成:
            建議中版本推進
        else:
            建議小版本推進
    else:
        建議繼續開發
```

### SubagentStop Hook

**觸發時機**：代理人（subagent）真正完成時，涵蓋前台與 `run_in_background: true` 派發兩種模式。

**input 關鍵欄位**：

| 欄位 | 用途 |
|------|------|
| `agent_id` | 代理人精準識別碼，狀態檔案匹配的 source of truth |
| `agent_type` | 代理人類型（如 thyme-extension-engineer） |
| `agent_transcript_path` | 代理人對話記錄路徑 |
| `last_assistant_message` (optional) | 代理人最後一則訊息 |

**典型責任**：清理派發追蹤記錄（如 `dispatch-active.json`，依 `agent_id` 精準匹配）、驗證代理人 commit（避開啟動誤觸發）、廣播代理人完成狀態、handoff 提醒、累積執行統計（duration、tool_use_count）。

**禁止用於**：啟動時邏輯（註冊派發、驗證 prompt）-> 應使用 PreToolUse(Agent)；主線程結束邏輯 -> 應使用 Stop。

### Performance Monitor Hook

**檔案**: `.claude/hooks/performance-monitor-hook.sh`

**方法論**：持續效能監控，預防 hook 系統本身成為開發瓶頸。監控執行時間、記憶體使用、執行頻率。

**效能閾值設計**：理想 < 1 秒（正常運作）、警告 2-5 秒（建議優化）、錯誤 > 5 秒（需要立即優化）。

**優化策略自動建議**：檔案掃描優化（限制搜尋深度範圍）、快取機制（避免重複計算）、平行處理（獨立檢查項目並行）、條件執行（大量變更才執行完整檢查）。

### Auto-Documentation Update Hook

**檔案**: `.claude/hooks/auto-documentation-update-hook.sh`

**方法論**：主動文件同步提醒，確保文件與程式碼同步更新。根據變更檔案類型自動判斷需要更新的文件，依 High/Medium/Low 優先級指導更新順序。

**變更類型對應**：API 變更 -> `docs/api/`（High）；架構變更 -> `docs/domains/architecture/`（Medium）；配置變更 -> `README.md`（High）；新功能 -> `CHANGELOG.md`（Medium）；測試變更 -> `docs/testing/`（Low）。

---

## Event 選擇決策流程

### 選 event 的決策流程

```
新增 Hook 前：
1. 此 Hook 服務「啟動時」「完成時」還是「兩者」？
2. 若兩者 -> 拆成兩個 Hook 分掛兩個 event
3. 若完成時且涉及代理人 -> 必用 SubagentStop
4. 若是 task 狀態變更 -> TaskCreated / TaskCompleted
5. 若是 session / compact / config / cwd / file / worktree 生命週期 -> 查事件總覽選擇對應 event
6. 查 hook-spec 確認選用 event 在 background 模式的觸發時機
7. 確認狀態匹配使用 source of truth 識別碼（agent_id）
```

### Hook handler 選擇

| 需求 | Handler | 原因 |
|------|---------|------|
| 可用 deterministic script 判斷 | `command` | 可測、可重現、成本低 |
| 需呼叫本機或受控服務 | `http` | 將驗證集中到服務端，仍保留 JSON 決策 |
| 需模型做語意分類 | `prompt` | 單輪判斷即可，不需工具 |
| 需讀多檔或 grep 後再判斷 | `agent` | 可使用工具查證，但需限制 scope |

預設順序 `command` -> `http` -> `prompt` -> `agent`。越往右成本與不確定性越高，必須在設計中說明理由。

### `if` 條件使用

`if` 用來避免 hook handler 在不相關工具呼叫上啟動。

| 情境 | 做法 |
|------|------|
| 只關心某種 Bash 子命令 | `if: "Bash(git *)"` |
| 只關心特定副檔名 edit | `if: "Edit(*.ts)"` |
| 多條件 | 拆多個 handler，不把邏輯塞進一條 `if` |
| 非 tool event | 不使用 `if` |

若條件需要讀專案狀態或跨檔判斷，不要硬塞進 `if`；用 `if` 做粗篩，詳細判斷交給 handler。

### 啟動 vs 完成職責分掛兩 event

| 職責 | 對應 event |
|------|----------|
| 啟動時邏輯（註冊派發、驗證 prompt、檢查 ticket reference） | `PreToolUse(Agent)` |
| 完成時邏輯（清理記錄、驗證 commit、廣播完成、handoff 提醒） | `SubagentStop` |
| 主線程結束邏輯 | `Stop` |
| 工具執行後處理（一般工具 Read/Write/Bash 等） | `PostToolUse(<tool_name>)` |

**反模式**：將啟動與完成邏輯混掛同一 event（如全部掛 `PostToolUse(Agent)`），導致 background 模式時機錯位，必須加 `if background_mode: skip` guard 繞道。

---

## 模組化開發規範

### 共用模組架構（v0.28.0+）

v0.28.0 重構引入了共用模組系統，所有 Hook 腳本應優先使用這些模組：

```text
.claude/lib/
- config_loader.py    # 配置載入（含快取）
- git_utils.py        # Git 操作工具
- hook_io.py          # I/O 標準化
- hook_logging.py     # 日誌系統
- tests/              # 單元測試
```

### 標準 Hook 腳本結構

```python
#!/usr/bin/env python3
"""
Hook 名稱說明

觸發時機: PreToolUse/PostToolUse/...
主要功能: 簡要說明
"""

import sys
from pathlib import Path

# 標準化導入共用模組
sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import setup_hook_logging, run_hook_safely, read_json_from_stdin

def main():
    logger = setup_hook_logging("hook-name")
    input_data = read_json_from_stdin(logger)
    if input_data is None:
        return 0

    # ... 處理邏輯 ...

    output = create_pretooluse_output("allow", "檢查通過")
    write_hook_output(output)

if __name__ == "__main__":
    main()
```

### 模組使用規範

| 需求 | 使用模組 | 函式 |
|------|---------|------|
| 讀取 Hook 輸入 | hook_utils (hook_io) | `read_json_from_stdin(logger)` |
| 輸出決策結果 | hook_io | `write_hook_output()` |
| PreToolUse 輸出 | hook_io | `create_pretooluse_output()` |
| PostToolUse 輸出 | hook_io | `create_posttooluse_output()` |
| 日誌記錄 | hook_logging | `setup_hook_logging()` |
| 載入配置 | config_loader | `load_config()` |
| 代理人配置 | config_loader | `load_agents_config()` |
| Git 操作 | git_utils | `run_git_command()` |
| 分支檢查 | git_utils | `is_protected_branch()` |

### 輸出規範（stderr 與 exit code）

> **背景**：Claude Code 將 hook 的 stderr 輸出和 exit code 1 都視為 "hook error"（IMP-048, IMP-049）。此為 CLI 已知 bug（anthropics/claude-code#34713 等），但在 CLI 修復前 Hook 需配合。

**Hook 執行路徑規則**（由 `run_hook_safely` 呼叫的程式碼）：

| 規則 | 說明 |
|------|------|
| 禁止 `sys.exit(1)` | 改用 `return 0` 或拋出 Exception 由 `run_hook_safely` 捕獲 |
| 避免 stderr 輸出 | StreamHandler 使用 stdout，錯誤記錄到日誌檔 |
| ImportError 防護 | `sys.exit(0)` + stderr 報錯（ImportError 在 `run_hook_safely` 外，無法被捕獲） |

**`__main__` CLI 工具規則**（不經過 Hook 系統的 CLI 測試入口）：

| 規則 | 說明 |
|------|------|
| `sys.exit(1)` 是正確的 | CLI 用法錯誤或處理失敗應返回非零 exit code |
| stderr 輸出是正確的 | CLI 工具的標準錯誤輸出行為 |

**日誌配置標準模板**：

```python
# 正確：使用 stdout（Hook 執行路徑）
logging.basicConfig(
    level=log_level,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)  # Hook 路徑必須用 stdout
    ]
)
```

**與 quality-baseline 規則 4 的關係**：quality-baseline 要求「異常必須寫入 stderr」，但 Hook 系統因 CLI bug 限制無法遵守。Hook 的替代方案為異常記錄到日誌檔（`.claude/hook-logs/`），不寫 stderr。這是 CLI bug 的已知妥協，不適用於非 Hook 的一般程式碼。

### 測試要求

每個 Hook 腳本必須有對應的單元測試：

```text
.claude/hooks/my-hook.py  ->  .claude/lib/tests/test_my_hook.py
```

測試執行：
```bash
uv run --with pytest python -m pytest .claude/lib/tests/ -v
```

Hook tests under `.claude/hooks/tests/` may include PEP 723 inline dependencies. Before running them, inspect the file header and follow `.claude/hooks/tests/README.md`:

- PEP 723 test file: `uv run .claude/hooks/tests/<test-file>.py`
- Ordinary pytest file: `uv run --with pytest python -m pytest .claude/hooks/tests/<test-file>.py -v`
- Targeted selection on a PEP 723 file: mirror dependencies with `--with <package>`

### 配置外部化

可配置參數應放入 `.claude/config/` 目錄：

- `agents.yaml` - 代理人分派規則
- `quality_rules.yaml` - 品質檢測規則

詳細 API 參考請見：[共用模組 README](../lib/README.md)

### Hook 維護與擴展流程

**Hook 新增流程**：識別新的品質控制需求 -> 設計檢查邏輯和閾值 -> 實作 hook 腳本 -> 更新 `$CLAUDE_PROJECT_DIR/.claude/settings.local.json` -> 建立說明文件 -> 測試和驗證。

**效能優化流程**：Performance Monitor Hook 自動偵測 -> 分析效能瓶頸根因 -> 實施優化策略 -> 驗證改善效果 -> 更新效能基準。

---

## 跨平台部署規範

> **核心理念**：Hook 系統必須在 macOS、Linux、Windows 三平台行為一致。任何「我的機器可以跑」的假設在跨平台都是陷阱。

Hook 在 macOS/Linux 上行為正常不代表 Windows 上可用。Windows 平台有三個獨立的斷層點會讓 Hook 完全無法啟動或輸出亂碼。

### 斷層點總覽

| 斷層 | 症狀 | 根因 |
|------|------|------|
| Python 環境 | Hook 完全不執行，顯示「Failed with non-blocking status code: No stderr output」 | Windows 11 預裝 Microsoft Store Python Stub（exit 9009，不寫任何輸出） |
| Shebang 污染 | env 找不到命令，exit 127，無 stderr | `core.autocrlf=true` 把 `#!/usr/bin/env -S uv run` 尾端加上 `\r` |
| Console 編碼 | 中文輸出亂碼、JSON 解析失敗、異常寫 stderr 二次失敗 | Windows console 預設 cp950（Big5）/cp936（GBK），非 UTF-8 |

### 規範 1：Windows Python 環境要求

| 要求 | 說明 |
|------|------|
| 安裝真實 Python 3.12+ | 從 python.org 下載安裝，或使用 uv 管理（`uv python install 3.12`） |
| 關閉 Microsoft Store 別名 | 設定 -> 應用程式 -> 進階應用程式設定 -> App 執行別名 -> 關閉 python.exe 與 python3.exe |
| 驗證 | `python --version` 必須回傳版本號且 `$LASTEXITCODE=0`（若 exit 9009 表示 stub 仍生效） |

**偵測 stub 的標準命令**（可納入 session-start 檢查）：

```powershell
$result = & python --version 2>&1
if ($LASTEXITCODE -eq 9009 -or -not $result) {
    Write-Warning "Python 是 Microsoft Store stub，請安裝真實 Python 或關閉 App 執行別名"
}
```

### 規範 2：Shebang 與換行符防護

所有 Python Hook 的 shebang 為 `#!/usr/bin/env -S uv run --quiet --script`。此 shebang 在 Windows 下必須配合以下兩項措施：

| 措施 | 實施位置 |
|------|---------|
| 專案根目錄 `.gitattributes` 強制 `*.py text eol=lf` | 防止 `core.autocrlf=true` 污染 shebang |
| `.claude/.gitattributes` 同步設定 | 隨框架 sync 傳播到其他專案 |
| Windows 使用者 clone 後執行 `git config core.autocrlf false` | 防止後續 commit 被污染 |

**驗證方式**：

```bash
git check-attr eol .claude/hooks/<任一>.py
# 預期輸出：eol: lf（非 unspecified）
```

### 規範 3：UTF-8 I/O 強制

Hook 執行時不可依賴 locale codepage，必須在入口強制 UTF-8。三種機制擇一（建議三者並用）：

**機制 A：Hook 入口呼叫 `ensure_utf8_io()`**

```python
def ensure_utf8_io() -> None:
    """強制 stdin/stdout/stderr 使用 UTF-8。Python 3.11+ 可用 reconfigure。"""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

def main() -> int:
    ensure_utf8_io()  # 必須在 read_json_from_stdin 之前
    ...
```

**機制 B：PEP 723 inline metadata 指定環境變數**

受限於 PEP 723 無法設定 env，此機制改由 hook launcher（CC runtime）提供 `PYTHONUTF8=1`。使用者環境需確保此變數存在。

**機制 C：subprocess 呼叫強制 encoding**

```python
# 錯誤：Windows 會用 cp950 解碼子程序輸出
subprocess.run(["git", "log"], capture_output=True, text=True)

# 正確：顯式指定 UTF-8 並處理非法字元
subprocess.run(
    ["git", "log"],
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
)
```

### 規範 4：路徑分隔符

`settings.json` 中的 hook command 路徑必須使用 forward slash（`/`），Windows 可正確解析。禁止使用 Windows 原生 backslash 或 escape 後 backslash，這會在 macOS/Linux 失效。

```json
{
  "command": ".claude/hooks/my-hook.py"
}
```

### 規範 5：Windows 測試要求

每個新建或修改的 Hook 必須通過以下兩項跨平台驗證：

| 驗證項 | 方法 |
|-------|------|
| shebang LF | `git check-attr eol <hook.py>` 顯示 `eol: lf` |
| UTF-8 I/O | 中文字串通過 `ensure_utf8_io()` 後輸出無亂碼 |
| subprocess encoding | grep `subprocess\.(run|Popen|check_output)` 結果均含 `encoding="utf-8"` |

### Hook 作者檢查清單

開發新 Hook 時，必做以下項目：

- [ ] Hook 入口呼叫 `ensure_utf8_io()`
- [ ] 所有 `subprocess.run/Popen/check_output` 加 `encoding="utf-8", errors="replace"`
- [ ] `settings.json` 的 command 路徑使用 forward slash
- [ ] 測試在 cp950/cp936 locale 下輸出不亂碼（至少理論驗證）
- [ ] 使用者文件提醒：Windows 需安裝真實 Python 並關閉 Store 別名
- [ ] Hook 檔案無 CRLF 污染（`git check-attr eol` 驗證）

---

## Hook 設計決策樹與反模式

### Hook 設計完整決策樹

新增 Hook 或修改既有 Hook 前，依下列決策樹判斷：

```
新 Hook 設計需求
    |
    v
[階段判斷] 攔截的動作屬哪個階段？
    |
    +-- 前期（Proposal/Phase 0/Phase 1） -> 進主動設計分支
    +-- 後期（Phase 3b/Phase 4） -> 進被動防禦分支
    |
    v
[主動設計分支]
    |
    v
問 1：錯誤延遲顯現嗎？
    +-- 是 -> Hook 必須前置，不可等錯誤發生
    +-- 否 -> 依原則 1 判斷
    |
    v
問 2：決策點還是執行點？
    +-- 決策點 -> 阻擋力建議 block
    +-- 執行點 -> 阻擋力建議 warn
    |
    v
問 3：觸發頻率預估？
    +-- 高頻 -> 考慮抽樣或條件化 matcher
    +-- 低頻 -> 全量觸發
    |
    v
[輸出] 前期 Hook 設計規格（matcher + 阻擋力 + 頻率）

[被動防禦分支]
    |
    v
問 1：既有 Hook 能覆蓋嗎？
    +-- 是 -> 不加新 Hook，調整既有
    +-- 否 -> 進入設計
    |
    v
問 2：預設降級條件？
    +-- 連續 N 次無錯自動降級
    +-- 2 Wave 觀察期後評估移除
    |
    v
[輸出] 後期 Hook 設計規格（含降級條件）
```

### 反模式清單

| 反模式 | 問題 | 替代 |
|-------|------|------|
| 1. Hook 疊加 Hook | 偵測到 Hook 誤報，用另一個 Hook 去攔截誤報，這是無限遞迴 | 修正原 Hook 的 matcher 條件或降級 |
| 2. 前期 Hook 不設計，等錯誤發生再補 | 「先上線，錯誤出現再補 Hook」只對「錯誤立即可見」有效；前期階段錯誤延遲顯現，補 Hook 時 sunk cost 已支付 | 前期階段設計時同步規劃 Hook |
| 3. 後期 Hook 無降級條件 | Hook 設計時沒設降級條件，導致永久高頻觸發 | 所有 Hook 設計時明示降級條件 + 生命週期階段 |
| 4. Hook 密度與摩擦力曲線相反 | 後期執行階段 Hook 密度高過前期決策階段，造成摩擦力倒置 | Hook 密度設計參照摩擦力曲線（前期高、後期低） |
| 5. Hook 存在但無統計 | Hook 長期運行但無觸發統計，無法評估 ROI | 所有 Hook 必須有觸發日誌，定期統計 action 比例 |

### Hook 落地檢查清單

**新增 Hook 時**：
- [ ] 明示 Hook 屬哪個階段（前期 / 後期）
- [ ] 若前期：已依階段特性主動設計
- [ ] 若後期：已設降級條件與觀察期
- [ ] 已規劃觸發日誌與統計機制
- [ ] Hook 本身符合摩擦力原則（不造成新倒置）

**既有 Hook 盤點時**：
- [ ] 近 N 個 Wave 觸發次數與 action 比例
- [ ] 是否符合降級條件
- [ ] 是否與既有 Hook 功能重疊
- [ ] 是否有疊加 Hook 的反模式

**Hook 降級執行時**：
- [ ] 降級前記錄 action 歷史供回滾
- [ ] 設定觀察期（至少 2 Wave）
- [ ] 設定快速恢復機制
- [ ] 通知 basil-hook-architect 彙整統計

---

## 相關文件

- `.claude/methodologies/hook-system-methodology.md` — Hook 系統核心方法論（系統架構 + 設計原則 + 階段平衡 + 生命週期）
- `.claude/references/hook-system-downgrade-tracking.md` — 降級觀察追蹤表 + Rollback SOP
- `.claude/references/hook-architect-technical-reference.md` — Event input/output 規範、技術參考
- `.claude/error-patterns/architecture/ARCH-019-hook-event-timing-mismatch.md` — Event 時機錯位完整錯誤模式
- `.claude/lib/README.md` — 共用模組 API 參考

---

**Last Updated**: 2026-06-14
**Version**: 1.0.0 — 從 hook-system-methodology.md 外移（W8-020.6 hook 家族整併）：per-hook 程式碼詳解、Event 選擇決策流程、模組化開發規範、跨平台部署規範、Hook 設計完整決策樹與反模式清單；emoji 全數清理為純文字
