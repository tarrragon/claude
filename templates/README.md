# Templates 範本目錄

本目錄存放專案開發過程中使用的文件範本。

---

## 範本清單

| 範本 | 用途 | 使用情境 |
|------|------|---------|
| [CLAUDE-template.md](./CLAUDE-template.md) | 專案入口文件範本 | 新專案初始化時複製為 `CLAUDE.md` |
| [agent-template.md](./agent-template.md) | 代理人定義範本 | 新增代理人到 `.claude/agents/` |
| [work-log-template.md](./work-log-template.md) | 版本工作日誌範本 | 開始新版本時建立 `docs/work-logs/vX.X.X/` |
| [ticket-log-template.md](./ticket-log-template.md) | Ticket 執行日誌結構參考 | PM / ticket-lifecycle 方法論引用（非 `/ticket create` 自動套用） |
| [learning-record-template.md](./learning-record-template.md) | 學習記錄範本 | continuous-learning skill 使用 |
| [phase-3a-simplified-template.md](./phase-3a-simplified-template.md) | Phase 3a 策略規劃範本 | pepper-test-implementer 使用 |

---

## 使用方式

### 新專案初始化

```bash
cp .claude/templates/CLAUDE-template.md ./CLAUDE.md
# 編輯 CLAUDE.md，填入專案特定資訊
```

### 新增代理人

```bash
# 建立代理人定義（單一檔案，含三區塊：允許產出/禁止行為/適用情境）
cp .claude/templates/agent-template.md .claude/agents/{agent-name}.md
# 編輯並填入代理人完整定義
```

### 開始新版本

```bash
mkdir -p docs/work-logs/v{版本號}
cp .claude/templates/work-log-template.md docs/work-logs/v{版本號}/README.md
# 編輯版本目標和計畫
```

### 建立 Ticket

使用 `/ticket create` 指令建立新 Ticket。Ticket body（含 frontmatter 與各 section）由 live CLI 的 `ticket_system/lib/ticket_builder.py` 以程式碼生成，不讀取本目錄的 `.template` 檔。

---

## 範本維護原則

1. **同步更新**：當 CLAUDE.md 結構變更時，需同步更新 CLAUDE-template.md
2. **保持一致**：範本格式應與實際使用的文件格式一致
3. **註解說明**：範本中應包含必要的註解說明填寫方式
4. **版本控制**：範本變更應納入版本控制並記錄

---

## 相關指令

| 指令 | 說明 |
|------|------|
| `/ticket create` | 建立新 Ticket（body 由 `ticket_builder.py` 程式碼生成） |
| `/version-release` | 版本發布時參考 work-log-template |

---

**Last Updated**: 2026-01-28
