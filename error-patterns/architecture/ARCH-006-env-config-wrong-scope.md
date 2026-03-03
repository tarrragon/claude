# ARCH-006: 環境變數配置放錯作用域

## 基本資訊

- **Pattern ID**: ARCH-006
- **分類**: 架構設計
- **來源版本**: v0.31.0
- **發現日期**: 2026-03-02
- **風險等級**: 低

## 問題描述

### 症狀

將 Claude Code 專屬環境變數（如 `CLAUDE_CODE_MAX_OUTPUT_TOKENS`）寫入全域 shell profile（`~/.zshrc`），導致不必要的環境污染。

### 根本原因 (5 Why 分析)

1. Why 1: 環境變數被寫入 `~/.zshrc` 而非 `~/.claude/settings.json`
2. Why 2: 習慣性地使用 shell profile 設定所有環境變數
3. Why 3: 未優先考慮工具專屬的配置機制
4. Why 4: 不清楚 `~/.claude/settings.json` 的 `env` 區塊可以設定環境變數
5. Why 5: **缺乏「配置就近原則」的意識 — 配置應放在最小影響範圍的位置**

## 解決方案

### 正確做法

Claude Code 專屬環境變數放在 `~/.claude/settings.json` 的 `env` 區塊：

```json
{
  "env": {
    "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "64000",
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

### 配置位置選擇原則

| 配置性質 | 放置位置 | 範例 |
|---------|---------|------|
| Claude Code 專屬 | `~/.claude/settings.json` env | CLAUDE_CODE_MAX_OUTPUT_TOKENS |
| 專案專屬 | `.claude/settings.json` env | 專案級別覆寫 |
| 全域開發工具 | `~/.zshrc` | PATH, EDITOR |
| 臨時測試 | 命令前綴 | `VAR=value claude` |

### 錯誤做法 (避免)

```bash
# 錯誤：污染全域 shell 環境
echo 'export CLAUDE_CODE_MAX_OUTPUT_TOKENS=64000' >> ~/.zshrc
```

## 檢測方法

```bash
# 檢查 .zshrc 中是否有 CLAUDE_CODE 開頭的變數
grep 'CLAUDE_CODE' ~/.zshrc ~/.bashrc 2>/dev/null
```

## 額外資訊

- **已知 Bug**：Opus 4.6 的 CLAUDE_CODE_MAX_OUTPUT_TOKENS 可能無效，實際上限約 32768（GitHub #29488, #24159）
- **可設定最大值**：64000 tokens
- **預設值**：16384 tokens

## 標籤

`#架構` `#配置管理` `#環境變數` `#Claude-Code`
