---
id: IMP-BAL-019
title: hook-logs 相對路徑解析疊加 uv run --directory shim，稽核紀錄寫入錯誤位置
category: implementation
severity: medium
created: 2026-09-02
---

# IMP-BAL-019: hook-logs 相對路徑解析疊加 uv run --directory shim，稽核紀錄寫入錯誤位置

## 基本資訊

| 項目 | 內容 |
|------|------|
| 風險等級 | 中 |
| 首次發現 | 2026-09-02 |
| 來源版本 | v0.2.1 |
| 適用範圍 | 任何用「未錨定專案根目錄的相對路徑」解析 hook-logs（或其他 runtime state）寫入位置、且透過 `uv run --directory <skill_dir>` shim（ARCH-APP-002 根治方案）執行的 skill CLI；已確認 `skill_sync/cli.py` 命中，`ticket_system/lib/precondition.py` 有同構實作待查證 |
| 偵測成本 | 中（需全機搜尋同名檔比對內容，或直接讀 shim 腳本 + 呼叫路徑解析函式比對兩種 cwd 下的絕對路徑） |

## 摘要

**`_resolve_hook_logs_dir()` 用未加專案根目錄錨點的相對路徑（`.claude/hook-logs`）解析寫入目錄，而已安裝的全域 CLI shim（`~/.local/bin/skill-sync` 等，由 `install-skill-clis.py` 產生，ARCH-APP-002 的根治方案）以 `uv run --directory <skill_dir>` 執行，subprocess 的 cwd 因此恆等於 skill 自身套件目錄，不是專案根目錄。**兩個各自合理的設計疊加後，透過標準已安裝指令執行的每一次寫入都落在 `<repo>/.claude/skills/<skill>/.claude/hook-logs/`，而非文件承諾的 `<repo>/.claude/hook-logs/`——不是偶發的 cwd 汙染，是該呼叫路徑的確定性行為。

危害集中在「稽核記錄」這類低頻讀取、高信任的用途：寫入本身成功（無錯誤碼、無 stderr 警告），只是位置系統性錯置，讀者依文件承諾的 canonical 路徑查詢時會誤判為「沒有留痕」，而實際紀錄完整存在於另一個從未被查詢過的巢狀目錄。此問題先前已在 `.gitignore` 層被發現並加註說明（通用排除規則 `**/hook-logs/`；blog 專案 `.gitignore` 甚至明文寫出成因鏈），但僅止於避免污染 `git status`，未回頭修正路徑解析函式本身，缺口原樣保留至本次才被重新發現。

## 症狀

- 文件承諾稽核紀錄寫在 `<repo>/.claude/hook-logs/<file>.jsonl`，實際查詢該路徑只找到部分或零筆紀錄
- 全機搜尋同名檔（`find / -xdev -name "<file>.jsonl"`）發現額外副本位於 `<repo>/.claude/skills/<skill>/.claude/hook-logs/<file>.jsonl`，內容恰為「遺失」的那幾筆
- `.gitignore` 中已有 `.claude/skills/*/.claude/` 或 `**/hook-logs/` 之類的通用排除規則，且註解提及「cwd-relative 路徑解析產生的副產物」——代表此機制先前已被發現，但只做了 git 層級的緩解

## 根因

| 環節 | 事實 | 後果 |
|------|------|------|
| 路徑解析函式 | `Path(os.environ.get(ENV, ".claude/hook-logs"))`，未呼叫 `git rev-parse --show-toplevel` 或任何根目錄錨定機制 | 回傳值是相對路徑字串，實際寫入位置取決於呼叫當下的 process cwd |
| 全域 shim 的執行方式 | `uv run --directory "$skill_dir" <cmd> "$@"`（ARCH-APP-002 根治方案，用於避免 `uv tool install` 的全域 namespace 碰撞） | subprocess 的 cwd 固定為 `<repo>/.claude/skills/<skill>`，不是使用者實際所在的專案根目錄 |
| 兩者疊加 | 相對路徑字串 `.claude/hook-logs` 在 shim 執行下絕對化為 `<repo>/.claude/skills/<skill>/.claude/hook-logs` | 100% 透過已安裝指令的呼叫都寫到錯誤位置；唯一寫到正確位置的情形是繞過 shim、直接以「cwd=專案根目錄」呼叫底層 python 模組（例外用法，非常態） |
| 寫入本身無錯誤訊號 | `mkdir(parents=True, exist_ok=True)` + `open(mode="a")` 皆成功 | 沒有任何錯誤碼或警告可觸發使用者懷疑，缺口只能靠主動全機搜尋或內容比對才會現形 |
| 前次已發現但只做 git 層緩解 | `.gitignore` 通用規則、blog 專案的明文成因註解 | 問題在「不污染版控」的意義上已解決，但在「稽核紀錄可被找到」的意義上從未解決，兩個目標被誤判為同一件事 |

