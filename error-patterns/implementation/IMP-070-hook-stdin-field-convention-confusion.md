---
id: IMP-070
title: Hook stdin 欄位命名規範混淆（input snake_case vs output camelCase）
category: implementation
severity: high
first_seen: 2026-05-05
---

# IMP-070: Hook stdin 欄位命名規範混淆（input snake_case vs output camelCase）

## 基本資訊

- **Pattern ID**: IMP-070
- **分類**: implementation
- **來源版本**: v0.18.0
- **發現日期**: 2026-05-05
- **風險等級**: 高（hook 全失效且為靜默 no-op，PM 與代理人不會看到錯誤）

## 症狀

Hook 雖然有註冊到 settings.json、有執行權限、log 顯示 exit 0，但實際行為等同失效：

| 外在訊號 | 對應失效模式 |
|---------|------------|
| Hook log 大量 `未知的 Hook 事件: ` 警告（事件名稱為空字串） | stdin 用 camelCase 讀 `hookEventName`，永遠拿到空值 |
| Hook log 大量 `非目標觸發` / `跳過` 但實際派發本應命中 | stdin 用 camelCase 讀 `toolName`，永遠拿到 None 後 fall-through |
| Hook 看似正常運作（exit 0、無錯誤）但設計目的（如 ownership 檢查、派發計數警示）從未真正執行 | 路由分發或目標判斷邏輯 100% 進入 else 分支 |
| 密度審計（如 ginger Hook 密度審計）發現某 hook 觸發次數很高但命中目標次數為 0 | 同上 |

## 根因

Claude Code Hook 的 **input schema（stdin）** 與 **output schema（stdout）** 使用不同的命名慣例，極易混淆：

| 方向 | 規範 | 範例欄位 | 規範來源 |
|------|------|---------|---------|
| **stdin（input）** | **snake_case** | `hook_event_name` / `tool_name` / `tool_input` / `session_id` | `.claude/hook-specs/claude-code-hooks-official-standards.md` line 39-97 |
| **stdout（output）** | **camelCase** | `hookSpecificOutput.hookEventName` / `additionalContext` | 同檔 line 128-170；IMP-055 |

當 hook 撰寫者把「hook 通訊都用某一種命名慣例」當作預設假設，在 `input_data.get(...)` 從 stdin 讀取時誤用 camelCase，會導致 `.get()` 永遠回傳 None / 空字串 / 預設值，hook 進入 else 或 fall-through 分支等同失效。

由於 `dict.get()` 不會拋例外、hook 仍 exit 0，外觀完全正常，必須靠主動審計 log（如「全未知事件」「全非目標觸發」）才能暴露。

### 5 Why 分析

1. **Why 1**：為何 hook 靜默失效？→ stdin 讀 camelCase 欄位永遠拿不到值，路由全進 else 分支
2. **Why 2**：為何用 camelCase 讀 stdin？→ 同 hook 的 stdout 用 camelCase（`hookSpecificOutput.hookEventName`），撰寫者誤推 input 也是 camelCase
3. **Why 3**：為何混用？→ Claude Code 設計上 input snake_case / output camelCase 不對稱，缺乏一致性提示
4. **Why 4**：為何沒被早期偵測？→ `dict.get()` 對缺欄位不報錯、hook exit 0 看似正常；單元測試若也用 camelCase 構造 stdin fixture，會與 production bug 共構（測試驗證 bug 行為）
5. **Why 5（根本原因）**：撰寫 hook stdin parser 時未對照官方規範，且測試 fixture 與 production 邏輯使用同一命名假設，無法形成獨立檢驗

## 解決方案

### 正確做法

```python
# stdin 解析必用 snake_case
input_data = json.loads(sys.stdin.read())
hook_event_name = input_data.get("hook_event_name", "")  # snake_case
tool_name = input_data.get("tool_name", "")              # snake_case
tool_input = input_data.get("tool_input", {})            # snake_case

# stdout 輸出必用 camelCase（IMP-055）
output = {
    "hookSpecificOutput": {            # camelCase
        "hookEventName": "PostToolUse",  # camelCase
        "additionalContext": message,
    }
}
print(json.dumps(output, ensure_ascii=False))
```

