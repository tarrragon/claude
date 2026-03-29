# Skill 創建流程

> 建立新 Skill 前必讀本文件。

---

## 前置條件

1. 閱讀 `/skill-design-guide`（Skill 設計規範）
2. 確認無既有 Skill 覆蓋相同場景

## 創建步驟

1. **設計 description**（最重要）
   - 長度 < 100 字（推薦），< 250 字（硬上限）
   - 關鍵觸發詞放最前面
   - 第三人稱描述

2. **建立目錄結構**
   - `.claude/skills/{skill-name}/SKILL.md`
   - 必要時加 `references/` 子目錄

3. **撰寫 SKILL.md**
   - YAML frontmatter: name + description
   - 主體 < 500 行
   - 詳細內容放 references/

4. **驗證觸發**
   - 在新 session 中測試 description 是否能被自動觸發
   - 用不同措辭測試至少 3 種表達

## 品質檢查清單

- [ ] description < 100 字？
- [ ] 關鍵觸發詞在 description 最前面？
- [ ] SKILL.md < 500 行？
- [ ] 無與既有 Skill 重複的功能？
- [ ] 已在 Skill 列表中確認可見？

## 相關文件

- /skill-design-guide — 完整設計規範
- .claude/skills/skill-design-guide/SKILL.md — 技術規格

---

**Last Updated**: 2026-03-29
**Version**: 1.0.0