## 最小重現

```bash
# 同一相對路徑字串，因 cwd 不同而絕對化到不同位置
python3 -c "
import sys; sys.path.insert(0, '.claude/skills/skill-sync')
from skill_sync.cli import _resolve_hook_logs_dir
print(_resolve_hook_logs_dir().resolve())
"
# /Users/x/project/flutter_balance/.claude/hook-logs

(cd .claude/skills/skill-sync && python3 -c "
import sys; sys.path.insert(0, '.')
from skill_sync.cli import _resolve_hook_logs_dir
print(_resolve_hook_logs_dir().resolve())
")
# /Users/x/project/flutter_balance/.claude/skills/skill-sync/.claude/hook-logs

# 已安裝的全域 shim 確認 cwd 恆等於 skill 自身目錄
cat ~/.local/bin/skill-sync
# exec uv run --quiet --directory "$skill_dir" skill-sync "$@"
```

驗證環境：flutter_balance 專案，`skill-sync push broken-link-check --force` 實際執行兩次（違規數 48、42），皆未出現在 `<repo>/.claude/hook-logs/skill-sync-portability-force.jsonl`；全機搜尋找到兩筆紀錄完整落在 `<repo>/.claude/skills/skill-sync/.claude/hook-logs/skill-sync-portability-force.jsonl`，timestamp 與違規數逐筆吻合。blog 專案同結構的 stray 檔亦存在（兩筆歷史紀錄）。

## 案例：portability gate 的 --force 留痕缺口（2026-09-02）

查證 `skill-sync push broken-link-check --force` 依文件承諾應留痕於 `.claude/hook-logs/skill-sync-portability-force.jsonl`，但該檔僅存一筆更早期的歷史紀錄，本輪兩次 force 完全缺席。逐一排除「寫入失敗被吞」（無 `OSError`，`except` 分支從未觸發）與「未經過 gate 判斷」（`declared`/`force` 分支確實執行，違規清單正確印出）後，鎖定為路徑解析錯置；全機搜尋確認紀錄完整存在，只是在錯誤位置。此案例的下游風險：專案正計畫用 `--force` 批次處理數十個 skill 的外移作業，若缺口未修，屆時的稽核紀錄會系統性缺席而不自知。

## 防護

| 時機 | 動作 |
|------|------|
| 撰寫任何依賴 process cwd 解析寫入路徑的函式，且該函式可能被 `uv run --directory` 類 shim 呼叫 | 改用 `git rev-parse --show-toplevel` 或等價機制錨定專案根目錄，不依賴相對路徑 + 隱含 cwd 假設 |
| 為某類 runtime state 加 `.gitignore` 排除規則，且註解提到「cwd-relative 路徑解析」 | 視為信號：先查來源函式是否已修正，若未修正應同步建 IMP ticket，不能讓 gitignore 緩解取代 source fix |
| 導入 ARCH-APP-002 的 `uv run --directory` shim 到新的 skill CLI 前 | 檢查該 CLI 是否有任何函式假設 cwd == 專案根目錄（尤其是相對路徑寫入），逐一改為根目錄錨定 |
| 稽核類紀錄檔案的可靠性存疑時 | `find / -xdev -name "<filename>"` 全機搜尋同名檔，交叉比對內容而非只信任單一路徑的存在與否（規則參照 `tool-output-trust-rules.md` 規則 3） |

## 相關

- `ARCH-APP-002`（`uv tool install` 全域 namespace 碰撞；`uv run --directory` shim 是其根治方案，本案是該方案的未預期副作用）
- `.claude/rules/core/tool-output-trust-rules.md` 規則 3（關鍵事實用無法腦補的固定值交叉驗證）——本案的固定值是「全機搜尋同名檔 + 逐行內容比對」
- flutter_balance / blog 專案 `.gitignore` 中 `**/hook-logs/` 與 `.claude/skills/*/.claude/hook-logs/` 規則（先前已發現此機制，但僅做 git 層緩解）