### 錯誤做法（避免）

```python
# 錯誤：stdin 用 camelCase（會永遠拿不到值，hook 失效）
hook_event_name = input_data.get("hookEventName")  # 永遠 None
tool_name = input_data.get("toolName")              # 永遠 None
tool_input = input_data.get("toolInput", {})        # 永遠 {}
```

## 案例

### Case 1：commit `2d64dc5f`（外部 .claude v1.1.53 chore sync）

外部 .claude 版本 sync 引入兩個 hook，撰寫時混淆 stdin/stdout schema：

| Hook | 失效行 | 觸發次數 / 命中次數 |
|------|-------|-------------------|
| `dispatch-count-guard-hook.py` line 331 | `input_data.get("hookEventName", "")` | 160 / 0（log 全為「未知的 Hook 事件: 」） |
| `file-ownership-guard-hook.py` lines 256, 293-294 | `input_data.get("hookEventName")` / `toolName` / `toolInput` | 68 / 0（log 全為「非目標觸發」） |

兩個 hook 從引入到診斷期間長期失效，但因為靜默 no-op，PM 與代理人從未察覺。直到 W10-035.3 ginger Hook 密度審計暴露「觸發很多但命中為 0」的異常分布，才引發 W10-048 ANA 完整診斷。

### Case 2：W10-048 ANA → W17-141 IMP 修復實證

| Ticket | 角色 | 重點 |
|-------|------|------|
| `0.18.0-W10-048` | ANA 完整診斷 | 確認根因為 stdin schema 命名混淆；對照 IMP-055（output camelCase）區分兩端規範；產出 4 行修復方案 |
| `0.18.0-W17-141` | IMP 修復 | commit `8f84a58b`：line 331 / 256 / 293-294 改 snake_case；新增 6 個 dispatch-count 單元測試含 camelCase regression guard；既有 file-ownership 測試 fixture 從 camelCase 改 snake_case（既有測試之前在驗證 bug 行為，本身就是 Why 4 的具體案例） |
| `0.18.0-W17-142` | DOC（本檔） | 將事件提煉為跨專案可重用的 error-pattern |

### Case 3：與 IMP-055 的對照

IMP-055 處理的是 **stdout 端**：PostToolUse hook 用純文字 `print(message)` 輸出，缺 `hookSpecificOutput` 包裹導致 JSON validation failed。

IMP-070 處理的是 **stdin 端**：hook 用 camelCase `input_data.get("hookEventName")` 讀取，永遠拿不到值導致靜默失效。

| 維度 | IMP-055（stdout） | IMP-070（stdin） |
|------|-----------------|----------------|
| 方向 | hook → CLI | CLI → hook |
| 命名規範 | camelCase | snake_case |
| 失效模式 | CLI 顯示 JSON validation failed（顯式錯誤） | hook 靜默 fall-through（隱式失效） |
| 偵測難度 | 低（CLI 主動報錯） | 高（需主動審計 log） |

兩者合在一起即為「Hook 通訊雙端 schema 完整對照」，撰寫新 hook 必須同時遵守。

## 防護措施

### 1. 新建 / 修改 Hook 的 PR Review Checklist

審查含 `input_data.get(...)` 的 hook 程式碼變更時逐項對照：

- [ ] 所有 `input_data.get("X")` 的 X 為 snake_case（對照 `.claude/hook-specs/claude-code-hooks-official-standards.md` line 39-97）
- [ ] 所有 stdout JSON 輸出的鍵為 camelCase（對照 IMP-055 + 同檔 line 128-170）
- [ ] 沒有將 stdin 與 stdout 命名慣例假設為一致（如「都是 camelCase」「都是 snake_case」）
- [ ] docstring 引用欄位名時與實作一致（避免 line 281-282 docstring 寫 `hookEventName` 但實際應為 `hook_event_name` 的文件漂移）

