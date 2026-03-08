# 實作品質標準（Hub）

本文件為實作品質規則的入口索引。請根據語言選擇對應規則檔：

> **設計原則**：quality-common.md 為所有語言的品質基線，語言專屬規則是在通用規則之上額外補充。實作代理人應同時遵循通用規則和對應語言規則。

| 語言 | 規則檔 | 適用代理人 |
|------|-------|-----------|
| 所有語言通用 | quality-common.md | 所有實作代理人 |
| Dart/Flutter | quality-dart.md | parsley-flutter-developer |
| Go | quality-go.md | fennel-go-developer |
| Python | quality-python.md | thyme-python-developer, basil-hook-architect |
| 流程品質基線 | quality-baseline.md | 所有代理人（測試率/Phase 4/Hook 失敗等流程規則） |

> 重構代理人（cinnamon-refactor-owl）以 quality-common.md 為評估基線。

---

**Last Updated**: 2026-03-08
**Version**: 2.1.0 - 新增設計意圖說明、補充 quality-baseline.md 條目（parallel-evaluation 審核補充）
