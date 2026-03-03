# 查詢 vs 研究決策指南

> **核心原則**：外部資源研究必須派發代理人，主線程禁止直接執行 WebFetch/WebSearch。

---

## 快速判斷

```
接收查詢類問題 → 內部資料? → 是 → Read/Grep/ticket track
                            → 否 → 派發 oregano-data-miner
```

| 維度 | 內部查詢 | 外部資源研究 |
|------|---------|------------|
| 資料來源 | 專案文檔、Ticket、工作日誌 | GitHub、官方文檔、外部網站 |
| 工作量 | < 5 分鐘 | >= 5 分鐘 |
| 工具 | Read、Grep、/ticket track | WebFetch、WebSearch |

---

## 禁止行為

| 禁止 | 正確做法 |
|------|---------|
| 主線程直接 WebFetch/WebSearch | 派發 oregano-data-miner |
| 超過 5 分鐘的研究 | 派發對應代理人 |

---

## 諮詢類派發

| 問題類型 | 代理人 |
|---------|-------|
| 系統架構 | system-analyst |
| UI/UX | system-designer |
| 環境配置 | system-engineer |
| 安全 | security-reviewer |
| 效能 | ginger-performance-tuner |

> 詳細情境範例：.claude/references/query-research-scenario-examples.md

---

**Last Updated**: 2026-03-02
**Version**: 3.0.0 - Progressive Disclosure 精簡
