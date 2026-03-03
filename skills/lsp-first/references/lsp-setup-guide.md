# LSP 伺服器與插件設定指南

---

## 支援的語言和 LSP 伺服器

### 自建插件（已配置）

| 語言 | LSP 伺服器 | 插件位置 |
|------|-----------|---------|
| Dart/Flutter | dart language-server | `.claude/plugins/dart-lsp/` |
| Markdown | marksman | `.claude/plugins/marksman-lsp/` |
| YAML | yaml-language-server | `.claude/plugins/yaml-lsp/` |

### 官方插件市場

```bash
# 新增插件市場
/plugin marketplace add boostvolt/claude-code-lsps
```

| 語言 | LSP 伺服器 | 安裝指令 |
|------|-----------|---------|
| Dart/Flutter | dart-analyzer | `/plugin install dart-analyzer@claude-code-lsps` |
| TypeScript/JavaScript | vtsls | `/plugin install vtsls@claude-code-lsps` |
| Python | pyright | `/plugin install pyright@claude-code-lsps` |
| Go | gopls | `/plugin install gopls@claude-code-lsps` |
| Rust | rust-analyzer | `/plugin install rust-analyzer@claude-code-lsps` |
| Java | jdtls | `/plugin install jdtls@claude-code-lsps` |
| C/C++ | clangd | `/plugin install clangd@claude-code-lsps` |
| C# | omnisharp | `/plugin install omnisharp@claude-code-lsps` |
| PHP | intelephense | `/plugin install intelephense@claude-code-lsps` |
| Kotlin | kotlin | `/plugin install kotlin@claude-code-lsps` |
| Ruby | solargraph | `/plugin install solargraph@claude-code-lsps` |
| HTML/CSS | vscode-langservers | `/plugin install html-css@claude-code-lsps` |

---

## 自建 LSP 插件指南

### 目錄結構

```
.claude/plugins/<plugin-name>/
├── .claude-plugin/
│   └── plugin.json          # 插件清單
└── .lsp.json                 # LSP 配置
```

### plugin.json 範本

```json
{
  "name": "<plugin-name>",
  "version": "1.0.0",
  "description": "LSP plugin for <language>",
  "author": "Your Name"
}
```

### .lsp.json 範本

```json
{
  "<language-id>": {
    "command": "<lsp-server-command>",
    "args": ["--stdio"],
    "extensionToLanguage": {
      ".<ext>": "<language-id>"
    }
  }
}
```

### 範例：Markdown LSP 插件

**plugin.json**：
```json
{
  "name": "marksman-lsp",
  "version": "1.0.0",
  "description": "Marksman Markdown LSP for Claude Code",
  "author": "Project Team"
}
```

**.lsp.json**：
```json
{
  "markdown": {
    "command": "marksman",
    "args": ["server"],
    "extensionToLanguage": {
      ".md": "markdown",
      ".markdown": "markdown"
    }
  }
}
```

**完整配置範本**：`templates/lsp-plugin-config.json.template`

---

## 跨平台安裝

| 平台 | 安裝工具 |
|------|---------|
| macOS | Homebrew, npm |
| Linux | apt/dnf/pacman, Homebrew, npm |
| Windows | winget, scoop, npm |

---

## 常見問題和故障排除

### Q1: "No LSP server available for file type"

**可能原因**：
1. 該語言的 LSP 插件未配置
2. LSP 伺服器未安裝
3. 環境變數未設定

**解決方案**：
```bash
# 1. 確認 LSP 伺服器已安裝
which marksman
which yaml-language-server

# 2. 啟用 LSP 功能（如需要）
export ENABLE_LSP_TOOL=1

# 3. 執行 LSP 環境檢查
./.claude/hooks/lsp-environment-check.py
```

### Q2: LSP 操作返回空結果

**可能原因**：
1. 座標位置不正確（LSP 使用 0-based）
2. 檔案尚未被 LSP 索引
3. LSP 伺服器尚未啟動

**解決方案**：
1. 確認 line 和 column 使用 0-based（第一行是 0）
2. 等待幾秒讓 LSP 完成索引
3. 重新啟動 Claude Code

### Q3: 自建插件無法運作

**檢查清單**：
- [ ] LSP 伺服器已安裝且在 PATH 中
- [ ] `.lsp.json` 格式正確
- [ ] `extensionToLanguage` 對應正確
- [ ] 插件目錄結構正確
