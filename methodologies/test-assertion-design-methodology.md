# 測試斷言設計方法論（路由 Stub）

> **內容已收斂至 skill 層**：本檔為路由 stub，實質內容分層存放於以下兩處：

| 層級 | 位置 | 內容 |
|------|------|------|
| 跨專案通用概念框架 | `.claude/skills/test-assertion-design/SKILL.md` | 9 類型斷言問題、斷言品質三問（確定性／聚焦性／隔離性）、判斷決策表 |
| 本專案（Chrome Extension / JS / Jest）專屬規則 | `.claude/rules/core/test-assertion-design-rules.md` | 具體精度數字、`tests/perf/` 目錄規定、W1-017 / W1-018 實證案例 |

**背景**：本方法論原與 rules 檔重疊約 70%。W1-024 ANA 將通用概念收斂為 `.claude/skills/test-assertion-design/` skill（W1-025 建立），本檔於 W1-026 改為路由 stub，避免內容重複與跨專案 sync 污染。

**閱讀路徑**：

- 判斷斷言設計是否合理（跨語言）→ 讀 skill SKILL.md
- 本專案測試的具體落地規則 → 讀 rules 檔
- 首次實踐範本（W1-017）與全專案盤點（W1-018）→ 見 rules 檔「相關文件」

---

**Last Updated**: 2026-05-21
**Version**: 2.0.0 — 改為路由 stub（W1-026），指向 skill 概念框架與 rules 專案規則。1.0.0：初始建立（W1-018 WRAP 分析產出）
