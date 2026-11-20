---
id: IMP-067
title: Windows NTFS 無 executable bit 導致 git 對新檔 mode 降權為 100644
category: implementation
severity: high
status: active
created: 2026-04-20
related:
- IMP-062
---

# IMP-067: Windows NTFS 無 executable bit 導致 git 對新檔 mode 降權為 100644

## 問題描述

在 Windows 環境執行 `sync-claude-push.py`（或類似涉及 `git add -A` + `git push` 的跨平台同步流程），新增的 `.py` hook 檔案在 remote repo 被記錄為 `100644`（不可執行）。下游 macOS/Linux 使用者 `sync-pull` 下來後，`Stop hook` 與 `SessionStart hook` 執行時觸發 `Permission denied`。

### 具體觸發案例

- remote `tarrragon/claude.git` 在 v1.17.0 (Mac push) → v1.36.2 (Windows push) 之間：
  - 既有 `100755` 檔案維持 147 個未變
  - 新增 **379 個** `.py` 檔案 mode 全為 `100644`
- 受影響目錄：`hooks/acceptance_checkers/`、`hooks/tests/` 等本應可執行的 hook 子目錄

## 適用範圍註記（2026-11-20 重驗）

本節只更新適用範圍與現況結論；上方觸發案例與以下根本原因保留事發當時（v1.36.2）的敘述，不改寫。

- **根本原因仍成立**：NTFS 無可執行位、新檔首次 `git add` 落為 `100644`，屬 git 與檔案系統行為，未變。
- **「受影響行為」第 3 點的前提對 runtime 觸發路徑已不成立**：`.claude/settings.json` 的 hook 註冊已全數改為顯式解譯器形式（`uv run --quiet <path>` 或 `python3 <path>`），Bash 事件的 hook 經 `hook-dispatcher.py` 分派，皆不讀檔案的可執行位。mode 降為 `100644` 的 hook 由 runtime 觸發時不再回 `Permission denied`。
- **殘留影響（非零）**：以路徑直接執行（依 shebang）的手動驗證，以及 consumer 端仍為直接路徑形式的註冊，仍依賴可執行位；mode 遺失也仍會造成 `git diff --summary` 的 mode-only 變更雜訊。
- **正確做法現況**：兩端 safety net 皆已落地，對象改為「首行為 shebang 的檔案」（不再限 `hooks/**/*.py`），兩端共用 `.claude/lib/executable_bits.py`：pull 端 `sync-claude-pull.py` 的 `restore_executable_bits`，push 端 `sync-claude-push.py` 的 `git_update_index_chmod`（`git update-index --chmod=+x`）。下方程式片段為撰寫當時的示意，非現行實作。上方觸發案例列出的 `hooks/acceptance_checkers/`、`hooks/tests/` 下的檔案由 import 或 pytest 載入，不需可執行位。

## 根本原因

| 環境 | 行為 |
|------|------|
| macOS / Linux | `git add` 從 POSIX filesystem 讀取 executable bit，含 shebang 的 `.py` 預設 `100755` |
| Windows (NTFS) | NTFS 無 executable bit 概念，`git add` 對新檔案無從推斷，fallback 為 `100644` |

`core.filemode=false` 只保護「既有檔案」的既有 mode；對**新增檔案**首次 add 時的 mode 判定無保護力。

`shutil.copy2` 雖保留來源 mode，但若上游檔案 mode 本身已錯，保留的也是錯的。

## 受影響行為

- sync-push 後 remote repo 新增 `.py` 檔案 mode 記為 `100644`
- 下游 sync-pull 拉下 `100644` → 本地 filesystem 也是 `100644`
- Hook 執行（`Stop`、`SessionStart` 等） shell 呼叫 `.py` 檔直接執行，回 `Permission denied`
- Pull 後 `git diff --summary` 顯示 `mode change 100755 => 100644`（若本地 `.git HEAD` 記錄正確 mode）

## 正確做法

### Pull 端 safety net

`sync-claude-pull.py` 完成同步後，對 `.claude/hooks/**/*.py` 強制 chmod +x（convention-based）：

```python
for py_file in (claude_dir / "hooks").rglob("*.py"):
    mode = py_file.stat().st_mode
    py_file.chmod(mode | 0o111)
```

### Push 端 safety net（必要，治本）

filesystem chmod 在 Windows NTFS 無效。必須用 `git update-index --add --chmod=+x` 顯式設定 git index mode：

```python
for py_file in (temp_dir / "hooks").rglob("*.py"):
    rel = py_file.relative_to(temp_dir)
    subprocess.run(
        ["git", "-C", str(temp_dir), "update-index", "--add", "--chmod=+x", str(rel)],
        check=False
    )
```

此命令直接寫 git index，不依賴 filesystem 語意，跨平台一致。

### Windows 使用者指南

在 `.claude/scripts/WINDOWS-NOTES.md` 明示：
- filemode 行為差異對照表
- 手動驗證 push mode 正確性（`git ls-files --stage`）
- 建議優先在 macOS/Linux 做初次 push

## 預防清單

- [ ] 新增跨平台 sync 腳本時，預設假設「上游 mode 可能不可信」，在下游加 safety net
- [ ] push 流程用 `git update-index --chmod=+x` 顯式設定新檔 mode，不依賴 filesystem 推斷
- [ ] Windows 使用者文件明示此陷阱
- [ ] 首次 push 關鍵 release 建議在 POSIX 環境執行，降低 mode 污染風險

## 來源

- v1.36.2 事件實證（remote mode 分布統計）
