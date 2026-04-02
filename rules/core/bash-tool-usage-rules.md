# Bash 工具使用規則

本文件定義 Claude Code Bash 工具的使用規範，涵蓋工作目錄管理、工具輸出處理和 git 操作串接等核心問題。

---

## 核心原則

> **持久狀態意識**：Bash 工具在同一 session 內保持持久 shell 狀態。`cd` 會改變工作目錄並影響後續所有指令；大輸出會存為暫存檔案，不是背景任務。

---

## 規則一：禁止使用 cd 改變持久工作目錄

### 問題根源

Claude Code 的 Bash 工具在同一 session 內共享一個持久 shell。

```
session 開始
    → shell 工作目錄：/project/root
    → cd .claude/skills/ticket
    → shell 工作目錄：/project/root/.claude/skills/ticket  ← 永久改變
    → 後續 ./scripts/sync-push.sh  ← 找不到！
```

### 強制規範

| 場景 | 錯誤做法 | 正確做法 |
|------|---------|---------|
| 在特定目錄執行命令 | `cd .claude/skills/ticket && uv run ...` | `(cd .claude/skills/ticket && uv run ...)` |
| uv 指定目錄 | `cd .claude/skills/ticket && uv run ...` | `uv -d .claude/skills/ticket run ...` |
| 需要回到根目錄 | 無操作（工作目錄已污染） | `cd /your/project/root && ...` |

### 三種安全做法

**方法 1：子 shell（推薦，任何情況適用）**

```bash
# 括號建立子 shell，原工作目錄不受影響
(cd .claude/skills/ticket && uv run ticket track list)
```

**方法 2：uv -d 參數（適用 uv 指令）**

```bash
# uv 支援 -d 指定目錄，不改變 shell 工作目錄
uv -d .claude/skills/ticket run ticket track list
```

**方法 3：絕對路徑還原**

```bash
# 若已污染，每次命令前加絕對路徑 cd
cd /your/project/root && ./scripts/sync-push.sh
```

### 檢查清單

- [ ] 命令中有 `cd`？→ 改用子 shell `()` 或 `uv -d`
- [ ] 執行失敗「找不到檔案」？→ 確認 `pwd` 是否為預期目錄
- [ ] 多步驟序列？→ 第一步加 `cd /project/root &&`

---

## 規則二：正確區分 TaskOutput vs 暫存輸出檔案

### 問題根源

兩種機制外觀相似但用途完全不同：

| 機制 | 觸發條件 | 識別特徵 | 正確處理工具 |
|------|---------|---------|------------|
| 背景任務 | `run_in_background: true` | 訊息含「background task」 | `TaskOutput` |
| 暫存輸出檔案 | 輸出 > 2KB | `Output too large ... Full output saved to: /path/...txt` | `Read` |

### 判斷流程

```
工具執行完成
    |
    v
是否使用 run_in_background: true 啟動？
    |
    +-- 是 → TaskOutput(taskId: "xxx")
    |
    +-- 否 → 輸出是否顯示 "Full output saved to: /path/xxx.txt"？
        |
        +-- 是 → Read(file_path: "/path/xxx.txt")  ← 使用完整路徑
        +-- 否 → 直接讀取對話中的輸出
```

### 典型混淆案例

```
Bash 工具輸出：
"Output too large (279.4KB). Full output saved to: .../tool-results/b8refllkc.txt"

❌ 錯誤：TaskOutput(taskId: "b8refllkc")
   → 回傳：No task found with ID: b8refllkc
   → 原因：b8refllkc 是暫存檔案名，不是任務 ID

✅ 正確：Read(file_path: ".../tool-results/b8refllkc.txt")
   → 回傳：完整的輸出內容
```

### 主動預防大輸出

若預期輸出很大，提前使用防護措施：

| 工具 | 大輸出防護 |
|------|----------|
| Bash（測試） | `flutter test 2>&1 \| tail -20`（只看最後結果） |
| Bash（一般） | `命令 \| head -100` 或 `命令 \| wc -l` 確認大小 |
| Grep | 使用 `head_limit` 限制回傳行數 |
| Read | 使用 `offset` + `limit` 分頁讀取 |

---

## 規則三：禁止串接多個 git 寫入操作

### 問題根源

Claude Code 的 PostToolUse Hook 在每個 Bash 呼叫完成後觸發。Hook 內部會執行 git 命令（如 `git status`、`git log`）。

當多個 git 寫入操作用 `&&` 串接在同一個 Bash 呼叫中時：

```
git commit -m "msg" && git merge feat/xxx --no-edit
    |                      |
    v                      v
    commit 完成             merge 開始（同一 Bash 內，不等 Hook）
    |
    v
    Hook 觸發 → Hook 內的 git 命令
    |                      |
    v                      v
    git 競爭 index.lock ← git merge 也需要 index.lock
    → fatal: Unable to create index.lock
```

### 強制規範

| 組合 | 允許 | 原因 |
|------|------|------|
| `git add && git commit` | 允許 | add 不觸發 Hook，commit 是唯一的寫入操作 |
| `git commit && git merge` | 禁止 | 兩個寫入操作，Hook 和 merge 競爭 lock |
| `git commit && git push` | 禁止 | push 可能觸發遠端 Hook 或本地 post-push 處理 |
| `git merge && git push` | 禁止 | 同上 |

### 正確做法

每個 git 寫入操作（commit/merge/rebase/push）獨立一個 Bash 呼叫：

```bash
# 正確：分開呼叫
Bash: git add file.md && git commit -m "msg"     ← 第一個 Bash 呼叫
Bash: git merge feat/xxx --no-edit               ← 第二個 Bash 呼叫（等 Hook 完成後）
Bash: git push                                    ← 第三個 Bash 呼叫

# 錯誤：串接
Bash: git add file.md && git commit -m "msg" && git merge feat/xxx --no-edit && git push
```

### 檢查清單

- [ ] Bash 命令中有 `git commit`？→ commit 之後不可再串接 merge/push/rebase
- [ ] 需要連續執行多個 git 寫入操作？→ 拆成多個獨立的 Bash 呼叫
- [ ] 看到 `index.lock` 錯誤？→ 確認是否有 git 操作串接

---

## 統一檢查清單

執行 Bash 命令前：

- [ ] 命令包含 `cd`？→ 改用子 shell 或 `uv -d`
- [ ] 輸出可能很大？→ 提前加 `head` / 用摘要腳本
- [ ] 命令以 `run_in_background: true` 執行？→ 用 `TaskOutput`
- [ ] 看到「Full output saved to: /path/xxx.txt」？→ 用 `Read` 加完整路徑
- [ ] 命令串接多個 git 寫入操作？→ 拆成獨立 Bash 呼叫

---

## 相關文件

- .claude/references/quality-python.md - Python 執行規則（類似規範）
- .claude/error-patterns/implementation/IMP-008-bash-working-directory-pollution.md
- .claude/error-patterns/implementation/IMP-009-taskoutput-confusion.md
- CLAUDE.md - 專案開發規範（含語言特定的測試執行指令）

---

**Last Updated**: 2026-04-02
**Version**: 1.3.1 - 移除規則四（技術前提經驗證不成立，git status 在 Write 後正確偵測變更，W1-024）
**Source**: IMP-008（cd 污染）、IMP-009（TaskOutput 混淆）、index.lock 競爭（Hook 與 git 寫入操作衝突）
