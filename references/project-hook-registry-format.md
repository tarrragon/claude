# 專案自有 hook 清冊格式

專案自己寫的 hook 一律在 `.claude/project-integration/hook-registry.yaml` 宣告。框架讀這份清冊，把註冊產生到 `.claude/settings.local.json` 的 `hooks` 區段。專案不手寫 hook 註冊，也不改 `settings.json`。

---

## 為何是這個位置

| 載體 | 專案自有 hook 放這裡的問題 |
|------|--------------------------|
| `.claude/settings.json` | 框架檔，`/sync-pull` 以三方合併更新；專案改它，JSON 內可能留下衝突標記，沒有同步基準點時整份被上游覆蓋 |
| 手寫進 `.claude/settings.local.json` | 不進 git，其他機器與團隊成員拿不到；也無從與框架 hook 區分，coverage check 一律示警 |
| `.claude/project-integration/hook-registry.yaml` | 進 git、`/sync-pull` 不覆蓋，框架可據此區分專案 hook 與框架 hook |

**後果**：繞過清冊、直接手寫 `settings.local.json` 的 hook，coverage check 與 sync-pull 會把它當成框架 hook 的殘留註冊示警，且只在寫入的那台機器生效。

**行動**：新增、修改、移除專案 hook 時只改清冊，再開新 session 讓產生器重建。

---

## 檔案格式

```yaml
version: 1
hooks:
  check-api-schema.py:
    script: .claude/project-integration/hooks/check-api-schema.py
    event: PreToolUse
    matcher: Edit|Write
    timeout: 10
  notify-build.sh:
    script: .claude/project-integration/hooks/notify-build.sh
    event: Stop
```

| 欄位 | 必填 | 說明 |
|------|------|------|
| `version` | 是 | 清冊格式版本，現為 `1`。產生器遇到不認得的版本即停止並輸出錯誤，不做部分產生 |
| `hooks` | 是 | 對應表，鍵為這筆註冊的名稱，同一份清冊內不可重複；慣例用 hook 檔名 |
| `script` | 是 | 腳本路徑，相對於專案根目錄。建議放 `.claude/project-integration/hooks/`：該目錄不同步，不會被 pull 刪除 |
| `event` | 是 | Claude Code hook 事件名，例如 `PreToolUse`、`PostToolUse`、`UserPromptSubmit`、`SessionStart`、`Stop` |
| `matcher` | 否 | 工具名比對樣式；省略即不限工具。事件不支援 matcher 時不寫 |
| `timeout` | 否 | 單位為**秒**（Claude Code 平台單位）。框架 `.claude/config/hook-registry.yaml` 歷來以毫秒寫入，屬已知錯誤（tarrragon/claude#112），不可照抄其數值 |

同一支腳本要掛在多個事件時，以不同的鍵各寫一筆（例：`notify-build.sh@Stop`、`notify-build.sh@SubagentStop`），`script` 指向同一檔案。

---

## command 字串的正規化形式

`command` 由產生器組出，清冊不提供 `command` 欄位。

| `script` 副檔名 | 產生的 command |
|----------------|---------------|
| `.py` | `uv run --quiet $CLAUDE_PROJECT_DIR/<script>` |
| 其他 | `$CLAUDE_PROJECT_DIR/<script>`（腳本須有執行權限與 shebang） |

**為何固定由產生器組字串**：Claude Code 以 command 字串是否完全相同判定重複——字串相同的註冊只執行一次，字串差一個空白就各執行一次（Claude Code 2.1.322 實測，2026-11-12）。字串交給人手寫，同一支 hook 會以不同寫法出現兩次並每次事件執行兩次；固定格式後，重複能以字串比對偵測。`.py` 的形式與框架 hook 在 `settings.json` 的寫法一致（`uv run --quiet` 前綴）。

---

## 與框架的分工

| 動作 | 承擔者 |
|------|-------|
| 撰寫清冊與 hook 腳本 | 專案 |
| 依清冊重建 `settings.local.json` 的 `hooks` 區段 | 框架：SessionStart 產生器。sync-pull 尚未呼叫它，改了清冊或 pull 之後，要到下一個 session 才生效 |
| 把清冊內的條目視為合法的 local 註冊 | 框架：`hook-registration-coverage-check.py`、sync-pull 的 local 檢查 |
| 清冊外的 local hook 條目 | 框架只移除可判定為錯誤的兩類：指向不存在檔案的條目，以及重複註冊 `settings.json` 已註冊框架 hook 的條目，被移除的逐筆列出；其他條目保留並示警，提示加入清冊 |
| 從清冊刪除的條目 | 產生器把上次產生的 command 記在 `.claude/hook-logs/project-hook-registry-sync/generated.json`（本機狀態）；清冊刪除某條後，下次 SessionStart 移除對應註冊並列出。這些註冊由框架產生，不是手寫設定 |

框架 hook（`.claude/hooks/` 與 skill 的 `hooks/` 下的檔案）不可寫進清冊：框架 hook 的註冊由上游 `settings.json` 提供，寫進清冊等於第二份註冊，上游搬移該 hook 時即成幽靈。框架 hook 漏註冊時回報 framework issue（README〈回報框架問題〉）。

---

**Last Updated**: 2026-11-12 | **Version**: 1.0.0 — 初版：清冊位置、欄位、command 正規化形式、與框架的分工。
