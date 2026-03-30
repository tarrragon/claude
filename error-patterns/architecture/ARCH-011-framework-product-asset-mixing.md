# ARCH-011: 框架資產與專案產物混放

## 症狀

模板檔案（TEMPLATE.md）放在專案產物目錄（docs/proposals/、docs/spec/、docs/usecases/）中，與實際的提案、規格、用例文件混在一起。後續嘗試用「指向」方式（在產物中加註解指向 Skill）修正，仍然違反職責分離原則。

## 根因

未區分兩種不同性質的檔案：

| 類型 | 性質 | 正確位置 |
|------|------|---------|
| 框架資產 | 規範、模板、CLI、規則 | `.claude/skills/{skill}/` |
| 專案產物 | 實際建立的文件（提案、規格、用例） | `docs/` |

**行為模式**：建立新文件系統時，習慣將模板放在產物目錄旁邊（「方便複製」），忽略了框架/產物的職責邊界。

## 解決方案

1. 模板放在 Skill 的 `templates/` 子目錄
2. 規範放在 Skill 的 `references/` 子目錄
3. `docs/` 只放實際產物，README 中引用 Skill 路徑
4. 不使用「指向」（symlink 或註解引用）— 直接分離

```
.claude/skills/doc/
├── SKILL.md              # 入口
├── templates/             # 模板（框架資產）
│   ├── proposal-template.md
│   ├── spec-template.md
│   └── usecase-template.md
├── references/            # 規範（框架資產）
│   ├── proposals.md
│   ├── spec.md
│   ├── usecases.md
│   └── tracking.md
└── (未來) CLI             # 查詢工具

docs/
├── proposals/             # 產物（只有實際提案）
├── spec/                  # 產物（只有實際規格）
├── usecases/              # 產物（只有實際用例）
└── proposals-tracking.yaml
```

## 預防措施

**判斷規則**：建立新檔案時問自己：

| 問題 | 答案 | 位置 |
|------|------|------|
| 這個檔案會被複製來用嗎？ | 是 | Skill templates/ |
| 這個檔案定義規範/流程嗎？ | 是 | Skill references/ |
| 這個檔案是實際的工作產出嗎？ | 是 | docs/ 或專案目錄 |

**通用原則**：框架管「怎麼做」，專案放「做出來的東西」。

## 關聯

- 觸發場景：建立新的文件管理系統、新的 Skill
- 來源：0.16.2-W1-002 提案系統設計 session
- 類似模式：ARCH-001（config/code 混放）、ARCH-006（env config 作用域錯誤）
