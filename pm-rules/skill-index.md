# Skill 指令索引

> 完整 Skill 定義位於 `.claude/skills/` 目錄。

---

## 常用指令

| 指令 | 用途 |
|------|------|
| `/manager` | 主線程管理哲學（並行優先、非同步心態） |
| `/5w1h-decision` | 5W1H 決策格式 |
| `/pre-fix-eval` | 修復前評估（強制於錯誤發生時） |
| `/ticket` | 統一 Ticket 系統（create/track/handoff/resume/migrate/generate） |
| `/version-release` | 版本發布（check/update-docs/release） |
| `/tech-debt-capture` | 技術債務捕獲 |
| `/commit-as-prompt` | 提交流程 |

## 開發輔助

| 指令 | 用途 |
|------|------|
| `/lsp-first` | LSP 優先開發策略 |
| `/cognitive-load` | 認知負擔評估 |
| `/decision-helper` | 決策樹助手 |
| `/tdd-phase1-split` | Phase 1 SOLID 拆分 |
| `/parallel-evaluation` | 並行評估決策（多視角掃描） |
| `/bulk-evaluate` | 子任務拆分與 Context 卸載 |
| `/design-decision-framework` | 多方案評估決策框架 |

## 品質與審查

| 指令 | 用途 |
|------|------|
| `/error-pattern` | 錯誤模式知識庫（query/add） |
| `/scope-confirmation` | 功能範圍確認 |
| `/dispatch-strategy-review` | 派發策略檢討 |
| `/security-review` | 安全審查 |
| `/style-guardian` | Design System 規範執行 |
| `/i18n-checker` | 硬編碼中文字串掃描 |
| `/test-async-guardian` | 測試異步資源管理 |

## 文件與流程

| 指令 | 用途 |
|------|------|
| `/doc-flow` | 五重文件系統管理 |
| `/methodology-writing` | 方法論撰寫指南 |
| `/strategic-compact` | 策略性 Context 壓縮 |
| `/agent-team` | Agent Teams 協作派發 |
| `/continuous-learning` | 持續學習模式提取 |

## 架構與工具

| 指令 | 用途 |
|------|------|
| `/provider-architecture` | Riverpod Provider 架構規範 |
| `/search-tools-guide` | 搜尋工具使用指南 |
| `/branch-worktree-guardian` | Git 分支和 Worktree 管理 |
| `/mermaid-ascii` | Mermaid 圖表 ASCII 渲染 |
| `/skill-design-guide` | Skill 建立指南 |

## 自動化指令

| 指令 | 用途 |
|------|------|
| `/test-progress` | 測試進度追蹤 |
| `/smart-version-check` | 版本檢查 |
| `/delegate` | 委派指令 |
| `/sync-push` | 推送 .claude 配置到獨立 repo |
| `/sync-pull` | 從獨立 repo 拉取配置 |

---

## 完整 Skill 目錄

所有 Skill 定義位於 `.claude/skills/` 下的獨立子目錄，每個包含 `SKILL.md` 入口文件。

---

**Last Updated**: 2026-03-03
**Version**: 1.0.0
