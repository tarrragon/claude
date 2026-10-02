---
id: PC-GPD-030
title: 把 linked worktree 當成票務 CLI 的實驗沙盒，寫入命令實際改到主 checkout 的真票
severity: 高
---

# PC-GPD-030: 把 linked worktree 當成票務 CLI 的實驗沙盒，寫入命令實際改到主 checkout 的真票

## 基本資訊

| 項目 | 內容 |
|------|------|
| 風險等級 | 高 |
| 分類 | process-compliance |
| 來源版本 | 0.4.1 |
| 來源事件 | 發版前移流程的互動驗證（主線程以 worktree 模擬 `ticket migrate`） |
| 首次觀測 | 2026-10-02 |

## 症狀

linked worktree 對票務 CLI 的寫入不構成隔離：在 worktree 內執行的票務寫入命令，改到的是主 checkout 的真票，而且過程沒有任何提示。

觀測事件：主線程為了驗證「發版前移」與「子樹連帶遷移」的互動，用 `git worktree add --detach` 在暫存目錄建立一個 worktree，在其中執行 `ticket migrate <舊 ID> <新 ID>`，預期只改到 worktree 內的副本。實際上：

- 命令輸出的檔案路徑指向**主 checkout**。被遷移的票與被改寫引用的票，都是主 repo 的真票。
- CLI 以隔離提交把變更直接提交到主 repo 的分支上。
- 整個過程沒有任何提示說明「目前作用於主倉庫」；回報為成功（rc=0），外觀與在 worktree 內正常執行完全相同。

靠事後核對主 repo 的 `git log` 才發現，最後以 `git revert` 撤回。若沒有及時發現，被改寫的真票會隨下一次推送進入共用分支，其他 session 與代理人會讀到被搬移的票號與改寫過的引用，事後還原的範圍也隨之擴大。

**同類觀測**：派發到 worktree 的代理人執行 `append-log`、`check-acceptance` 等命令，提交同樣落在主 repo，而不是代理人的 worktree 分支。這是同一機制的正常使用面，問題只在呼叫者誤以為 worktree 能隔離。

## 根因

1. **票務狀態解析刻意回推主倉庫**。過去主線程在 main、代理人在 worktree，各自持有票面副本，兩份副本會分裂。為了解決這個問題，票務 CLI 的票檔路徑解析（`get_ticket_state_root()`，經 `get_tickets_dir()` 與 `get_ticket_path()`）在偵測到 linked worktree 時，一律回推主倉庫根目錄。這是正確的設計，但它意味著 **worktree 對票務 CLI 不構成隔離**。
2. **「worktree 等於隔離」是程式碼層的直覺**。對程式碼而言 worktree 確實隔離（各自的工作區與分支），呼叫者很自然地把同一個直覺套用到票務 CLI 上。
3. **導向沒有任何可觀測訊號**。shim 依 cwd 找到的是 worktree 內的 skill 目錄，CLI 卻在更深一層把票檔路徑導回主倉庫，中間沒有輸出任何提示；呼叫者無從察覺作用對象已經換了。
4. **誤判的第一個假設是環境變數**。直覺上以為是 `CLAUDE_PROJECT_DIR` 覆蓋了 cwd，實測 shell 中該變數為空，且直接呼叫 `get_project_root()` 會解析到 worktree。更根本的是，專案根解析在 linked worktree 中先偵測 worktree，優先於該變數，所以在此場景下它結構上就不可能是導向點。真正的導向點在票檔解析層，不在專案根解析層。兩者不同，必須以實際呼叫 `get_ticket_path()` 驗證。

## 解決方案

1. 若已誤改主 repo：票務遷移會產生單一隔離提交，以 `git revert --no-edit <該提交>` 整筆撤回，不要逐檔 `git restore`，否則會漏掉引用者的改寫與 topic 追加行。撤回後以 `git diff <事前提交> HEAD` 確認為空。
2. 需要對票務 CLI 做寫入實驗時，改用**獨立 clone**：`git clone --no-hardlinks <主 repo> <scratch 路徑>`。獨立 clone 沒有 linked worktree 關係，票檔解析會留在 clone 內。
3. 執行任何寫入前，先在實驗環境中呼叫票檔解析函式確認作用對象，例如在 skill 目錄下執行 `uv run python -c "from ticket_system.lib.paths import get_ticket_state_root; print(get_ticket_state_root())"`，確認印出的路徑位於實驗環境內；每一步寫入後再比對主 repo 的 `git rev-parse HEAD` 是否未變。
4. 用 `pytest` 的 `tmp_path` 加 `git init` 建立的測試 repo 不受影響，因為它不是主 repo 的 linked worktree。

## 預防措施

- **派發與實驗指引**：需要「不影響真票」的票務 CLI 實驗時，指名使用獨立 clone 或 `tmp_path` 測試 repo，明寫「worktree 不隔離票務寫入」。
- **工具層**：票務 CLI 從 linked worktree 導回主倉庫時，在 stderr 輸出一行 `[INFO]`，說明實際作用的主倉庫路徑。導向本身是正確設計；讓它可觀測，呼叫者在第一次寫入時就能察覺，不必等到事後核對 `git log`。在工具具備此輸出之前，以派發與實驗指引承擔。

## 相關

- `PC-163`：主線程與 worktree 代理人票面分裂；本模式是該修正（票務狀態回推主倉庫）的另一面。
- `tool-output-trust-rules` 規則 5：重大狀態以世界平面為準。本例靠核對主 repo 的 `git log` 才發現，而非靠命令輸出。