### 2. Hook 單元測試 Regression Guard

測試 fixture 必須包含至少一個 **camelCase 反向案例**驗證 hook 在錯誤輸入下不命中：

```python
def test_camel_case_stdin_does_not_match_handler():
    """Regression guard: 確保 hook 對 camelCase stdin 不會誤命中（防 IMP-070 復發）"""
    stdin = {"hookEventName": "PostToolUse", "toolName": "Write"}  # camelCase 反向案例
    result = run_hook(stdin)
    assert result.matched_handler is None  # 應 fall-through，因官方 stdin 為 snake_case
```

否則測試 fixture 與 production code 共用同一命名假設時（Why 4），bug 會被測試「驗證為正確」。

### 3. Hook 密度審計納入「命中率」指標

ginger 等 Hook 密度審計工具應計算每個 hook 的「觸發次數 vs 命中目標次數」比例。**長期 100% 觸發但 0% 命中** 是強烈失效訊號，應觸發類 IMP-070 診斷。

### 4. 與 IMP-051 / IMP-054 / IMP-055 聯動：新建 Hook 四件套

| 檢查項 | 來源 |
|-------|------|
| 註冊到 settings.json | IMP-051 |
| 設定執行權限（+x） | IMP-054 / IMP-026 / PC-086 |
| stdout 為 JSON 格式（hookSpecificOutput camelCase） | IMP-055 |
| **stdin 解析用 snake_case 欄位** | **IMP-070（本檔）** |

## 抽象層級分析

| 欄位 | 內容 |
|------|------|
| 症狀層級 | 工具層（hook log 顯示「未知事件」「非目標觸發」，hook runtime 行為） |
| 根因層級 | 實作層（stdin 解析具體程式碼用錯命名慣例） + 協作層（Claude Code 設計上 input/output schema 不對稱） |
| 跨層路徑 | 工具層 → 實作層（向下 1 層）+ 協作層（橫向） |
| 防護層級 | 實作層（PR review checklist + 單元測試 regression guard）+ 工具層（密度審計命中率指標）；落地至 `.claude/hook-specs/claude-code-hooks-official-standards.md` 與本檔 |
| 跨層警示 | 禁止提升至認知層（不可推論為「撰寫者粗心」「working memory 不足」，無支撐文件；根因為 schema 設計不對稱 + 測試 fixture 與 production 共構，屬實作層 / 協作層問題） |

## 行為模式

Hook 撰寫者習慣假設「同一個系統的 input/output 通訊應該命名一致」。Claude Code 設計上 input snake_case / output camelCase 是反直覺的不對稱（推測來自 Python convention 與 JS/JSON convention 的混合來源），缺乏一致性提示。當撰寫者先寫 stdout（camelCase），再寫 stdin parser 時，極易把 camelCase 假設帶入 stdin 解析。

此外，Hook 失效模式為 **靜默 no-op**：`dict.get()` 對缺欄位不報錯、hook exit 0、CLI 端不顯示警告。失效不像 IMP-055（CLI 主動報 JSON validation failed）會立即被注意到，必須靠主動審計 log 才能暴露。這讓 IMP-070 比 IMP-055 風險更高（兩個 hook 從引入到偵測長期失效）。

## 相關資源

- `.claude/hook-specs/claude-code-hooks-official-standards.md`（input vs output schema 規範權威來源）
- `.claude/error-patterns/implementation/IMP-055-hook-stdout-plain-text-breaks-json-validation.md`（stdout 端 camelCase 規範）
- `.claude/error-patterns/implementation/IMP-051-new-hook-not-registered.md`（新建 Hook 三件套）
- W10-048 ANA：完整診斷與修復決策
- W17-141 IMP：實際修復 commit `8f84a58b`
- W17-142 DOC（本檔）：error-pattern 提煉
- commit `2d64dc5f`：bug 引入點（外部 .claude v1.1.53 chore sync）

## 標籤

`#hook` `#stdin` `#schema` `#naming-convention` `#silent-failure` `#imp-055-related`
