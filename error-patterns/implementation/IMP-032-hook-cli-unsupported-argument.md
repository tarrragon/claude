# IMP-032: Hook 傳遞 CLI 不支援的參數

## 基本資訊

- **Pattern ID**: IMP-032
- **分類**: 實作
- **來源版本**: v0.1.1
- **發現日期**: 2026-03-14
- **風險等級**: 中

## 問題描述

### 症狀

Session 啟動時顯示「[Project Init] 環境檢查失敗，請查看詳細日誌」，但無任何具體錯誤資訊。日誌檔只記錄執行時間，無法判斷失敗原因。

### 根本原因 (5 Why 分析)

1. Why 1: Hook 呼叫 `project-init check --project-root <path>` 失敗（exit code 2）
2. Why 2: `project-init check` 不支援 `--project-root` 參數，argparse 直接拒絕
3. Why 3: Hook 開發時假設 CLI 支援該參數，但未實際驗證 CLI 的 `--help` 輸出
4. Why 4: Hook 和 CLI 由不同時間點/不同代理人開發，介面契約未明確記錄
5. Why 5: **根本原因**：Hook 呼叫 CLI 時未驗證參數相容性，且 CLI 的 stderr 輸出未被 Hook 捕獲和記錄

## 解決方案

### 正確做法

```python
# 不傳遞 CLI 不支援的參數，使用 cwd 指定工作目錄
result = subprocess.run(
    ["project-init", "check"],
    capture_output=True,
    text=True,
    timeout=30,
    cwd=str(project_root)
)
```

**開發 Hook 呼叫 CLI 時的檢查清單**：
1. 執行 `<cli> <subcommand> --help` 確認支援的參數
2. 在 Hook 中記錄 stderr 輸出（不只是 stdout），便於偵錯
3. CLI 介面變更時同步更新所有呼叫端

### 錯誤做法 (避免)

```python
# 假設 CLI 支援某參數，未經驗證
result = subprocess.run(
    ["project-init", "check", "--project-root", str(project_root)],
    ...
)
```

## 防護建議

- Hook 開發時強制要求：先執行 CLI `--help` 確認參數
- CLI 的 stderr 應在 Hook 日誌中記錄，避免錯誤訊息被丟棄
- 考慮在 Hook 中加入 CLI 參數相容性檢查（捕獲 exit code 2 並輸出明確提示）

## 相關資源

- `.claude/hooks/project-init-env-check-hook.py` - 修正的 Hook
- `.claude/skills/project-init/` - project-init CLI

## 標籤

`#hook` `#cli` `#參數不相容` `#靜默失敗`
